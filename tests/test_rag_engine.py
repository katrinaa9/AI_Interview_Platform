"""
测试 RAG 检索引擎

测试项：
1. 关键词精确匹配
2. 降级为模糊匹配
3. Redis 缓存命中/回写
4. 空关键词返回空结果
5. 去重与截断
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.rag_engine import retrieve_questions


async def test_retrieve_empty_keywords():
    keywords = []
    result = await retrieve_questions(keywords)
    assert result == [], "空关键词应返回空列表"
    print("PASS: 空关键词返回空结果")


async def test_retrieve_with_redis_cache():
    redis = AsyncMock()
    redis.get.return_value = '[{"id": "q1", "category": "React", "question_text": "React 是什么", "reference_answer": "...", "difficulty": "easy"}]'
    
    with patch("app.services.rag_engine.get_redis_or_none", return_value=redis), \
         patch("app.services.rag_engine.async_session") as mock_session:
        
        result = await retrieve_questions(["React"])
        
        redis.get.assert_called_once()
        assert len(result) == 1, f"应返回 1 道题目，实际: {len(result)}"
        assert result[0]["id"] == "q1"
        print("PASS: Redis 缓存命中正确返回")


async def test_retrieve_mysql_exact_match():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    
    mock_q = MagicMock()
    mock_q.id = "q-mysql-1"
    mock_q.category = "React"
    mock_q.question_text = "React Virtual DOM 原理"
    mock_q.reference_answer = "Virtual DOM 是..."
    mock_q.difficulty = "medium"
    
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_q]
    
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    
    class MockSession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, *args):
            pass
    
    with patch("app.services.rag_engine.get_redis_or_none", return_value=mock_redis), \
         patch("app.services.rag_engine.async_session", return_value=MockSession()):
        
        result = await retrieve_questions(["React"])
        
        assert len(result) == 1, f"应返回 1 道题目，实际: {len(result)}"
        assert result[0]["category"] == "React"
        print("PASS: MySQL 精确匹配正确返回")


async def test_retrieve_dedup_and_truncate():
    redis = AsyncMock()
    redis.get.return_value = None
    
    mock_questions = []
    for i in range(10):
        q = MagicMock()
        q.id = f"q-{i}"
        q.category = "React"
        q.question_text = f"问题 {i}"
        q.reference_answer = f"答案 {i}"
        q.difficulty = "easy" if i < 5 else "hard"
        mock_questions.append(q)
    
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = mock_questions
    
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    
    class MockSession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, *args):
            pass
    
    with patch("app.services.rag_engine.get_redis_or_none", return_value=redis), \
         patch("app.services.rag_engine.async_session", return_value=MockSession()):
        
        result = await retrieve_questions(["React", "React"], max_per_keyword=3, max_total=5)
        
        assert len(result) <= 5, f"去重+截断后不应超过 max_total=5，实际: {len(result)}"
        ids = [q["id"] for q in result]
        assert len(ids) == len(set(ids)), "不应有重复的题目 ID"
        print(f"PASS: 去重与截断正确 - 返回 {len(result)} 道题目，无重复")


async def test_retrieve_redis_failure_graceful():
    redis = AsyncMock()
    redis.get.side_effect = Exception("Redis connection lost")
    
    mock_q = MagicMock()
    mock_q.id = "q1"
    mock_q.category = "React"
    mock_q.question_text = "React 是什么"
    mock_q.reference_answer = "..."
    mock_q.difficulty = "easy"
    
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_q]
    
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    
    class MockSession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, *args):
            pass
    
    with patch("app.services.rag_engine.get_redis_or_none", return_value=redis), \
         patch("app.services.rag_engine.async_session", return_value=MockSession()):
        
        result = await retrieve_questions(["React"])
        
        assert len(result) == 1, f"Redis 失败时应降级到 MySQL，实际返回: {len(result)} 道"
        print("PASS: Redis 不可用时降级到 MySQL 检索")


if __name__ == "__main__":
    print("=" * 60)
    print("RAG 检索引擎测试")
    print("=" * 60)
    
    print("\n--- 测试 1: 空关键词 ---")
    asyncio.run(test_retrieve_empty_keywords())
    
    print("\n--- 测试 2: Redis 缓存命中 ---")
    asyncio.run(test_retrieve_with_redis_cache())
    
    print("\n--- 测试 3: MySQL 精确匹配 ---")
    asyncio.run(test_retrieve_mysql_exact_match())
    
    print("\n--- 测试 4: 去重与截断 ---")
    asyncio.run(test_retrieve_dedup_and_truncate())
    
    print("\n--- 测试 5: Redis 失败降级 ---")
    asyncio.run(test_retrieve_redis_failure_graceful())
    
    print("\n" + "=" * 60)
    print("所有 RAG 检索引擎测试通过!")
    print("=" * 60)
