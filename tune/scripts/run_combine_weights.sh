#!/bin/bash
set -euo pipefail

STATE_JSON="$1"
BACKEND="$2"            # app | prof
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
  PHASE_KEY="P7_${BACKEND}"
fi
TAG="${PHASE_KEY#P7_}"
log_msg "7" "$TAG" "Started."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"

if [[ "$N_INPUT_DIRS" -lt 2 ]]; then
  log_msg "7" "$TAG" "Requires at least two input dirs."
  exit 1
fi

case "$BACKEND" in
  app)  FOLDER="Apprentice"; ORDERS="${APP_ORDERS_SAFE:-}"; TUNE_PREFIX="tune.apprentice" ;;
  prof) FOLDER="Professor";  ORDERS="${PROF_ORDERS:-}";     TUNE_PREFIX="tune.professor"  ;;
  *)    log_msg "7" "$TAG" "ERROR: unknown backend '$BACKEND'."
        exit 1 ;;
esac
if [[ -z "$ORDERS" ]]; then
  log_msg "7" "$TAG" "ERROR: backend '$BACKEND' is not configured."
  exit 1
fi

DIRS=()
WEIGHTS=()
for idx in $(seq 1 "$N_INPUT_DIRS"); do
  DIR_VAR="INPUT_DIR_${idx}"
  DIRS[idx]="${!DIR_VAR}"
  WEIGHTS[idx]="${DIRS[idx]}/weights.txt"
done
require_inputs "7" "$TAG" "${WEIGHTS[@]}"

mkdir -p "$MERGED_DIR/$FOLDER"

combine_order() {
  local safe="$1"
  local idx
  local out="$MERGED_DIR/$FOLDER/weights.${safe}.txt"
  local out_err="$MERGED_DIR/$FOLDER/err.weights.${safe}.txt"
  rm -f "$out" "$out_err"

  if [[ "$COMBINE_MODE" == "custom" ]]; then
    require_inputs "7" "$TAG" "$MERGED_DIR/custom.weights.txt"
    log_msg "7" "$TAG" "Using custom merged weights: $MERGED_DIR/custom.weights.txt"
    cp "$MERGED_DIR/custom.weights.txt" "$out"
    cp "$MERGED_DIR/custom.weights.txt" "$out_err"
    return
  fi

  local args=()
  local args_err=()
  local required=()
  for idx in $(seq 1 "$N_INPUT_DIRS"); do
    if [[ "$COMBINE_MODE" == "weighted" ]]; then
      local tune="${DIRS[idx]}/$FOLDER/${TUNE_PREFIX}.${safe}.dir${idx}"
      local tune_err="${DIRS[idx]}/$FOLDER/${TUNE_PREFIX}.err.${safe}.dir${idx}"
      required+=("$tune" "$tune_err")
      args+=("${WEIGHTS[idx]}" "$tune")
      args_err+=("${WEIGHTS[idx]}" "$tune_err")
    else
      args+=("${WEIGHTS[idx]}" 1.0)
      args_err+=("${WEIGHTS[idx]}" 1.0)
    fi
  done
  if [[ "${#required[@]}" -gt 0 ]]; then
    require_inputs "7" "$TAG" "${required[@]}"
  fi

  run_cmd "7" "$TAG" app-tools-combine_weights "${args[@]}"     -o "$out"
  run_cmd "7" "$TAG" app-tools-combine_weights "${args_err[@]}" -o "$out_err"
}

if [[ "$BACKEND" == "app" ]]; then
  require_inputs "7" "$TAG" "$MERGED_DIR/data.json"
fi

for safe in $ORDERS; do
  log_msg "7" "$TAG" "Combining weights for order ${safe//_/,}."
  combine_order "$safe"
done

log_msg "7" "$TAG" "Completed successfully."
