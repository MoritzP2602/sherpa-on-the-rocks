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

require_backend_tunes() {
  local root="$1" folder="$2" name="$3" safe="$4" suffix="$5"
  if [[ "${VALIDATION_ONLY_ERR:-0}" == "1" ]]; then
    REQUIRED_INPUTS+=("$root/$folder/${name}.err.${safe}.${suffix}")
  else
    REQUIRED_INPUTS+=("$root/$folder/${name}.${safe}.${suffix}"
                      "$root/$folder/${name}.err.${safe}.${suffix}")
  fi
}

add_validation_grid() {
  local root="$1" folder="$2" name="$3"
  local prefix="$name"
  if [[ "${VALIDATION_ONLY_ERR:-0}" == "1" ]]; then
    prefix="${name}.err"
  fi
  local cmd=(app-tools-create_grid tune "$root/$folder" template.yaml --outdir validation --tune-prefix "$prefix")
  run_cmd "6" "$TAG" "${cmd[@]}"
}

REQUIRED_INPUTS=("$INPUT_DIR"
                 "$INPUT_DIR/template.yaml"
                 "$SHERPA_ON_THE_ROCKS_DIR/prepare_runs.sh")
if [[ "${VALIDATION_ONLY_MERGED:-0}" != "1" ]]; then
  if [[ -n "${APP_ORDER:-}" ]]; then
    require_backend_tunes "$INPUT_DIR" Apprentice tune.apprentice "$APP_ORDER_SAFE" "dir${DIR_INDEX}"
  fi
  if [[ -n "${PROF_ORDER:-}" ]]; then
    require_backend_tunes "$INPUT_DIR" Professor tune.professor "$PROF_ORDER_SAFE" "dir${DIR_INDEX}"
  fi
fi
if [[ "$N_INPUT_DIRS" == "2" ]]; then
  if [[ -n "${APP_ORDER:-}" ]]; then
    require_backend_tunes "$MERGED_DIR" Apprentice tune.apprentice "$APP_ORDER_SAFE" merged
  fi
  if [[ -n "${PROF_ORDER:-}" ]]; then
    require_backend_tunes "$MERGED_DIR" Professor tune.professor "$PROF_ORDER_SAFE" merged
  fi
fi
require_inputs "6" "$TAG" "${REQUIRED_INPUTS[@]}"

cd "$INPUT_DIR"
rm -rf validation

if [[ "${VALIDATION_ONLY_MERGED:-0}" != "1" ]]; then
  if [[ -n "${APP_ORDER:-}" ]]; then add_validation_grid "$INPUT_DIR" Apprentice tune.apprentice; fi
  if [[ -n "${PROF_ORDER:-}" ]]; then add_validation_grid "$INPUT_DIR" Professor tune.professor; fi
fi

if [[ "$N_INPUT_DIRS" == "2" ]]; then
  if [[ -n "${APP_ORDER:-}" ]]; then add_validation_grid "$MERGED_DIR" Apprentice tune.apprentice; fi
  if [[ -n "${PROF_ORDER:-}" ]]; then add_validation_grid "$MERGED_DIR" Professor tune.professor; fi
fi

run_cmd "6" "$TAG" bash "$SHERPA_ON_THE_ROCKS_DIR/prepare_runs.sh" validation "$N_VAL_SUBRUNS" --quiet

if [[ ! -f runs.txt ]]; then
  log_msg "6" "$TAG" "Failed: prepare_runs.sh did not create runs.txt."
  exit 1
fi

log_msg "6" "$TAG" "Completed successfully."
