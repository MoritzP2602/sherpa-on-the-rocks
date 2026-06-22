#!/bin/bash
set -euo pipefail

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
log_msg "5" "$TAG" "Started."

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

SCAN1="$DIR1/newscan"
SCAN2="$DIR2/newscan"
if [[ "$REWEIGHT_1" == "1" ]]; then
  SCAN1="$DIR1/newscan.rew.split"
fi
if [[ "$REWEIGHT_2" == "1" ]]; then
  SCAN2="$DIR2/newscan.rew.split"
fi

REQUIRED_INPUTS=("$DIR1/weights.txt"
                 "$DIR2/weights.txt"
                 "$SCAN1"
                 "$SCAN2")

if [[ -n "${APP_ORDER:-}" ]]; then
  APP_TUNE1="$DIR1/Apprentice/tune.apprentice.${APP_ORDER_SAFE}.dir1"
  APP_TUNE2="$DIR2/Apprentice/tune.apprentice.${APP_ORDER_SAFE}.dir2"
  APP_TUNE1_ERR="$DIR1/Apprentice/tune.apprentice.err.${APP_ORDER_SAFE}.dir1"
  APP_TUNE2_ERR="$DIR2/Apprentice/tune.apprentice.err.${APP_ORDER_SAFE}.dir2"
  REQUIRED_INPUTS+=("$MERGED_DIR/data.json")
  if [[ "$COMBINE_MODE" == "weighted" ]]; then
    REQUIRED_INPUTS+=("$APP_TUNE1" "$APP_TUNE2" "$APP_TUNE1_ERR" "$APP_TUNE2_ERR")
  fi
fi
if [[ -n "${PROF_ORDER:-}" ]]; then
  PROF_IPOL1="$DIR1/Professor/ipol.${PROF_ORDER_SAFE}.dat"
  PROF_IPOL2="$DIR2/Professor/ipol.${PROF_ORDER_SAFE}.dat"
  PROF_IPOL1_ERR="$DIR1/Professor/ipol.err.${PROF_ORDER_SAFE}.dat"
  PROF_IPOL2_ERR="$DIR2/Professor/ipol.err.${PROF_ORDER_SAFE}.dat"
  PROF_TUNE1="$DIR1/Professor/tune.professor.${PROF_ORDER_SAFE}.dir1"
  PROF_TUNE2="$DIR2/Professor/tune.professor.${PROF_ORDER_SAFE}.dir2"
  PROF_TUNE1_ERR="$DIR1/Professor/tune.professor.err.${PROF_ORDER_SAFE}.dir1"
  PROF_TUNE2_ERR="$DIR2/Professor/tune.professor.err.${PROF_ORDER_SAFE}.dir2"
  REQUIRED_INPUTS+=("$PROF_IPOL1" "$PROF_IPOL2" "$PROF_IPOL1_ERR" "$PROF_IPOL2_ERR")
  if [[ "$COMBINE_MODE" == "weighted" ]]; then
    REQUIRED_INPUTS+=("$PROF_TUNE1" "$PROF_TUNE2" "$PROF_TUNE1_ERR" "$PROF_TUNE2_ERR")
  fi
fi
require_inputs "5" "$TAG" "${REQUIRED_INPUTS[@]}"

mkdir -p "$MERGED_DIR"

