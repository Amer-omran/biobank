from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from healthmisinfo.api.deps import get_viewer, require_admin
from healthmisinfo.db.models import ModelVersion, TrainingRun, User
from healthmisinfo.db.session import get_db
from healthmisinfo.inference.service import SLOTS, inference_service, runtime_available
from healthmisinfo.ml.registry import RegistrationError, activate_model

router = APIRouter(prefix="/api/v1", tags=["models"])


def _mv_dict(mv: ModelVersion) -> dict:
    t = mv.test_metrics or {}
    return {
        "id": mv.id,
        "version_tag": mv.version_tag,
        "language": mv.language,
        "base_model": mv.base_model,
        "status": mv.status,
        "is_calibrated": mv.is_calibrated,
        "temperature": mv.temperature,
        "abstention_threshold": mv.abstention_threshold,
        "test_metrics": {k: t.get(k) for k in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "n")},
        "created_at": mv.created_at,
        "activated_at": mv.activated_at,
        "training_run_id": mv.training_run_id,
        "checkpoint_sha256": mv.checkpoint_sha256,
    }


@router.get("/models", summary="Model slots, their state (ready / not_trained / ...) and registered versions")
def list_models(db: Session = Depends(get_db), _: User = Depends(get_viewer)):
    versions = db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all()
    return {
        "runtime_available": runtime_available(),
        "slots": [inference_service.slot_status(db, lang) for lang in SLOTS],
        "versions": [_mv_dict(v) for v in versions],
        "note": "A model appears here only after a real fine-tuning run produced a checkpoint and a held-out "
        "test evaluation, and an administrator registered it.",
    }


@router.get("/models/{model_id}", summary="Full metrics of a registered model version")
def get_model(model_id: int, db: Session = Depends(get_db), _: User = Depends(get_viewer)):
    mv = db.get(ModelVersion, model_id)
    if mv is None:
        raise HTTPException(404, "Model version not found")
    run = db.get(TrainingRun, mv.training_run_id) if mv.training_run_id else None
    card = None
    if mv.model_card_path:
        try:
            with open(mv.model_card_path, encoding="utf-8") as f:
                card = f.read()
        except OSError:
            card = None
    return {
        **_mv_dict(mv),
        "val_metrics": mv.val_metrics,
        "test_metrics_full": mv.test_metrics,
        "calibration": mv.calibration,
        "training_run": None
        if run is None
        else {
            "run_tag": run.run_tag,
            "seed": run.seed,
            "hyperparameters": run.hyperparameters,
            "dataset_version": run.dataset_version,
            "data_sha256": run.data_sha256,
            "environment": run.environment,
            "git_commit": run.git_commit,
        },
        "model_card_markdown": card,
    }


@router.post("/models/{model_id}/activate", summary="Make this version the active model for its language (admin)")
def activate(model_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    mv = db.get(ModelVersion, model_id)
    if mv is None:
        raise HTTPException(404, "Model version not found")
    try:
        activate_model(db, mv, user.id)
    except RegistrationError as e:
        raise HTTPException(409, str(e))
    db.commit()
    return _mv_dict(mv)
