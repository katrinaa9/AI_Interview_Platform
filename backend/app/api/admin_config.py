"""
面试配置管理 API —— 管理员读取/编辑 interview_config.yaml
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import User
from app.api.auth import get_current_user
from app.services.interview_config import (
    get_config,
    update_config_file,
    get_config_file_path,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/config", tags=["管理-面试配置"])


class ConfigUpdateRequest(BaseModel):
    content: str  # YAML 文本内容


class ConfigResponse(BaseModel):
    path: str
    content: str
    max_turns: int
    phases: list[dict]
    message: str = "ok"


async def _require_admin(user: User) -> None:
    """确保当前用户是管理员"""
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="仅管理员可访问面试配置管理",
        )


@router.get("", response_model=ConfigResponse)
async def get_interview_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """读取当前的面试配置（YAML 原始内容 + 解析后的结构化数据）"""
    await _require_admin(current_user)

    config = get_config(force_reload=True)
    config_path = get_config_file_path()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
    except FileNotFoundError:
        raw_content = "# 配置文件未找到"

    return ConfigResponse(
        path=config_path,
        content=raw_content,
        max_turns=config.get("max_turns", 15),
        phases=config.get("phases", []),
        message="ok",
    )


@router.put("", response_model=dict)
async def update_interview_config(
    body: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新面试配置（写入 YAML 文件）"""
    await _require_admin(current_user)

    success, message = update_config_file(body.content)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    logger.info(f"管理员 {current_user.username} 更新了面试配置")
    return {"success": True, "message": message}


@router.get("/phases", response_model=dict)
async def get_phases_summary(
    current_user: User = Depends(get_current_user),
):
    """获取阶段配置摘要（无需管理员权限，供前端展示面试流程）"""
    config = get_config()
    phases = config.get("phases", [])
    return {
        "max_turns": config.get("max_turns", 15),
        "phases": [
            {
                "name": p.get("name", ""),
                "rounds": p.get("rounds", []),
                "description": p.get("description", ""),
            }
            for p in phases
        ],
    }