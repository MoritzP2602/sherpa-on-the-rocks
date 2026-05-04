#!/bin/bash

STATE_JSON="$1"
PHASE_KEY="$2"
RETURN_CODE="$3"

trap 'exit 0' EXIT ERR

if [[ ! -f "$STATE_JSON" ]]; then
  exit 0
fi

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

if [[ -z "$EMAIL" ]]; then
  exit 0
fi

SUBJECT_BASE="Tune ${DAG_CLUSTER_ID:-unknown}"
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
Submitted at      : $(date)
Config            : ${CONFIG_PATH}
"
  printf '%s\n' "$BODY" | mail \
    -s "$SUBJECT_BASE" \
    -C "Message-ID: ${MSG_ID}" \
    "$EMAIL" >/dev/null 2>&1
else
  LOG_DIR="${CONDOR_OUTPUT}/${PHASE_KEY}"

  if [[ "$PHASE_KEY" == P2_* || "$PHASE_KEY" == P7_* ]]; then
    if compgen -G "${LOG_DIR}/overview.*.log" > /dev/null 2>&1; then
      OUTPUT=$(cat "${LOG_DIR}"/overview.*.log 2>/dev/null || true)
    else
      OUTPUT="(no overview log found in ${LOG_DIR})"
    fi
  else
    if compgen -G "${LOG_DIR}/job.*.out" > /dev/null 2>&1; then
      OUTPUT=$(cat "${LOG_DIR}"/job.*.out 2>/dev/null || true)
    else
      OUTPUT="(no job output found in ${LOG_DIR})"
    fi
  fi

  OUTPUT=$(truncate "$OUTPUT")

  BODY="Phase ${PHASE_KEY} finished with return code ${RETURN_CODE}.

--- Output ---
${OUTPUT}"

  printf '%s\n' "$BODY" | mail \
    -s "RE: $SUBJECT_BASE" \
    -C "In-Reply-To: ${MSG_ID}" \
    -C "References: ${MSG_ID}" \
    "$EMAIL" >/dev/null 2>&1
fi
