import logging
from app.models.database import async_session
from app.models.models import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    operator: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: str | None = None,
    status: str = "success",
    ip_address: str | None = None,
):
    try:
        async with async_session() as db:
            log = AuditLog(
                operator=operator,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                status=status,
                ip_address=ip_address,
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        logger.warning(f"审计日志写入失败: {e}")
