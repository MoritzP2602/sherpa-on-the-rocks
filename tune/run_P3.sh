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

PHASE_KEY="P3_dir${DIR_INDEX}"
TAG="dir${DIR_INDEX}"
log_msg "3" "$TAG" "Started."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"

TARGET="newscan"
if [[ "$REWEIGHT" == "1" ]]; then
  TARGET="newscan.rew"
fi

MERGER_SCRIPT="$SHERPA_ON_THE_ROCKS_DIR/rivet-merge_runs.sh"
if [[ "$MERGE_MODE" == "yoda" ]]; then
  MERGER_SCRIPT="$SHERPA_ON_THE_ROCKS_DIR/yodamerge_runs.sh"
fi

require_inputs "3" "$TAG" "$INPUT_DIR" "$INPUT_DIR/$TARGET" "$MERGER_SCRIPT"
if ! find "$INPUT_DIR/$TARGET" -name "*.yoda*" -print -quit 2>/dev/null | grep -q .; then
  log_msg "3" "$TAG" "ERROR: Missing required input: no YODA files found in $INPUT_DIR/$TARGET"
  log_msg "3" "$TAG" "Skipping phase due to missing inputs."
  exit 1
fi

cd "$INPUT_DIR"

MERGE_NPROC="$MAX_CPUS"
if [[ "$REWEIGHT" == "1" ]]; then
  run_cmd "3" "$TAG" bash "$MERGER_SCRIPT" --rm --chunked 10 "$TARGET" "$MERGE_NPROC"
else
  run_cmd "3" "$TAG" bash "$MERGER_SCRIPT" --rm "$TARGET" "$MERGE_NPROC"
fi

log_msg "3" "$TAG" "Completed successfully."
