"""
测试审计日志记录

测试项：
1. 管理后台写操作（上传/删除/编辑）均写入 audit_logs
2. 写入失败不阻断业务流程
3. 日志字段完整性
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.audit_service import log_action


async def test_log_action_success():
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()
    
    class MockSession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, *args):
            pass
    
    with patch("app.services.audit_service.async_session", return_value=MockSession()):
        await log_action(
            operator="admin_user",
            action="upload",
            resource_type="document",
            resource_id="doc-123",
            details="上传文档: test.pdf",
            status="success",
            ip_address="192.168.1.100",
        )
        
        assert mock_db.add.called, "应调用 db.add 写入日志"
        assert mock_db.commit.called, "应调用 db.commit 提交"
        print("PASS: 审计日志写入成功")


async def test_log_action_failure_does_not_block():
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock(side_effect=Exception("Database connection lost"))
    
    class MockSession:
        async def __aenter__(self):
            return mock_db
        async def __aexit__(self, *args):
            pass
    
    with patch("app.services.audit_service.async_session", return_value=MockSession()):
        await log_action(
            operator="admin_user",
            action="delete",
            resource_type="document",
            resource_id="doc-456",
            details="删除文档",
        )
        
        print("PASS: 审计日志写入失败不抛出异常（业务不受影响）")


async def test_log_action_all_actions():
    actions_to_test = [
        ("upload", "document", "上传文档"),
        ("delete", "document", "删除文档"),
        ("update", "chunk", "更新知识片段"),
        ("create", "question", "创建题目"),
        ("save", "prompt_version", "保存提示词版本"),
        ("rollback", "prompt_version", "回滚提示词版本"),
    ]
    
    for action, resource_type, details in actions_to_test:
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        
        class MockSession:
            async def __aenter__(self):
                return mock_db
            async def __aexit__(self, *args):
                pass
        
        with patch("app.services.audit_service.async_session", return_value=MockSession()):
            await log_action(
                operator="test_admin",
                action=action,
                resource_type=resource_type,
                details=details,
            )
            assert mock_db.add.called, f"{action} 操作应写入日志"
    
    print(f"PASS: 所有 {len(actions_to_test)} 种操作类型均正确记录审计日志:")
    for action, resource_type, details in actions_to_test:
        print(f"  - {action} ({resource_type}): {details}")


def test_log_action_fields():
    from app.models.models import AuditLog
    
    log = AuditLog(
        operator="admin",
        action="upload",
        resource_type="document",
        resource_id="doc-123",
        details="上传了 test.pdf",
        status="success",
        ip_address="192.168.1.100",
    )
    
    assert log.operator == "admin"
    assert log.action == "upload"
    assert log.resource_type == "document"
    assert log.resource_id == "doc-123"
    assert log.status == "success"
    assert log.ip_address == "192.168.1.100"
    print("PASS: 审计日志字段完整性验证通过")


if __name__ == "__main__":
    print("=" * 60)
    print("审计日志记录测试")
    print("=" * 60)
    
    print("\n--- 测试 1: 日志写入成功 ---")
    asyncio.run(test_log_action_success())
    
    print("\n--- 测试 2: 写入失败不阻断业务 ---")
    asyncio.run(test_log_action_failure_does_not_block())
    
    print("\n--- 测试 3: 所有操作类型 ---")
    asyncio.run(test_log_action_all_actions())
    
    print("\n--- 测试 4: 字段完整性 ---")
    test_log_action_fields()
    
    print("\n" + "=" * 60)
    print("所有审计日志测试通过!")
    print("=" * 60)
