"""模型配置管理API - 可视化管理后端"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.schemas.model_config import (
    ModelConfigCreate, ModelConfigUpdate, ModelConfigResponse,
    ModelDeploymentCreate, ModelDeploymentResponse,
    ABTestCreate, ABTestResponse,
)
from app.schemas.common import PageResponse

router = APIRouter()

# 内存存储(示例，生产环境用DB)
_model_configs: dict[str, dict] = {}
_deployments: dict[str, dict] = {}
_ab_tests: dict[str, dict] = {}


@router.get("", response_model=PageResponse[ModelConfigResponse])
async def list_model_configs(
    model_type: str = Query(default="", description="模型类型过滤"),
    provider: str = Query(default="", description="提供商过滤"),
    is_active: bool | None = Query(default=None, description="是否激活"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """获取模型配置列表"""
    items = list(_model_configs.values())
    if model_type:
        items = [i for i in items if i.get("model_type") == model_type]
    if provider:
        items = [i for i in items if i.get("provider") == provider]
    if is_active is not None:
        items = [i for i in items if i.get("is_active") == is_active]

    total = len(items)
    start = (page - 1) * page_size
    paged = items[start:start + page_size]

    return PageResponse(
        items=paged, total=total, page=page,
        page_size=page_size, total_pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=ModelConfigResponse)
async def create_model_config(req: ModelConfigCreate):
    """创建模型配置"""
    config_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    config = {
        "id": config_id,
        "tenant_id": "default",
        **req.model_dump(),
        "api_key_encrypted": "",
        "is_active": True,
        "is_default": False,
        "version": 1,
        "avg_latency_ms": None,
        "avg_tokens_per_second": None,
        "error_rate": None,
        "quality_score": None,
        "created_at": now,
        "updated_at": now,
    }
    # 脱敏存储API Key
    if req.api_key:
        config["api_key_encrypted"] = "***encrypted***"
    config.pop("api_key", None)
    config["api_endpoint"] = req.api_endpoint or None

    _model_configs[config_id] = config
    return config


@router.get("/{config_id}", response_model=ModelConfigResponse)
async def get_model_config(config_id: str):
    """获取模型配置详情"""
    config = _model_configs.get(config_id)
    if not config:
        raise HTTPException(404, "模型配置不存在")
    return config


@router.put("/{config_id}", response_model=ModelConfigResponse)
async def update_model_config(config_id: str, req: ModelConfigUpdate):
    """更新模型配置"""
    config = _model_configs.get(config_id)
    if not config:
        raise HTTPException(404, "模型配置不存在")

    update_data = req.model_dump(exclude_unset=True)
    if "api_key" in update_data:
        update_data.pop("api_key")

    config.update(update_data)
    config["version"] = config.get("version", 1) + 1
    config["updated_at"] = datetime.now(timezone.utc)

    return config


@router.delete("/{config_id}")
async def delete_model_config(config_id: str):
    """删除模型配置"""
    if config_id not in _model_configs:
        raise HTTPException(404, "模型配置不存在")
    del _model_configs[config_id]
    return {"message": "删除成功"}


@router.post("/{config_id}/toggle")
async def toggle_model_config(config_id: str):
    """启用/禁用模型配置"""
    config = _model_configs.get(config_id)
    if not config:
        raise HTTPException(404, "模型配置不存在")
    config["is_active"] = not config["is_active"]
    return {"is_active": config["is_active"]}


@router.post("/{config_id}/set-default")
async def set_default_model(config_id: str):
    """设为默认模型"""
    config = _model_configs.get(config_id)
    if not config:
        raise HTTPException(404, "模型配置不存在")

    # 取消其他同类型默认
    for c in _model_configs.values():
        if c.get("model_type") == config["model_type"]:
            c["is_default"] = False

    config["is_default"] = True
    return {"message": "已设为默认"}


# === 模型部署 ===

@router.post("/deployments", response_model=ModelDeploymentResponse)
async def create_deployment(req: ModelDeploymentCreate):
    """创建模型部署"""
    dep_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    deployment = {
        "id": dep_id,
        "tenant_id": "default",
        **req.model_dump(),
        "status": "pending",
        "health_status": "unknown",
        "current_qps": 0.0,
        "max_qps": 0.0,
        "avg_latency_ms": 0.0,
        "p99_latency_ms": 0.0,
        "created_at": now,
        "updated_at": now,
    }
    _deployments[dep_id] = deployment
    return deployment


@router.get("/deployments", response_model=list[ModelDeploymentResponse])
async def list_deployments(model_config_id: str = ""):
    """获取部署列表"""
    items = list(_deployments.values())
    if model_config_id:
        items = [d for d in items if str(d.get("model_config_id")) == model_config_id]
    return items


# === A/B测试 ===

@router.post("/ab-tests", response_model=ABTestResponse)
async def create_ab_test(req: ABTestCreate):
    """创建A/B测试"""
    test_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    test = {
        "id": test_id,
        "tenant_id": "default",
        **req.model_dump(),
        "metrics_config": {},
        "control_metrics": {},
        "treatment_metrics": {},
        "winner": None,
        "status": "draft",
        "started_at": None,
        "ended_at": None,
        "created_at": now,
    }
    _ab_tests[test_id] = test
    return test


@router.get("/ab-tests", response_model=list[ABTestResponse])
async def list_ab_tests():
    """获取A/B测试列表"""
    return list(_ab_tests.values())


@router.post("/ab-tests/{test_id}/start")
async def start_ab_test(test_id: str):
    """启动A/B测试"""
    test = _ab_tests.get(test_id)
    if not test:
        raise HTTPException(404, "A/B测试不存在")
    test["status"] = "running"
    test["started_at"] = datetime.now(timezone.utc)
    return {"message": "A/B测试已启动"}


@router.post("/ab-tests/{test_id}/stop")
async def stop_ab_test(test_id: str):
    """停止A/B测试"""
    test = _ab_tests.get(test_id)
    if not test:
        raise HTTPException(404, "A/B测试不存在")
    test["status"] = "completed"
    test["ended_at"] = datetime.now(timezone.utc)
    return {"message": "A/B测试已停止"}
