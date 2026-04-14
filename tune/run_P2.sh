#!/bin/bash
set -euo pipefail

STATE_JSON="$1"
DIR_INDEX="$2"
CLUSTER="${3:-}"
PROCESS="${4:-}"
PHASE_LOG_DIR="${5:-}"
DIRECTORY="${6:-}"
RUN_BASE_DIR="${7:-}"
MAXRUNTIME="${8:-86400}"
PHASE_KEY="${9:-P2}"

if [[ -n "$RUN_BASE_DIR" && "$DIRECTORY" != /* ]]; then
  DIRECTORY="${RUN_BASE_DIR%/}/$DIRECTORY"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

load_global_state "$STATE_JSON"
load_dir_state "$STATE_JSON" "$DIR_INDEX"

SHERPA_BINARY="$(realpath "${SHERPA_BINARY/#\~/$HOME}")"

STATUS_LOG=""
if [[ -n "$PHASE_LOG_DIR" ]]; then
  mkdir -p "$PHASE_LOG_DIR"
  PHASE_LOG_DIR=$(realpath "$PHASE_LOG_DIR")
  STATUS_LOG="$PHASE_LOG_DIR/overview.${CLUSTER}.log"
fi
if [[ -n "$PHASE_LOG_DIR" && -n "$CLUSTER" && -n "$PROCESS" ]]; then
  setup_tmp_logging "$PHASE_LOG_DIR" "$CLUSTER" "$PROCESS"
fi
if [[ -n "$STATE_JSON" && -n "$DIR_INDEX" ]]; then
  record_phase_time "$STATE_JSON" "${PHASE_KEY}_dir${DIR_INDEX}" "start"
  if [[ -n "$CLUSTER" ]]; then
    record_condor_id "$STATE_JSON" "${PHASE_KEY}_dir${DIR_INDEX}" "$CLUSTER" "$PROCESS"
  fi
fi

if [[ -z "$DIRECTORY" ]]; then
  echo "ERROR: Run directory argument is missing."
  exit 1
fi

get_last_event_count() {
  if [[ -z "${OUTFILE:-}" || ! -f "$OUTFILE" ]]; then
    echo "unknown"
    return
  fi
  local last_event
  last_event=$(grep -Eo 'Event[[:space:]]+[0-9]+' "$OUTFILE" | awk '{print $2}' | tail -n 1 || true)
  if [[ -n "$last_event" ]]; then
    echo "$last_event"
  else
    echo "unknown"
  fi
}

cleanup() {
  if [[ "${CLEANUP_DONE:-0}" -eq 1 ]]; then
    return
  fi
  CLEANUP_DONE=1
  echo ""
  if [[ -f "$TMPDIR/Analysis.yoda.gz" && -d "$OUTDIR" ]]; then
    if cp -f "$TMPDIR/Analysis.yoda.gz" "$OUTDIR/$YODA" 2>/dev/null; then
      echo "Successfully copied Analysis.yoda.gz to $OUTDIR/$YODA"
    else
      echo "Warning: Failed to copy Analysis.yoda.gz"
    fi
  else
    echo "Warning: Analysis.yoda.gz not found"
  fi
  cleanup_tmp_logging
}
trap cleanup EXIT SIGTERM SIGINT SIGQUIT

start_epoch=$(date +%s)
echo "Job ${CLUSTER}.${PROCESS} started on $(hostname)"
echo ""

INTEGRATION_RESULTS=""
HAS_RESULTS=false

SEARCH_DIRS=()
if [[ -n "$RUN_BASE_DIR" ]]; then
  SEARCH_DIRS+=("$RUN_BASE_DIR/init" "$RUN_BASE_DIR")
fi

for d in "${SEARCH_DIRS[@]}"; do
  if [[ -d "$d" && -d "$d/Process" ]]; then
    INTEGRATION_RESULTS="$(realpath "$d")"
    if ls "$d"/Results.zip* >/dev/null 2>&1; then
      HAS_RESULTS=true
    fi
    break
  fi
done

if [[ -z "$INTEGRATION_RESULTS" ]]; then
  echo "ERROR: No Process directory found!"
  exit 1
fi

if [[ "$HAS_RESULTS" == false ]]; then
  echo "WARNING: No integration results (Results.zip*) found!"
  echo "WARNING: Integration might be performed for each run on the node."
  echo ""
fi

if [[ ! -d "$DIRECTORY" ]]; then
  echo "ERROR: Run directory $DIRECTORY not found!"
  exit 1
fi

YAML_FILE=$(find "$DIRECTORY" -maxdepth 1 -name "*.yaml" | head -n 1)
if [[ -z "$YAML_FILE" ]]; then
  YAML_FILE=$(find "$DIRECTORY/.." -maxdepth 1 -name "*.yaml" | head -n 1)
fi
if [[ -z "$YAML_FILE" ]]; then
  echo "ERROR: No YAML file found!"
  exit 1
fi

YAML=$(realpath "$YAML_FILE")
OUTDIR=$(realpath "$DIRECTORY")
YODA_BASENAME=$(basename "$DIRECTORY")
YODA="$YODA_BASENAME.yoda.gz"
SEED=$(od -An -N4 -tu4 < /dev/urandom | tr -d ' ')

echo "SHERPA_BINARY       : $SHERPA_BINARY"
echo "INTEGRATION_RESULTS : $INTEGRATION_RESULTS"
echo "YAML                : $YAML"
echo "YODA                : $YODA"
echo "OUTDIR              : $OUTDIR"
echo "PHASE_LOG_DIR              : $PHASE_LOG_DIR"
echo "SEED                : $SEED"
echo "MAXRUNTIME          : $MAXRUNTIME seconds"
echo ""

DESIRED_WALL_TIME_1=$((MAXRUNTIME * 3 / 2))
DESIRED_WALL_TIME_2=$((MAXRUNTIME + 86400))
if [[ $DESIRED_WALL_TIME_1 -le $DESIRED_WALL_TIME_2 ]]; then
  DESIRED_WALL_TIME=$DESIRED_WALL_TIME_1
else
  DESIRED_WALL_TIME=$DESIRED_WALL_TIME_2
fi

if [[ "$MAXRUNTIME" -le 3600 ]]; then
  QUEUE_LIMIT=3600
elif [[ "$MAXRUNTIME" -le 86400 ]]; then
  QUEUE_LIMIT=86400
else
  QUEUE_LIMIT=$((28 * 86400))
fi

if [[ $DESIRED_WALL_TIME -le $QUEUE_LIMIT ]]; then
  WALL_TIME_LIMIT=$DESIRED_WALL_TIME
else
  WALL_TIME_LIMIT=$QUEUE_LIMIT
fi

TIMEOUT=$((WALL_TIME_LIMIT - 120))
echo "SHERPA will be terminated after $TIMEOUT seconds."
echo ""

cp -r "$INTEGRATION_RESULTS/Process" "$TMPDIR"
if [[ "$HAS_RESULTS" == true ]]; then
  cp -r "$INTEGRATION_RESULTS"/Results.zip* "$TMPDIR"
fi

cd "$TMPDIR"

timeout -s TERM "$TIMEOUT" "$SHERPA_BINARY" -f "$YAML" -R "$SEED" || {
  exit_code=$?
  last_event=$(get_last_event_count)
  if [[ $exit_code -eq 124 ]]; then
    if [[ -n "$STATUS_LOG" ]]; then
      {
        flock -x 200
        printf "[TIMEOUT] %s.%s | DIR: %s | EVENTS: %s | Timeout: %ss\n" "$CLUSTER" "$PROCESS" "$OUTDIR" "$last_event" "$TIMEOUT" >> "$STATUS_LOG"
      } 200>"$STATUS_LOG.lock"
      rm -f "$STATUS_LOG.lock"
    fi
    if [[ -n "$STATE_JSON" && -n "$DIR_INDEX" ]]; then
      record_phase_time "$STATE_JSON" "${PHASE_KEY}_dir${DIR_INDEX}" "end"
    fi
    exit 0
  else
    if [[ -n "$STATUS_LOG" ]]; then
      {
        flock -x 200
        printf "[FAILED] %s.%s | DIR: %s | EVENTS: %s | Exit code: %s\n" "$CLUSTER" "$PROCESS" "$OUTDIR" "$last_event" "$exit_code" >> "$STATUS_LOG"
      } 200>"$STATUS_LOG.lock"
      rm -f "$STATUS_LOG.lock"
    fi
    if [[ -n "$STATE_JSON" && -n "$DIR_INDEX" ]]; then
      record_phase_time "$STATE_JSON" "${PHASE_KEY}_dir${DIR_INDEX}" "end"
    fi
    exit 0
  fi
}

end_epoch=$(date +%s)
elapsed=$(( end_epoch - start_epoch ))
if [[ -n "$STATUS_LOG" ]]; then
  {
    flock -x 200
    printf "[COMPLETE] %s.%s | DIR: %s | ELAPSED: %ss\n" "$CLUSTER" "$PROCESS" "$OUTDIR" "$elapsed" >> "$STATUS_LOG"
  } 200>"$STATUS_LOG.lock"
  rm -f "$STATUS_LOG.lock"
fi
if [[ -n "$STATE_JSON" && -n "$DIR_INDEX" ]]; then
  record_phase_time "$STATE_JSON" "${PHASE_KEY}_dir${DIR_INDEX}" "end"
fi
