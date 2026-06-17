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

PHASE_KEY="P6_dir${DIR_INDEX}"
TAG="dir${DIR_INDEX}"
log_msg "6" "$TAG" "Started."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"

REQUIRED_INPUTS=("$INPUT_DIR"
                 "$INPUT_DIR/template.yaml"
                 "$SHERPA_ON_THE_ROCKS_DIR/prepare_runs.sh")
if [[ "${VALIDATION_REWEIGHT:-0}" == "1" ]]; then
  REQUIRED_INPUTS+=("$INPUT_DIR/nominal.json")
fi
if [[ "${VALIDATION_ONLY_MERGED:-0}" != "1" ]]; then
  if [[ "${VALIDATION_ONLY_ERR:-0}" == "1" ]]; then
    REQUIRED_INPUTS+=("$INPUT_DIR/tune.err.${SURROGATE_ORDER_SAFE}.dir${DIR_INDEX}")
  else
    REQUIRED_INPUTS+=("$INPUT_DIR/tune.${SURROGATE_ORDER_SAFE}.dir${DIR_INDEX}"
                      "$INPUT_DIR/tune.err.${SURROGATE_ORDER_SAFE}.dir${DIR_INDEX}")
  fi
fi
if [[ "$N_INPUT_DIRS" == "2" ]]; then
  if [[ "${VALIDATION_ONLY_ERR:-0}" == "1" ]]; then
    REQUIRED_INPUTS+=("$MERGED_DIR/tune.err.${SURROGATE_ORDER_SAFE}.merged")
  else
    REQUIRED_INPUTS+=("$MERGED_DIR/tune.${SURROGATE_ORDER_SAFE}.merged"
                      "$MERGED_DIR/tune.err.${SURROGATE_ORDER_SAFE}.merged")
  fi
fi
require_inputs "6" "$TAG" "${REQUIRED_INPUTS[@]}"

cd "$INPUT_DIR"

PREFIX_ARGS=()
if [[ "${VALIDATION_ONLY_ERR:-0}" == "1" ]]; then
  PREFIX_ARGS=(--tune-prefix tune.err)
fi

if [[ "${VALIDATION_ONLY_MERGED:-0}" != "1" ]]; then
  CREATE_VALIDATION_GRID_CMD=(app-tools-create_grid tune "." template.yaml --outdir validation "${PREFIX_ARGS[@]}")
  if [[ "${VALIDATION_REWEIGHT:-0}" == "1" ]]; then
    CREATE_VALIDATION_GRID_CMD+=(--nominal nominal.json)
  fi
  run_cmd "6" "$TAG" "${CREATE_VALIDATION_GRID_CMD[@]}"
fi

if [[ "$N_INPUT_DIRS" == "2" ]]; then
  MERGED_VALIDATION_GRID_CMD=(app-tools-create_grid tune "$MERGED_DIR" template.yaml --outdir validation "${PREFIX_ARGS[@]}")
  if [[ "${VALIDATION_REWEIGHT:-0}" == "1" ]]; then
    MERGED_VALIDATION_GRID_CMD+=(--nominal nominal.json)
  fi
  run_cmd "6" "$TAG" "${MERGED_VALIDATION_GRID_CMD[@]}"
fi

run_cmd "6" "$TAG" bash "$SHERPA_ON_THE_ROCKS_DIR/prepare_runs.sh" validation "$N_VAL_SUBRUNS" --quiet

if [[ ! -f runs.txt ]]; then
  log_msg "6" "$TAG" "Failed: prepare_runs.sh did not create runs.txt."
  exit 1
fi

log_msg "6" "$TAG" "Completed successfully."
