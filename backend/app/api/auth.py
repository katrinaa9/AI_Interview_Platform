import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import User
from app.schemas.schemas import UserRegister, UserLogin, TokenResponse, UserResponse
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])
oauth2_scheme = HTTPBearer(auto_error=False)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    try:
        result = await db.execute(select(User).where(User.username == body.username))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名已被注册",
            )

        user = User(
            id=str(uuid.uuid4()),
            username=body.username,
            password_hash=hash_password(body.password),
            role="student",
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

        token = create_access_token(data={"sub": user.id, "role": user.role})
        logger.info(f"新用户注册成功: username={body.username}, user_id={user.id}")

        return TokenResponse(
            access_token=token,
            user=UserResponse(
                id=user.id,
                username=user.username,
                role=user.role,
                created_at=user.created_at,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败 | username={body.username} | 错误: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {e}",
        )


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    try:
        result = await db.execute(select(User).where(User.username == body.username))
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"登录失败: 用户不存在 | username={body.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        if not verify_password(body.password, user.password_hash):
            logger.warning(f"登录失败: 密码错误 | username={body.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        token = create_access_token(data={"sub": user.id, "role": user.role})
        logger.info(f"用户登录成功: username={body.username}, user_id={user.id}")

        return TokenResponse(
            access_token=token,
            user=UserResponse(
                id=user.id,
                username=user.username,
                role=user.role,
                created_at=user.created_at,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"登录异常 | username={body.username} | {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录服务暂时不可用，请稍后重试",
        )


async def get_current_user(
    token: HTTPAuthorizationCredentials | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT Token 获取当前登录用户"""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭证，请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )
    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Admin 角色鉴权拦截器——仅允许 role='admin' 的用户访问"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足，仅限管理员访问",
        )
    return current_user