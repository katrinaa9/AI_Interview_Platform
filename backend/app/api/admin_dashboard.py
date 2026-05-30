import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import (
    User, QuestionBank, InterviewSession, KnowledgeDocument,
    KnowledgeChunk, AuditLog, EvaluationReport,
)
from app.api.auth import require_admin
from app.schemas.schemas import DashboardStatsResponse, AuditLogResponse

logger = logging.getLogger(__name__)

INTERVIEW_TYPE_LABELS = {
    "technical": "基础技术面",
    "pressure": "压力面试",
    "friendly": "轻松聊天",
}

router = APIRouter(
    prefix="/api/admin/dashboard",
    tags=["管理-仪表盘"],
    dependencies=[Depends(require_admin)],
)


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    q_count = await db.execute(select(func.count()).select_from(QuestionBank))
    d_count = await db.execute(select(func.count()).select_from(KnowledgeDocument))
    c_count = await db.execute(select(func.count()).select_from(KnowledgeChunk))
    u_count = await db.execute(select(func.count()).select_from(User))

    today_s = await db.execute(
        select(func.count()).select_from(InterviewSession)
        .where(InterviewSession.started_at >= today_start)
    )
    week_s = await db.execute(
        select(func.count()).select_from(InterviewSession)
        .where(InterviewSession.started_at >= week_start)
    )
    month_s = await db.execute(
        select(func.count()).select_from(InterviewSession)
        .where(InterviewSession.started_at >= month_start)
    )
    total_s = await db.execute(select(func.count()).select_from(InterviewSession))
    completed_s = await db.execute(
        select(func.count()).select_from(InterviewSession)
        .where(InterviewSession.status == "completed")
    )
    failed_logs = await db.execute(
        select(func.count()).select_from(AuditLog)
        .where(AuditLog.status == "failure")
    )

    report_result = await db.execute(select(EvaluationReport))
    reports = report_result.scalars().all()
    report_averages: list[int] = []
    dimension_values: dict[str, list[float]] = {}
    for report in reports:
        numeric_scores = [
            value for value in (report.radar_scores or {}).values()
            if isinstance(value, (int, float))
        ]
        if numeric_scores:
            report_averages.append(round(sum(numeric_scores) / len(numeric_scores)))
        for name, value in (report.radar_scores or {}).items():
            if isinstance(value, (int, float)):
                dimension_values.setdefault(name, []).append(value)

    type_result = await db.execute(
        select(InterviewSession.interview_type, func.count())
        .group_by(InterviewSession.interview_type)
    )
    type_distribution = [
        {
            "type": interview_type,
            "label": INTERVIEW_TYPE_LABELS.get(interview_type, interview_type),
            "count": count,
        }
        for interview_type, count in type_result.all()
    ]

    weak_dimensions = sorted(
        [
            {
                "dimension": name,
                "average_score": round(sum(values) / len(values)),
                "sample_count": len(values),
            }
            for name, values in dimension_values.items()
            if values
        ],
        key=lambda item: item["average_score"],
    )[:6]

    recent_result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(10)
    )
    recent_logs = recent_result.scalars().all()

    return DashboardStatsResponse(
        total_questions=q_count.scalar() or 0,
        total_documents=d_count.scalar() or 0,
        total_chunks=c_count.scalar() or 0,
        today_sessions=today_s.scalar() or 0,
        week_sessions=week_s.scalar() or 0,
        month_sessions=month_s.scalar() or 0,
        total_sessions=total_s.scalar() or 0,
        completed_sessions=completed_s.scalar() or 0,
        average_score=round(sum(report_averages) / len(report_averages)) if report_averages else None,
        interview_type_distribution=type_distribution,
        weak_dimensions=weak_dimensions,
        failed_logs_count=failed_logs.scalar() or 0,
        total_users=u_count.scalar() or 0,
        recent_logs=[
            AuditLogResponse(
                id=log.id,
                operator=log.operator,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                status=log.status,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in recent_logs
        ],
    )
