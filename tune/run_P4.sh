#!/bin/bash
set -euo pipefail
log_msg "4" "$TAG" "Started."

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

PHASE_KEY="P4_dir${DIR_INDEX}"
TAG="dir${DIR_INDEX}"

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"
cd "$INPUT_DIR"

SCAN_DIR="newscan"
if [[ "$REWEIGHT" == "1" ]]; then
  if command -v app-tools-split_reweighting >/dev/null 2>&1; then
    run_cmd "4" "$TAG" app-tools-split_reweighting newscan.rew "MPI.v" --variations newscan.rew.var.dat
  elif command -v app-tools-split_reweighted_runs >/dev/null 2>&1; then
    run_cmd "4" "$TAG" app-tools-split_reweighted_runs newscan.rew "MPI.v" --variations newscan.rew.var.dat
  else
    log_msg "4" "$TAG" "ERROR: app-tools-split_reweighting not found."
    exit 1
  fi
  SCAN_DIR="newscan.rew.split"
fi

APP_JSON="app_${ORDER_SAFE}.json"
ERR_JSON="err_${ORDER_SAFE}.json"
TUNE_DIR="tune.${ORDER_SAFE}.dir${DIR_INDEX}"
TUNE_DIR_ERR="tune.err.${ORDER_SAFE}.dir${DIR_INDEX}"

run_cmd "4" "$TAG" app-build "$SCAN_DIR" --order "$ORDER" -o "$APP_JSON" -w weights.txt
run_cmd "4" "$TAG" app-build "$SCAN_DIR" --order "$ORDER" -o "$ERR_JSON" -w weights.txt --errs
run_cmd "4" "$TAG" app-tune2 weights.txt data.json "$APP_JSON"                -s "$START_POINT_SURVEY" -r "$RESTARTS" -p -o "$TUNE_DIR"
run_cmd "4" "$TAG" app-tune2 weights.txt data.json "$APP_JSON" -e "$ERR_JSON" -s "$START_POINT_SURVEY" -r "$RESTARTS" -p -o "$TUNE_DIR_ERR"

record_phase_time "$STATE_JSON" "$PHASE_KEY" "end"
log_msg "4" "$TAG" "Completed successfully."
