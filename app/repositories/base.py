from sqlalchemy.ext.asyncio import AsyncSession
from app.models.postgres import AuditLog
from datetime import datetime

class BaseRepository:
    def __init__(self, db: AsyncSession, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    async def log_audit(self, action, entity, entity_id,
                        user_id=None, old_data=None, new_data=None, ip_address=None):
        log = AuditLog(
            tenant_id=self.tenant_id, user_id=user_id,
            action=action, entity=entity, entity_id=entity_id,
            old_data=old_data, new_data=new_data, ip_address=ip_address,
        )
        self.db.add(log)