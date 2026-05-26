import logging
from typing import Optional
import redis.asyncio as aioredis
from app.config import settings

logger = logging.getLogger(__name__)

# 全局 Redis 连接池（单例）
_pool: Optional[aioredis.ConnectionPool] = None
_client: Optional[aioredis.Redis] = None


async def init_redis() -> aioredis.Redis:
    """初始化 Redis 连接池（应用启动时调用一次）"""
    global _pool, _client
    if _client is not None:
        return _client

    try:
        _pool = aioredis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            max_connections=20,
            decode_responses=True,
        )
        _client = aioredis.Redis(connection_pool=_pool)
        # 验证连接
        await _client.ping()
        logger.info(f"Redis 连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    except Exception as e:
        logger.warning(f"Redis 连接失败，将降级运行: {e}")
        # 创建空客户端，后续调用会优雅降级
        _client = None
        _pool = None

    return _client


async def close_redis():
    """关闭 Redis 连接（应用关闭时调用）"""
    global _client, _pool
    if _client:
        await _client.close()
        _client = None
    if _pool:
        await _pool.disconnect()
        _pool = None
    logger.info("Redis 连接已关闭")


def get_redis() -> Optional[aioredis.Redis]:
    """获取 Redis 客户端（依赖注入），若未连接则返回 None"""
    return _client


async def get_redis_or_none() -> Optional[aioredis.Redis]:
    """异步获取 Redis 客户端"""
    if _client is None:
        try:
            await init_redis()
        except Exception:
            pass
    return _client