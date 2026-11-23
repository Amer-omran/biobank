#!/usr/bin/env bash
# Fetch the publicly downloadable datasets at the exact revisions audited in
# data/registry/sources.json and verify their SHA-256. Raw data goes to data/raw/ (gitignored) and is
# never committed. Licenses: AraFacts = CC BY-NC 4.0 (non-commercial, attribution);
# AraCOVID19-MFH = NO LICENSE FILE (unclear, flagged for review; tweet IDs only).
# PUBHEALTH must be downloaded manually (Google Drive) into data/manual/pubhealth/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$ROOT/data/raw"
mkdir -p "$RAW"

fetch() { # name url revision
  local name="$1" url="$2" rev="$3" dir="$RAW/$1"
  if [ ! -d "$dir/.git" ]; then
    git clone --quiet "$url" "$dir"
  fi
  git -C "$dir" fetch --quiet origin "$rev" 2>/dev/null || git -C "$dir" fetch --quiet origin
  git -C "$dir" checkout --quiet "$rev"
  echo "$name @ $(git -C "$dir" rev-parse HEAD)"
}

verify() { # file expected_sha256
  local got
  got="$(sha256sum "$1" | cut -d' ' -f1)"
  if [ "$got" != "$2" ]; then
    echo "SHA-256 MISMATCH for $1: expected $2 got $got" >&2
    exit 1
  fi
  echo "  verified $(basename "$1")"
}

fetch arafacts https://gitlab.com/bigirqu/AraFacts.git 69d48d39afaec609d7040c446c2e2691b85fa86b
verify "$RAW/arafacts/Dataset/AraFacts 2/AraFacts 2.csv" 7f6682e2c1c59fadbff8769858c42b9e061841d5e1e4ff694b515ff6f90f24e2

fetch aracovid19_mfh https://github.com/HadjAmeur/AraCovid19-MFH.git 2078c7b5a9e17a623477fdb7486411a6aed07dce
verify "$RAW/aracovid19_mfh/AraCOVID19-MFH_V1.0.csv" 6c439f96f4fcfcfb1a77c5dd38a802e1879c81f174687e33330e813c844569ea

if ls "$ROOT/data/manual/pubhealth/"*.tsv >/dev/null 2>&1; then
  echo "PUBHEALTH files present in data/manual/pubhealth/"
else
  echo "PUBHEALTH not present: download PUBHEALTH.zip from the official link in"
  echo "  https://github.com/neemakot/Health-Fact-Checking/blob/master/data/README.md"
  echo "  and unzip train.tsv/dev.tsv/test.tsv into data/manual/pubhealth/"
fi
