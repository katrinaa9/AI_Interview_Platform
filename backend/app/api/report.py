import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import InterviewSession, EvaluationReport, Resume, User
from app.schemas.schemas import EvaluationReportResponse
from app.api.auth import get_current_user
from app.services.evaluator import evaluate_interview

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/report", tags=["评估报告"])

INTERVIEW_TYPE_LABELS = {
    "technical": "基础技术面",
    "pressure": "压力面试",
    "friendly": "轻松聊天",
}


def _extract_keywords_from_resume(resume: Resume | None) -> list[str]:
    if resume and resume.parsed_keywords:
        kw_data = resume.parsed_keywords
        if isinstance(kw_data, dict) and "keywords" in kw_data:
            return kw_data["keywords"]
    return []


def _extract_job_context_from_resume(resume: Resume | None) -> tuple[str | None, str | None]:
    if resume and resume.parsed_keywords and isinstance(resume.parsed_keywords, dict):
        return (
            resume.parsed_keywords.get("job_title"),
            resume.parsed_keywords.get("job_description"),
        )
    return None, None


def _format_duration(started_at, ended_at) -> str:
    if not started_at:
        return "未知"
    end = ended_at or datetime.utcnow()
    delta = end - started_at
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{max(1, total_seconds)} 秒"
    elif total_seconds < 3600:
        return f"{total_seconds // 60} 分钟"
    else:
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        return f"{h}小时{m}分钟"


async def _generate_and_persist_report(
    session: InterviewSession,
    keywords: list[str],
    db: AsyncSession,
    job_title: str | None = None,
    job_description: str | None = None,
) -> EvaluationReport:
    dialogue_messages = []
    if session.dialogue_history and "messages" in session.dialogue_history:
        dialogue_messages = session.dialogue_history["messages"]

    radar_scores, ai_feedback = await evaluate_interview(
        dialogue_messages, keywords, job_title, job_description
    )

    report = EvaluationReport(
        session_id=session.id,
        radar_scores=radar_scores,
        ai_feedback=ai_feedback,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)

    logger.info(
        f"AI 评估报告已生成 | report_id={report.id} | session={session.id} "
        f"| scores={list(radar_scores.values())} | job_title={job_title or '未提供'}"
    )
    return report


@router.get("/history/list")
async def get_report_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == current_user.id,
            InterviewSession.status == "completed",
        )
        .order_by(InterviewSession.started_at.desc())
    )
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        report_result = await db.execute(
            select(EvaluationReport).where(EvaluationReport.session_id == s.id)
        )
        report = report_result.scalar_one_or_none()

        avg_score = None
        if report and report.radar_scores:
            scores = [v for v in report.radar_scores.values() if isinstance(v, (int, float))]
            if scores:
                avg_score = round(sum(scores) / len(scores))

        type_label = INTERVIEW_TYPE_LABELS.get(s.interview_type, s.interview_type)
        duration = _format_duration(s.started_at, s.ended_at)

        items.append({
            "session_id": s.id,
            "interview_type": s.interview_type,
            "type_label": type_label,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "duration": duration,
            "average_score": avg_score,
            "has_report": report is not None,
        })

    return {"items": items, "total": len(items)}


@router.delete("/{session_id}")
async def delete_report_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="历史面试不存在")
    if session.status != "completed":
        raise HTTPException(status_code=400, detail="只能删除已完成的历史面试")

    await db.execute(
        delete(EvaluationReport).where(EvaluationReport.session_id == session_id)
    )
    await db.delete(session)
    await db.commit()

    logger.info(
        f"用户删除历史面试 | session={session_id} | user={current_user.id}"
    )
    return {"message": "历史面试已删除", "session_id": session_id}


@router.get("/{session_id}", response_model=EvaluationReportResponse)
async def get_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    if session.status != "completed":
        raise HTTPException(status_code=400, detail="面试尚未结束，无法生成报告")

    result = await db.execute(
        select(EvaluationReport).where(
            EvaluationReport.session_id == session_id
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        resume_result = await db.execute(
            select(Resume)
            .where(Resume.user_id == current_user.id)
            .order_by(Resume.created_at.desc())
            .limit(1)
        )
        resume = resume_result.scalar_one_or_none()
        keywords = _extract_keywords_from_resume(resume)
        job_title, job_description = _extract_job_context_from_resume(resume)

        report = await _generate_and_persist_report(
            session, keywords, db, job_title, job_description
        )

    interview_type_label = INTERVIEW_TYPE_LABELS.get(
        session.interview_type, session.interview_type
    )
    interview_duration = _format_duration(session.started_at, session.ended_at)

    return EvaluationReportResponse(
        id=report.id,
        session_id=report.session_id,
        radar_scores=report.radar_scores,
        ai_feedback=report.ai_feedback,
        created_at=report.created_at,
        interview_date=session.started_at,
        interview_duration=interview_duration,
        interview_type=interview_type_label,
    )
