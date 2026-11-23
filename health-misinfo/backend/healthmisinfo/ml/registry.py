"""Model registration. A model can only be registered from a completed run directory containing a
saved checkpoint, a tokenizer, calibration.json and evaluation.json with held-out test metrics.
Smoke-test runs and runs on synthetic data are always refused."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from healthmisinfo.audit import audit
from healthmisinfo.db.models import Dataset, ModelVersion, TrainingRun

WEIGHT_FILES = ("model.safetensors", "pytorch_model.bin")


class RegistrationError(ValueError):
    pass


def _weights_file(ckpt: Path) -> Path | None:
    for name in WEIGHT_FILES:
        if (ckpt / name).exists():
            return ckpt / name
    return None


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_run_dir(run_dir: Path) -> dict:
    run_dir = Path(run_dir)
    ckpt = run_dir / "checkpoint"
    problems = []
    if not ckpt.is_dir():
        problems.append("checkpoint/ directory missing")
    elif _weights_file(ckpt) is None:
        problems.append("no model weights in checkpoint/")
    elif not (ckpt / "config.json").exists():
        problems.append("checkpoint/config.json missing")
    elif not any((ckpt / f).exists() for f in ("tokenizer.json", "vocab.txt", "sentencepiece.bpe.model", "tokenizer_config.json")):
        problems.append("tokenizer files missing in checkpoint/")
    for f in ("evaluation.json", "calibration.json", "run_config.json", "model_card.md"):
        if not (run_dir / f).exists():
            problems.append(f"{f} missing")
    if problems:
        raise RegistrationError("; ".join(problems))
    evaluation = json.loads((run_dir / "evaluation.json").read_text(encoding="utf-8"))
    calibration = json.loads((run_dir / "calibration.json").read_text(encoding="utf-8"))
    run_config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    if evaluation.get("smoke_test"):
        raise RegistrationError("Refusing to register a smoke-test run (random-initialised model)")
    if evaluation.get("synthetic_data"):
        raise RegistrationError("Refusing to register a model trained on synthetic fixture data")
    if "test" not in evaluation or "macro_f1" not in evaluation["test"]:
        raise RegistrationError("evaluation.json has no held-out test metrics")
    return {"evaluation": evaluation, "calibration": calibration, "run_config": run_config}


def register_model(db: Session, run_dir: Path, activate: bool = False, user_id: int | None = None) -> ModelVersion:
    run_dir = Path(run_dir).resolve()
    info = validate_run_dir(run_dir)
    ev, cal, rc = info["evaluation"], info["calibration"], info["run_config"]
    tag = ev["run_tag"]
    if db.scalar(select(ModelVersion).where(ModelVersion.version_tag == tag)):
        raise RegistrationError(f"Model {tag} already registered")
    split_ds = db.scalar(select(Dataset).where(Dataset.kind == "split", Dataset.language == ev["language"], Dataset.version == ev["split_version"]))
    cfg = rc["config"]
    run = TrainingRun(
        run_tag=tag,
        language=ev["language"],
        base_model=ev["base_model"],
        dataset_id=split_ds.id if split_ds else None,
        dataset_version=ev["split_version"],
        data_sha256=ev.get("split_data_sha256"),
        hyperparameters={
            k: cfg[k]
            for k in ("epochs", "learning_rate", "batch_size", "max_length", "weight_decay", "warmup_ratio", "class_weighting", "early_stopping_patience")
        },
        seed=cfg["seed"],
        status="completed",
        output_dir=str(run_dir),
        val_metrics=ev["validation"],
        test_metrics=ev["test"],
        environment=rc.get("environment", {}),
        git_commit=rc.get("git_commit"),
        finished_at=datetime.fromisoformat(ev["evaluated_at"]) if ev.get("evaluated_at") else None,
    )
    db.add(run)
    db.flush()
    ckpt = run_dir / "checkpoint"
    mv = ModelVersion(
        version_tag=tag,
        language=ev["language"],
        base_model=ev["base_model"],
        checkpoint_path=str(ckpt),
        checkpoint_sha256=_sha256(_weights_file(ckpt)),
        training_run_id=run.id,
        trained_on_dataset_id=split_ds.id if split_ds else None,
        status="registered",
        is_calibrated=cal.get("method") == "temperature_scaling" and cal.get("temperature") is not None,
        temperature=cal.get("temperature"),
        abstention_threshold=(cal.get("abstention") or {}).get("threshold"),
        val_metrics=ev["validation"],
        test_metrics={**ev["test"], "calibration": ev.get("test_calibration"), "selective": ev.get("test_selective"), "subgroups": ev.get("subgroups")},
        calibration={k: v for k, v in cal.items() if k != "abstention"}
        | {"abstention": {k: v for k, v in (cal.get("abstention") or {}).items() if k != "curve"}},
        model_card_path=str(run_dir / "model_card.md"),
        registered_by_id=user_id,
    )
    db.add(mv)
    db.flush()
    audit(db, "model.register", "model_version", mv.id, actor_id=user_id, details={"tag": tag, "run_dir": str(run_dir)})
    if activate:
        activate_model(db, mv, user_id)
    return mv


def activate_model(db: Session, mv: ModelVersion, user_id: int | None = None) -> ModelVersion:
    if not Path(mv.checkpoint_path).is_dir():
        raise RegistrationError(f"Checkpoint {mv.checkpoint_path} no longer exists")
    for other in db.scalars(select(ModelVersion).where(ModelVersion.language == mv.language, ModelVersion.status == "active")):
        if other.id != mv.id:
            other.status = "registered"
    mv.status = "active"
    mv.activated_at = datetime.now(UTC)
    audit(db, "model.activate", "model_version", mv.id, actor_id=user_id, details={"tag": mv.version_tag})
    db.flush()
    return mv
