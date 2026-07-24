#!/bin/bash
set -euo pipefail

STATE_JSON="$1"
CLUSTER="${2:-}"
PROCESS="${3:-}"
PHASE_LOG_DIR="${4:-}"
TUNE_MODE="${5:-}"      # "" = run everything in this job, or: app / prof
TUNE_ORDER="${6:-}"     # single surrogate order for split subjobs, e.g. 2,0 or 3

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
  PHASE_KEY="P5${TUNE_MODE:+_${TUNE_MODE}}${TUNE_ORDER:+_${TUNE_ORDER//,/_}}"
fi
TAG=""
if [[ "$PHASE_KEY" != "P5" ]]; then
  TAG="${PHASE_KEY#P5_}"
fi
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

SEL_APP_ORDERS=""
SEL_PROF_ORDERS=""
case "$TUNE_MODE" in
  "")   SEL_APP_ORDERS="${APP_ORDERS:-}"; SEL_PROF_ORDERS="${PROF_ORDERS:-}" ;;
  app|prof)
        if [[ -z "$TUNE_ORDER" ]]; then
          log_msg "5" "$TAG" "ERROR: tune mode '$TUNE_MODE' requires a surrogate order."
          exit 1
        fi
        if [[ "$TUNE_MODE" == "app" ]]; then SEL_APP_ORDERS="$TUNE_ORDER"; else SEL_PROF_ORDERS="$TUNE_ORDER"; fi ;;
  *)    log_msg "5" "$TAG" "ERROR: unknown tune mode '$TUNE_MODE'."
        exit 1 ;;
esac

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
require_inputs "5" "$TAG" "${REQUIRED_INPUTS[@]}"

mkdir -p "$MERGED_DIR"

APP_BUILD_OPTS=()
APP_TUNE2_OPTS=()
if [[ -n "${APP_BUILD_OPTIONS:-}" ]]; then read -ra APP_BUILD_OPTS <<< "$APP_BUILD_OPTIONS"; fi
if [[ -n "${APP_TUNE2_OPTIONS:-}" ]]; then read -ra APP_TUNE2_OPTS <<< "$APP_TUNE2_OPTIONS"; fi
PROF_TUNE_OPTS=()
if [[ -n "${PROF2_TUNE_OPTIONS:-}" ]]; then read -ra PROF_TUNE_OPTS <<< "$PROF2_TUNE_OPTIONS"; fi

# ---------------------------------------------------------------------------- #
# Apprentice backend                                                           #
# ---------------------------------------------------------------------------- #
run_apprentice_merged_order() {
  local order="$1"
  local safe="${order//,/_}"
  local idx
  log_msg "5" "$TAG" "Combining and tuning with Apprentice (order ${order})."

  local app_tunes=()
  local app_tunes_err=()
  for idx in $(seq 1 "$N_INPUT_DIRS"); do
    app_tunes[idx]="${DIRS[idx]}/Apprentice/tune.apprentice.${safe}.dir${idx}"
    app_tunes_err[idx]="${DIRS[idx]}/Apprentice/tune.apprentice.err.${safe}.dir${idx}"
  done
  local required=("$MERGED_DIR/data.json")
  if [[ "$COMBINE_MODE" == "weighted" ]]; then
    required+=("${app_tunes[@]}" "${app_tunes_err[@]}")
  elif [[ "$COMBINE_MODE" == "custom" ]]; then
    required+=("$MERGED_DIR/custom.weights.txt")
  fi
  require_inputs "5" "$TAG" "${required[@]}"

  mkdir -p "$MERGED_DIR/Apprentice"
  local app_w="$MERGED_DIR/Apprentice/weights.${safe}.txt"
  local app_we="$MERGED_DIR/Apprentice/err.weights.${safe}.txt"
  local app_json="$MERGED_DIR/Apprentice/app.${safe}.json"
  local err_json="$MERGED_DIR/Apprentice/err.${safe}.json"
  local tune_merged="$MERGED_DIR/Apprentice/tune.apprentice.${safe}.merged"
  local tune_merged_err="$MERGED_DIR/Apprentice/tune.apprentice.err.${safe}.merged"
  rm -rf "$app_w" "$app_we" "$app_json" "$err_json" "$tune_merged" "$tune_merged_err"

  if [[ "$COMBINE_MODE" == "custom" ]]; then
    log_msg "5" "$TAG" "Using custom merged weights: $MERGED_DIR/custom.weights.txt"
    cp "$MERGED_DIR/custom.weights.txt" "$app_w"
    cp "$MERGED_DIR/custom.weights.txt" "$app_we"
  else
    local app_w_args=()
    local app_we_args=()
    for idx in $(seq 1 "$N_INPUT_DIRS"); do
      if [[ "$COMBINE_MODE" == "weighted" ]]; then
        app_w_args+=("${WEIGHTS[idx]}" "${app_tunes[idx]}")
        app_we_args+=("${WEIGHTS[idx]}" "${app_tunes_err[idx]}")
      else
        app_w_args+=("${WEIGHTS[idx]}" 1.0)
        app_we_args+=("${WEIGHTS[idx]}" 1.0)
      fi
    done
    run_cmd "5" "$TAG" app-tools-combine_weights "${app_w_args[@]}"  -o "$app_w"
    run_cmd "5" "$TAG" app-tools-combine_weights "${app_we_args[@]}" -o "$app_we"
  fi

  run_cmd "5" "$TAG" app-build "${SCANS[@]}" --order "$order" -w "$app_w"         -o "$app_json" "${APP_BUILD_OPTS[@]}"
  run_cmd "5" "$TAG" app-build "${SCANS[@]}" --order "$order" -w "$app_we" --errs -o "$err_json" "${APP_BUILD_OPTS[@]}"
  run_cmd "5" "$TAG" app-tune2 "$app_w"  "$MERGED_DIR/data.json" "$app_json"                -o "$tune_merged"     "${APP_TUNE2_OPTS[@]}"
  run_cmd "5" "$TAG" app-tune2 "$app_we" "$MERGED_DIR/data.json" "$app_json" -e "$err_json" -o "$tune_merged_err" "${APP_TUNE2_OPTS[@]}"
}

