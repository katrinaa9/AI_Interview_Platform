"""
Redis 滑动窗口接口限流中间件（纯 ASGI 实现）

算法：Sliding Window（滑动窗口），基于 Redis Sorted Set。
- 每个请求以时间戳作为 score 插入 sorted set
- 查询当前窗口内的请求数，超限返回 429 Too Many Requests
- Redis 不可用时自动降级放行，不影响业务可用性

分层限流策略：
- /api/interview/chat    → 15次/分钟
- /api/interview/start   → 10次/分钟
- /api/auth/*            → 20次/分钟
- /api/admin/*           → 200次/分钟
- 其他                    → 200次/分钟

使用纯 ASGI 中间件（非 BaseHTTPMiddleware）以避免破坏 FastAPI
的 async generator 依赖注入（如 get_db）。
"""

import time
import logging
from typing import Optional

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# 不需要限流的路径
_EXEMPT_PATHS = frozenset({
    "/health",
    "/health/db",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
})

# 分路径限流配置
_PATH_LIMITS: dict[str, dict[str, int]] = {
    "/api/interview/chat":   {"window": 60, "max": 15},
    "/api/interview/start":  {"window": 60, "max": 10},
    "/api/auth":             {"window": 60, "max": 20},
    "/api/admin":            {"window": 60, "max": 200},
}
_DEFAULT_LIMIT = {"window": 60, "max": 200}

_limiters: dict[str, "SlidingWindowRateLimiter"] = {}


class SlidingWindowRateLimiter:
    """基于 Redis Sorted Set 的滑动窗口限流器"""

    def __init__(self, window: int = 60, max: int = 30):
        self.window = window
        self.max_requests = max

    async def is_allowed(self, key: str) -> tuple[bool, int]:
        """检查 key 是否允许通过。返回 (allowed, remaining)"""
        redis = get_redis()
        if redis is None:
            return True, -1

        now_ts = time.time()
        window_start = now_ts - self.window
        redis_key = f"rl:{key}"

        try:
            async with redis.pipeline(transaction=True) as pipe:
                pipe.zremrangebyscore(redis_key, 0, window_start)
                pipe.zcard(redis_key)
                pipe.zadd(redis_key, {f"{now_ts}:{time.monotonic_ns()}": now_ts})
                pipe.expire(redis_key, self.window + 10)
                _, current_count, _, _ = await pipe.execute()

            current_count = int(current_count)
            remaining = max(0, self.max_requests - current_count)
            allowed = current_count <= self.max_requests

            if not allowed:
                logger.warning(
                    f"限流触发 | key={key} | {current_count}/{self.max_requests}/{self.window}s"
                )
            return allowed, remaining
        except Exception:
            logger.exception(f"Redis 限流异常，降级放行 | key={key}")
            return True, -1


def _resolve_path_limit(path: str) -> SlidingWindowRateLimiter:
    """根据请求路径解析对应的限流器（带缓存复用）"""
    for prefix, config in _PATH_LIMITS.items():
        if path.startswith(prefix):
            if prefix not in _limiters:
                _limiters[prefix] = SlidingWindowRateLimiter(**config)
            return _limiters[prefix]
    if "__default__" not in _limiters:
        _limiters["__default__"] = SlidingWindowRateLimiter(**_DEFAULT_LIMIT)
    return _limiters["__default__"]


class RateLimitMiddleware:
    """纯 ASGI 限流中间件 —— 不破坏 FastAPI 的依赖注入上下文"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # 仅处理 HTTP 请求
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # 跳过免限流路径
        if request.url.path in _EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return

        # 客户端 IP 识别
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.headers.get("X-Real-IP", "")
            or (request.client.host if request.client else "unknown")
        )

        limiter = _resolve_path_limit(request.url.path)
        allowed, remaining = await limiter.is_allowed(client_ip)

        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "请求过于频繁，请稍候再试",
                    "retry_after_seconds": limiter.window,
                },
                headers={
                    "Retry-After": str(limiter.window),
                    "X-RateLimit-Remaining": "0",
                },
            )
            await response(scope, receive, send)
            return

        # 包装 send，在响应头中注入剩余配额
        async def send_wrapper(message):
            if message["type"] == "http.response.start" and remaining >= 0:
                headers = dict(message.get("headers", []))
                headers[b"x-ratelimit-remaining"] = str(remaining).encode()
                message["headers"] = list(headers.items())
            await send(message)

        await self.app(scope, receive, send_wrapper)