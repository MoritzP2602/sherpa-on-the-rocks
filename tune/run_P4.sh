#!/bin/bash
set -euo pipefail

STATE_JSON="$1"
DIR_INDEX="$2"
CLUSTER="${3:-}"
PROCESS="${4:-}"
PHASE_LOG_DIR="${5:-}"
TUNE_MODE="${6:-}"      # "" = run everything in this job, or: prep / app / prof
TUNE_ORDER="${7:-}"     # single surrogate order for split subjobs, e.g. 2,0 or 3

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

if [[ -n "$PHASE_LOG_DIR" && -n "$CLUSTER" && -n "$PROCESS" ]]; then
  setup_tmp_logging "$PHASE_LOG_DIR" "$CLUSTER" "$PROCESS"
fi

# PHASE_KEY must match the DAG node name (node names are defined in tune.py,
# which sets PHASE_LOG_DIR to condor_output/<node name>).
if [[ -n "$PHASE_LOG_DIR" ]]; then
  PHASE_KEY="$(basename "$PHASE_LOG_DIR")"
else
  PHASE_KEY="P4_dir${DIR_INDEX}${TUNE_MODE:+_${TUNE_MODE}}${TUNE_ORDER:+_${TUNE_ORDER//,/_}}"
fi
TAG="${PHASE_KEY#P4_}"
log_msg "4" "$TAG" "Started."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"

SEL_APP_ORDERS=""
SEL_PROF_ORDERS=""
RUN_PREP=0
case "$TUNE_MODE" in
  "")   SEL_APP_ORDERS="${APP_ORDERS:-}"; SEL_PROF_ORDERS="${PROF_ORDERS:-}"; RUN_PREP="$REWEIGHT" ;;
  prep) RUN_PREP=1 ;;
  app|prof)
        if [[ -z "$TUNE_ORDER" ]]; then
          log_msg "4" "$TAG" "ERROR: tune mode '$TUNE_MODE' requires a surrogate order."
          exit 1
        fi
        if [[ "$TUNE_MODE" == "app" ]]; then SEL_APP_ORDERS="$TUNE_ORDER"; else SEL_PROF_ORDERS="$TUNE_ORDER"; fi ;;
  *)    log_msg "4" "$TAG" "ERROR: unknown tune mode '$TUNE_MODE'."
        exit 1 ;;
esac

REQUIRED_INPUTS=("$INPUT_DIR"
                 "$INPUT_DIR/weights.txt")
if [[ -n "$SEL_APP_ORDERS" ]]; then
  REQUIRED_INPUTS+=("$INPUT_DIR/data.json")
fi
if [[ "$REWEIGHT" == "1" ]]; then
  if [[ "$RUN_PREP" == "1" ]]; then
    REQUIRED_INPUTS+=("$INPUT_DIR/newscan.rew" "$INPUT_DIR/newscan.rew.var.dat")
  else
    REQUIRED_INPUTS+=("$INPUT_DIR/newscan.rew.split")
  fi
else
  REQUIRED_INPUTS+=("$INPUT_DIR/newscan")
fi
require_inputs "4" "$TAG" "${REQUIRED_INPUTS[@]}"

cd "$INPUT_DIR"

SCAN_DIR="newscan"
if [[ "$REWEIGHT" == "1" ]]; then
  SCAN_DIR="newscan.rew.split"
fi

if [[ "$RUN_PREP" == "1" ]]; then
  if command -v app-tools-split_reweighting >/dev/null 2>&1; then
    run_cmd "4" "$TAG" app-tools-split_reweighting newscan.rew "$PATTERN" --variations newscan.rew.var.dat --overwrite --quiet
  else
    log_msg "4" "$TAG" "ERROR: app-tools-split_reweighting not found."
    exit 1
  fi
fi
if [[ "$TUNE_MODE" == "prep" ]]; then
  log_msg "4" "$TAG" "Completed successfully."
  exit 0
fi

