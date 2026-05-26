import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import AuditLog
from app.api.auth import require_admin
from app.schemas.schemas import AuditLogResponse, AuditLogListResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/audit",
    tags=["管理-操作日志"],
    dependencies=[Depends(require_admin)],
)


@router.get("/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None, description="按操作类型筛选"),
    resource_type: str | None = Query(default=None, description="按资源类型筛选"),
    operator: str | None = Query(default=None, description="按操作人筛选"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog)

    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if operator:
        stmt = stmt.where(AuditLog.operator.contains(operator))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                operator=log.operator,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details,
                status=log.status,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/logs/actions")
async def get_action_types(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    actions = [row[0] for row in result.all()]
    return {"actions": actions}


@router.get("/logs/resource-types")
async def get_resource_types(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuditLog.resource_type).distinct().order_by(AuditLog.resource_type)
    )
    types = [row[0] for row in result.all()]
    return {"resource_types": types}
