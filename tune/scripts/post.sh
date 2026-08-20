#!/bin/bash

STATE_JSON="$1"
PHASE_KEY="$2"
RETURN_CODE="${3:-1}"
PRE_MODE="${4:-}"

if [[ "$RETURN_CODE" == "start" ]]; then
  if [[ -f "$STATE_JSON" ]]; then
    PRE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$PRE_SCRIPT_DIR/utils.sh"
    record_phase_time "$STATE_JSON" "$PHASE_KEY" "start" || true
  fi
  if [[ -z "$PRE_MODE" ]]; then
    exit 0
  fi
  PHASE_KEY="$PRE_MODE"
  RETURN_CODE=0
fi

if ! [[ "$RETURN_CODE" =~ ^-?[0-9]+$ ]]; then
  RETURN_CODE=1
fi
if [[ "$RETURN_CODE" -eq 0 ]]; then
  EXIT_CODE=0
  STATUS="SUCCESS"
else
  EXIT_CODE=1
  STATUS="FAILED"
fi

finish() {
  if [[ "$PHASE_KEY" == "init" || "$PHASE_KEY" == "resume" ]]; then
    exit 0
  fi
  # A failed Sherpa subrun must not tear down the whole tune: it is recorded as
  # FAILED above, and the next phase merges whatever YODA files were produced.
  # DAGMan takes the node's result from this script, so the job itself is free
  # to report its true exit code.
  if [[ "$PHASE_KEY" == P2_* || "$PHASE_KEY" == P11_* ]]; then
    exit 0
  fi
  exit "$EXIT_CODE"
}

if [[ ! -f "$STATE_JSON" ]]; then
  finish
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils.sh"

read_state() {
  python3 - "$STATE_JSON" "$1" <<'PY'
import json, sys
try:
    with open(sys.argv[1], encoding='utf-8') as f:
        s = json.load(f)
    print(s.get(sys.argv[2], ''))
except Exception:
    print('')
PY
}

EMAIL=$(read_state email)
DAG_CLUSTER_ID=$(read_state dag_cluster_id)
CONDOR_OUTPUT=$(read_state condor_output)
CONFIG_PATH=$(read_state config_path)

SELECTION=""
if [[ "$PHASE_KEY" == P6_* || "$PHASE_KEY" == P9_* ]]; then
  SELECTION_CODE=0
  SELECTION=$(select_repeat_winners "$STATE_JSON" "$PHASE_KEY" 2>&1) \
    || SELECTION_CODE=$?
  if [[ -n "$SELECTION" ]]; then
    mkdir -p "${CONDOR_OUTPUT}/${PHASE_KEY}" 2>/dev/null || true
    printf '%s\n' "$SELECTION" > "${CONDOR_OUTPUT}/${PHASE_KEY}/select_repeats.log" 2>/dev/null || true
    printf '%s\n' "$SELECTION"
    if [[ "$SELECTION_CODE" -ne 0 ]]; then
      EXIT_CODE=1
      STATUS="FAILED"
    elif [[ "$EXIT_CODE" -ne 0 ]]; then
      SELECTION+="
Every tune of this node kept a usable repeat, so the node counts as successful
despite the failed job(s) reported above."
      EXIT_CODE=0
      STATUS="SUCCESS"
    fi
  fi
fi

if [[ "$PHASE_KEY" != "init" && "$PHASE_KEY" != "resume" && "$EXIT_CODE" -eq 0 ]]; then
  record_phase_time "$STATE_JSON" "$PHASE_KEY" "end" || true
fi

if [[ -z "$EMAIL" ]]; then
  finish
fi

SUBJECT_BASE="TUNE - ${DAG_CLUSTER_ID:-unknown}"
MSG_ID="<tune.${DAG_CLUSTER_ID:-unknown}@$(hostname -s 2>/dev/null || echo 'rocks')>"

MAX_BYTES=102400

truncate() {
  local content="$1"
  local n
  n=$(printf '%s' "$content" | wc -c)
  if [[ "$n" -gt "$MAX_BYTES" ]]; then
    printf '[Output truncated — showing last 100 KB of %d bytes total]\n' "$n"
    printf '%s' "$content" | tail -c "$MAX_BYTES"
  else
    printf '%s' "$content"
  fi
}

if [[ "$PHASE_KEY" == "init" ]]; then
  BODY="Tune workflow started.

