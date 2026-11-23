from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from healthmisinfo.api.deps import app_setting, require_admin
from healthmisinfo.api.schemas import SettingsUpdate, UserCreate, UserOut, UserUpdate
from healthmisinfo.audit import audit
from healthmisinfo.data.registry import seed_registry
from healthmisinfo.db.models import AppSetting, AuditLog, TrainingRun, User
from healthmisinfo.db.session import get_db
from healthmisinfo.users import UserError, create_user

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

SETTING_KEYS = ("reviews_required", "store_analysis_text", "auto_queue_abstained", "auto_queue_needs_review")


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(select(User).order_by(User.id)).all()


@router.post("/users", response_model=UserOut, status_code=201)
def add_user(body: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    try:
        u = create_user(db, body.email, body.display_name, body.password, body.role)
    except UserError as e:
        raise HTTPException(422, str(e))
    audit(db, "user.create", "user", u.id, actor_id=admin.id, details={"role": u.role})
    db.commit()
    return u


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found")
    changes = body.model_dump(exclude_none=True)
    if u.id == admin.id and (changes.get("role", "admin") != "admin" or changes.get("is_active") is False):
        raise HTTPException(409, "You cannot demote or deactivate yourself")
    if u.role == "admin" and (changes.get("role", "admin") != "admin" or changes.get("is_active") is False):
        active_admins = db.scalar(select(func.count(User.id)).where(User.role == "admin", User.is_active.is_(True)))
        if active_admins <= 1:
            raise HTTPException(409, "Cannot remove the last active administrator")
    for k, v in changes.items():
        setattr(u, k, v)
    audit(db, "user.update", "user", u.id, actor_id=admin.id, details=changes)
    db.commit()
    return u


@router.get("/settings")
def get_settings_(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return {k: app_setting(db, k) for k in SETTING_KEYS}


@router.put("/settings")
def put_settings(body: SettingsUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        row = db.get(AppSetting, k) or AppSetting(key=k)
        row.value = v
        row.updated_by_id = admin.id
        db.add(row)
    audit(db, "settings.update", "app_settings", None, actor_id=admin.id, details=changes)
    db.commit()
    return {k: app_setting(db, k) for k in SETTING_KEYS}


@router.get("/audit-logs")
def audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    entity_type: str | None = Query(None, max_length=64),
    action: str | None = Query(None, max_length=64),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = select(AuditLog)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if action:
        q = q.where(AuditLog.action == action)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    codes = dict(db.execute(select(User.id, User.reviewer_code)).all())
    return {
        "items": [
            {
                "id": r.id,
                "created_at": r.created_at,
                "actor": codes.get(r.actor_id),
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "details": r.details,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/training-runs")
def training_runs(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return {
        "items": [
            {
                "id": r.id,
                "run_tag": r.run_tag,
                "language": r.language,
                "base_model": r.base_model,
                "status": r.status,
                "seed": r.seed,
                "dataset_version": r.dataset_version,
                "data_sha256": r.data_sha256,
                "hyperparameters": r.hyperparameters,
                "test_macro_f1": (r.test_metrics or {}).get("macro_f1"),
                "git_commit": r.git_commit,
                "finished_at": r.finished_at,
                "error": r.error,
            }
            for r in db.scalars(select(TrainingRun).order_by(TrainingRun.created_at.desc()))
        ]
    }


@router.post("/seed-registry", summary="Re-load data/registry/sources.json into the source registry")
def reseed(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    keys = seed_registry(db)
    audit(db, "source.seed", "source_registry", None, actor_id=admin.id, details={"keys": keys})
    db.commit()
    return {"sources": keys}
