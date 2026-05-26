"""
用户级异步并发控制模块

基于 asyncio.Semaphore 实现同一用户同时只能有一个活跃的 AI 推理请求。
后续请求自动排队等待（最多 30 秒超时），防止 API 额度滥用与服务器过载。

核心机制：
- 每个 user_id 分配一个 asyncio.Semaphore(1)
- acquire(user_id): 获取槽位，若被占用则异步等待（超时 30s → 429）
- release(user_id): 释放槽位，唤醒下一个等待请求
- 应用关闭时自动清理所有信号量
"""

import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# 单个请求最大排队等待时间（秒）
DEFAULT_SLOT_TIMEOUT = 30.0


class SlotTimeoutError(Exception):
    """槽位获取超时——当前用户已有请求在处理中"""
    pass


class UserSlotManager:
    """
    用户槽位管理器。

    用法:
        manager = UserSlotManager()

        # 在请求入口处获取槽位
        await manager.acquire(user_id)  # 可能阻塞等待

        # 请求处理完成后释放
        manager.release(user_id)
    """

    def __init__(self):
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()  # 保护 _semaphores 字典的并发访问

    async def acquire(self, user_id: str, timeout: float = DEFAULT_SLOT_TIMEOUT) -> None:
        """
        获取用户槽位。

        若当前无其他请求在处理，立即返回。
        若已有请求在处理中，阻塞等待直到槽位释放或超时。

        Args:
            user_id: 用户 ID
            timeout: 最大等待秒数

        Raises:
            SlotTimeoutError: 等待超时
        """
        # 线程安全地获取或创建信号量
        async with self._lock:
            if user_id not in self._semaphores:
                self._semaphores[user_id] = asyncio.Semaphore(1)

        sem = self._semaphores[user_id]

        logger.debug(f"用户 {user_id} 尝试获取槽位 (当前可用: {sem._value})")

        try:
            acquired = await asyncio.wait_for(sem.acquire(), timeout=timeout)
            if acquired:
                logger.debug(f"用户 {user_id} 获取槽位成功")
        except asyncio.TimeoutError:
            logger.warning(f"用户 {user_id} 槽位获取超时 ({timeout}s)")
            raise SlotTimeoutError(
                f"当前用户的面试请求正在处理中，请等待不超过 {int(timeout)} 秒后重试"
            )

    def release(self, user_id: str) -> None:
        """
        释放用户槽位，允许下一个等待请求进入。

        幂等操作：对已释放的槽位重复调用无副作用。
        """
        sem = self._semaphores.get(user_id)
        if sem is None:
            return

        # 仅在槽位已被占用时释放（防止多次释放导致计数溢出）
        # _value >= 0 表示有可用槽位，无需释放
        try:
            sem.release()
            logger.debug(f"用户 {user_id} 释放槽位成功 (可用: {sem._value})")
        except ValueError:
            # Semaphore 计数已满（release 过多）
            logger.warning(f"用户 {user_id} 槽位释放时计数已满，忽略")

    @property
    def active_users(self) -> int:
        """当前活跃（占用槽位）的用户数"""
        count = 0
        for sem in self._semaphores.values():
            if sem._value <= 0:
                count += 1
        return count

    async def cleanup(self):
        """清理所有信号量（应用关闭时调用）"""
        async with self._lock:
            for user_id in list(self._semaphores.keys()):
                sem = self._semaphores[user_id]
                # 释放所有等待者（它们会因 CancelledError 而被唤醒）
                while sem.locked():
                    sem.release()
            self._semaphores.clear()
            logger.info(f"用户槽位管理器已清理")


# 全局单例（由 lifespan 初始化）
_slot_manager: UserSlotManager | None = None


def get_slot_manager() -> UserSlotManager:
    """获取全局槽位管理器单例"""
    global _slot_manager
    if _slot_manager is None:
        _slot_manager = UserSlotManager()
    return _slot_manager


async def init_slot_manager():
    """初始化槽位管理器（应用启动时调用）"""
    global _slot_manager
    _slot_manager = UserSlotManager()
    logger.info("用户槽位管理器已初始化")


async def shutdown_slot_manager():
    """关闭槽位管理器（应用关闭时调用）"""
    global _slot_manager
    if _slot_manager:
        await _slot_manager.cleanup()
        _slot_manager = None
        logger.info("用户槽位管理器已关闭")