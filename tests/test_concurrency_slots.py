"""
测试用户并发槽位控制

测试项：
1. 同一用户并发请求排队等待
2. 30 秒超时抛出 SlotTimeoutError
3. finally 确保槽位释放
4. 幂等释放（重复释放不报错）
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.core.concurrency import UserSlotManager, SlotTimeoutError


async def test_acquire_and_release():
    manager = UserSlotManager()
    
    await manager.acquire("user-1")
    assert manager.active_users == 1, "获取槽位后活跃用户应为 1"
    
    manager.release("user-1")
    assert manager.active_users == 0, "释放槽位后活跃用户应为 0"
    print("PASS: 槽位获取与释放正常")


async def test_concurrent_requests_queue():
    manager = UserSlotManager()
    execution_order = []
    
    async def request(user_id, delay):
        await manager.acquire(user_id)
        try:
            execution_order.append(f"{user_id}_start")
            await asyncio.sleep(delay)
            execution_order.append(f"{user_id}_end")
        finally:
            manager.release(user_id)
    
    task1 = asyncio.create_task(request("user-1", 0.1))
    await asyncio.sleep(0.05)
    task2 = asyncio.create_task(request("user-1", 0.1))
    
    await asyncio.gather(task1, task2)
    
    assert execution_order == ["user-1_start", "user-1_end", "user-1_start", "user-1_end"], \
        f"执行顺序错误: {execution_order}"
    print(f"PASS: 并发请求正确排队 - 顺序: {execution_order}")


async def test_timeout_rejection():
    manager = UserSlotManager()
    
    await manager.acquire("user-2")
    
    try:
        await manager.acquire("user-2", timeout=0.5)
        assert False, "应该超时抛出 SlotTimeoutError"
    except SlotTimeoutError as e:
        assert "正在处理中" in str(e), f"错误消息应包含提示信息，实际: {e}"
    finally:
        manager.release("user-2")
    
    print("PASS: 超时请求正确拒绝 (SlotTimeoutError)")


async def test_idempotent_release():
    manager = UserSlotManager()
    
    await manager.acquire("user-3")
    manager.release("user-3")
    manager.release("user-3")
    manager.release("user-3")
    
    print("PASS: 重复释放不报错（幂等性）")


async def test_finally_slot_release():
    manager = UserSlotManager()
    
    try:
        await manager.acquire("user-4")
        raise ValueError("模拟业务异常")
    except ValueError:
        pass
    finally:
        manager.release("user-4")
    
    assert manager.active_users == 0, "异常后槽位应正确释放"
    print("PASS: finally 确保槽位释放（即使发生异常）")


async def test_multiple_users_independent():
    manager = UserSlotManager()
    
    await manager.acquire("user-A")
    await manager.acquire("user-B")
    
    assert manager.active_users == 2, "两个不同用户应各有独立槽位"
    
    manager.release("user-A")
    assert manager.active_users == 1, "释放 user-A 不应影响 user-B"
    
    manager.release("user-B")
    assert manager.active_users == 0, "全部释放后应为 0"
    
    print("PASS: 多用户槽位相互独立")


if __name__ == "__main__":
    print("=" * 60)
    print("用户并发槽位控制测试")
    print("=" * 60)
    
    async def run_all():
        print("\n--- 测试 1: 槽位获取与释放 ---")
        await test_acquire_and_release()
        
        print("\n--- 测试 2: 并发请求排队 ---")
        await test_concurrent_requests_queue()
        
        print("\n--- 测试 3: 超时拒绝 ---")
        await test_timeout_rejection()
        
        print("\n--- 测试 4: 幂等释放 ---")
        await test_idempotent_release()
        
        print("\n--- 测试 5: finally 确保释放 ---")
        await test_finally_slot_release()
        
        print("\n--- 测试 6: 多用户独立槽位 ---")
        await test_multiple_users_independent()
    
    asyncio.run(run_all())
    
    print("\n" + "=" * 60)
    print("所有并发槽位控制测试通过!")
    print("=" * 60)
