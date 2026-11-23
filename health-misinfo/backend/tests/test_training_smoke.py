"""End-to-end PIPELINE smoke test: synthetic split -> tiny RANDOM model -> calibration -> test eval ->
model card -> registration refused -> inference code path.

Nothing here is a research result: the network is randomly initialised and the data is synthetic.
"""

import json

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

from healthmisinfo.data.synthetic import make_synthetic_split  # noqa: E402
from healthmisinfo.db.models import ModelVersion  # noqa: E402
from healthmisinfo.inference.service import inference_service  # noqa: E402
from healthmisinfo.ml.registry import RegistrationError, register_model  # noqa: E402
from healthmisinfo.ml.train import SplitIntegrityError, TrainConfig, train_and_evaluate  # noqa: E402

from .conftest import FIXTURES  # noqa: E402


@pytest.fixture(scope="module")
def smoke_run(tmp_path_factory):
    root = tmp_path_factory.mktemp("smoke")
    make_synthetic_split(FIXTURES / "synthetic_claims_en.csv", "en", root / "split", seed=5)
    cfg = TrainConfig(
        language="en",
        split_dir=str(root / "split"),
        output_root=str(root / "models"),
        seed=5,
        epochs=2,
        batch_size=8,
        learning_rate=5e-3,
        max_length=32,
        smoke_test_tiny_random=True,
        allow_synthetic=True,
        run_tag="en-smoke-test",
    )
    return root, train_and_evaluate(cfg)


def test_refuses_synthetic_split_without_smoke_flags(smoke_run):
    root, _ = smoke_run
    with pytest.raises(SplitIntegrityError, match="synthetic"):
        train_and_evaluate(TrainConfig(language="en", split_dir=str(root / "split"), output_root=str(root / "x")))


def test_refuses_tampered_split(smoke_run, tmp_path):
    import shutil

    root, _ = smoke_run
    shutil.copytree(root / "split", tmp_path / "split")
    with (tmp_path / "split" / "test.csv").open("a", encoding="utf-8") as f:
        f.write("tampered\n")
    with pytest.raises(SplitIntegrityError, match="sha256"):
        train_and_evaluate(
            TrainConfig(language="en", split_dir=str(tmp_path / "split"), output_root=str(tmp_path / "m"), smoke_test_tiny_random=True, allow_synthetic=True)
        )


def test_artifacts_written_and_flagged(smoke_run):
    _, out = smoke_run
    from pathlib import Path

    run_dir = Path(out["run_dir"])
    for f in (
        "checkpoint/config.json",
        "evaluation.json",
        "calibration.json",
        "run_config.json",
        "model_card.md",
        "predictions_test.csv",
        "confusion_matrix_test.png",
    ):
        assert (run_dir / f).exists(), f
    ev = json.loads((run_dir / "evaluation.json").read_text())
    assert ev["smoke_test"] is True and ev["synthetic_data"] is True
    assert set(ev["test"]["per_class"]) == {"SUPPORTED", "MISLEADING", "NEEDS_REVIEW"}
    assert sum(map(sum, ev["test"]["confusion_matrix"]["matrix"])) == ev["test"]["n"]
    cal = json.loads((run_dir / "calibration.json").read_text())
    assert cal["fitted_on"] == "validation" and cal["temperature"] > 0
    assert "PIPELINE SMOKE TEST" in (run_dir / "model_card.md").read_text()


def test_registration_refused_for_smoke_runs(smoke_run, db):
    _, out = smoke_run
    with pytest.raises(RegistrationError, match="smoke-test"):
        register_model(db, out["run_dir"])


def test_inference_code_path_with_smoke_checkpoint(smoke_run, client, auth, db):
    """Exercise the serving code path. The DB row is inserted directly (registration is refused for
    smoke runs by design) and exists only in this throw-away test database."""
    _, out = smoke_run
    cal = out["calibration"]
    mv = ModelVersion(
        version_tag="TEST-ONLY-smoke",
        language="en",
        base_model="tiny-random",
        status="active",
        checkpoint_path=f"{out['run_dir']}/checkpoint",
        is_calibrated=True,
        temperature=cal["temperature"],
        abstention_threshold=0.99,
        test_metrics={},
    )
    db.add(mv)
    db.commit()
    body = client.post("/api/v1/analyze", json={"text": "regular handwashing with soap lowers the spread of measles"}, headers=auth["res"]).json()
    assert body["status"] == "completed" and body["model"]["version_tag"] == "TEST-ONLY-smoke"
    p = body["prediction"]
    assert p["is_calibrated"] is True and abs(sum(p["calibrated_probabilities"].values()) - 1) < 1e-4
    assert abs(sum(p["raw_scores"].values()) - 1) < 1e-4
    assert p["abstained"] is True and p["display_label"] == "NEEDS_REVIEW"  # threshold 0.99 forces abstention
    assert body["review_status"] == "pending"
    assert body["explanation"]["method"] == "leave_one_word_out" and body["explanation"]["tokens"]
    status = inference_service.slot_status(db, "en")
    assert status["state"] == "ready"
