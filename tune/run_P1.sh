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

PHASE_KEY="P1_dir${DIR_INDEX}"
TAG="dir${DIR_INDEX}"
log_msg "1" "$TAG" "Started."

record_phase_time "$STATE_JSON" "$PHASE_KEY" "start"
if [[ -n "$CLUSTER" ]]; then
  record_condor_id "$STATE_JSON" "$PHASE_KEY" "$CLUSTER" "$PROCESS"
fi

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"
cd "$INPUT_DIR"

CREATE_GRID_CMD=(app-tools-create_grid)
if [[ "$GRID_MODE" == "import" ]]; then
  CREATE_GRID_CMD+=(import "${INPUT_DIR_1}/newscan.grid.dat" template.yaml)
else
  CREATE_GRID_CMD+=(sample parameter.json template.yaml -n "$N_GRID")
fi
CREATE_GRID_CMD+=(--table --plots --outdir newscan --overwrite)
if [[ "$REWEIGHT" == "1" ]]; then
  CREATE_GRID_CMD+=(--nominal nominal.json)
fi

run_cmd "1" "$TAG" "${CREATE_GRID_CMD[@]}"

SPLIT_TARGET="newscan"
if [[ "$REWEIGHT" == "1" ]]; then
  SPLIT_TARGET="newscan.rew"
fi

run_cmd "1" "$TAG" bash "$SHERPA_ON_THE_ROCKS_DIR/prepare_runs.sh" "$SPLIT_TARGET" "$N_SUBRUNS"

if [[ ! -f runs.txt ]]; then
  log_msg "1" "$TAG" "Failed: prepare_runs.sh did not create runs.txt."
  exit 1
fi

record_phase_time "$STATE_JSON" "$PHASE_KEY" "end"
log_msg "1" "$TAG" "Completed successfully."
