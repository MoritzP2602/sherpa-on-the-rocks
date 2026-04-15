#!/bin/bash
set -euo pipefail
log_msg "5" "$TAG" "Started."

STATE_JSON="$1"
CLUSTER="${2:-}"
PROCESS="${3:-}"
PHASE_LOG_DIR="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

if [[ -n "$PHASE_LOG_DIR" && -n "$CLUSTER" && -n "$PROCESS" ]]; then
  setup_tmp_logging "$PHASE_LOG_DIR" "$CLUSTER" "$PROCESS"
fi

PHASE_KEY="P5"
TAG=""

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"

if [[ $N_INPUT_DIRS != 2 ]]; then
  log_msg "5" "$TAG" "Phase 5 requires exactly two input dirs."
  exit 1
fi

DIR1="$INPUT_DIR_1"
DIR2="$INPUT_DIR_2"

mkdir -p "$MERGED_DIR"

TUNE1="$DIR1/tune.${ORDER_SAFE}.dir1"
TUNE2="$DIR2/tune.${ORDER_SAFE}.dir2"
TUNE1_ERR="$DIR1/tune.err.${ORDER_SAFE}.dir1"
TUNE2_ERR="$DIR2/tune.err.${ORDER_SAFE}.dir2"

if [[ "$COMBINE_MODE" == "weighted" ]]; then
  run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" "$TUNE1" "$DIR2/weights.txt" "$TUNE2" -o "$MERGED_DIR/weights.txt"
  run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" "$TUNE1_ERR" "$DIR2/weights.txt" "$TUNE2_ERR" -o "$MERGED_DIR/weights.err.txt"
else
  run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" 1.0 "$DIR2/weights.txt" 1.0 -o "$MERGED_DIR/weights.txt"
  run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" 1.0 "$DIR2/weights.txt" 1.0 -o "$MERGED_DIR/weights.err.txt"
fi

SCAN1="$DIR1/newscan"
SCAN2="$DIR2/newscan"
if [[ "$REWEIGHT_1" == "1" ]]; then
  SCAN1="$DIR1/newscan.rew.split"
fi
if [[ "$REWEIGHT_2" == "1" ]]; then
  SCAN2="$DIR2/newscan.rew.split"
fi

TUNE_MERGED="$MERGED_DIR/tune.${ORDER_SAFE}.merged"
TUNE_MERGED_ERR="$MERGED_DIR/tune.err.${ORDER_SAFE}.merged"

APP_JSON="$MERGED_DIR/app_${ORDER_SAFE}.json"
ERR_JSON="$MERGED_DIR/err_${ORDER_SAFE}.json"
MERGED_DATA="$MERGED_DIR/data.json"
run_cmd "5" "$TAG" app-build "$SCAN1" "$SCAN2" --order "$ORDER" -o "$APP_JSON" -w "$MERGED_DIR/weights.txt"
run_cmd "5" "$TAG" app-build "$SCAN1" "$SCAN2" --order "$ORDER" -o "$ERR_JSON" -w "$MERGED_DIR/weights.err.txt" --errs
run_cmd "5" "$TAG" app-tune2 "$MERGED_DIR/weights.txt"     "$MERGED_DATA" "$APP_JSON" -s "$START_POINT_SURVEY" -r "$RESTARTS" -p -o "$TUNE_MERGED"
run_cmd "5" "$TAG" app-tune2 "$MERGED_DIR/weights.err.txt" "$MERGED_DATA" "$ERR_JSON" -s "$START_POINT_SURVEY" -r "$RESTARTS" -p -o "$TUNE_MERGED_ERR"

record_phase_time "$STATE_JSON" "$PHASE_KEY" "end"
log_msg "5" "$TAG" "Completed successfully."
