import uuid
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import InterviewSession, Resume, User, EvaluationReport
from app.schemas.schemas import (
    InterviewStartRequest,
    InterviewSessionResponse,
    ChatMessageRequest,
)
from app.api.auth import get_current_user
from app.services.rag_engine import retrieve_questions
from app.services.prompt_builder import (
    build_messages,
    build_welcome_message,
    build_simple_welcome,
    get_system_prompt,
    get_max_turns,
    DEFAULT_MAX_TURNS,
)
from app.services.evaluator import evaluate_interview
from app.config import settings
from app.core.concurrency import get_slot_manager, SlotTimeoutError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interview", tags=["面试间"])


# ===== 辅助函数 =====

async def _get_user_keywords(user_id: str, db: AsyncSession) -> tuple[list[str], str | None]:
    """获取用户最新简历的关键词和求职岗位"""
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    resume = result.scalar_one_or_none()
    if resume and resume.parsed_keywords:
        kw_data = resume.parsed_keywords
        if isinstance(kw_data, dict):
            keywords = kw_data.get("keywords", [])
            position = kw_data.get("position")
            return keywords, position
    return [], None


# ===== 路由 =====

@router.post("/start", response_model=InterviewSessionResponse, status_code=201)
async def start_interview(
    body: InterviewStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新的面试会话，生成 AI 开场白

    并发保护：同一用户同时只能有一个 ongoing 会话，
    创建新会话前自动关闭旧的 ongoing 会话。
    """
    # ===== 并发保护：关闭用户旧会话 =====
    old_result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == current_user.id,
            InterviewSession.status == "ongoing",
        )
    )
    old_sessions = old_result.scalars().all()
    for old in old_sessions:
        old.status = "completed"
        old.ended_at = datetime.utcnow()
        logger.info(
            f"自动关闭旧会话 | id={old.id} | user={current_user.username}"
        )

    # 获取用户简历关键词
    keywords, position_name = await _get_user_keywords(current_user.id, db)

    # 尝试 LLM 生成个性化开场白，失败时使用模板
    try:
        welcome_text = await build_welcome_message(
            keywords, body.interview_type, position_name
        )
    except Exception as e:
        logger.warning(f"个性化开场白生成失败，降级使用模板: {e}")
        welcome_text = build_simple_welcome(keywords, body.interview_type)

    # 创建会话
    session = InterviewSession(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        interview_type=body.interview_type,
        status="ongoing",
        dialogue_history={
            "messages": [{"role": "assistant", "content": welcome_text}]
        },
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    logger.info(
        f"面试会话创建 | id={session.id} | user={current_user.username} "
        f"| type={body.interview_type} | keywords={keywords} | position={position_name or '未识别'}"
    )

    return InterviewSessionResponse(
        id=session.id,
        status=session.status,
        interview_type=session.interview_type,
        started_at=session.started_at,
    )


@router.post("/chat")
async def chat(
    body: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发送消息并获取 AI 流式回复 (SSE)

    事件类型:
    - event: status   -> 状态提示
    - event: message  -> 增量文本内容
    - event: error    -> 错误信息
    - event: end      -> 对话终止信号

    并发控制：同一用户同时只能有一个 AI 推理请求在活跃状态。
    槽位在 generate() 内部管理，确保异常时不会泄漏。
    """
    # ===== 查找并校验会话 =====
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == body.session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="面试会话不存在")
    if session.status != "ongoing":
        raise HTTPException(status_code=400, detail="会话已结束，无法继续对话")

    # ===== 轮次阈值检查 =====
    max_turns = get_max_turns()
    dialogue = session.dialogue_history or {"messages": []}
    history_messages: list[dict] = dialogue.get("messages", [])
    user_turn_count = len([m for m in history_messages if m.get("role") == "user"])
    next_turn = user_turn_count + 1

    if user_turn_count >= max_turns:
        raise HTTPException(
            status_code=400,
            detail=f"面试已达到最大轮次（{max_turns}轮），请结束当前面试并查看评估报告",
        )

    # ===== 前置操作：获取简历数据 + 保存用户消息（槽位之前，失败不泄漏） =====
    keywords, position_name = await _get_user_keywords(current_user.id, db)

    history_messages.append({"role": "user", "content": body.content})
    dialogue["messages"] = history_messages
    session.dialogue_history = dialogue
    await db.flush()

    # ===== SSE 流式生成器（槽位管理在内部） =====
    async def generate():
        ai_full_response = ""

        # ----- 并发控制：获取用户槽位（在生成器内部，确保 finally 释放）-----
        slot_manager = get_slot_manager()
        try:
            await slot_manager.acquire(current_user.id)
        except SlotTimeoutError as e:
            logger.warning(f"槽位获取超时: user={current_user.id}, error={e}")
            yield f"event: error\ndata: {json.dumps({'message': '当前请求排队超时，AI 正在处理前一个问题，请稍等片刻后重新发送'})}\n\n"
            yield f"event: end\ndata: {json.dumps({'message': '排队超时'})}\n\n"
            return

        try:
            # ----- 状态 1: 检索简历 -----
            yield f"event: status\ndata: {json.dumps({'message': '正在检索你的简历与技术栈信息...'})}\n\n"

            # ----- 状态 2: RAG 检索 -----
            yield f"event: status\ndata: {json.dumps({'message': '正在匹配题库中的相关考点...'})}\n\n"

            rag_questions = await retrieve_questions(keywords)

            # ----- 状态 3: 组装 Prompt -----
            yield f"event: status\ndata: {json.dumps({'message': 'AI 正在思考中...'})}\n\n"

            system_prompt = get_system_prompt(
                keywords=keywords,
                interview_type=session.interview_type,
                turn=next_turn,
                max_turns=max_turns,
                position_name=position_name,
            )

            rag_context = ""
            if rag_questions:
                rag_parts = []
                for i, q in enumerate(rag_questions[:3], 1):
                    rag_parts.append(
                        f"{i}. {q.get('question_text', '')}（参考答案要点：{q.get('reference_answer', '')[:120]}）"
                    )
                rag_context = "\n".join(rag_parts)

            messages = build_messages(
                system_prompt=system_prompt,
                dialogue_history=history_messages,
                rag_context=rag_context,
            )

            # ----- 状态 4: 调用 LLM 流式输出 -----
            use_mock = not settings.DEEPSEEK_API_KEY

            if not use_mock:
                try:
                    from app.services.llm_client import chat_completion_stream

                    async for chunk in chat_completion_stream(messages):
                        ai_full_response += chunk
                        yield f"event: message\ndata: {json.dumps({'content': chunk})}\n\n"

                except (ValueError, RuntimeError) as e:
                    # DeepSeek API 不可用，降级为 Mock 流式输出
                    logger.warning(f"DeepSeek API 调用失败，降级为 Mock: {e}")
                    use_mock = True

            # Mock 降级流
            if use_mock:
                yield f"event: status\ndata: {json.dumps({'message': '（注意：当前为 Mock 模式，请配置 DEEPSEEK_API_KEY 启用 AI 面试）'})}\n\n"

                mock_response = _build_mock_response(
                    keywords, history_messages, session.interview_type
                )
                import asyncio as aio
                for i, char in enumerate(mock_response):
                    ai_full_response += char
                    yield f"event: message\ndata: {json.dumps({'content': char})}\n\n"
                    if i % 3 == 0:
                        await aio.sleep(0.015)

            # ----- 结束：保存 AI 回复 + 发送 end 事件 -----
            if ai_full_response:
                history_messages.append({
                    "role": "assistant",
                    "content": ai_full_response,
                })
                dialogue["messages"] = history_messages
                session.dialogue_history = dialogue
                # 使用独立 session 刷新（防止 FastAPI 提前关闭依赖注入的 session）
                from app.models.database import async_session as _async_session
                async with _async_session() as flush_db:
                    result = await flush_db.execute(
                        select(InterviewSession).where(InterviewSession.id == session.id)
                    )
                    session_obj = result.scalar_one_or_none()
                    if session_obj:
                        session_obj.dialogue_history = dialogue
                        await flush_db.commit()
                        logger.debug(f"AI 回复已持久化: session={session.id}, turn={next_turn}")
                    else:
                        logger.warning(f"持久化 AI 回复时找不到会话: session={session.id}")

            yield f"event: end\ndata: {json.dumps({'message': '回复完成'})}\n\n"

        except Exception as e:
            logger.exception(f"SSE 流式生成异常: session={session.id}, user={current_user.id}, error={e}")
            yield f"event: error\ndata: {json.dumps({'message': 'AI 服务暂时不可用，请稍后重试'})}\n\n"
            yield f"event: end\ndata: {json.dumps({'message': '异常结束'})}\n\n"

        finally:
            # 无论成功/失败/客户端断开，都释放槽位
            slot_manager.release(current_user.id)
            logger.debug(f"槽位已释放: user={current_user.id}, session={session.id}")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/end")