# ---------------------------------------------------------------------------- #
# Professor backend                                                            #
# ---------------------------------------------------------------------------- #
run_professor_merged_order() {
  local order="$1"
  local safe="$order"
  local idx
  log_msg "5" "$TAG" "Combining and tuning with Professor (order ${order})."

  local prof_ipols=()
  local prof_ipols_err=()
  local prof_tunes=()
  local prof_tunes_err=()
  for idx in $(seq 1 "$N_INPUT_DIRS"); do
    prof_ipols[idx]="${DIRS[idx]}/Professor/ipol.${safe}.dat"
    prof_ipols_err[idx]="${DIRS[idx]}/Professor/ipol.err.${safe}.dat"
    prof_tunes[idx]="${DIRS[idx]}/Professor/tune.professor.${safe}.dir${idx}"
    prof_tunes_err[idx]="${DIRS[idx]}/Professor/tune.professor.err.${safe}.dir${idx}"
  done
  local required=("${prof_ipols[@]}" "${prof_ipols_err[@]}")
  if [[ "$COMBINE_MODE" == "weighted" ]]; then
    required+=("${prof_tunes[@]}" "${prof_tunes_err[@]}")
  elif [[ "$COMBINE_MODE" == "custom" ]]; then
    required+=("$MERGED_DIR/custom.weights.txt")
  fi
  require_inputs "5" "$TAG" "${required[@]}"

  mkdir -p "$MERGED_DIR/Professor"
  local prof_w="$MERGED_DIR/Professor/weights.${safe}.txt"
  local prof_we="$MERGED_DIR/Professor/err.weights.${safe}.txt"
  local tune_merged="$MERGED_DIR/Professor/tune.professor.${safe}.merged"
  local tune_merged_err="$MERGED_DIR/Professor/tune.professor.err.${safe}.merged"
  rm -rf "$prof_w" "$prof_we" "$tune_merged" "$tune_merged_err"

  if [[ "$COMBINE_MODE" == "custom" ]]; then
    log_msg "5" "$TAG" "Using custom merged weights: $MERGED_DIR/custom.weights.txt"
    cp "$MERGED_DIR/custom.weights.txt" "$prof_w"
    cp "$MERGED_DIR/custom.weights.txt" "$prof_we"
  else
    local prof_w_args=()
    local prof_we_args=()
    for idx in $(seq 1 "$N_INPUT_DIRS"); do
      if [[ "$COMBINE_MODE" == "weighted" ]]; then
        prof_w_args+=("${WEIGHTS[idx]}" "${prof_tunes[idx]}")
        prof_we_args+=("${WEIGHTS[idx]}" "${prof_tunes_err[idx]}")
      else
        prof_w_args+=("${WEIGHTS[idx]}" 1.0)
        prof_we_args+=("${WEIGHTS[idx]}" 1.0)
      fi
    done
    run_cmd "5" "$TAG" app-tools-combine_weights "${prof_w_args[@]}"  -o "$prof_w"
    run_cmd "5" "$TAG" app-tools-combine_weights "${prof_we_args[@]}" -o "$prof_we"
  fi

  run_cmd "5" "$TAG" prof2-tune "${prof_ipols[@]}"     -w "$prof_w"  -R -o "$tune_merged"     "${PROF_TUNE_OPTS[@]}"
  run_cmd "5" "$TAG" prof2-tune "${prof_ipols_err[@]}" -w "$prof_we" -R -o "$tune_merged_err" "${PROF_TUNE_OPTS[@]}"
}

# Non-split jobs own the whole backend folder and start fresh; split subjobs
# share it with parallel subjobs and only replace their own order's artifacts.
if [[ -z "$TUNE_MODE" ]]; then
  if [[ -n "$SEL_APP_ORDERS" ]];  then rm -rf "$MERGED_DIR/Apprentice"; fi
  if [[ -n "$SEL_PROF_ORDERS" ]]; then rm -rf "$MERGED_DIR/Professor";  fi
fi
for order in $SEL_APP_ORDERS;  do run_apprentice_merged_order "$order"; done
for order in $SEL_PROF_ORDERS; do run_professor_merged_order  "$order"; done

log_msg "5" "$TAG" "Completed successfully."