APP_BUILD_OPTS=()
APP_TUNE2_OPTS=()
if [[ -n "${APP_BUILD_OPTIONS:-}" ]]; then read -ra APP_BUILD_OPTS <<< "$APP_BUILD_OPTIONS"; fi
if [[ -n "${APP_TUNE2_OPTIONS:-}" ]]; then read -ra APP_TUNE2_OPTS <<< "$APP_TUNE2_OPTIONS"; fi
PROF_IPOL_OPTS=()
PROF_TUNE_OPTS=()
if [[ -n "${PROF2_IPOL_OPTIONS:-}" ]]; then read -ra PROF_IPOL_OPTS <<< "$PROF2_IPOL_OPTIONS"; fi
if [[ -n "${PROF2_TUNE_OPTIONS:-}" ]]; then read -ra PROF_TUNE_OPTS <<< "$PROF2_TUNE_OPTIONS"; fi

# ---------------------------------------------------------------------------- #
# Apprentice backend                                                           #
# ---------------------------------------------------------------------------- #
run_apprentice_order() {
  local order="$1"
  local safe="${order//,/_}"
  log_msg "4" "$TAG" "Building and tuning with Apprentice (order ${order})."
  mkdir -p Apprentice

  local app_json="Apprentice/app.${safe}.json"
  local err_json="Apprentice/err.${safe}.json"
  local tune_dir="Apprentice/tune.apprentice.${safe}.dir${DIR_INDEX}"
  local tune_dir_err="Apprentice/tune.apprentice.err.${safe}.dir${DIR_INDEX}"
  rm -rf "$app_json" "$err_json" "$tune_dir" "$tune_dir_err"

  run_cmd "4" "$TAG" app-build "$SCAN_DIR" --order "$order" -w weights.txt        -o "$app_json" "${APP_BUILD_OPTS[@]}"
  run_cmd "4" "$TAG" app-build "$SCAN_DIR" --order "$order" -w weights.txt --errs -o "$err_json" "${APP_BUILD_OPTS[@]}"
  run_cmd "4" "$TAG" app-tune2 weights.txt data.json "$app_json"                -o "$tune_dir"     "${APP_TUNE2_OPTS[@]}"
  run_cmd "4" "$TAG" app-tune2 weights.txt data.json "$app_json" -e "$err_json" -o "$tune_dir_err" "${APP_TUNE2_OPTS[@]}"
}

# ---------------------------------------------------------------------------- #
# Professor backend                                                            #
# ---------------------------------------------------------------------------- #
run_professor_order() {
  local order="$1"
  local safe="$order"
  log_msg "4" "$TAG" "Building and tuning with Professor (order ${order})."
  mkdir -p Professor

  local ipol="Professor/ipol.${safe}.dat"
  local ipol_err="Professor/ipol.err.${safe}.dat"
  local tune_dir="Professor/tune.professor.${safe}.dir${DIR_INDEX}"
  local tune_dir_err="Professor/tune.professor.err.${safe}.dir${DIR_INDEX}"
  rm -rf "$ipol" "$ipol_err" "$tune_dir" "$tune_dir_err"

  run_cmd "4" "$TAG" prof2-ipol "$SCAN_DIR" "$ipol"     --order "$order" -w weights.txt --ierr none  "${PROF_IPOL_OPTS[@]}"
  run_cmd "4" "$TAG" prof2-ipol "$SCAN_DIR" "$ipol_err" --order "$order" -w weights.txt              "${PROF_IPOL_OPTS[@]}"
  run_cmd "4" "$TAG" prof2-tune "$ipol"     -w weights.txt -R -o "$tune_dir"     "${PROF_TUNE_OPTS[@]}"
  run_cmd "4" "$TAG" prof2-tune "$ipol_err" -w weights.txt -R -o "$tune_dir_err" "${PROF_TUNE_OPTS[@]}"
}

# Non-split jobs own the whole backend folder and start fresh; split subjobs
# share it with parallel subjobs and only replace their own order's artifacts.
if [[ -z "$TUNE_MODE" ]]; then
  if [[ -n "$SEL_APP_ORDERS" ]];  then rm -rf Apprentice; fi
  if [[ -n "$SEL_PROF_ORDERS" ]]; then rm -rf Professor;  fi
fi
for order in $SEL_APP_ORDERS;  do run_apprentice_order "$order"; done
for order in $SEL_PROF_ORDERS; do run_professor_order  "$order"; done

log_msg "4" "$TAG" "Completed successfully."