async def end_interview(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """结束面试会话，并自动触发 AI 评估生成报告"""
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="面试会话不存在")

    # 允许对已完成的会话重复请求（幂等），但跳过评估重新生成
    already_completed = session.status == "completed"

    if not already_completed:
        session.status = "completed"
        session.ended_at = datetime.utcnow()
        await db.flush()
        logger.info(f"面试会话结束: id={session_id}, user={current_user.username}")

    # ---- 自动触发 AI 评估 ----
    # 检查是否已有报告，避免重复生成
    existing = await db.execute(
        select(EvaluationReport).where(
            EvaluationReport.session_id == session_id
        )
    )
    existing_report = existing.scalar_one_or_none()

    if existing_report:
        logger.info(f"评估报告已存在，跳过重新生成: report_id={existing_report.id}")
        return {
            "message": "面试已结束，评估报告已就绪",
            "session_id": session_id,
            "report_id": existing_report.id,
        }

    # 生成新报告
    try:
        # 获取关键词
        keywords, position_name = await _get_user_keywords(current_user.id, db)

        # 提取对话历史
        dialogue_messages = []
        if session.dialogue_history and "messages" in session.dialogue_history:
            dialogue_messages = session.dialogue_history["messages"]

        # 调用 AI 评估
        radar_scores, ai_feedback = await evaluate_interview(
            dialogue_messages, keywords
        )

        # 持久化报告
        report = EvaluationReport(
            session_id=session.id,
            radar_scores=radar_scores,
            ai_feedback=ai_feedback,
        )
        db.add(report)
        await db.flush()
        await db.commit()  # 确保报告已持久化到数据库

        logger.info(
            f"面试结束自动评估完成 | report_id={report.id} "
            f"| session={session_id} | avg={sum(radar_scores.values()) / len(radar_scores):.1f}"
        )

        return {
            "message": "面试已结束，评估报告已生成",
            "session_id": session_id,
            "report_id": report.id,
        }

    except Exception as e:
        # 评估失败不影响面试结束（用户后续查看报告时会重新尝试生成）
        logger.warning(f"面试结束自动评估失败（将在查看报告时重试）: {e}")
        return {
            "message": "面试已结束（评估报告将在查看时生成）",
            "session_id": session_id,
            "report_id": None,
        }


