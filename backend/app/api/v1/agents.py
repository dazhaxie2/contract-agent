"""Agent执行API"""

import time
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.agent import AgentExecuteRequest, AgentExecuteResponse, AgentExecutionDetail
from app.agents.master_agent import master_agent
from app.rag.retriever import hybrid_retriever
from app.rag.context_builder import context_builder

router = APIRouter()

_executions: dict[str, dict] = {}


@router.post("/execute", response_model=AgentExecuteResponse)
async def execute_agent(req: AgentExecuteRequest):
    """执行Agent任务"""
    execution_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4()).replace("-", "")[:32]
    start_time = time.perf_counter()

    # Step 1: 检索相关上下文
    retrieval_results = await hybrid_retriever.retrieve(
        query=req.query,
        tenant_id="default",
        filters=req.filters,
    )

    # Step 2: 构建上下文
    ctx = context_builder.build(retrieval_results)

    # Step 3: Agent执行
    agent_context = {
        "retrieval_context": ctx["context"],
        "references": ctx["references"],
    }

    result = await master_agent.execute(req.query, context=agent_context)
    latency_ms = (time.perf_counter() - start_time) * 1000

    # 构建响应
    steps_data = [
        {
            "step_number": i + 1,
            "step_type": s.step_type.value,
            "content": s.content[:500],
            "action": s.action,
            "tool_name": s.tool_name,
            "tokens_used": s.tokens_used,
            "latency_ms": round(s.latency_ms, 2),
        }
        for i, s in enumerate(result.steps)
    ]

    execution = {
        "execution_id": execution_id,
        "trace_id": trace_id,
        "status": "completed" if result.success else "failed",
        "result": result.output,
        "references": ctx["references"],
        "steps": steps_data,
        "usage": {
            "total_tokens": result.total_tokens,
            "retrieval_chunks": ctx["chunk_count"],
        },
        "latency_ms": round(latency_ms, 2),
    }

    _executions[execution_id] = execution
    return execution


@router.post("/chat")
async def chat_stream(req: AgentExecuteRequest):
    """流式对话"""
    from app.services.llm_service import llm_service

    messages = [
        {"role": "system", "content": master_agent._build_system_prompt()},
        {"role": "user", "content": req.query},
    ]

    async def generate():
        async for chunk in llm_service.generate_stream(messages):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/executions")
async def list_executions(
    task_type: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
):
    """获取执行历史列表"""
    items = list(_executions.values())
    total = len(items)
    start = (page - 1) * page_size
    return {
        "items": items[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/executions/{execution_id}")
async def get_execution_detail(execution_id: str):
    """获取执行详情(含全链路步骤)"""
    execution = _executions.get(execution_id)
    if not execution:
        raise HTTPException(404, "执行记录不存在")
    return execution


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: str):
    """按Trace ID查询链路追踪"""
    for exc in _executions.values():
        if exc.get("trace_id") == trace_id:
            return exc
    raise HTTPException(404, "链路不存在")


@router.post("/executions/{execution_id}/feedback")
async def submit_feedback(execution_id: str, score: int, comment: str = ""):
    """提交用户反馈"""
    execution = _executions.get(execution_id)
    if not execution:
        raise HTTPException(404, "执行记录不存在")
    if not 1 <= score <= 5:
        raise HTTPException(400, "评分范围1-5")
    execution["user_feedback"] = score
    execution["user_comment"] = comment
    return {"message": "反馈已提交"}
