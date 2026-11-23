"""Append-only audit trail helper."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from healthmisinfo.db.models import AuditLog
from healthmisinfo.security import hash_ip


def audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    actor_id: int | None = None,
    details: dict | None = None,
    ip: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        details=details or {},
        ip_hash=hash_ip(ip),
    )
    db.add(entry)
    return entry
