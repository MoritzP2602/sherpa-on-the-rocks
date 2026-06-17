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
log_msg "8" "$TAG" "Started."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"

MERGE_NPROC="$MAX_CPUS"
MERGER_SCRIPT="$SHERPA_ON_THE_ROCKS_DIR/rivet-merge_runs.sh"
if [[ "$MERGE_MODE" == "yoda" ]]; then
    MERGER_SCRIPT="$SHERPA_ON_THE_ROCKS_DIR/yodamerge_runs.sh"
fi

require_inputs "8" "$TAG" "$INPUT_DIR" "$INPUT_DIR/validation" "$MERGER_SCRIPT"
if ! find "$INPUT_DIR/validation" -name "*.yoda*" -print -quit 2>/dev/null | grep -q .; then
  log_msg "8" "$TAG" "ERROR: Missing required input: no YODA files found in $INPUT_DIR/validation"
  log_msg "8" "$TAG" "Skipping phase due to missing inputs."
  exit 1
fi

cd "$INPUT_DIR"

run_cmd "8" "$TAG" bash "$MERGER_SCRIPT" --rm validation "$MERGE_NPROC" --quiet

log_msg "8" "$TAG" "Completed successfully."
