"""Command-line interface for the offline research pipeline.

    python -m healthmisinfo.cli <command> [options]

Commands: init-db, seed-registry, create-user, import-arafacts, import-aracovid, import-pubhealth,
import-generic, approve-mapping, refresh-dataset, build-splits, train, register-model,
activate-model, status.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select

from healthmisinfo.config import PROJECT_ROOT, get_settings


def _session():
    from healthmisinfo.db.session import SessionLocal

    return SessionLocal()


def cmd_init_db(_a) -> int:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "backend" / "alembic"))
    command.upgrade(cfg, "head")
    with _session() as db:
        from healthmisinfo.data.registry import seed_registry

        keys = seed_registry(db)
        db.commit()
    print(f"Database migrated; source registry seeded: {keys}")
    return 0


def cmd_seed_registry(_a) -> int:
    from healthmisinfo.data.registry import seed_registry

    with _session() as db:
        keys = seed_registry(db)
        db.commit()
    print("Seeded:", ", ".join(keys))
    return 0


def cmd_create_user(a) -> int:
    from healthmisinfo.users import UserError, create_user

    pw = os.environ.get("HMD_NEW_USER_PASSWORD") or getpass.getpass("Password (min 10 chars, 3 classes): ")
    with _session() as db:
        try:
            u = create_user(db, a.email, a.name, pw, a.role)
        except UserError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        db.commit()
        print(f"Created {u.role} {u.email} ({u.reviewer_code})")
    return 0


def _import(result, a, source_key: str, mapper_from_registry: bool = True) -> int:
    from healthmisinfo.data.pipeline import import_records
    from healthmisinfo.data.registry import LabelMapper, mapping_path

    mapper = LabelMapper.load(source_key) if mapper_from_registry and mapping_path(source_key).exists() else None
    with _session() as db:
        ds = import_records(
            db,
            result,
            name=a.name,
            version=a.version,
            mapper=mapper,
            params={"adapter": source_key, "mapping_origin": "registry" if mapper else None, "cli_args": vars(a) | {"func": None}},
        )
        db.commit()
        print(json.dumps({"dataset_id": ds.id, "name": ds.name, "version": ds.version, "stats": ds.stats}, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_import_arafacts(a) -> int:
    from healthmisinfo.data.adapters.arafacts import load_arafacts

    cats = None if a.all_categories else a.categories
    return _import(load_arafacts(a.file, cats), a, "arafacts")


def cmd_import_aracovid(a) -> int:
    from healthmisinfo.data.adapters.aracovid import load_aracovid

    return _import(load_aracovid(a.file, a.hydrated), a, "aracovid19_mfh")


def cmd_import_pubhealth(a) -> int:
    from healthmisinfo.data.adapters.pubhealth import load_pubhealth

    return _import(load_pubhealth(a.dir), a, "pubhealth")


def cmd_import_generic(a) -> int:
    from healthmisinfo.data.adapters.generic import ColumnMapping, parse_generic
    from healthmisinfo.data.pipeline import import_records
    from healthmisinfo.data.registry import LabelMapper

    data = Path(a.file).read_bytes()
    parsed = parse_generic(
        data, Path(a.file).name, a.language, ColumnMapping(text=a.text_col, label=a.label_col, id=a.id_col, group_key=a.group_col), source_key=a.source_key
    )
    mapper = None
    if a.mapping_json:
        mapper = LabelMapper.from_inline(a.source_key, json.loads(Path(a.mapping_json).read_text(encoding="utf-8")), approved_by=a.approved_by or "cli")
    with _session() as db:
        ds = import_records(
            db,
            parsed.adapter,
            name=a.name,
            version=a.version,
            mapper=mapper,
            is_synthetic=a.synthetic,
            rejected_rows=len(parsed.row_errors),
            row_errors=parsed.row_errors,
            license_confirmed_by_uploader=a.license_confirmed,
            params={"adapter": "generic"},
        )
        db.commit()
        print(json.dumps({"dataset_id": ds.id, "stats": ds.stats}, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_approve_mapping(a) -> int:
    """Record a HUMAN approval in the version-controlled mapping file. Never run on someone's behalf."""
    from healthmisinfo.data.registry import LabelMapper, mapping_path

    p = mapping_path(a.source)
    data = json.loads(p.read_text(encoding="utf-8"))
    wanted = None if a.entries == "all" else {e.strip() for e in a.entries.split(",")}
    approved = 0
    for e in data["entries"]:
        if e["status"] != "proposed":
            continue
        if a.entries == "low-ambiguity":
            if e.get("ambiguity") != "low":
                continue
        elif wanted is not None and e["original"] not in wanted:
            continue
        if a.set_label:
            e["proposed_label"] = a.set_label
        e["status"] = "approved"
        e["approved_by"] = a.approved_by
        e["approved_at"] = date.today().isoformat()
        approved += 1
    if approved:
        base = data["mapping_version"].split("+")[0]
        data["mapping_version"] = f"{base}+approved-{date.today().isoformat()}"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LabelMapper.load(a.source)  # validate
    print(f"Approved {approved} entries in {p} by {a.approved_by}. Commit this file and run refresh-dataset.")
    return 0


