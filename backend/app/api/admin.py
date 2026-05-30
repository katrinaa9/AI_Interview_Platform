import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import QuestionBank, User, InterviewSession, EvaluationReport
from app.schemas.schemas import (
    AdminInterviewDeleteResponse,
    AdminInterviewItem,
    AdminInterviewListResponse,
    AdminInterviewReportResponse,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserRoleUpdate,
    AdminUserStatusUpdate,
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
    QuestionListResponse,
    QuestionStatsItem,
    QuestionStatsResponse,
    QuestionDeleteResponse,
)
from app.api.auth import require_admin
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

INTERVIEW_TYPE_LABELS = {
    "technical": "基础技术面",
    "pressure": "压力面试",
    "friendly": "轻松聊天",
}


def _format_duration(started_at, ended_at) -> str:
    if not started_at:
        return "未知"
    end = ended_at or datetime.utcnow()
    seconds = max(0, int((end - started_at).total_seconds()))
    if seconds < 60:
        return f"{max(1, seconds)} 秒"
    if seconds < 3600:
        return f"{seconds // 60} 分钟"
    return f"{seconds // 3600}小时{(seconds % 3600) // 60}分钟"


def _average_score(report: EvaluationReport | None) -> int | None:
    if not report or not report.radar_scores:
        return None
    scores = [
        value for value in report.radar_scores.values()
        if isinstance(value, (int, float))
    ]
    if not scores:
        return None
    return round(sum(scores) / len(scores))


def _message_count(session: InterviewSession) -> int:
    if not session.dialogue_history or not isinstance(session.dialogue_history, dict):
        return 0
    messages = session.dialogue_history.get("messages") or []
    return len(messages) if isinstance(messages, list) else 0


def _build_interview_item(
    session: InterviewSession,
    user: User,
    report: EvaluationReport | None = None,
) -> AdminInterviewItem:
    return AdminInterviewItem(
        session_id=session.id,
        user_id=user.id,
        username=user.username,
        status=session.status,
        interview_type=session.interview_type,
        type_label=INTERVIEW_TYPE_LABELS.get(session.interview_type, session.interview_type),
        started_at=session.started_at,
        ended_at=session.ended_at,
        duration=_format_duration(session.started_at, session.ended_at),
        average_score=_average_score(report),
        has_report=report is not None,
        message_count=_message_count(session),
    )


async def _count_active_admins(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(User).where(
            User.role == "admin",
            User.is_active.is_(True),
        )
    )
    return result.scalar() or 0


router = APIRouter(
    prefix="/api/admin",
    tags=["后台管理"],
    dependencies=[Depends(require_admin)],  # 整个路由组强制 Admin 鉴权
)


# ===== 用户与权限管理 =====

