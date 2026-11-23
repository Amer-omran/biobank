"""Generate a model card (Mitchell et al., 2019 structure) from REAL run artefacts only."""

from __future__ import annotations

from pathlib import Path


def _pct(x) -> str:
    return "n/a" if x is None else f"{100 * float(x):.2f}%"


def write_model_card(run_dir: Path, run_config: dict, evaluation: dict, calibration: dict, manifest: dict) -> Path:
    cfg = run_config["config"]
    t = evaluation["test"]
    v = evaluation["validation"]
    smoke = evaluation.get("smoke_test")
    lines = []
    if smoke:
        lines += [
            "> ⚠️ **PIPELINE SMOKE TEST — NOT A RESEARCH RESULT.** This run used a tiny, randomly",
            "> initialised network" + (" on SYNTHETIC fixture data" if evaluation.get("synthetic_data") else "") + ".",
            "> Its numbers only prove the code path executes. It cannot be registered or served.",
            "",
        ]
    lines += [
        f"# Model card — {cfg['run_tag']}",
        "",
        "## Model details",
        f"- Task: health-claim classification, scheme `{evaluation.get('label_scheme', 'three_class')}` ({', '.join(t['confusion_matrix']['labels'])})"
        + (" — NEEDS_REVIEW is produced only by calibrated abstention" if evaluation.get("label_scheme") == "binary" else ""),
        f"- Language: `{cfg['language']}`",
        f"- Base model: `{cfg['base_model']}`" + (" (NOT used: tiny random init)" if smoke else ""),
        f"- Seed: {cfg['seed']}; epochs ≤ {cfg['epochs']}; lr {cfg['learning_rate']}; batch {cfg['batch_size']}; "
        f"max_length {cfg['max_length']}; class weighting `{cfg['class_weighting']}`",
        f"- Best validation macro-F1 (model selection): {run_config.get('best_metric_validation_macro_f1')}",
        f"- Code commit: `{run_config.get('git_commit')}`",
        f"- Environment: {run_config.get('environment')}",
        "",
        "## Intended use",
        "Research on automatic detection of health misinformation. Outputs are **research predictions** that",
        "must be verified against reliable evidence and may require expert review.",
        "",
        "## Out-of-scope use",
        "- Medical diagnosis, treatment recommendations or any clinical decision.",
        "- Automated removal/censorship of content or definitive public fact-check verdicts.",
        "- Languages other than the training language; non-health claims.",
        "",
        "## Training data",
        f"- Split version `{manifest.get('version')}` (data sha256 `{manifest.get('data_sha256')}`), seed {manifest.get('seed')}",
        f"- Split sizes: {manifest.get('split_sizes')}",
        f"- Label distribution per split: {manifest.get('label_distribution')}",
        f"- Group-aware split; grouping: {manifest.get('grouping', {}).get('method')} (threshold {manifest.get('near_dup_threshold')})",
        f"- Candidates: {manifest.get('candidate_count')} vs. target {manifest.get('target_per_language')} (shortfall {manifest.get('shortfall_vs_target')})",
        "",
        "## Evaluation (held-out test split, evaluated once after model selection)",
        "| Metric | Validation | Test |",
        "| --- | --- | --- |",
        f"| Accuracy | {_pct(v['accuracy'])} | {_pct(t['accuracy'])} |",
        f"| Macro precision | {_pct(v['macro_precision'])} | {_pct(t['macro_precision'])} |",
        f"| Macro recall | {_pct(v['macro_recall'])} | {_pct(t['macro_recall'])} |",
        f"| Macro F1 | {_pct(v['macro_f1'])} | {_pct(t['macro_f1'])} |",
        "",
        "Per-class (test):",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "| --- | --- | --- | --- | --- |",
    ]
    for name, m in t["per_class"].items():
        lines.append(f"| {name} | {_pct(m['precision'])} | {_pct(m['recall'])} | {_pct(m['f1'])} | {m['support']} |")
    cm = t["confusion_matrix"]["matrix"]
    lines += [
        "",
        "Confusion matrix (test; rows = true, columns = predicted):",
        "",
        "| | " + " | ".join(t["confusion_matrix"]["labels"]) + " |",
        "| --- " * (len(t["confusion_matrix"]["labels"]) + 1) + "|",
    ]
    for i, name in enumerate(t["confusion_matrix"]["labels"]):
        lines.append(f"| **{name}** | " + " | ".join(str(x) for x in cm[i]) + " |")
    ab = calibration["abstention"]
    tc = evaluation["test_calibration"]
    ts = evaluation.get("test_selective") or {}
    lines += [
        "",
        "## Calibration & abstention (fitted on validation only)",
        f"- Temperature T = {calibration['temperature']:.4f}",
        f"- Test ECE: raw softmax {tc['ece_raw']:.4f} → calibrated {tc['ece_calibrated']:.4f}",
        f"- Abstention threshold: {ab['threshold']} (target selective accuracy {ab['target_selective_accuracy']}, "
        f"min coverage {ab['min_coverage']}, **target met on validation: {ab['target_met']}**)",
        f"- Test at that threshold: coverage {ts.get('coverage')}, selective accuracy {ts.get('selective_accuracy')}",
        "- Predictions below the threshold are shown as *abstained → needs expert review*.",
        "",
        "## Subgroup evaluation (test)",
        "Health topics are assigned by a transparent keyword heuristic (topics-v1), not by experts.",
        "",
        "| Group | n | Accuracy | Macro F1 | Note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for kind, groups in evaluation["subgroups"].items():
        for g, m in groups.items():
            note = "small sample (<30) – unreliable" if m["small_sample_warning"] else ""
            lines.append(f"| {kind}: {g} | {m['n']} | {_pct(m['accuracy'])} | {_pct(m['macro_f1'])} | {note} |")
    lines += [
        "",
        "## Limitations",
        "- Labels derive from fact-checker verdicts mapped to a 3-class scheme; the mapping is a research",
        "  decision documented in `data/registry/label_mappings/` and may not transfer to other definitions.",
        "- The classifier sees only the claim text; it does not retrieve or verify evidence. A prediction",
        "  of MISLEADING is not proof of falsity, and absence of supporting sources is not treated as falsity.",
        "- Class imbalance (especially few SUPPORTED / NEEDS_REVIEW claims) limits per-class reliability.",
        "- Temporal drift: claims (e.g. COVID-19 era) may not represent future rumours.",
        "- Dialectal Arabic coverage is limited to what appears in the source fact-checks.",
        "",
        "## Ethical considerations",
        "Misclassification can stigmatise true health information or legitimise false information. Use only",
        "with human expert review and clear disclaimers. No personal health information is used for training.",
    ]
    p = run_dir / "model_card.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p
