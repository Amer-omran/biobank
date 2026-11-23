"""Deploy the platform to a free Hugging Face Space (Docker) to get a public link.

    pip install huggingface_hub
    export HF_TOKEN=hf_...            # a *write* token from https://huggingface.co/settings/tokens
    python scripts/deploy_hf_space.py --space <your-username>/health-claims-ai --admin-email you@example.org

The admin password is asked interactively (or read from $HMD_ADMIN_PASSWORD) and stored only as a
Space *secret*, never in the uploaded files. Add --models-dir models to include trained run folders.
--dry-run only builds the staging folder and prints its path.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns(
    ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "*.db", "node_modules", ".next", "coverage", "tests", "*.tsbuildinfo"
)


def stage(models_dir: Path | None) -> Path:
    out = Path(tempfile.mkdtemp(prefix="hf-space-"))
    shutil.copytree(ROOT / "backend", out / "backend", ignore=IGNORE)
    shutil.copytree(ROOT / "frontend", out / "frontend", ignore=IGNORE)
    shutil.copytree(ROOT / "data" / "registry", out / "data" / "registry")
    (out / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts" / "fetch_datasets.sh", out / "scripts" / "fetch_datasets.sh")
    (out / "models").mkdir()
    (out / "models" / "README.md").write_text("Trained run folders (models/<lang>/<run_tag>/) are registered at start-up.\n")
    if models_dir:
        for run in sorted(Path(models_dir).glob("*/*/evaluation.json")):
            ev = json.loads(run.read_text(encoding="utf-8"))
            if ev.get("smoke_test") or ev.get("synthetic_data"):
                print(f"skipping {run.parent.name}: smoke test / synthetic run (never deployed)")
                continue
            dest = out / "models" / run.parent.parent.name / run.parent.name
            shutil.copytree(run.parent, dest, ignore=shutil.ignore_patterns("trainer"))  # skip intermediate checkpoints
            print(f"including model run {run.parent.name}")
    for f in ("Dockerfile", "start.sh", "README.md"):
        shutil.copy2(ROOT / "deploy" / "hf_space" / f, out / f)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--space", help="<username>/<space-name>")
    ap.add_argument("--admin-email")
    ap.add_argument("--admin-name", default="Administrator")
    ap.add_argument("--models-dir", type=Path)
    ap.add_argument("--private", action="store_true", help="create the Space as private")
    ap.add_argument("--database-url", help="optional persistent PostgreSQL URL (stored as a secret)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    staged = stage(a.models_dir)
    if a.dry_run:
        print(f"staged: {staged}")
        return 0
    if not a.space or not a.admin_email:
        ap.error("--space and --admin-email are required (unless --dry-run)")
    token = os.environ.get("HF_TOKEN")
    if not token:
        ap.error("set HF_TOKEN to a Hugging Face write token")
    password = os.environ.get("HMD_ADMIN_PASSWORD") or getpass.getpass("Admin password (min 10 chars, mix of 3 kinds): ")

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(a.space, repo_type="space", space_sdk="docker", exist_ok=True, private=a.private)
    secrets_ = {
        "HMD_ADMIN_EMAIL": a.admin_email,
        "HMD_ADMIN_NAME": a.admin_name,
        "HMD_ADMIN_PASSWORD": password,
        "HMD_SECRET_KEY": secrets.token_urlsafe(48),
    }
    if a.database_url:
        secrets_["HMD_DATABASE_URL"] = a.database_url
    for k, v in secrets_.items():
        api.add_space_secret(a.space, k, v)
    api.upload_folder(repo_id=a.space, repo_type="space", folder_path=str(staged), commit_message="Deploy health misinformation platform")
    owner, name = a.space.split("/")
    url = f"https://{owner.lower()}-{name.lower().replace('_', '-').replace('.', '-')}.hf.space"
    print(f"\nUploaded. The Space builds for ~10-15 minutes, then opens at:\n  {url}\nSign in with {a.admin_email}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
