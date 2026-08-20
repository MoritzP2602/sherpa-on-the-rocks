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

PHASE_KEY="P13"
TAG=""
log_msg "13" "$TAG" "Started."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"

REQUIRED_INPUTS=()
for idx in $(seq 1 "$N_INPUT_DIRS"); do
  var="INPUT_DIR_${idx}"; DIR_PATH="${!var}"
  var="WEIGHTS_${idx}"; WEIGHTS="${!var}"
  REQUIRED_INPUTS+=("$DIR_PATH/validation" "$WEIGHTS")
done
require_inputs "13" "$TAG" "${REQUIRED_INPUTS[@]}"
for idx in $(seq 1 "$N_INPUT_DIRS"); do
  var="INPUT_DIR_${idx}"; DIR_PATH="${!var}"
  if ! find "$DIR_PATH/validation" -name "*.yoda*" -print -quit 2>/dev/null | grep -q .; then
    log_msg "13" "$TAG" "ERROR: Missing required input: no YODA files found in $DIR_PATH/validation"
    log_msg "13" "$TAG" "Skipping phase due to missing inputs."
    exit 1
  fi
done

for idx in $(seq 1 "$N_INPUT_DIRS"); do
  var="INPUT_DIR_${idx}"; DIR_PATH="${!var}"
  var="WEIGHTS_${idx}"; WEIGHTS="${!var}"

  if command -v app-tools-compute_chi2 >/dev/null 2>&1; then
    (
      cd "$DIR_PATH"
      run_cmd "13" "$TAG" app-tools-compute_chi2 validation --weights "$WEIGHTS" --tags "tune" --depth 1
    )
  else
    log_msg "13" "$TAG" "ERROR: app-tools-compute_chi2 not found."
    exit 1
  fi
  (
    cd "$DIR_PATH"
    run_cmd "13" "$TAG" app-tools-plot_chi2 chi2.json
  )
done

plot_params_for() {
  local root="$1"
  local dirs=()
  if [[ -n "${APP_ORDERS:-}"  && -d "$root/Apprentice" ]]; then dirs+=("Apprentice"); fi
  if [[ -n "${PROF_ORDERS:-}" && -d "$root/Professor"  ]]; then dirs+=("Professor");  fi
  if [[ "${#dirs[@]}" -eq 0 ]]; then
    log_msg "13" "$TAG" "No backend folder in $root; skipping its parameter forest plot."
    return
  fi
  (
    cd "$root"
    run_cmd "13" "$TAG" app-tools-plot_params "${dirs[@]}" -o params_forest.pdf --overwrite \
            --title "Tune parameters with fit errors ($(basename "$root"))"
  )
}

if ! command -v app-tools-plot_params >/dev/null 2>&1; then
  log_msg "13" "$TAG" "ERROR: app-tools-plot_params not found."
  exit 1
fi

for idx in $(seq 1 "$N_INPUT_DIRS"); do
  var="INPUT_DIR_${idx}"; DIR_PATH="${!var}"
  plot_params_for "$DIR_PATH"
done
if [[ "$N_INPUT_DIRS" -ge 2 && -n "${MERGED_DIR:-}" ]]; then
  plot_params_for "$MERGED_DIR"
fi

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
print()
print('\n'.join(lines))
PY

log_msg "13" "$TAG" "Completed successfully."
