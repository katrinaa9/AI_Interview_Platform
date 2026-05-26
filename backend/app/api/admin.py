import uuid
import logging
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import QuestionBank, User
from app.schemas.schemas import (
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
    QuestionListResponse,
    QuestionStatsItem,
    QuestionStatsResponse,
    QuestionDeleteResponse,
)
from app.api.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["后台管理"],
    dependencies=[Depends(require_admin)],  # 整个路由组强制 Admin 鉴权
)


# ===== 题库 CRUD =====

@router.get("/questions", response_model=QuestionListResponse)
async def list_questions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    category: str | None = Query(default=None, description="按技术栈标签筛选"),
    search: str | None = Query(default=None, description="模糊搜索题目文本"),
    db: AsyncSession = Depends(get_db),
):
    """分页获取题库列表，支持按标签筛选和关键词搜索"""
    # 构建查询
    stmt = select(QuestionBank)

    # 条件过滤
    if category:
        stmt = stmt.where(QuestionBank.category == category)
    if search:
        stmt = stmt.where(
            QuestionBank.question_text.contains(search)
        )

    # 获取总数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.order_by(QuestionBank.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    questions = result.scalars().all()

    items = [
        QuestionResponse(
            id=q.id,
            category=q.category,
            question_text=q.question_text,
            reference_answer=q.reference_answer,
            difficulty=q.difficulty,
            times_asked=q.times_asked,
            times_wrong=q.times_wrong,
            created_at=q.created_at,
        )
        for q in questions
    ]

    return QuestionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def create_question(
    body: QuestionCreate,
    db: AsyncSession = Depends(get_db),
):
    """新增题库题目"""
    question = QuestionBank(
        id=str(uuid.uuid4()),
        category=body.category,
        question_text=body.question_text,
        reference_answer=body.reference_answer,
        difficulty=body.difficulty,
    )
    db.add(question)
    await db.flush()
    await db.refresh(question)

    logger.info(
        f"管理员新增题目 | id={question.id} | category={question.category}"
    )

    return QuestionResponse(
        id=question.id,
        category=question.category,
        question_text=question.question_text,
        reference_answer=question.reference_answer,
        difficulty=question.difficulty,
        times_asked=question.times_asked,
        times_wrong=question.times_wrong,
        created_at=question.created_at,
    )


@router.put("/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: str,
    body: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新题库题目（部分字段可选）"""
    result = await db.execute(
        select(QuestionBank).where(QuestionBank.id == question_id)
    )
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 仅更新传入的非 None 字段
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(question, key, value)

    await db.flush()
    await db.refresh(question)

    logger.info(f"管理员更新题目: id={question_id}")

    return QuestionResponse(
        id=question.id,
        category=question.category,
        question_text=question.question_text,
        reference_answer=question.reference_answer,
        difficulty=question.difficulty,
        times_asked=question.times_asked,
        times_wrong=question.times_wrong,
        created_at=question.created_at,
    )


@router.delete("/questions/{question_id}", response_model=QuestionDeleteResponse)
async def delete_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除题库题目"""
    result = await db.execute(
        select(QuestionBank).where(QuestionBank.id == question_id)
    )
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    await db.delete(question)
    await db.flush()

    logger.info(f"管理员删除题目: id={question_id} | category={question.category}")

    return QuestionDeleteResponse(message="题目已删除", id=question_id)


# ===== 统计接口 =====

@router.get("/questions/stats", response_model=QuestionStatsResponse)
async def get_wrong_question_stats(
    limit: int = Query(default=10, ge=1, le=50, description="返回 Top N 高频错题"),
    db: AsyncSession = Depends(get_db),
):
    """
    高频错题统计

    返回被回答错误次数最多的题目，按错误次数降序排列。
    error_rate = times_wrong / times_asked（times_asked 为 0 时 error_rate = 0）。
    """
    stmt = (
        select(QuestionBank)
        .where(QuestionBank.times_wrong > 0)
        .order_by(QuestionBank.times_wrong.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    questions = result.scalars().all()

    items = []
    for q in questions:
        rate = q.times_wrong / q.times_asked if q.times_asked > 0 else 0.0
        items.append(
            QuestionStatsItem(
                id=q.id,
                category=q.category,
                question_text=q.question_text[:120],  # 截断长文本
                times_asked=q.times_asked,
                times_wrong=q.times_wrong,
                error_rate=round(rate, 4),
            )
        )

    return QuestionStatsResponse(items=items, total=len(items))