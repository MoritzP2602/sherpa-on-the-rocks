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

if [[ "$N_INPUT_DIRS" -lt 2 ]]; then
  log_msg "5" "$TAG" "Phase 5 requires at least two input dirs."
  exit 1
fi

DIRS=()
WEIGHTS=()
SCANS=()
REQUIRED_INPUTS=()
for idx in $(seq 1 "$N_INPUT_DIRS"); do
  DIR_VAR="INPUT_DIR_${idx}"
  REW_VAR="REWEIGHT_${idx}"
  DIRS[idx]="${!DIR_VAR}"
  WEIGHTS[idx]="${DIRS[idx]}/weights.txt"
  SCANS[idx]="${DIRS[idx]}/newscan"
  if [[ "${!REW_VAR}" == "1" ]]; then
    SCANS[idx]="${DIRS[idx]}/newscan.rew.split"
  fi
  REQUIRED_INPUTS+=("${WEIGHTS[idx]}" "${SCANS[idx]}")
done

if [[ -n "${APP_ORDER:-}" ]]; then
  APP_TUNES=()
  APP_TUNES_ERR=()
  for idx in $(seq 1 "$N_INPUT_DIRS"); do
    APP_TUNES[idx]="${DIRS[idx]}/Apprentice/tune.apprentice.${APP_ORDER_SAFE}.dir${idx}"
    APP_TUNES_ERR[idx]="${DIRS[idx]}/Apprentice/tune.apprentice.err.${APP_ORDER_SAFE}.dir${idx}"
  done
  REQUIRED_INPUTS+=("$MERGED_DIR/data.json")
  if [[ "$COMBINE_MODE" == "weighted" ]]; then
    REQUIRED_INPUTS+=("${APP_TUNES[@]}" "${APP_TUNES_ERR[@]}")
  fi
fi
if [[ -n "${PROF_ORDER:-}" ]]; then
  PROF_IPOLS=()
  PROF_IPOLS_ERR=()
  PROF_TUNES=()
  PROF_TUNES_ERR=()
  for idx in $(seq 1 "$N_INPUT_DIRS"); do
    PROF_IPOLS[idx]="${DIRS[idx]}/Professor/ipol.${PROF_ORDER_SAFE}.dat"
    PROF_IPOLS_ERR[idx]="${DIRS[idx]}/Professor/ipol.err.${PROF_ORDER_SAFE}.dat"
    PROF_TUNES[idx]="${DIRS[idx]}/Professor/tune.professor.${PROF_ORDER_SAFE}.dir${idx}"
    PROF_TUNES_ERR[idx]="${DIRS[idx]}/Professor/tune.professor.err.${PROF_ORDER_SAFE}.dir${idx}"
  done
  REQUIRED_INPUTS+=("${PROF_IPOLS[@]}" "${PROF_IPOLS_ERR[@]}")
  if [[ "$COMBINE_MODE" == "weighted" ]]; then
    REQUIRED_INPUTS+=("${PROF_TUNES[@]}" "${PROF_TUNES_ERR[@]}")
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
  APP_W_ARGS=()
  APP_WE_ARGS=()
  for idx in $(seq 1 "$N_INPUT_DIRS"); do
    if [[ "$COMBINE_MODE" == "weighted" ]]; then
      APP_W_ARGS+=("${WEIGHTS[idx]}" "${APP_TUNES[idx]}")
      APP_WE_ARGS+=("${WEIGHTS[idx]}" "${APP_TUNES_ERR[idx]}")
    else
      APP_W_ARGS+=("${WEIGHTS[idx]}" 1.0)
      APP_WE_ARGS+=("${WEIGHTS[idx]}" 1.0)
    fi
  done
  run_cmd "5" "$TAG" app-tools-combine_weights "${APP_W_ARGS[@]}"  -o "$APP_W"
  run_cmd "5" "$TAG" app-tools-combine_weights "${APP_WE_ARGS[@]}" -o "$APP_WE"

  APP_JSON="$MERGED_DIR/Apprentice/app.${APP_ORDER_SAFE}.json"
  ERR_JSON="$MERGED_DIR/Apprentice/err.${APP_ORDER_SAFE}.json"
  APP_TUNE_MERGED="$MERGED_DIR/Apprentice/tune.apprentice.${APP_ORDER_SAFE}.merged"
  APP_TUNE_MERGED_ERR="$MERGED_DIR/Apprentice/tune.apprentice.err.${APP_ORDER_SAFE}.merged"
  run_cmd "5" "$TAG" app-build "${SCANS[@]}" --order "$APP_ORDER" -w "$APP_W"         -o "$APP_JSON" "${APP_BUILD_OPTS[@]}"
  run_cmd "5" "$TAG" app-build "${SCANS[@]}" --order "$APP_ORDER" -w "$APP_WE" --errs -o "$ERR_JSON" "${APP_BUILD_OPTS[@]}"
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
  PROF_W_ARGS=()
  PROF_WE_ARGS=()
  for idx in $(seq 1 "$N_INPUT_DIRS"); do
    if [[ "$COMBINE_MODE" == "weighted" ]]; then
      PROF_W_ARGS+=("${WEIGHTS[idx]}" "${PROF_TUNES[idx]}")
      PROF_WE_ARGS+=("${WEIGHTS[idx]}" "${PROF_TUNES_ERR[idx]}")
    else
      PROF_W_ARGS+=("${WEIGHTS[idx]}" 1.0)
      PROF_WE_ARGS+=("${WEIGHTS[idx]}" 1.0)
    fi
  done
  run_cmd "5" "$TAG" app-tools-combine_weights "${PROF_W_ARGS[@]}"  -o "$PROF_W"
  run_cmd "5" "$TAG" app-tools-combine_weights "${PROF_WE_ARGS[@]}" -o "$PROF_WE"

  PROF_TUNE_MERGED="$MERGED_DIR/Professor/tune.professor.${PROF_ORDER_SAFE}.merged"
  PROF_TUNE_MERGED_ERR="$MERGED_DIR/Professor/tune.professor.err.${PROF_ORDER_SAFE}.merged"
  run_cmd "5" "$TAG" prof2-tune "${PROF_IPOLS[@]}"     -w "$PROF_W"  -R -o "$PROF_TUNE_MERGED"     "${PROF_TUNE_OPTS[@]}"
  run_cmd "5" "$TAG" prof2-tune "${PROF_IPOLS_ERR[@]}" -w "$PROF_WE" -R -o "$PROF_TUNE_MERGED_ERR" "${PROF_TUNE_OPTS[@]}"
fi

log_msg "5" "$TAG" "Completed successfully."