def cmd_refresh_dataset(a) -> int:
    from healthmisinfo.data.pipeline import refresh_dataset
    from healthmisinfo.data.registry import LabelMapper, mapping_path
    from healthmisinfo.db.models import Dataset, SourceRegistry

    with _session() as db:
        ds = db.get(Dataset, a.id)
        if ds is None:
            print("dataset not found", file=sys.stderr)
            return 2
        src = db.get(SourceRegistry, ds.source_id) if ds.source_id else None
        mapper = LabelMapper.load(src.key) if src and mapping_path(src.key).exists() and ds.params.get("mapping_origin") != "inline" else None
        stats = refresh_dataset(db, ds, mapper=mapper)
        db.commit()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def cmd_build_splits(a) -> int:
    from healthmisinfo.data.split import SplitError, build_splits

    with _session() as db:
        try:
            res = build_splits(
                db,
                a.language,
                version=a.version,
                seed=a.seed,
                require_human_review=a.require_human_review,
                dataset_ids=a.dataset_ids,
                near_dup_threshold=a.near_dup_threshold,
                label_scheme=a.label_scheme,
            )
        except SplitError as e:
            db.commit()
            print(f"SPLIT REFUSED: {e}", file=sys.stderr)
            print(json.dumps(e.report, ensure_ascii=False, indent=2), file=sys.stderr)
            return 3
        db.commit()
        print(json.dumps(res.report, ensure_ascii=False, indent=2))
    return 0


def cmd_register_model(a) -> int:
    from healthmisinfo.ml.registry import RegistrationError, register_model

    with _session() as db:
        try:
            mv = register_model(db, Path(a.run_dir), activate=a.activate)
        except RegistrationError as e:
            print(f"REGISTRATION REFUSED: {e}", file=sys.stderr)
            return 3
        db.commit()
        print(f"Registered {mv.version_tag} (status={mv.status})")
    return 0


def cmd_activate_model(a) -> int:
    from healthmisinfo.db.models import ModelVersion
    from healthmisinfo.ml.registry import activate_model

    with _session() as db:
        mv = db.scalar(select(ModelVersion).where(ModelVersion.version_tag == a.tag))
        if mv is None:
            print("model not found", file=sys.stderr)
            return 2
        activate_model(db, mv)
        db.commit()
        print(f"Activated {mv.version_tag}")
    return 0


def cmd_bootstrap(_a) -> int:
    """Idempotent start-up for a hosted demo: migrate, seed registry, create the admin from
    $HMD_ADMIN_EMAIL/$HMD_ADMIN_PASSWORD, import AraFacts (for similar-claim retrieval) if its raw file
    is present, and register + activate valid trained runs found in the models directory.
    Runs that are smoke tests, synthetic or incomplete are refused by the registry and reported."""
    from healthmisinfo.data.adapters.arafacts import load_arafacts
    from healthmisinfo.data.pipeline import import_records
    from healthmisinfo.data.registry import LabelMapper
    from healthmisinfo.db.models import Dataset, ModelVersion, User
    from healthmisinfo.ml.registry import RegistrationError, activate_model, register_model
    from healthmisinfo.users import UserError, create_user

    cmd_init_db(_a)
    s = get_settings()
    with _session() as db:
        email, pw = os.environ.get("HMD_ADMIN_EMAIL"), os.environ.get("HMD_ADMIN_PASSWORD")
        if email and pw and db.scalar(select(User.id).where(User.email == email.strip().lower())) is None:
            try:
                create_user(db, email, os.environ.get("HMD_ADMIN_NAME", "Administrator"), pw, "admin")
                db.commit()
                print(f"bootstrap: admin {email} created")
            except UserError as e:
                print(f"bootstrap: admin NOT created: {e}", file=sys.stderr)

        raw = s.data_dir / "raw" / "arafacts" / "Dataset" / "AraFacts 2" / "AraFacts 2.csv"
        if raw.exists() and db.scalar(select(Dataset.id).where(Dataset.name == "arafacts-health")) is None:
            ds = import_records(
                db,
                load_arafacts(raw),
                name="arafacts-health",
                version="v2-2024-06-23",
                mapper=LabelMapper.load("arafacts"),
                params={"adapter": "arafacts", "mapping_origin": "registry", "via": "bootstrap"},
            )
            db.commit()
            print(f"bootstrap: imported AraFacts health subset ({ds.imported_count} claims, {ds.stats['eligible']} eligible)")

        known = set(db.scalars(select(ModelVersion.checkpoint_path)))
        newest: dict[str, ModelVersion] = {}
        for ev in sorted(s.models_dir.glob("*/*/evaluation.json")):
            run_dir = ev.parent
            if str((run_dir / "checkpoint").resolve()) in known:
                continue
            try:
                mv = register_model(db, run_dir)
                db.commit()
                print(f"bootstrap: registered {mv.version_tag}")
            except RegistrationError as e:
                db.rollback()
                print(f"bootstrap: skipped {run_dir.name}: {e}")
        for mv in db.scalars(select(ModelVersion).order_by(ModelVersion.created_at)):
            newest[mv.language] = mv
        for mv in newest.values():
            if mv.status != "active" and not db.scalar(select(ModelVersion.id).where(ModelVersion.language == mv.language, ModelVersion.status == "active")):
                activate_model(db, mv)
                db.commit()
                print(f"bootstrap: activated {mv.version_tag}")
    return 0


