"""提示词管理API - 可视化管理后端"""

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.schemas.prompt import (
    PromptTemplateCreate, PromptTemplateUpdate, PromptTemplateResponse,
    PromptVersionResponse, PromptTestRequest, PromptTestResponse,
)
from app.schemas.common import PageResponse

router = APIRouter()

_templates: dict[str, dict] = {}
_versions: dict[str, list[dict]] = {}


@router.get("", response_model=PageResponse[PromptTemplateResponse])
async def list_prompts(
    category: str = Query(default="", description="分类过滤"),
    task_type: str = Query(default="", description="任务类型过滤"),
    status: str = Query(default="", description="状态过滤"),
    target_agent: str = Query(default="", description="目标Agent过滤"),
    search: str = Query(default="", description="关键词搜索"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """获取提示词模板列表"""
    items = list(_templates.values())
    if category:
        items = [i for i in items if i.get("category") == category]
    if task_type:
        items = [i for i in items if i.get("task_type") == task_type]
    if status:
        items = [i for i in items if i.get("status") == status]
    if target_agent:
        items = [i for i in items if i.get("target_agent") == target_agent]
    if search:
        items = [i for i in items if search.lower() in (i.get("name", "") + i.get("display_name", "")).lower()]

    total = len(items)
    start = (page - 1) * page_size
    return PageResponse(
        items=items[start:start + page_size], total=total,
        page=page, page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=PromptTemplateResponse)
async def create_prompt(req: PromptTemplateCreate):
    """创建提示词模板"""
    tpl_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    template = {
        "id": tpl_id,
        "tenant_id": "default",
        **req.model_dump(),
        "variables": [v.model_dump() for v in req.variables],
        "current_version": 1,
        "status": "draft",
        "is_default": False,
        "avg_quality_score": None,
        "usage_count": 0,
        "created_by": None,
        "published_by": None,
        "created_at": now,
        "updated_at": now,
        "published_at": None,
    }

    _templates[tpl_id] = template

    # 保存版本1
    version = {
        "id": str(uuid.uuid4()),
        "template_id": tpl_id,
        "tenant_id": "default",
        "version": 1,
        "system_prompt": req.system_prompt,
        "user_prompt_template": req.user_prompt_template,
        "variables": [v.model_dump() for v in req.variables],
        "output_format": req.output_format,
        "output_schema": req.output_schema,
        "validation_rules": req.validation_rules,
        "changelog": "初始版本",
        "evaluation_results": {},
        "quality_score": None,
        "created_by": None,
        "created_at": now,
    }
    _versions[tpl_id] = [version]

    return template


@router.get("/{template_id}", response_model=PromptTemplateResponse)
async def get_prompt(template_id: str):
    """获取提示词详情"""
    tpl = _templates.get(template_id)
    if not tpl:
        raise HTTPException(404, "提示词模板不存在")
    return tpl


@router.put("/{template_id}", response_model=PromptTemplateResponse)
async def update_prompt(template_id: str, req: PromptTemplateUpdate):
    """更新提示词模板(自动创建新版本)"""
    tpl = _templates.get(template_id)
    if not tpl:
        raise HTTPException(404, "提示词模板不存在")

    update_data = req.model_dump(exclude_unset=True)
    changelog = update_data.pop("changelog", "")

    if "variables" in update_data and update_data["variables"]:
        update_data["variables"] = [v.model_dump() if hasattr(v, 'model_dump') else v for v in update_data["variables"]]

    tpl.update(update_data)
    tpl["current_version"] += 1
    tpl["updated_at"] = datetime.now(timezone.utc)

    # 保存新版本
    version = {
        "id": str(uuid.uuid4()),
        "template_id": template_id,
        "tenant_id": "default",
        "version": tpl["current_version"],
        "system_prompt": tpl.get("system_prompt"),
        "user_prompt_template": tpl["user_prompt_template"],
        "variables": tpl.get("variables", []),
        "output_format": tpl.get("output_format"),
        "output_schema": tpl.get("output_schema"),
        "validation_rules": tpl.get("validation_rules", []),
        "changelog": changelog,
        "evaluation_results": {},
        "quality_score": None,
        "created_by": None,
        "created_at": datetime.now(timezone.utc),
    }
    _versions.setdefault(template_id, []).append(version)

    return tpl


@router.post("/{template_id}/publish")
async def publish_prompt(template_id: str):
    """发布提示词"""
    tpl = _templates.get(template_id)
    if not tpl:
        raise HTTPException(404, "提示词模板不存在")
    tpl["status"] = "published"
    tpl["published_at"] = datetime.now(timezone.utc)
    return {"message": "提示词已发布", "version": tpl["current_version"]}


@router.post("/{template_id}/deprecate")
async def deprecate_prompt(template_id: str):
    """废弃提示词"""
    tpl = _templates.get(template_id)
    if not tpl:
        raise HTTPException(404, "提示词模板不存在")
    tpl["status"] = "deprecated"
    return {"message": "提示词已废弃"}


@router.get("/{template_id}/versions", response_model=list[PromptVersionResponse])
async def list_prompt_versions(template_id: str):
    """获取提示词版本历史"""
    versions = _versions.get(template_id, [])
    return sorted(versions, key=lambda v: v["version"], reverse=True)


@router.get("/{template_id}/versions/{version}", response_model=PromptVersionResponse)
async def get_prompt_version(template_id: str, version: int):
    """获取指定版本详情"""
    versions = _versions.get(template_id, [])
    for v in versions:
        if v["version"] == version:
            return v
    raise HTTPException(404, f"版本 {version} 不存在")


@router.post("/{template_id}/versions/{version}/rollback")
async def rollback_prompt(template_id: str, version: int):
    """回滚到指定版本"""
    tpl = _templates.get(template_id)
    if not tpl:
        raise HTTPException(404, "提示词模板不存在")

    versions = _versions.get(template_id, [])
    target = None
    for v in versions:
        if v["version"] == version:
            target = v
            break
    if not target:
        raise HTTPException(404, f"版本 {version} 不存在")

    tpl["system_prompt"] = target["system_prompt"]
    tpl["user_prompt_template"] = target["user_prompt_template"]
    tpl["variables"] = target["variables"]
    tpl["output_format"] = target.get("output_format")
    tpl["current_version"] += 1
    tpl["updated_at"] = datetime.now(timezone.utc)

    return {"message": f"已回滚到版本 {version}", "new_version": tpl["current_version"]}


@router.post("/test", response_model=PromptTestResponse)
async def test_prompt(req: PromptTestRequest):
    """测试提示词效果"""
    import time
    from app.services.llm_service import llm_service

    # 渲染提示词
    rendered = req.user_prompt_template
    for var_name, var_value in req.variables.items():
        rendered = rendered.replace(f"{{{{{var_name}}}}}", str(var_value))

    messages = []
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})
    messages.append({"role": "user", "content": rendered})

    start_time = time.perf_counter()
    result = await llm_service.generate(
        messages=messages,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    latency_ms = (time.perf_counter() - start_time) * 1000

    return PromptTestResponse(
        rendered_prompt=rendered,
        output=result["content"],
        model=result.get("model", ""),
        usage=result.get("usage", {}),
        latency_ms=round(latency_ms, 2),
    )
