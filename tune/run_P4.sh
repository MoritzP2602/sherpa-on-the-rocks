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

PHASE_KEY="P4_dir${DIR_INDEX}"
TAG="dir${DIR_INDEX}"
log_msg "4" "$TAG" "Started."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"

REQUIRED_INPUTS=("$INPUT_DIR"
                 "$INPUT_DIR/weights.txt")
if [[ -n "${APP_ORDER:-}" ]]; then
  REQUIRED_INPUTS+=("$INPUT_DIR/data.json")
fi
if [[ "$REWEIGHT" == "1" ]]; then
  REQUIRED_INPUTS+=("$INPUT_DIR/newscan.rew" "$INPUT_DIR/newscan.rew.var.dat")
else
  REQUIRED_INPUTS+=("$INPUT_DIR/newscan")
fi
require_inputs "4" "$TAG" "${REQUIRED_INPUTS[@]}"

cd "$INPUT_DIR"

SCAN_DIR="newscan"
if [[ "$REWEIGHT" == "1" ]]; then
  if command -v app-tools-split_reweighting >/dev/null 2>&1; then
    run_cmd "4" "$TAG" app-tools-split_reweighting newscan.rew "$PATTERN" --variations newscan.rew.var.dat --overwrite --quiet
  else
    log_msg "4" "$TAG" "ERROR: app-tools-split_reweighting not found."
    exit 1
  fi
  SCAN_DIR="newscan.rew.split"
fi

# ---------------------------------------------------------------------------- #
# Apprentice backend                                                           #
# ---------------------------------------------------------------------------- #
if [[ -n "${APP_ORDER:-}" ]]; then
  log_msg "4" "$TAG" "Building and tuning with Apprentice (order ${APP_ORDER})."
  APP_BUILD_OPTS=()
  APP_TUNE2_OPTS=()
  if [[ -n "${APP_BUILD_OPTIONS:-}" ]]; then read -ra APP_BUILD_OPTS <<< "$APP_BUILD_OPTIONS"; fi
  if [[ -n "${APP_TUNE2_OPTIONS:-}" ]]; then read -ra APP_TUNE2_OPTS <<< "$APP_TUNE2_OPTIONS"; fi

  rm -rf Apprentice
  mkdir -p Apprentice

  APP_JSON="Apprentice/app.${APP_ORDER_SAFE}.json"
  ERR_JSON="Apprentice/err.${APP_ORDER_SAFE}.json"
  TUNE_DIR="Apprentice/tune.apprentice.${APP_ORDER_SAFE}.dir${DIR_INDEX}"
  TUNE_DIR_ERR="Apprentice/tune.apprentice.err.${APP_ORDER_SAFE}.dir${DIR_INDEX}"

  run_cmd "4" "$TAG" app-build "$SCAN_DIR" --order "$APP_ORDER" -w weights.txt        -o "$APP_JSON" "${APP_BUILD_OPTS[@]}" --quiet
  run_cmd "4" "$TAG" app-build "$SCAN_DIR" --order "$APP_ORDER" -w weights.txt --errs -o "$ERR_JSON" "${APP_BUILD_OPTS[@]}" --quiet
  run_cmd "4" "$TAG" app-tune2 weights.txt data.json "$APP_JSON"                "${APP_TUNE2_OPTS[@]}" -p -o "$TUNE_DIR"     --quiet
  run_cmd "4" "$TAG" app-tune2 weights.txt data.json "$APP_JSON" -e "$ERR_JSON" "${APP_TUNE2_OPTS[@]}" -p -o "$TUNE_DIR_ERR" --quiet
fi

# ---------------------------------------------------------------------------- #
# Professor backend                                                            #
# ---------------------------------------------------------------------------- #
if [[ -n "${PROF_ORDER:-}" ]]; then
  log_msg "4" "$TAG" "Building and tuning with Professor (order ${PROF_ORDER})."
  PROF_IPOL_OPTS=()
  PROF_TUNE_OPTS=()
  if [[ -n "${PROF2_IPOL_OPTIONS:-}" ]]; then read -ra PROF_IPOL_OPTS <<< "$PROF2_IPOL_OPTIONS"; fi
  if [[ -n "${PROF2_TUNE_OPTIONS:-}" ]]; then read -ra PROF_TUNE_OPTS <<< "$PROF2_TUNE_OPTIONS"; fi

  rm -rf Professor
  mkdir -p Professor

  IPOL="Professor/ipol.${PROF_ORDER_SAFE}.dat"
  IPOL_ERR="Professor/ipol.err.${PROF_ORDER_SAFE}.dat"
  PROF_TUNE_DIR="Professor/tune.professor.${PROF_ORDER_SAFE}.dir${DIR_INDEX}"
  PROF_TUNE_DIR_ERR="Professor/tune.professor.err.${PROF_ORDER_SAFE}.dir${DIR_INDEX}"

  run_cmd "4" "$TAG" prof2-ipol "$SCAN_DIR" "$IPOL"     --order "$PROF_ORDER" -w weights.txt --ierrs none "${PROF_IPOL_OPTS[@]}"
  run_cmd "4" "$TAG" prof2-ipol "$SCAN_DIR" "$IPOL_ERR" --order "$PROF_ORDER" -w weights.txt              "${PROF_IPOL_OPTS[@]}"
  run_cmd "4" "$TAG" prof2-tune "$IPOL"     -w weights.txt -R -o "$PROF_TUNE_DIR"     "${PROF_TUNE_OPTS[@]}"
  run_cmd "4" "$TAG" prof2-tune "$IPOL_ERR" -w weights.txt -R -o "$PROF_TUNE_DIR_ERR" "${PROF_TUNE_OPTS[@]}"
fi

log_msg "4" "$TAG" "Completed successfully."
