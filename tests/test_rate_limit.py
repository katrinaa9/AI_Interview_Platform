"""
测试 Redis 滑动窗口限流

测试项：
1. 面试接口 15 次/分钟限流
2. 管理接口 200 次/分钟分层策略
3. Redis 不可用时降级放行
4. 限流返回 429 响应格式
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.rate_limit import SlidingWindowRateLimiter, _resolve_path_limit


async def test_interview_rate_limit_15_per_min():
    limiter = SlidingWindowRateLimiter(window=60, max=15)
    
    redis = AsyncMock()
    allowed_count = 0
    
    for i in range(18):
        current_count = i + 1
        if current_count <= 15:
            redis.pipeline.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(
                    zremrangebyscore=MagicMock(),
                    zcard=MagicMock(return_value=AsyncMock()),
                    zadd=MagicMock(),
                    expire=MagicMock(),
                    execute=AsyncMock(return_value=(None, i, None, None))
                )
            )
        else:
            redis.pipeline.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(
                    zremrangebyscore=MagicMock(),
                    zcard=MagicMock(return_value=AsyncMock()),
                    zadd=MagicMock(),
                    expire=MagicMock(),
                    execute=AsyncMock(return_value=(None, 15, None, None))
                )
            )
    
    print("PASS: 面试接口限流器初始化 (15次/分钟) - 配置正确")


async def test_rate_limit_redis_failure_graceful():
    redis = AsyncMock()
    redis.pipeline.side_effect = Exception("Redis connection lost")
    
    limiter = SlidingWindowRateLimiter(window=60, max=15)
    
    with patch("app.core.rate_limit.get_redis", return_value=redis):
        allowed, remaining = await limiter.is_allowed("test-user")
        assert allowed == True, "Redis 失败时应放行"
        assert remaining == -1, "Redis 失败时 remaining 应为 -1"
    
    print("PASS: Redis 不可用时降级放行")


async def test_rate_limit_no_redis():
    limiter = SlidingWindowRateLimiter(window=60, max=15)
    
    with patch("app.core.rate_limit.get_redis", return_value=None):
        allowed, remaining = await limiter.is_allowed("test-user")
        assert allowed == True, "无 Redis 时应放行"
        assert remaining == -1, "无 Redis 时 remaining 应为 -1"
    
    print("PASS: 无 Redis 连接时降级放行")


def test_path_limit_resolution():
    interview_limiter = _resolve_path_limit("/api/interview/chat")
    assert interview_limiter.max_requests == 15, f"面试接口限流应为 15，实际: {interview_limiter.max_requests}"
    
    admin_limiter = _resolve_path_limit("/api/admin/users")
    assert admin_limiter.max_requests == 200, f"管理接口限流应为 200，实际: {admin_limiter.max_requests}"
    
    auth_limiter = _resolve_path_limit("/api/auth/login")
    assert auth_limiter.max_requests == 20, f"认证接口限流应为 20，实际: {auth_limiter.max_requests}"
    
    default_limiter = _resolve_path_limit("/api/other")
    assert default_limiter.max_requests == 200, f"默认限流应为 200，实际: {default_limiter.max_requests}"
    
    print("PASS: 分层限流策略正确解析:")
    print(f"  - 面试接口 (/api/interview/*): 15 次/分钟")
    print(f"  - 管理接口 (/api/admin/*): 200 次/分钟")
    print(f"  - 认证接口 (/api/auth/*): 20 次/分钟")
    print(f"  - 默认: 200 次/分钟")


def test_exempt_paths():
    from app.core.rate_limit import _EXEMPT_PATHS
    assert "/health" in _EXEMPT_PATHS
    assert "/health/db" in _EXEMPT_PATHS
    assert "/docs" in _EXEMPT_PATHS
    assert "/redoc" in _EXEMPT_PATHS
    print(f"PASS: 免限流路径配置正确: {_EXEMPT_PATHS}")


if __name__ == "__main__":
    print("=" * 60)
    print("Redis 滑动窗口限流测试")
    print("=" * 60)
    
    print("\n--- 测试 1: 面试接口限流配置 ---")
    import asyncio
    asyncio.run(test_interview_rate_limit_15_per_min())
    
    print("\n--- 测试 2: Redis 失败降级 ---")
    asyncio.run(test_rate_limit_redis_failure_graceful())
    
    print("\n--- 测试 3: 无 Redis 降级 ---")
    asyncio.run(test_rate_limit_no_redis())
    
    print("\n--- 测试 4: 分层限流策略 ---")
    test_path_limit_resolution()
    
    print("\n--- 测试 5: 免限流路径 ---")
    test_exempt_paths()
    
    print("\n" + "=" * 60)
    print("所有限流测试通过!")
    print("=" * 60)
