#!/bin/bash
set -euo pipefail

STATE_JSON="$1"
CLUSTER="${2:-}"
PROCESS="${3:-}"
PHASE_LOG_DIR="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

if [[ -n "$PHASE_LOG_DIR" && -n "$CLUSTER" && -n "$PROCESS" ]]; then
  setup_tmp_logging "$PHASE_LOG_DIR" "$CLUSTER" "$PROCESS"
fi

PHASE_KEY="P9"
TAG=""
log_msg "9" "$TAG" "Started."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"

for idx in $(seq 1 "$N_INPUT_DIRS"); do
  eval "DIR_PATH=\$INPUT_DIR_${idx}"
  eval "WEIGHTS=\$WEIGHTS_${idx}"

  if command -v app-tools-compute_chi2 >/dev/null 2>&1; then
    run_cmd "9" "$TAG" bash -lc "cd '$DIR_PATH' && app-tools-compute_chi2 validation --weights '$WEIGHTS' --tags 'tune' --depth 1"
  else
    log_msg "9" "$TAG" "ERROR: app-tools-compute_chi2 not found."
    exit 1
  fi
  run_cmd "9" "$TAG" bash -lc "cd '$DIR_PATH' && app-tools-plot_chi2 chi2.json"
done

python3 - "$STATE_JSON" <<'PY'
import json, os, sys
from datetime import datetime

state_path = sys.argv[1]
with open(state_path, 'r', encoding='utf-8') as f:
    state = json.load(f)

condor_ids = {}
if os.path.exists(state['condor_ids_file']):
    with open(state['condor_ids_file'], 'r', encoding='utf-8') as f:
        condor_ids = json.load(f)
phase_times = {}
if os.path.exists(state['phase_times_file']):
    with open(state['phase_times_file'], 'r', encoding='utf-8') as f:
        phase_times = json.load(f)

def dur(start, end):
    if not start or not end:
        return 'n/a'
    try:
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end)
        return str(e - s)
    except Exception:
        return 'n/a'

lines = []
lines.append('SUMMARY')
lines.append(f"DAGMan cluster ID: {state.get('dag_cluster_id', 'unknown')}")
lines.append('')
lines.append('Condor cluster IDs per phase:')
for key in sorted(condor_ids):
    cid = condor_ids[key].get('cluster_id', 'n/a')
    lines.append(f"  - {key}: {cid}")
lines.append('')
lines.append('Measured time per phase:')
for key in sorted(phase_times):
    st = phase_times[key].get('start_time')
    en = phase_times[key].get('end_time')
    lines.append(f"  - {key}: start = {st or 'n/a'}; end = {en or 'n/a'}; duration = {dur(st, en)}")
lines.append('')
# list state here
print()
print('\n'.join(lines))
PY

record_phase_time "$STATE_JSON" "$PHASE_KEY" "end"
log_msg "9" "$TAG" "Completed successfully."