def cmd_status(_a) -> int:
    from healthmisinfo.db.models import Dataset
    from healthmisinfo.inference.service import SLOTS, inference_service

    with _session() as db:
        out = {"models": [inference_service.slot_status(db, lang) for lang in SLOTS], "datasets": []}
        for d in db.scalars(select(Dataset).order_by(Dataset.id)):
            out["datasets"].append(
                {
                    "id": d.id,
                    "name": d.name,
                    "version": d.version,
                    "kind": d.kind,
                    "language": d.language,
                    "synthetic": d.is_synthetic,
                    "rows": d.imported_count,
                    "eligible": (d.stats or {}).get("eligible", (d.stats or {}).get("candidate_count")),
                    "exclusions": (d.stats or {}).get("exclusion_reasons"),
                }
            )
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="healthmisinfo", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db").set_defaults(func=cmd_init_db)
    sub.add_parser("seed-registry").set_defaults(func=cmd_seed_registry)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("bootstrap", help="idempotent start-up for hosted demos").set_defaults(func=cmd_bootstrap)

    p = sub.add_parser("create-user", help="password from $HMD_NEW_USER_PASSWORD or interactive prompt")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--role", choices=["admin", "reviewer", "researcher"], default="researcher")
    p.set_defaults(func=cmd_create_user)

    def add_nv(p):
        p.add_argument("--name", required=True)
        p.add_argument("--version", required=True)

    p = sub.add_parser("import-arafacts")
    p.add_argument("--file", required=True, help="path to 'AraFacts 2.csv'")
    p.add_argument("--categories", nargs="+", default=["Health"])
    p.add_argument("--all-categories", action="store_true")
    add_nv(p)
    p.set_defaults(func=cmd_import_arafacts)

    p = sub.add_parser("import-aracovid")
    p.add_argument("--file", required=True)
    p.add_argument("--hydrated", help="CSV Tweet_ID,text obtained lawfully via the X API")
    add_nv(p)
    p.set_defaults(func=cmd_import_aracovid)

    p = sub.add_parser("import-pubhealth")
    p.add_argument("--dir", required=True, help="directory with train.tsv/dev.tsv/test.tsv")
    add_nv(p)
    p.set_defaults(func=cmd_import_pubhealth)

    p = sub.add_parser("import-generic")
    p.add_argument("--file", required=True)
    p.add_argument("--language", choices=["ar", "en"], required=True)
    p.add_argument("--source-key", default="user_upload")
    p.add_argument("--text-col", default="text")
    p.add_argument("--label-col", default="label")
    p.add_argument("--id-col")
    p.add_argument("--group-col")
    p.add_argument("--mapping-json", help="JSON file {original_label: TARGET}")
    p.add_argument("--approved-by")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--license-confirmed", action="store_true")
    add_nv(p)
    p.set_defaults(func=cmd_import_generic)

    p = sub.add_parser("approve-mapping", help="record a human approval of label-mapping entries")
    p.add_argument("--source", required=True)
    p.add_argument("--approved-by", required=True, help="name of the responsible researcher")
    p.add_argument("--entries", default="low-ambiguity", help="'all', 'low-ambiguity', or comma-separated original labels")
    p.add_argument("--set-label", choices=["SUPPORTED", "MISLEADING", "NEEDS_REVIEW", "EXCLUDE"], help="override the proposed target for the listed entries")
    p.set_defaults(func=cmd_approve_mapping)

    p = sub.add_parser("refresh-dataset")
    p.add_argument("--id", type=int, required=True)
    p.set_defaults(func=cmd_refresh_dataset)

    p = sub.add_parser("build-splits")
    p.add_argument("--language", choices=["ar", "en"], required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dataset-ids", type=int, nargs="*")
    p.add_argument("--require-human-review", action="store_true")
    p.add_argument("--near-dup-threshold", type=float, default=0.85)
    p.add_argument("--label-scheme", choices=["three_class", "binary"], default="three_class")
    p.set_defaults(func=cmd_build_splits)

    p = sub.add_parser("train", help="forwards to python -m healthmisinfo.ml.train", add_help=False)
    p.set_defaults(func=None)

    p = sub.add_parser("register-model")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--activate", action="store_true")
    p.set_defaults(func=cmd_register_model)

    p = sub.add_parser("activate-model")
    p.add_argument("--tag", required=True)
    p.set_defaults(func=cmd_activate_model)

    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "train":
        from healthmisinfo.ml.train import main as train_main

        return train_main(argv[1:])
    a = ap.parse_args(argv)
    get_settings()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
