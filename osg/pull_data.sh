#!/bin/bash
# ---------------------------------------------------------------------------
# OSG wrapper: pull PubMed data via NCBI E-utilities. Installs pip deps to a
# local target dir (works with osgvo-ubuntu-20.04 which lacks python3-venv).
# ---------------------------------------------------------------------------
# NOTE: `set -u` intentionally omitted so we can safely reference
# NCBI_API_KEY / NCBI_EMAIL even if the environment did not deliver them.
set -eo pipefail
export PS4='+ [pull_data $(date +%H:%M:%S)] '
set -x

# ALWAYS create the output dir first so that even if pip / python later fail,
# HTCondor's transfer_output_files = data still finds a directory to ship.
mkdir -p data deps
: > data/.placeholder

echo "[pull_data] host=$(hostname)  start=$(date -Iseconds)"
NCBI_API_KEY="${NCBI_API_KEY:-}"
NCBI_EMAIL="${NCBI_EMAIL:-}"
echo "[pull_data] NCBI_API_KEY set? ${NCBI_API_KEY:+yes} (len=${#NCBI_API_KEY})"
echo "[pull_data] NCBI_EMAIL=$NCBI_EMAIL"
echo "[pull_data] pwd=$(pwd)  ls -la:"
ls -la
python3 -m ensurepip --user 2>/dev/null || true
python3 -m pip install --upgrade --target=deps pip 2>/dev/null || python3 -m pip install --user --upgrade pip
python3 -m pip install --target=deps -r requirements-osg.txt

export PYTHONPATH="$PWD/deps:${PYTHONPATH:-}"
python3 pull_all_pubmed.py

echo "[pull_data] done=$(date -Iseconds)  files:"
ls -lh data
