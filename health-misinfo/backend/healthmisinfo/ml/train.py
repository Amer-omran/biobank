"""Fine-tune one language-specific classifier, calibrate on validation, evaluate ONCE on test.

Usage (Arabic):
    python -m healthmisinfo.ml.train --language ar --split-dir ../data/processed/ar/<version> \
        --base-model aubmindlab/bert-base-arabertv02 --output-root ../models

Order of operations (the test split is touched exactly once, after model selection):
  1. verify the split manifest (status=valid, sha256 of every CSV) – refuse otherwise
  2. train on train.csv, select the best epoch by validation macro-F1 (early stopping)
  3. fit temperature + abstention threshold on validation logits only
  4. evaluate the selected, calibrated model on test.csv; write evaluation.json + model card

``--smoke-test-tiny-random`` builds a tiny randomly initialised BERT and a vocabulary from the
training texts so the pipeline can be exercised without downloading weights. Its outputs are
flagged ``smoke_test=true`` and can NEVER be registered as a model (see ml/registry.py).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from healthmisinfo.labels import LABEL_NAMES, LABEL_SCHEMES
from healthmisinfo.ml.calibration import calibration_report, fit_temperature, risk_coverage, select_abstention_threshold, softmax
from healthmisinfo.ml.metrics import classification_metrics, expected_calibration_error, subgroup_metrics

DEFAULT_BASE_MODELS = {"ar": "aubmindlab/bert-base-arabertv02", "en": "FacebookAI/xlm-roberta-base"}


class SplitIntegrityError(RuntimeError):
    pass


@dataclass
class TrainConfig:
    language: str
    split_dir: str
    output_root: str
    base_model: str = ""
    run_tag: str = ""
    seed: int = 42
    epochs: float = 4.0
    learning_rate: float = 2e-5
    batch_size: int = 16
    eval_batch_size: int = 32
    max_length: int = 128
    weight_decay: float = 0.01
    warmup_ratio: float = 0.06
    class_weighting: str = "balanced"  # balanced | none
    early_stopping_patience: int = 2
    target_selective_accuracy: float = 0.90
    min_coverage: float = 0.30
    smoke_test_tiny_random: bool = False
    allow_synthetic: bool = False
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- data


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_split(split_dir: Path, allow_synthetic: bool = False) -> tuple[dict, dict[str, list[dict]]]:
    manifest_p = split_dir / "manifest.json"
    if not manifest_p.exists():
        raise SplitIntegrityError(f"{manifest_p} not found – build splits first")
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    if manifest.get("status") != "valid":
        raise SplitIntegrityError("Split manifest status is not 'valid'")
    if manifest.get("synthetic") and not allow_synthetic:
        raise SplitIntegrityError("Refusing to train on a synthetic fixture split")
    rows: dict[str, list[dict]] = {}
    for name in ("train", "validation", "test"):
        p = split_dir / f"{name}.csv"
        expected = manifest["files"][name]["sha256"]
        if sha256_file(p) != expected:
            raise SplitIntegrityError(f"{p} sha256 mismatch with manifest – data changed after splitting")
        with p.open(encoding="utf-8") as f:
            rows[name] = list(csv.DictReader(f))
        for r in rows[name]:
            r["label"] = int(r["label"])
    return manifest, rows


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None


def environment_info() -> dict:
    import torch
    import transformers

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "cuda_available": torch.cuda.is_available(),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
    }


# --------------------------------------------------------------------------- models


def build_tiny_random_model(texts: list[str], out_dir: Path, classes: list[int]):
    """Tiny random BERT + word-level vocab from the training texts. Pipeline smoke test ONLY."""
    from transformers import BertConfig, BertForSequenceClassification, BertTokenizerFast

    counts = Counter(w for t in texts for w in t.lower().split())
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"] + [w for w, _ in counts.most_common(3000)]
    out_dir.mkdir(parents=True, exist_ok=True)
    vocab_file = out_dir / "smoke_vocab.txt"
    vocab_file.write_text("\n".join(dict.fromkeys(vocab)), encoding="utf-8")
    tok = BertTokenizerFast(vocab_file=str(vocab_file), do_lower_case=True)
    cfg = BertConfig(
        vocab_size=tok.vocab_size,
        hidden_size=32,
        num_hidden_layers=2,
        num_attention_heads=2,
        intermediate_size=64,
        max_position_embeddings=256,
        num_labels=len(classes),
        id2label={i: LABEL_NAMES[c] for i, c in enumerate(classes)},
        label2id={LABEL_NAMES[c]: i for i, c in enumerate(classes)},
    )
    return tok, BertForSequenceClassification(cfg)


def load_pretrained(base_model: str, classes: list[int]):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=len(classes),
        id2label={i: LABEL_NAMES[c] for i, c in enumerate(classes)},
        label2id={LABEL_NAMES[c]: i for i, c in enumerate(classes)},
    )
    return tok, model


# --------------------------------------------------------------------------- training


class _TextDataset:
    def __init__(self, rows, tokenizer, max_length):
        self.enc = tokenizer([r["text"] for r in rows], truncation=True, max_length=max_length)
        self.labels = [r["label"] for r in rows]

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        item["labels"] = self.labels[i]
        return item


def predict_logits(trainer, dataset) -> np.ndarray:
    out = trainer.predict(dataset)
    logits = out.predictions[0] if isinstance(out.predictions, tuple) else out.predictions
    return np.asarray(logits, dtype=float)


def train_and_evaluate(cfg: TrainConfig) -> dict:
    import torch
    from torch import nn
    from transformers import (
        DataCollatorWithPadding,
        EarlyStoppingCallback,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    started = time.time()
    split_dir = Path(cfg.split_dir)
    manifest, rows = load_split(split_dir, allow_synthetic=cfg.allow_synthetic)
    if manifest.get("language") != cfg.language:
        raise SplitIntegrityError(f"Split language {manifest.get('language')} != --language {cfg.language}")
    label_scheme = manifest.get("label_scheme", "three_class")
    classes = LABEL_SCHEMES[label_scheme]  # class ids are 0..k-1 in both schemes
    cfg.base_model = cfg.base_model or DEFAULT_BASE_MODELS[cfg.language]
    cfg.run_tag = cfg.run_tag or (
        f"{cfg.language}-{'smoke' if cfg.smoke_test_tiny_random else cfg.base_model.split('/')[-1]}-"
        f"{manifest['version']}-s{cfg.seed}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
    )
    run_dir = Path(cfg.output_root) / cfg.language / cfg.run_tag
    ckpt_dir = run_dir / "checkpoint"
    run_dir.mkdir(parents=True, exist_ok=True)

    set_seed(cfg.seed)
    torch.set_num_threads(max(1, min(os.cpu_count() or 1, 8)))

    if cfg.smoke_test_tiny_random:
        tokenizer, model = build_tiny_random_model([r["text"] for r in rows["train"]], run_dir, classes)
    else:
        tokenizer, model = load_pretrained(cfg.base_model, classes)

    ds = {k: _TextDataset(v, tokenizer, cfg.max_length) for k, v in rows.items()}
    train_counts = Counter(r["label"] for r in rows["train"])
    if cfg.class_weighting == "balanced":
        n, k = len(rows["train"]), len(classes)
        weights = [n / (k * max(1, train_counts.get(c, 0))) for c in classes]
    else:
        weights = [1.0, 1.0, 1.0]
    class_weights = torch.tensor(weights, dtype=torch.float)

    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            loss = nn.functional.cross_entropy(outputs.logits, labels, weight=class_weights.to(outputs.logits.device))
            return (loss, outputs) if return_outputs else loss

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        logits = logits[0] if isinstance(logits, tuple) else logits
        m = classification_metrics(labels, np.argmax(logits, axis=1), classes)
        return {"macro_f1": m["macro_f1"], "accuracy": m["accuracy"]}

    import inspect

    # transformers<5 uses warmup_ratio; transformers>=5 accepts a float in [0, 1) as warmup_steps.
    warmup = (
        {"warmup_ratio": cfg.warmup_ratio} if "warmup_ratio" in inspect.signature(TrainingArguments.__init__).parameters else {"warmup_steps": cfg.warmup_ratio}
    )
    args = TrainingArguments(
        output_dir=str(run_dir / "trainer"),
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=2,
        learning_rate=cfg.learning_rate,
        per_device_train_batch_size=cfg.batch_size,
        per_device_eval_batch_size=cfg.eval_batch_size,
        num_train_epochs=cfg.epochs,
        weight_decay=cfg.weight_decay,
        seed=cfg.seed,
        data_seed=cfg.seed,
        logging_steps=10,
        report_to=[],
        use_cpu=not torch.cuda.is_available(),
        **warmup,
    )
    trainer = WeightedTrainer(
        model=model,
        args=args,
        train_dataset=ds["train"],
        eval_dataset=ds["validation"],
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=compute_metrics,
        processing_class=tokenizer,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=cfg.early_stopping_patience)],
    )
    train_out = trainer.train()
    trainer.save_model(str(ckpt_dir))
    tokenizer.save_pretrained(str(ckpt_dir))

    # ---- validation: model-selection metrics + calibration (validation only)
    y_val = np.array([r["label"] for r in rows["validation"]])
    val_logits = predict_logits(trainer, ds["validation"])
    val_metrics = classification_metrics(y_val, val_logits.argmax(axis=1), classes)
    temperature = fit_temperature(val_logits, y_val)
    val_cal = calibration_report(val_logits, y_val, temperature)
    abstention = select_abstention_threshold(softmax(val_logits, temperature), y_val, cfg.target_selective_accuracy, cfg.min_coverage)
    calibration = {
        "method": "temperature_scaling",
        "fitted_on": "validation",
        "temperature": temperature,
        "validation": val_cal,
        "abstention": abstention,
    }
    (run_dir / "calibration.json").write_text(json.dumps(calibration, indent=2), encoding="utf-8")

    # ---- test: touched once, after selection and calibration are frozen
    y_test = np.array([r["label"] for r in rows["test"]])
    test_logits = predict_logits(trainer, ds["test"])
    test_pred = test_logits.argmax(axis=1)
    test_probs_cal = softmax(test_logits, temperature)
    test_metrics = classification_metrics(y_test, test_pred, classes)
    thr = abstention["threshold"]
    selective = risk_coverage(test_probs_cal, y_test, [thr])[0] if thr is not None else None
    evaluation = {
        "run_tag": cfg.run_tag,
        "language": cfg.language,
        "base_model": cfg.base_model,
        "smoke_test": cfg.smoke_test_tiny_random,
        "label_scheme": label_scheme,
        "synthetic_data": bool(manifest.get("synthetic")),
        "split_version": manifest["version"],
        "split_data_sha256": manifest.get("data_sha256"),
        "evaluated_at": datetime.now(UTC).isoformat(),
        "validation": val_metrics,
        "test": test_metrics,
        "test_calibration": {
            "ece_raw": expected_calibration_error(softmax(test_logits, 1.0), y_test),
            "ece_calibrated": expected_calibration_error(test_probs_cal, y_test),
            "temperature": temperature,
        },
        "test_selective": {"threshold": thr, **(selective or {})},
        "subgroups": {
            "health_topic": subgroup_metrics(y_test, test_pred, [r["health_topic"] for r in rows["test"]], labels=classes),
            "source": subgroup_metrics(y_test, test_pred, [r["source_key"] for r in rows["test"]], labels=classes),
        },
        "class_distribution": {k: {LABEL_NAMES[c]: int(v) for c, v in sorted(Counter(r["label"] for r in rows[k]).items())} for k in rows},
    }
    (run_dir / "evaluation.json").write_text(json.dumps(evaluation, indent=2, ensure_ascii=False), encoding="utf-8")
    with (run_dir / "predictions_test.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sample_id", "label", "predicted", *[f"p_cal_{LABEL_NAMES[c]}" for c in classes]])
        for r, p, probs in zip(rows["test"], test_pred, test_probs_cal, strict=True):
            w.writerow([r["sample_id"], r["label"], int(p), *[round(float(x), 6) for x in probs]])
    _plot_confusion(test_metrics["confusion_matrix"]["matrix"], run_dir / "confusion_matrix_test.png", cfg.run_tag, test_metrics["confusion_matrix"]["labels"])

    run_config = {
        "config": asdict(cfg),
        "class_weights": weights,
        "train_runtime_seconds": round(time.time() - started, 1),
        "trainer_metrics": train_out.metrics,
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "best_metric_validation_macro_f1": trainer.state.best_metric,
        "split_manifest": {k: manifest.get(k) for k in ("version", "data_sha256", "split_sizes", "label_distribution", "seed")},
        "environment": environment_info(),
        "git_commit": git_commit(),
        "checkpoint_dir": str(ckpt_dir),
    }
    (run_dir / "run_config.json").write_text(json.dumps(run_config, indent=2, default=str), encoding="utf-8")

    from healthmisinfo.ml.model_card import write_model_card

    write_model_card(run_dir, run_config, evaluation, calibration, manifest)
    return {"run_dir": str(run_dir), "evaluation": evaluation, "calibration": calibration, "run_config": run_config}


def _plot_confusion(matrix, path: Path, title: str, names: list[str]) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    m = np.asarray(matrix)
    fig, ax = plt.subplots(figsize=(4.6, 4))
    ax.imshow(m, cmap="Blues")
    ax.set_xticks(range(len(names)), names, rotation=30, ha="right")
    ax.set_yticks(range(len(names)), names)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    for i in range(len(names)):
        for j in range(len(names)):
            ax.text(j, i, int(m[i, j]), ha="center", va="center", color="white" if m[i, j] > m.max() / 2 else "black")
    ax.set_title(f"Test confusion matrix\n{title}", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--language", required=True, choices=["ar", "en"])
    ap.add_argument("--split-dir", required=True)
    ap.add_argument("--output-root", default=str(Path(__file__).resolve().parents[3] / "models"))
    ap.add_argument("--base-model", default="")
    ap.add_argument("--run-tag", default="")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--epochs", type=float, default=4.0)
    ap.add_argument("--learning-rate", type=float, default=2e-5)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=128)
    ap.add_argument("--class-weighting", choices=["balanced", "none"], default="balanced")
    ap.add_argument("--early-stopping-patience", type=int, default=2)
    ap.add_argument("--target-selective-accuracy", type=float, default=0.90)
    ap.add_argument("--min-coverage", type=float, default=0.30)
    ap.add_argument("--smoke-test-tiny-random", action="store_true")
    ap.add_argument("--allow-synthetic", action="store_true", help="only together with --smoke-test-tiny-random")
    a = ap.parse_args(argv)
    if a.allow_synthetic and not a.smoke_test_tiny_random:
        ap.error("--allow-synthetic is only permitted with --smoke-test-tiny-random")
    cfg = TrainConfig(
        language=a.language,
        split_dir=a.split_dir,
        output_root=a.output_root,
        base_model=a.base_model,
        run_tag=a.run_tag,
        seed=a.seed,
        epochs=a.epochs,
        learning_rate=a.learning_rate,
        batch_size=a.batch_size,
        max_length=a.max_length,
        class_weighting=a.class_weighting,
        early_stopping_patience=a.early_stopping_patience,
        target_selective_accuracy=a.target_selective_accuracy,
        min_coverage=a.min_coverage,
        smoke_test_tiny_random=a.smoke_test_tiny_random,
        allow_synthetic=a.allow_synthetic,
    )
    out = train_and_evaluate(cfg)
    t = out["evaluation"]["test"]
    print(
        json.dumps(
            {"run_dir": out["run_dir"], "test_macro_f1": t["macro_f1"], "test_accuracy": t["accuracy"], "smoke_test": cfg.smoke_test_tiny_random}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
