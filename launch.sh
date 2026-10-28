#!/bin/bash
# One-command NCBI launcher  -  sources ~/.ncbi_env on the access point so the
# environment= directive picks up the API key.
# Usage: ./launch.sh {pull|regress|status|pull-back}
set -euo pipefail
REMOTE_HOST="samah.alshrief@ap40.uw.osg-htc.org"
REMOTE_DIR="~/ncbi-analysis"
LOCAL_DIR="$(cd "$(dirname "$0")" && pwd)"
CMD="${1:-status}"

case "$CMD" in pull|regress|status|pull-back) ;;
  *) echo "Usage: $0 {pull|regress|status|pull-back}"; exit 2 ;;
esac

if [ "$CMD" = "pull" ] || [ "$CMD" = "regress" ]; then
  rsync -avz --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude '.ipynb_checkpoints' \
    --exclude 'data/*.parquet' --exclude 'results/*' --exclude '.DS_Store' \
    --exclude '.env' \
    "${LOCAL_DIR}/" "${REMOTE_HOST}:${REMOTE_DIR}/"
fi

if [ "$CMD" = "pull" ]; then
  ssh "$REMOTE_HOST" "source ~/.ncbi_env && cd ${REMOTE_DIR}/osg && chmod +x *.sh && mkdir -p logs && bash preflight.sh"
  CLUSTER=$(ssh "$REMOTE_HOST" "source ~/.ncbi_env && cd ${REMOTE_DIR}/osg && condor_submit pull_data.submit" | tee /dev/stderr | awk '/submitted to cluster/ {print $NF}' | tr -d '.')
  echo "==> Cluster $CLUSTER  -  tailing logs, Ctrl-C to detach:"
  ssh "$REMOTE_HOST" "cd ${REMOTE_DIR}/osg && tail -F logs/pull.${CLUSTER}.out logs/pull.${CLUSTER}.err 2>/dev/null"
elif [ "$CMD" = "regress" ]; then
  ssh "$REMOTE_HOST" "source ~/.ncbi_env && cd ${REMOTE_DIR}/osg && chmod +x *.sh && mkdir -p logs && bash preflight.sh"
  CLUSTER=$(ssh "$REMOTE_HOST" "cd ${REMOTE_DIR}/osg && condor_submit run_regression.submit" | tee /dev/stderr | awk '/submitted to cluster/ {print $NF}' | tr -d '.')
  echo "==> Cluster $CLUSTER  -  tailing RQ1, Ctrl-C to detach:"
  ssh "$REMOTE_HOST" "cd ${REMOTE_DIR}/osg && tail -F logs/regress.${CLUSTER}.0.out logs/regress.${CLUSTER}.0.err 2>/dev/null"
elif [ "$CMD" = "status" ]; then
  ssh "$REMOTE_HOST" "condor_q; echo; condor_history samah.alshrief | head -6"
elif [ "$CMD" = "pull-back" ]; then
  rsync -avz "${REMOTE_HOST}:${REMOTE_DIR}/osg/data/"    "${LOCAL_DIR}/data/"    || true
  rsync -avz "${REMOTE_HOST}:${REMOTE_DIR}/osg/results/" "${LOCAL_DIR}/results/" || true
fi
