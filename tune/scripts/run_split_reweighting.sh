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

if [[ -n "$PHASE_LOG_DIR" ]]; then
  PHASE_KEY="$(basename "$PHASE_LOG_DIR")"
else
  PHASE_KEY="P4_dir${DIR_INDEX}"
fi
TAG="${PHASE_KEY#P4_}"
log_msg "4" "$TAG" "Started."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"

if [[ "$REWEIGHT" != "1" ]]; then
  log_msg "4" "$TAG" "ERROR: this node only runs for input dirs with REWEIGHTING enabled."
  exit 1
fi

require_inputs "4" "$TAG" "$INPUT_DIR" \
                          "$INPUT_DIR/newscan.rew" \
                          "$INPUT_DIR/newscan.rew.var.dat"

cd "$INPUT_DIR"

if ! command -v app-tools-split_reweighting >/dev/null 2>&1; then
  log_msg "4" "$TAG" "ERROR: app-tools-split_reweighting not found."
  exit 1
fi
run_cmd "4" "$TAG" app-tools-split_reweighting newscan.rew "$PATTERN" \
                   --variations newscan.rew.var.dat --overwrite --quiet

log_msg "4" "$TAG" "Completed successfully."
