import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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
    """从简历记录中提取关键词"""
    if resume and resume.parsed_keywords:
        kw_data = resume.parsed_keywords
        if isinstance(kw_data, dict) and "keywords" in kw_data:
            return kw_data["keywords"]
    return []


def _format_duration(started_at, ended_at) -> str:
    """格式化面试时长为可读字符串"""
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
) -> EvaluationReport:
    """调用 AI 评估引擎生成报告并持久化到数据库"""
    dialogue_messages = []
    if session.dialogue_history and "messages" in session.dialogue_history:
        dialogue_messages = session.dialogue_history["messages"]

    radar_scores, ai_feedback = await evaluate_interview(
        dialogue_messages, keywords
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
        f"| scores={list(radar_scores.values())}"
    )
    return report


@router.get("/{session_id}", response_model=EvaluationReportResponse)
async def get_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取面试评估报告（若不存在则实时生成），包含面试元数据"""
    # 查询会话
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

    # 先查询是否已有报告
    result = await db.execute(
        select(EvaluationReport).where(
            EvaluationReport.session_id == session_id
        )
    )
    report = result.scalar_one_or_none()

    if not report:
        # 获取用户简历关键词
        resume_result = await db.execute(
            select(Resume)
            .where(Resume.user_id == current_user.id)
            .order_by(Resume.created_at.desc())
            .limit(1)
        )
        resume = resume_result.scalar_one_or_none()
        keywords = _extract_keywords_from_resume(resume)

        # 调用 AI 评估引擎生成报告并持久化
        report = await _generate_and_persist_report(session, keywords, db)

    # 构建面试元数据
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