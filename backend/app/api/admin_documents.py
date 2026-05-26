import uuid
import asyncio
import logging
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import KnowledgeDocument, KnowledgeChunk
from app.api.auth import require_admin
from app.schemas.schemas import (
    DocumentResponse, DocumentListResponse,
    ChunkResponse, ChunkListResponse,
    ChunkCreateRequest, ChunkUpdateRequest, BatchDeleteRequest,
)
from app.services.document_processor import (
    validate_file, process_document, UPLOAD_DIR,
)
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/documents",
    tags=["管理-知识库文档"],
    dependencies=[Depends(require_admin)],
)


def _doc_to_response(doc: KnowledgeDocument) -> DocumentResponse:
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        uploaded_by=doc.uploaded_by,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def _chunk_to_response(chunk: KnowledgeChunk) -> ChunkResponse:
    return ChunkResponse(
        id=chunk.id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        category=chunk.category,
        difficulty=chunk.difficulty,
        keywords=chunk.keywords,
        created_at=chunk.created_at,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(KnowledgeDocument)
    if status_filter:
        stmt = stmt.where(KnowledgeDocument.status == status_filter)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(KnowledgeDocument.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    docs = result.scalars().all()

    return DocumentListResponse(
        items=[_doc_to_response(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    filename = file.filename or "unknown"
    content = await file.read()
    file_size = len(content)

    ok, err = validate_file(filename, file_size)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    file_type = Path(filename).suffix.lower().lstrip(".")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    doc_id = str(uuid.uuid4())
    safe_name = f"{doc_id}.{file_type}"
    file_path = str(UPLOAD_DIR / safe_name)

    with open(file_path, "wb") as f:
        f.write(content)

    doc = KnowledgeDocument(
        id=doc_id,
        filename=filename,
        file_type=file_type,
        file_size=file_size,
        status="pending",
        uploaded_by=current_user.username,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    await db.commit()

    background_tasks.add_task(process_document, doc_id, file_path, file_type)

    await log_action(
        operator=current_user.username,
        action="upload",
        resource_type="document",
        resource_id=doc_id,
        details=f"上传文档: {filename} ({file_size / 1024:.1f}KB)",
    )

    return _doc_to_response(doc)


@router.post("/upload/batch", response_model=list[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def upload_documents_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="单次批量上传不超过 10 个文件")

    results = []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    for file in files:
        filename = file.filename or "unknown"
        content = await file.read()
        file_size = len(content)

        ok, err = validate_file(filename, file_size)
        if not ok:
            continue

        file_type = Path(filename).suffix.lower().lstrip(".")
        doc_id = str(uuid.uuid4())
        safe_name = f"{doc_id}.{file_type}"
        file_path = str(UPLOAD_DIR / safe_name)

        with open(file_path, "wb") as f:
            f.write(content)

        doc = KnowledgeDocument(
            id=doc_id,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            status="pending",
            uploaded_by=current_user.username,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)

        background_tasks.add_task(process_document, doc_id, file_path, file_type)
        results.append(_doc_to_response(doc))

    await db.commit()

    await log_action(
        operator=current_user.username,
        action="batch_upload",
        resource_type="document",
        details=f"批量上传 {len(results)} 个文档",
    )

    return results


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    doc = await db.get(KnowledgeDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    file_path = UPLOAD_DIR / f"{document_id}.{doc.file_type}"
    if file_path.exists():
        os.remove(file_path)

    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
    await db.delete(doc)
    await db.flush()
    await db.commit()

    await log_action(
        operator=current_user.username,
        action="delete",
        resource_type="document",
        resource_id=document_id,
        details=f"删除文档: {doc.filename}",
    )

    return {"message": "文档及关联数据已删除", "id": document_id}


@router.post("/batch-delete")
async def batch_delete_documents(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    count = 0
    for doc_id in body.ids:
        doc = await db.get(KnowledgeDocument, doc_id)
        if doc:
            file_path = UPLOAD_DIR / f"{doc_id}.{doc.file_type}"
            if file_path.exists():
                os.remove(file_path)
            await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id))
            await db.delete(doc)
            count += 1

    await db.flush()
    await db.commit()

    await log_action(
        operator=current_user.username,
        action="batch_delete",
        resource_type="document",
        details=f"批量删除 {count} 个文档",
    )

    return {"message": f"已删除 {count} 个文档", "count": count}


@router.post("/reprocess/{document_id}", response_model=DocumentResponse)
async def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    doc = await db.get(KnowledgeDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id))
    doc.status = "pending"
    doc.chunk_count = 0
    doc.error_message = None
    await db.flush()
    await db.commit()

    file_path = str(UPLOAD_DIR / f"{document_id}.{doc.file_type}")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="原始文件已丢失，请重新上传")

    background_tasks.add_task(process_document, document_id, file_path, doc.file_type)

    await log_action(
        operator=current_user.username,
        action="reprocess",
        resource_type="document",
        resource_id=document_id,
        details=f"重新处理文档: {doc.filename}",
    )

    return _doc_to_response(doc)


@router.get("/{document_id}/chunks", response_model=ChunkListResponse)
async def list_document_chunks(
    document_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(KnowledgeChunk.chunk_index).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    return ChunkListResponse(
        items=[_chunk_to_response(c) for c in chunks],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/chunks/search", response_model=ChunkListResponse)
async def search_chunks(
    keyword: str = Query(default="", description="搜索关键词"),
    category: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(KnowledgeChunk)
    if keyword:
        stmt = stmt.where(KnowledgeChunk.content.contains(keyword))
    if category:
        stmt = stmt.where(KnowledgeChunk.category == category)
    if difficulty:
        stmt = stmt.where(KnowledgeChunk.difficulty == difficulty)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(KnowledgeChunk.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    return ChunkListResponse(
        items=[_chunk_to_response(c) for c in chunks],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/chunks", response_model=ChunkResponse, status_code=status.HTTP_201_CREATED)
async def create_chunk(
    body: ChunkCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    max_idx_result = await db.execute(
        select(func.coalesce(func.max(KnowledgeChunk.chunk_index), -1))
    )
    next_idx = (max_idx_result.scalar() or -1) + 1

    chunk = KnowledgeChunk(
        document_id="manual",
        chunk_index=next_idx,
        content=body.content,
        category=body.category,
        difficulty=body.difficulty,
        keywords=body.keywords,
    )
    db.add(chunk)
    await db.flush()
    await db.refresh(chunk)
    await db.commit()

    await log_action(
        operator=current_user.username,
        action="create",
        resource_type="chunk",
        resource_id=chunk.id,
        details=f"手动添加知识片段: {body.content[:50]}...",
    )

    return _chunk_to_response(chunk)


@router.put("/chunks/{chunk_id}", response_model=ChunkResponse)
async def update_chunk(
    chunk_id: str,
    body: ChunkUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    chunk = await db.get(KnowledgeChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="知识片段不存在")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(chunk, key, value)

    await db.flush()
    await db.refresh(chunk)
    await db.commit()

    await log_action(
        operator=current_user.username,
        action="update",
        resource_type="chunk",
        resource_id=chunk_id,
        details="更新知识片段",
    )

    return _chunk_to_response(chunk)


@router.delete("/chunks/{chunk_id}")
async def delete_chunk(
    chunk_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    chunk = await db.get(KnowledgeChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="知识片段不存在")

    await db.delete(chunk)
    await db.flush()
    await db.commit()

    await log_action(
        operator=current_user.username,
        action="delete",
        resource_type="chunk",
        resource_id=chunk_id,
        details="删除知识片段",
    )

    return {"message": "知识片段已删除", "id": chunk_id}


@router.post("/chunks/batch-delete")
async def batch_delete_chunks(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    count = 0
    for chunk_id in body.ids:
        chunk = await db.get(KnowledgeChunk, chunk_id)
        if chunk:
            await db.delete(chunk)
            count += 1

    await db.flush()
    await db.commit()

    await log_action(
        operator=current_user.username,
        action="batch_delete",
        resource_type="chunk",
        details=f"批量删除 {count} 个知识片段",
    )

    return {"message": f"已删除 {count} 个知识片段", "count": count}
