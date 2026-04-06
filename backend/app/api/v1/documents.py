"""文档管理API"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query

from app.rag.document_processor import document_processor
from app.rag.chunker import document_chunker

router = APIRouter()

_documents: dict[str, dict] = {}
_chunks: dict[str, list[dict]] = {}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form(default="auto"),
    title: str = Form(default=""),
):
    """上传并处理文档"""
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Step 1: 文档预处理
    processed = await document_processor.process(
        file=file.file, filename=file.filename, tenant_id="default"
    )

    # Step 2: 分块
    actual_type = doc_type if doc_type != "auto" else processed["metadata"].get("doc_type", "guide")
    chunks = document_chunker.chunk(processed["cleaned_text"], doc_type=actual_type)

    # 保存文档记录
    doc = {
        "id": doc_id,
        "tenant_id": "default",
        "title": title or processed["metadata"].get("title", file.filename),
        "doc_type": actual_type,
        "file_name": file.filename,
        "file_size": processed["file_size"],
        "file_hash": processed["file_hash"],
        "mime_type": file.content_type or "application/octet-stream",
        "metadata": processed["metadata"],
        "status": "processed",
        "chunk_count": len(chunks),
        "created_at": now,
    }
    _documents[doc_id] = doc

    # 保存块
    chunk_records = []
    for i, chunk in enumerate(chunks):
        chunk_records.append({
            "id": chunk.id,
            "doc_id": doc_id,
            "content": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
            "chunk_type": chunk.chunk_type,
            "hierarchy_path": chunk.hierarchy_path,
            "hierarchy_level": chunk.hierarchy_level,
            "chunk_index": i,
            "token_count": chunk.token_count,
            "parent_chunk_id": chunk.parent_id,
        })
    _chunks[doc_id] = chunk_records

    return {
        "document": doc,
        "chunks_created": len(chunks),
        "message": "文档处理完成",
    }


@router.get("")
async def list_documents(
    doc_type: str = Query(default=""),
    status: str = Query(default=""),
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """获取文档列表"""
    items = list(_documents.values())
    if doc_type:
        items = [d for d in items if d.get("doc_type") == doc_type]
    if status:
        items = [d for d in items if d.get("status") == status]
    if search:
        items = [d for d in items if search.lower() in d.get("title", "").lower()]

    total = len(items)
    start = (page - 1) * page_size
    return {
        "items": items[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """获取文档详情"""
    doc = _documents.get(doc_id)
    if not doc:
        raise HTTPException(404, "文档不存在")
    return doc


@router.get("/{doc_id}/chunks")
async def get_document_chunks(doc_id: str):
    """获取文档分块列表"""
    if doc_id not in _documents:
        raise HTTPException(404, "文档不存在")
    return _chunks.get(doc_id, [])


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """删除文档"""
    if doc_id not in _documents:
        raise HTTPException(404, "文档不存在")
    del _documents[doc_id]
    _chunks.pop(doc_id, None)
    return {"message": "文档已删除"}