# ===== Mock 降级回复生成器（无 DeepSeek API Key 时使用） =====

def _build_mock_response(
    keywords: list[str],
    history: list[dict],
    interview_type: str,
) -> str:
    """生成 Mock 回复，模拟5阶段面试流程（1-2介绍→3-8技术→9-11压力→12-13素养→14-15收尾）。"""
    turn = len([m for m in history if m["role"] == "user"])
    tech = keywords[turn % len(keywords)] if keywords else "你的项目"

    # ===== Phase 1: 简历介绍与自我介绍（turn 1-2） =====
    if turn == 1:
        return (
            f"感谢你的分享，让我对你的背景有了初步了解。\n\n"
            f"你提到了 **{tech}**，你在实际工作中是怎么接触到它的？"
            f"能否展开说说你的技术成长历程？"
        )

    elif turn == 2:
        return (
            f"好的，对你的背景和兴趣有了更多了解。\n\n"
            f"接下来我们进入技术考察环节——"
            f"关于 **{tech}**，请解释它的核心工作原理，以及与其他同类技术相比的优劣势。"
        )

    # ===== Phase 2: 技术能力考察（turn 3-8） =====
    elif turn == 3:
        return (
            f"基础原理说得不错。请深入一层——**{tech}** 的底层实现机制是什么？"
            f"你在项目中是如何利用这些机制来优化性能的？"
        )

    elif turn == 4:
        return (
            f"好的，基础能力掌握得还可以。\n\n"
            f"接下来聊聊实际项目——请选一个你做过的最具挑战性的项目，"
            f"详细说说业务背景、技术架构和你负责的部分。"
        )

    elif turn == 5:
        return (
            f"有意思的项目。为什么在这个项目中选择了 **{tech}**？"
            f"有没有对比过其他方案？请具体分析你的技术选型理由。"
        )

    elif turn == 6:
        return (
            f"技术选型思路明确了。请描述一下这个项目的整体架构设计，"
            f"各模块间的职责划分和数据流转。遇到的主要技术挑战是什么？"
        )

    elif turn == 7:
        return (
            f"架构部分说清楚了。那落地后的效果呢？"
            f"有没有具体的性能指标提升数据可以分享？"
            f"项目上线后你是否参与了运维和监控？"
        )

    elif turn == 8:
        return (
            f"项目经验聊得比较深了。换个角度——"
            f"如果让你从零重新设计这个项目，你会做哪些不同的选择？为什么？"
        )

    # ===== Phase 3: 压力面试（turn 9-11） =====
    elif turn == 9:
        return (
            f"刚才你的回答有一些地方我需要挑战一下。\n\n"
            f"你说用了 **{tech}** 来解决性能问题——但这真的是最优方案吗？"
            f"如果我是你的技术leader，我会质疑为什么不用更轻量的方案。你怎么说服我？"
        )

    elif turn == 10:
        return (
            f"我注意到你对一些问题的回答避重就轻。\n\n"
            f"换个直接的问题：你觉得你在当前技术团队中处于什么水平？"
            f"你最大的技术短板是什么？诚实回答，不需要包装。"
        )

    elif turn == 11:
        return (
            f"很好，你的坦诚值得肯定。再追问一个——"
            f"如果你的方案在生产环境出现严重问题，凌晨三点被叫起来排查，"
            f"你会首先做什么？你的排查思路是什么？"
        )

    # ===== Phase 4: 职业素养与人品考察（turn 12-13） =====
    elif turn == 12:
        return (
            f"技术部分聊得差不多了，换个话题。\n\n"
            f"请描述一次你与同事发生分歧的经历——"
            f"你们在什么问题上产生了分歧？你怎么处理的？最终结果如何？"
        )

    elif turn == 13:
        return (
            f"了解。再问几个关于个人成长的问题——\n\n"
            f"你如何评价自己的职业道德和责任心？有没有加班到很晚的经历？"
            f"你对加班文化怎么看？未来三年的职业规划是什么？"
        )

    # ===== Phase 5: 公司情况询问与期望了解（turn 14-15） =====
    elif turn == 14:
        return (
            f"感谢你的坦诚分享。已经聊了很多技术和职业方面的话题了。\n\n"
            f"现在我想了解一下——你对我们的公司有什么了解？"
            f"为什么选择投递这个岗位？你希望通过这份工作获得什么？"
        )

    elif turn >= 15:
        return (
            f"经过这15轮的交流，我对你的技术能力、项目经验、职业素养和价值观"
            f"都有了比较全面的了解。你在 **{tech}** 方面展现了不错的功底，"
            f"整体表现达到了面试的预期。\n\n"
            f"感谢你参与今天的面试！后续如果有进一步安排，我们会及时联系你。"
            f"你还有什么想了解的吗？"
        )

    return f"请继续——关于 **{tech}**，你还有哪些想分享的经验？"