"""
测试 JWT 认证与 RBAC

测试项：
1. 注册/登录签发 Token
2. Token 过期拒绝访问
3. student 角色访问 admin 接口返回 403
4. 密码哈希与验证
5. Token 解码与 payload 提取
"""

import sys
import asyncio
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import timedelta
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)


# ===== 测试 1: 密码哈希与验证 =====

def test_hash_and_verify():
    password = "my_secure_password_123"
    hashed = hash_password(password)
    
    assert hashed != password, "哈希值不应等于原密码"
    assert hashed.startswith("$2"), "应使用 bcrypt 哈希"
    assert verify_password(password, hashed), "正确密码应验证通过"
    assert not verify_password("wrong_password", hashed), "错误密码应验证失败"
    print(f"PASS: 密码哈希与验证成功 (哈希前 20 字符: {hashed[:20]}...)")


def test_long_password():
    long_password = "a" * 200
    hashed = hash_password(long_password)
    assert verify_password(long_password, hashed), "超长密码应正常处理"
    print("PASS: 超长密码（200 字符）正常处理")


# ===== 测试 2: Token 生成与解码 =====

@patch("app.services.auth_service.settings")
def test_token_create_and_decode(mock_settings):
    mock_settings.JWT_SECRET = "test-secret"
    mock_settings.JWT_ALGORITHM = "HS256"
    mock_settings.JWT_EXPIRE_MINUTES = 60
    
    token = create_access_token(data={"sub": "user-123", "role": "student"})
    assert len(token) > 20, "Token 应有合理长度"
    
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123", "sub 字段应匹配"
    assert payload["role"] == "student", "role 字段应匹配"
    assert "exp" in payload, "应包含过期时间"
    print(f"PASS: Token 生成与解码成功 (payload: {payload})")


@patch("app.services.auth_service.settings")
def test_token_wrong_secret(mock_settings):
    mock_settings.JWT_SECRET = "test-secret"
    mock_settings.JWT_ALGORITHM = "HS256"
    mock_settings.JWT_EXPIRE_MINUTES = 60
    
    token = create_access_token(data={"sub": "user-123"})
    
    with patch("app.services.auth_service.settings") as mock_settings2:
        mock_settings2.JWT_SECRET = "wrong-secret"
        mock_settings2.JWT_ALGORITHM = "HS256"
        mock_settings2.JWT_EXPIRE_MINUTES = 60
        
        payload = decode_access_token(token)
        assert payload["sub"] is None, "错误密钥应返回 None sub"
    print("PASS: 错误密钥解码返回 None")


@patch("app.services.auth_service.settings")
def test_token_expired(mock_settings):
    mock_settings.JWT_SECRET = "test-secret"
    mock_settings.JWT_ALGORITHM = "HS256"
    mock_settings.JWT_EXPIRE_MINUTES = 60
    
    token = create_access_token(
        data={"sub": "user-123"},
        expires_delta=timedelta(seconds=-1)
    )
    
    payload = decode_access_token(token)
    assert payload["sub"] is None, "过期 Token 应返回 None sub"
    print("PASS: 过期 Token 正确拒绝")


# ===== 测试 3: RBAC 权限控制 =====

def test_rbac_student_blocked_from_admin():
    """student 角色访问 admin 接口应返回 403"""
    mock_user = MagicMock()
    mock_user.role = "student"
    mock_user.username = "test_student"
    mock_user.id = "user-123"
    
    from app.api.auth import require_admin
    
    try:
        async def test():
            await require_admin(mock_user)
        
        asyncio.get_event_loop().run_until_complete(test())
        assert False, "应该抛出 403"
    except HTTPException as e:
        assert e.status_code == 403, f"应返回 403，实际: {e.status_code}"
        print("PASS: student 角色访问 admin 接口返回 403")


def test_rbac_admin_allowed():
    """admin 角色访问 admin 接口应允许"""
    mock_user = MagicMock()
    mock_user.role = "admin"
    mock_user.username = "test_admin"
    mock_user.id = "user-456"
    
    import asyncio
    from app.api.auth import require_admin
    
    async def test():
        result = await require_admin(mock_user)
        assert result == mock_user, "应返回用户对象"
    
    asyncio.get_event_loop().run_until_complete(test())
    print("PASS: admin 角色访问 admin 接口允许")


if __name__ == "__main__":
    print("=" * 60)
    print("JWT 认证与 RBAC 测试")
    print("=" * 60)
    
    print("\n--- 测试 1: 密码哈希与验证 ---")
    test_hash_and_verify()
    test_long_password()
    
    print("\n--- 测试 2: Token 生成与解码 ---")
    test_token_create_and_decode()
    test_token_wrong_secret()
    test_token_expired()
    
    print("\n--- 测试 3: RBAC 权限控制 ---")
    test_rbac_student_blocked_from_admin()
    test_rbac_admin_allowed()
    
    print("\n" + "=" * 60)
    print("所有 JWT 认证与 RBAC 测试通过!")
    print("=" * 60)