DAGMan cluster ID : ${DAG_CLUSTER_ID:-unknown}
Submitted at : $(date)
Config : ${CONFIG_PATH}
"
  {
    printf 'To: %s\n' "$EMAIL"
    printf 'Subject: %s\n' "$SUBJECT_BASE"
    printf 'Message-ID: %s\n' "$MSG_ID"
    printf '\n'
    printf '%s\n' "$BODY"
  } | mail -t >/dev/null 2>&1 || true
elif [[ "$PHASE_KEY" == "resume" ]]; then
  BODY="Tune workflow resumed.

DAGMan cluster ID : ${DAG_CLUSTER_ID:-unknown}
Submitted at : $(date)
Config : ${CONFIG_PATH}
"
  {
    printf 'To: %s\n' "$EMAIL"
    printf 'Subject: %s\n' "$SUBJECT_BASE"
    printf 'Message-ID: %s\n' "$MSG_ID"
    printf '\n'
    printf '%s\n' "$BODY"
  } | mail -t >/dev/null 2>&1 || true
else
  LOG_DIR="${CONDOR_OUTPUT}/${PHASE_KEY}"

  N_JOBS=0
  if compgen -G "${LOG_DIR}/job.*.out" > /dev/null 2>&1; then
    N_JOBS=$(ls -1 "${LOG_DIR}"/job.*.out 2>/dev/null | wc -l)
  fi

  # A node holding many jobs writes one overview log for all of them; summarise
  # that rather than concatenating every job output, which for the Sherpa phases
  # would be hundreds of files. A single-job node is more useful in full.
  if [[ "$N_JOBS" -gt 1 ]] && compgen -G "${LOG_DIR}/overview.*.log" > /dev/null 2>&1; then
    {
      OVERVIEW=$(cat "${LOG_DIR}"/overview.*.log 2>/dev/null || true)
      N_COMPLETE=$(printf '%s\n' "$OVERVIEW" | grep -c '^\[COMPLETE\]' || true)
      N_TIMEOUT=$(printf '%s\n'  "$OVERVIEW" | grep -c '^\[TIMEOUT\]'  || true)
      N_FAILED=$(printf '%s\n'   "$OVERVIEW" | grep -c '^\[FAILED\]'   || true)
      N_REMOVED=$(printf '%s\n'  "$OVERVIEW" | grep -c '^\[REMOVED\]'  || true)
      PROBLEM_LINES=$(printf '%s\n' "$OVERVIEW" | grep -E '^\[(TIMEOUT|FAILED|REMOVED)\]' || true)
      OUTPUT="Job summary:
  COMPLETE / TIMEOUT / FAILED / REMOVED : ${N_COMPLETE} / ${N_TIMEOUT} / ${N_FAILED} / ${N_REMOVED}
"
      if [[ -n "$PROBLEM_LINES" ]]; then
        OUTPUT+="
Jobs that did not complete:
${PROBLEM_LINES}
"
      fi
    }
  elif compgen -G "${LOG_DIR}/job.*.out" > /dev/null 2>&1; then
    OUTPUT=$(cat "${LOG_DIR}"/job.*.out 2>/dev/null || true)
  else
    OUTPUT="(no job output file found in ${LOG_DIR})"
  fi

  if compgen -G "${LOG_DIR}/job.*.err" > /dev/null 2>&1; then
    ERROR=$(cat "${LOG_DIR}"/job.*.err 2>/dev/null || true)
  else
    ERROR="(no job error output file found in ${LOG_DIR})"
  fi

  OUTPUT=$(truncate "$OUTPUT")
  ERROR=$(truncate "$ERROR")

  BODY="${PHASE_KEY} finished with return code ${RETURN_CODE} [${STATUS}]."
  if [[ "$EXIT_CODE" -ne 0 ]]; then
    BODY+="
Dependent nodes will be skipped; resume the tune with tune.py after fixing the problem."
  fi
  BODY+="

--- OUTPUT ---
${OUTPUT}"
  if [[ -n "$SELECTION" ]]; then
    BODY+="

--- REPEAT SELECTION ---
${SELECTION}"
  fi
  if [[ "$EXIT_CODE" -ne 0 ]]; then
    BODY+="

--- ERROR OUTPUT ---
${ERROR}"
  fi
  {
    printf 'To: %s\n' "$EMAIL"
    printf 'Subject: RE: %s\n' "$SUBJECT_BASE"
    printf 'In-Reply-To: %s\n' "$MSG_ID"
    printf 'References: %s\n' "$MSG_ID"
    printf '\n'
    printf '%s\n' "$BODY"
  } | mail -t >/dev/null 2>&1 || true
fi

finish
