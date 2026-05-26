import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import PromptVersion, PromptTemplate
from app.api.auth import require_admin
from app.schemas.schemas import (
    PromptVersionResponse, PromptVersionListResponse, PromptSaveRequest,
    PromptTemplateResponse, PromptTemplateCreateRequest, PromptTemplateUpdateRequest,
)
from app.services.prompt_service import (
    get_active_prompt, save_prompt_version, rollback_to_version,
)
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/prompt",
    tags=["管理-提示词配置"],
    dependencies=[Depends(require_admin)],
)


def _version_to_response(v: PromptVersion) -> PromptVersionResponse:
    return PromptVersionResponse(
        id=v.id,
        version_number=v.version_number,
        content=v.content,
        description=v.description,
        is_active=v.is_active,
        created_by=v.created_by,
        created_at=v.created_at,
    )


def _template_to_response(t: PromptTemplate) -> PromptTemplateResponse:
    return PromptTemplateResponse(
        id=t.id,
        name=t.name,
        description=t.description,
        content=t.content,
        is_builtin=t.is_builtin,
        created_by=t.created_by,
        created_at=t.created_at,
    )


@router.get("/active")
async def get_active_prompt_content():
    content = await get_active_prompt()
    return {
        "content": content or "",
        "has_custom": content is not None,
    }


@router.get("/versions", response_model=PromptVersionListResponse)
async def list_prompt_versions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PromptVersion).order_by(PromptVersion.version_number.desc())
    )
    versions = result.scalars().all()
    return PromptVersionListResponse(
        items=[_version_to_response(v) for v in versions],
        total=len(versions),
    )


@router.post("/save", response_model=PromptVersionResponse, status_code=status.HTTP_201_CREATED)
async def save_prompt(
    body: PromptSaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    if len(body.content) > 10000:
        raise HTTPException(status_code=400, detail="提示词内容过长，建议控制在 10000 字符以内")

    version = await save_prompt_version(
        content=body.content,
        description=body.description,
        created_by=current_user.username,
    )

    await log_action(
        operator=current_user.username,
        action="save",
        resource_type="prompt_version",
        resource_id=version.id,
        details=f"保存提示词版本 {version.version_number}: {body.description or ''}",
    )

    return _version_to_response(version)


@router.post("/rollback/{version_id}", response_model=PromptVersionResponse)
async def rollback_prompt(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    success = await rollback_to_version(version_id, current_user.username)
    if not success:
        raise HTTPException(status_code=404, detail="版本不存在")

    result = await db.execute(
        select(PromptVersion).where(PromptVersion.is_active == True).order_by(PromptVersion.version_number.desc())
    )
    active = result.scalar_one_or_none()

    await log_action(
        operator=current_user.username,
        action="rollback",
        resource_type="prompt_version",
        resource_id=version_id,
        details="回滚提示词版本",
    )

    return _version_to_response(active)


@router.post("/test")
async def test_prompt(
    body: PromptSaveRequest,
    current_user=Depends(require_admin),
):
    test_keywords = ["React", "TypeScript", "Node.js"]
    test_turn = 3

    system_prompt = body.content
    if "{keywords}" in system_prompt:
        system_prompt = system_prompt.replace("{keywords}", "、".join(test_keywords))
    if "{turn}" in system_prompt:
        system_prompt = system_prompt.replace("{turn}", str(test_turn))
    if "{max_turns}" in system_prompt:
        system_prompt = system_prompt.replace("{max_turns}", "15")

    return {
        "preview": system_prompt[:2000],
        "char_count": len(body.content),
        "test_keywords": test_keywords,
        "test_turn": test_turn,
    }


@router.get("/templates", response_model=list[PromptTemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PromptTemplate).order_by(PromptTemplate.is_builtin.desc(), PromptTemplate.created_at.desc())
    )
    templates = result.scalars().all()
    return [_template_to_response(t) for t in templates]


@router.post("/templates", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    body: PromptTemplateCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    template = PromptTemplate(
        name=body.name,
        description=body.description,
        content=body.content,
        is_builtin=False,
        created_by=current_user.username,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    await db.commit()

    await log_action(
        operator=current_user.username,
        action="create",
        resource_type="prompt_template",
        resource_id=template.id,
        details=f"创建提示词模板: {body.name}",
    )

    return _template_to_response(template)


@router.put("/templates/{template_id}", response_model=PromptTemplateResponse)
async def update_template(
    template_id: str,
    body: PromptTemplateUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    template = await db.get(PromptTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    if template.is_builtin:
        raise HTTPException(status_code=403, detail="内置模板不可编辑")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)

    await db.flush()
    await db.refresh(template)
    await db.commit()

    await log_action(
        operator=current_user.username,
        action="update",
        resource_type="prompt_template",
        resource_id=template_id,
        details=f"更新提示词模板: {template.name}",
    )

    return _template_to_response(template)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    template = await db.get(PromptTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    if template.is_builtin:
        raise HTTPException(status_code=403, detail="内置模板不可删除")

    await db.delete(template)
    await db.flush()
    await db.commit()

    await log_action(
        operator=current_user.username,
        action="delete",
        resource_type="prompt_template",
        resource_id=template_id,
        details=f"删除提示词模板: {template.name}",
    )

    return {"message": "模板已删除", "id": template_id}


@router.post("/templates/{template_id}/apply", response_model=PromptVersionResponse)
async def apply_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    template = await db.get(PromptTemplate, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    version = await save_prompt_version(
        content=template.content,
        description=f"应用模板: {template.name}",
        created_by=current_user.username,
    )

    await log_action(
        operator=current_user.username,
        action="apply_template",
        resource_type="prompt_version",
        resource_id=version.id,
        details=f"应用提示词模板: {template.name}",
    )

    return _version_to_response(version)
