"""
认证服务 —— 密码哈希、JWT Token 生成与验证。

密码安全策略：
- 使用 SHA-256 预哈希后再经 bcrypt 处理，彻底消除 bcrypt 72 字节输入限制
- 任意长度的密码均可安全处理，不会因密码长度导致注册/登录失败
- 此方案为业界标准做法（Django、Spring Security 等均采用类似策略）
"""

import hashlib
import logging
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

logger = logging.getLogger(__name__)

# bcrypt 配置
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _pre_hash(password: str) -> str:
    """
    SHA-256 预哈希，将任意长度密码转为固定 64 字符的十六进制字符串。

    此举消除 bcrypt 的 72 字节输入限制，确保任意长度的密码都能正常处理。
    SHA-256 在此处的作用是「标准化输入长度」，不替代 bcrypt 的密钥派生功能。
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """
    对密码进行安全哈希。

    流程：原始密码 → SHA-256 → bcrypt
    返回 bcrypt 哈希字符串，可直接存入数据库。
    """
    pre_hashed = _pre_hash(password)
    return pwd_context.hash(pre_hashed)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码是否匹配。

    流程：原始密码 → SHA-256 → bcrypt.verify()
    """
    try:
        pre_hashed = _pre_hash(plain_password)
        return pwd_context.verify(pre_hashed, hashed_password)
    except Exception as e:
        logger.error(f"密码验证异常: {type(e).__name__}: {e}")
        return False


def create_access_token(
    data: dict, expires_delta: timedelta | None = None
) -> str:
    """生成 JWT 访问令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> dict:
    """解码 JWT Token"""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return {"sub": None}