# ---------------------------------------------------------------------------- #
# Apprentice backend                                                           #
# ---------------------------------------------------------------------------- #
if [[ -n "${APP_ORDER:-}" ]]; then
  log_msg "5" "$TAG" "Combining and tuning with Apprentice (order ${APP_ORDER})."
  APP_BUILD_OPTS=()
  APP_TUNE2_OPTS=()
  if [[ -n "${APP_BUILD_OPTIONS:-}" ]]; then read -ra APP_BUILD_OPTS <<< "$APP_BUILD_OPTIONS"; fi
  if [[ -n "${APP_TUNE2_OPTIONS:-}" ]]; then read -ra APP_TUNE2_OPTS <<< "$APP_TUNE2_OPTIONS"; fi

  rm -rf "$MERGED_DIR/Apprentice"
  mkdir -p "$MERGED_DIR/Apprentice"
  APP_W="$MERGED_DIR/Apprentice/weights.txt"
  APP_WE="$MERGED_DIR/Apprentice/err.weights.txt"
  if [[ "$COMBINE_MODE" == "weighted" ]]; then
    run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" "$APP_TUNE1"     "$DIR2/weights.txt" "$APP_TUNE2"     -o "$APP_W"
    run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" "$APP_TUNE1_ERR" "$DIR2/weights.txt" "$APP_TUNE2_ERR" -o "$APP_WE"
  else
    run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" 1.0 "$DIR2/weights.txt" 1.0 -o "$APP_W"
    run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" 1.0 "$DIR2/weights.txt" 1.0 -o "$APP_WE"
  fi

  APP_JSON="$MERGED_DIR/Apprentice/app.${APP_ORDER_SAFE}.json"
  ERR_JSON="$MERGED_DIR/Apprentice/err.${APP_ORDER_SAFE}.json"
  APP_TUNE_MERGED="$MERGED_DIR/Apprentice/tune.apprentice.${APP_ORDER_SAFE}.merged"
  APP_TUNE_MERGED_ERR="$MERGED_DIR/Apprentice/tune.apprentice.err.${APP_ORDER_SAFE}.merged"
  run_cmd "5" "$TAG" app-build "$SCAN1" "$SCAN2" --order "$APP_ORDER" -w "$APP_W"         -o "$APP_JSON" "${APP_BUILD_OPTS[@]}"
  run_cmd "5" "$TAG" app-build "$SCAN1" "$SCAN2" --order "$APP_ORDER" -w "$APP_WE" --errs -o "$ERR_JSON" "${APP_BUILD_OPTS[@]}"
  run_cmd "5" "$TAG" app-tune2 "$APP_W"  "$MERGED_DIR/data.json" "$APP_JSON"                -o "$APP_TUNE_MERGED"     "${APP_TUNE2_OPTS[@]}"
  run_cmd "5" "$TAG" app-tune2 "$APP_WE" "$MERGED_DIR/data.json" "$APP_JSON" -e "$ERR_JSON" -o "$APP_TUNE_MERGED_ERR" "${APP_TUNE2_OPTS[@]}"
fi

# ---------------------------------------------------------------------------- #
# Professor backend                                                            #
# ---------------------------------------------------------------------------- #
if [[ -n "${PROF_ORDER:-}" ]]; then
  log_msg "5" "$TAG" "Combining and tuning with Professor (order ${PROF_ORDER})."
  PROF_TUNE_OPTS=()
  if [[ -n "${PROF2_TUNE_OPTIONS:-}" ]]; then read -ra PROF_TUNE_OPTS <<< "$PROF2_TUNE_OPTIONS"; fi

  rm -rf "$MERGED_DIR/Professor"
  mkdir -p "$MERGED_DIR/Professor"
  PROF_W="$MERGED_DIR/Professor/weights.txt"
  PROF_WE="$MERGED_DIR/Professor/err.weights.txt"
  if [[ "$COMBINE_MODE" == "weighted" ]]; then
    run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" "$PROF_TUNE1"     "$DIR2/weights.txt" "$PROF_TUNE2"     -o "$PROF_W"
    run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" "$PROF_TUNE1_ERR" "$DIR2/weights.txt" "$PROF_TUNE2_ERR" -o "$PROF_WE"
  else
    run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" 1.0 "$DIR2/weights.txt" 1.0 -o "$PROF_W"
    run_cmd "5" "$TAG" app-tools-combine_weights "$DIR1/weights.txt" 1.0 "$DIR2/weights.txt" 1.0 -o "$PROF_WE"
  fi

  PROF_TUNE_MERGED="$MERGED_DIR/Professor/tune.professor.${PROF_ORDER_SAFE}.merged"
  PROF_TUNE_MERGED_ERR="$MERGED_DIR/Professor/tune.professor.err.${PROF_ORDER_SAFE}.merged"
  run_cmd "5" "$TAG" prof2-tune "$PROF_IPOL1"     "$PROF_IPOL2"     -w "$PROF_W"  -R -o "$PROF_TUNE_MERGED"     "${PROF_TUNE_OPTS[@]}"
  run_cmd "5" "$TAG" prof2-tune "$PROF_IPOL1_ERR" "$PROF_IPOL2_ERR" -w "$PROF_WE" -R -o "$PROF_TUNE_MERGED_ERR" "${PROF_TUNE_OPTS[@]}"
fi

log_msg "5" "$TAG" "Completed successfully."
