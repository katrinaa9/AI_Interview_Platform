"""
RAG 检索增强引擎

核心流程:
    用户简历关键词 → Redis 缓存查询 → 未命中 → MySQL 题库检索 → 回写 Redis 缓存
                                                    ↓
                                            更新 times_asked 统计

返回：匹配的标准题库题目列表，作为 LLM 的引用上下文
"""

import json
import logging
from typing import List, Optional
from sqlalchemy import select, update
from app.models.database import async_session
from app.models.models import QuestionBank
from app.core.redis import get_redis_or_none

logger = logging.getLogger(__name__)

# Redis 缓存配置
CACHE_KEY_PREFIX = "rag:questions"
CACHE_TTL = 3600  # 1 小时


async def retrieve_questions(
    keywords: List[str],
    max_per_keyword: int = 3,
    max_total: int = 8,
) -> List[dict]:
    """
    根据简历关键词检索相关题库题目（RAG 检索）。

    检索策略：
    1. 对每个关键词，优先查 Redis 缓存
    2. 缓存未命中 → 异步查询 MySQL（精确匹配 category，降级为 LIKE 模糊匹配）
    3. 查到的结果写回 Redis 缓存
    4. 聚合去重后返回，每关键词最多 max_per_keyword 道，总计不超过 max_total

    Args:
        keywords: 简历技术栈关键词列表，如 ["React", "TypeScript", "FastAPI"]
        max_per_keyword: 每个关键词最多返回的题目数
        max_total: 总共最多返回的题目数

    Returns:
        题目列表，每道题为 dict: {
            "id": str, "category": str, "question_text": str,
            "reference_answer": str, "difficulty": str
        }
    """
    if not keywords:
        logger.warning("RAG 检索：关键词列表为空，返回空结果")
        return []

    all_questions: dict[str, dict] = {}  # key: id, 去重
    redis = await get_redis_or_none()

    for keyword in keywords:
        if len(all_questions) >= max_total:
            break

        cache_key = f"{CACHE_KEY_PREFIX}:{keyword.lower()}"

        # ===== 步骤 1: 尝试 Redis 缓存 =====
        cached = None
        if redis:
            try:
                cached_raw = await redis.get(cache_key)
                if cached_raw:
                    cached = json.loads(cached_raw)
                    logger.debug(f"Redis 命中: {keyword} ({len(cached)} 条)")
            except Exception as e:
                logger.warning(f"Redis 读取异常 (keyword={keyword}): {e}")

        if cached:
            for q in cached[:max_per_keyword]:
                if q["id"] not in all_questions:
                    all_questions[q["id"]] = q
            continue

        # ===== 步骤 2: Redis 未命中，查询 MySQL =====
        async with async_session() as db:
            try:
                # 精确匹配 category
                result = await db.execute(
                    select(QuestionBank)
                    .where(QuestionBank.category == keyword)
                    .order_by(QuestionBank.times_asked.asc())  # 优先抽取低频题目
                    .limit(max_per_keyword * 2)  # 多取一些，后续去重
                )
                questions = result.scalars().all()

                # 若无精确匹配，尝试模糊匹配
                if not questions:
                    result = await db.execute(
                        select(QuestionBank)
                        .where(QuestionBank.category.contains(keyword))
                        .order_by(QuestionBank.times_asked.asc())
                        .limit(max_per_keyword * 2)
                    )
                    questions = result.scalars().all()

                # 转换为字典列表
                matched: List[dict] = []
                for q in questions:
                    q_dict = {
                        "id": q.id,
                        "category": q.category,
                        "question_text": q.question_text,
                        "reference_answer": q.reference_answer,
                        "difficulty": q.difficulty,
                    }
                    matched.append(q_dict)
                    if q.id not in all_questions:
                        all_questions[q.id] = q_dict

                # ===== 步骤 3: 回写 Redis 缓存 =====
                if redis and matched:
                    try:
                        await redis.setex(
                            cache_key,
                            CACHE_TTL,
                            json.dumps(matched, ensure_ascii=False),
                        )
                    except Exception as e:
                        logger.warning(f"Redis 回写失败 (keyword={keyword}): {e}")

                # ===== 步骤 4: 更新 times_asked 统计 =====
                if matched:
                    try:
                        for q in matched:
                            await db.execute(
                                update(QuestionBank)
                                .where(QuestionBank.id == q["id"])
                                .values(times_asked=QuestionBank.times_asked + 1)
                            )
                        await db.commit()
                    except Exception as e:
                        logger.warning(f"更新 times_asked 失败: {e}")
                        await db.rollback()

            except Exception as e:
                logger.exception(f"MySQL 检索失败 (keyword={keyword}): {e}")
                await db.rollback()
                continue

    # ===== 最终聚合：按难度排序（easy → medium → hard），截断 =====
    difficulty_order = {"easy": 0, "medium": 1, "hard": 2}
    results = sorted(
        all_questions.values(),
        key=lambda q: difficulty_order.get(q["difficulty"], 1),
    )[:max_total]

    logger.info(
        f"RAG 检索完成: keywords={keywords} → 命中 {len(results)} 道题目 "
        f"(categories: {list(set(q['category'] for q in results))})"
    )
    return results


async def get_question_by_id(question_id: str) -> Optional[dict]:
    """按 ID 获取单道题目（供后续使用）"""
    async with async_session() as db:
        result = await db.execute(
            select(QuestionBank).where(QuestionBank.id == question_id)
        )
        q = result.scalar_one_or_none()
        if not q:
            return None
        return {
            "id": q.id,
            "category": q.category,
            "question_text": q.question_text,
            "reference_answer": q.reference_answer,
            "difficulty": q.difficulty,
        }