@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
    search: str | None = Query(default=None, description="按用户名搜索"),
    role: str | None = Query(default=None, pattern="^(student|admin)$"),
    is_active: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User)
    if search:
        stmt = stmt.where(User.username.contains(search))
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar() or 0

    result = await db.execute(
        stmt.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = result.scalars().all()

    items: list[AdminUserItem] = []
    for user in users:
        session_count = (
            await db.execute(
                select(func.count()).select_from(InterviewSession)
                .where(InterviewSession.user_id == user.id)
            )
        ).scalar() or 0
        completed_count = (
            await db.execute(
                select(func.count()).select_from(InterviewSession)
                .where(
                    InterviewSession.user_id == user.id,
                    InterviewSession.status == "completed",
                )
            )
        ).scalar() or 0
        last_session = (
            await db.execute(
                select(InterviewSession)
                .where(InterviewSession.user_id == user.id)
                .order_by(InterviewSession.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        report_result = await db.execute(
            select(EvaluationReport)
            .join(InterviewSession, EvaluationReport.session_id == InterviewSession.id)
            .where(InterviewSession.user_id == user.id)
        )
        report_scores = [
            score for score in (_average_score(report) for report in report_result.scalars().all())
            if score is not None
        ]

        items.append(
            AdminUserItem(
                id=user.id,
                username=user.username,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
                interview_count=session_count,
                completed_interview_count=completed_count,
                average_score=round(sum(report_scores) / len(report_scores)) if report_scores else None,
                last_interview_at=last_session.started_at if last_session else None,
            )
        )

    return AdminUserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.patch("/users/{user_id}/role", response_model=AdminUserItem)
async def update_user_role(
    user_id: str,
    body: AdminUserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == current_user.id and body.role != "admin":
        raise HTTPException(status_code=400, detail="不能降低自己的管理员权限")
    if target.role == "admin" and body.role != "admin" and target.is_active:
        if await _count_active_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="至少需要保留一个可用管理员")

    old_role = target.role
    target.role = body.role
    await db.flush()
    await db.refresh(target)
    await log_action(
        operator=current_user.username,
        action="role_update",
        resource_type="user",
        resource_id=target.id,
        details=f"{target.username}: {old_role} -> {target.role}",
    )

    return AdminUserItem(
        id=target.id,
        username=target.username,
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


@router.patch("/users/{user_id}/status", response_model=AdminUserItem)
async def update_user_status(
    user_id: str,
    body: AdminUserStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == current_user.id and not body.is_active:
        raise HTTPException(status_code=400, detail="不能禁用自己的账号")
    if target.role == "admin" and target.is_active and not body.is_active:
        if await _count_active_admins(db) <= 1:
            raise HTTPException(status_code=400, detail="至少需要保留一个可用管理员")

    old_status = target.is_active
    target.is_active = body.is_active
    await db.flush()
    await db.refresh(target)
    await log_action(
        operator=current_user.username,
        action="status_update",
        resource_type="user",
        resource_id=target.id,
        details=f"{target.username}: {old_status} -> {target.is_active}",
    )

    return AdminUserItem(
        id=target.id,
        username=target.username,
        role=target.role,
        is_active=target.is_active,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


# ===== 全量面试记录管理 =====

@router.get("/interviews", response_model=AdminInterviewListResponse)
async def list_interviews(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
    search: str | None = Query(default=None, description="按用户名搜索"),
    status_filter: str | None = Query(default=None, alias="status"),
    interview_type: str | None = Query(default=None, pattern="^(technical|pressure|friendly)$"),
    user_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(InterviewSession, User).join(User, InterviewSession.user_id == User.id)
    if search:
        stmt = stmt.where(User.username.contains(search))
    if status_filter:
        stmt = stmt.where(InterviewSession.status == status_filter)
    if interview_type:
        stmt = stmt.where(InterviewSession.interview_type == interview_type)
    if user_id:
        stmt = stmt.where(InterviewSession.user_id == user_id)

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar() or 0
    result = await db.execute(
        stmt.order_by(InterviewSession.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    items: list[AdminInterviewItem] = []
    for session, user in result.all():
        report = (
            await db.execute(
                select(EvaluationReport).where(EvaluationReport.session_id == session.id)
            )
        ).scalar_one_or_none()
        items.append(_build_interview_item(session, user, report))

    return AdminInterviewListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/interviews/{session_id}", response_model=AdminInterviewReportResponse)
async def get_interview_report_detail(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InterviewSession, User)
        .join(User, InterviewSession.user_id == User.id)
        .where(InterviewSession.id == session_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="面试记录不存在")

    session, user = row
    report = (
        await db.execute(
            select(EvaluationReport).where(EvaluationReport.session_id == session.id)
        )
    ).scalar_one_or_none()

    return AdminInterviewReportResponse(
        session=_build_interview_item(session, user, report),
        radar_scores=report.radar_scores if report else None,
        ai_feedback=report.ai_feedback if report else None,
        created_at=report.created_at if report else None,
    )


@router.delete("/interviews/{session_id}", response_model=AdminInterviewDeleteResponse)
async def delete_interview_record(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(InterviewSession, User)
        .join(User, InterviewSession.user_id == User.id)
        .where(InterviewSession.id == session_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="面试记录不存在")

    session, owner = row
    await db.execute(
        delete(EvaluationReport).where(EvaluationReport.session_id == session.id)
    )
    await db.delete(session)
    await db.flush()
    await log_action(
        operator=current_user.username,
        action="delete_interview",
        resource_type="interview_session",
        resource_id=session_id,
        details=f"删除 {owner.username} 的面试记录",
    )

    return AdminInterviewDeleteResponse(message="面试记录已删除", session_id=session_id)


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
