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

PHASE_KEY="P8_dir${DIR_INDEX}"
TAG="dir${DIR_INDEX}"

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"
cd "$INPUT_DIR"

MERGE_NPROC=8
MERGER_SCRIPT="$SHERPA_ON_THE_ROCKS_DIR/yodamerge_runs.sh"
if [[ "$MERGE_MODE" == "rivet" ]]; then
    MERGER_SCRIPT="$SHERPA_ON_THE_ROCKS_DIR/rivetmerge_runs.sh"
fi

run_cmd "8" "$TAG" bash "$MERGER_SCRIPT" --rm validation "$MERGE_NPROC"

record_phase_time "$STATE_JSON" "$PHASE_KEY" "end"
log_msg "8" "$TAG" "Completed successfully."
