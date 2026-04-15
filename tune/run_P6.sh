#!/bin/bash
set -euo pipefail

STATE_JSON="$1"
DIR_INDEX="$2"
CLUSTER="${3:-}"
PROCESS="${4:-}"
PHASE_LOG_DIR="${5:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

if [[ -n "$PHASE_LOG_DIR" && -n "$CLUSTER" && -n "$PROCESS" ]]; then
  setup_tmp_logging "$PHASE_LOG_DIR" "$CLUSTER" "$PROCESS"
fi

PHASE_KEY="P6_dir${DIR_INDEX}"
TAG="dir${DIR_INDEX}"

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"
cd "$INPUT_DIR"

CREATE_VALIDATION_GRID_CMD=(app-tools-create_grid tune "." template.yaml --outdir validation)
if [[ "${VALIDATION_REWEIGHT:-0}" == "1" ]]; then
  CREATE_VALIDATION_GRID_CMD+=(--nominal nominal.json)
fi
run_cmd "6" "$TAG" "${CREATE_VALIDATION_GRID_CMD[@]}"

if [[ "$N_INPUT_DIRS" == "2" ]]; then
  MERGED_SOURCE="$INPUT_DIR_1/merged"
  MERGED_VALIDATION_GRID_CMD=(app-tools-create_grid tune "$MERGED_SOURCE" template.yaml --outdir validation)
  if [[ "${VALIDATION_REWEIGHT:-0}" == "1" ]]; then
    MERGED_VALIDATION_GRID_CMD+=(--nominal nominal.json)
  fi
  run_cmd "6" "$TAG" "${MERGED_VALIDATION_GRID_CMD[@]}"
fi

run_cmd "6" "$TAG" bash "$SHERPA_ON_THE_ROCKS_DIR/prepare_runs.sh" validation "$N_VAL_SUBRUNS"

log_msg "6" "$TAG" "Validation setup done. Submission happens in Phase 7."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "end"
log_msg "6" "$TAG" "Completed successfully."
