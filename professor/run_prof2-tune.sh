#!/bin/bash
set -e

PROF2_TUNE="$1"
RIVET_ENV="$2"
shift 2

export PATH=/usr/bin:$PATH
if [ -z "$PROF2_TUNE" ]; then
  echo "ERROR: No prof2-tune provided as first argument!" >&2
  exit 1
fi
PROF2_TUNE="$(realpath "$PROF2_TUNE")"
if [ ! -x "$PROF2_TUNE" ]; then
  echo "ERROR: prof2-tune not found or not executable: $PROF2_TUNE" >&2
  exit 1
fi
if [ -n "$RIVET_ENV" ]; then
  if [ ! -f "$RIVET_ENV" ]; then
    echo "ERROR: RIVET_ENV not found: $RIVET_ENV" >&2
    exit 1
  fi
  source "$RIVET_ENV"
fi

LOGDIR="$1"
CLUSTER="$2"
PROCESS="$3"
MAXRUNTIME="${4:-86400}"
shift 4
TUNE_ARGS=("$@")

OUTFILE="$TMPDIR/job.${CLUSTER}.${PROCESS}.out"
ERRFILE="$TMPDIR/job.${CLUSTER}.${PROCESS}.err"
exec >"$OUTFILE" 2>"$ERRFILE"

mkdir -p "$LOGDIR"
LOGDIR=$(realpath "$LOGDIR")
STATUS_LOG="$LOGDIR/overview.${CLUSTER}.log"
WORKDIR=$(realpath "$PWD")

print_end_time() {
  local elapsed days hours minutes seconds
  end_time=$(date '+%Y-%m-%d %H:%M:%S')
  elapsed=$(( $(date +%s) - start_epoch ))

  # Convert seconds to D-HH:MM:SS
  days=$(( elapsed / 86400 ))
  hours=$(( (elapsed % 86400) / 3600 ))
  minutes=$(( (elapsed % 3600) / 60 ))
  seconds=$(( elapsed % 60 ))

  echo "Job ended at: $end_time"
  printf "Total elapsed time: %d-%02d:%02d:%02d\n" "$days" "$hours" "$minutes" "$seconds"
}

OUTPUT_TARGET=""
cleanup() {
  cp -f "$OUTFILE" "$LOGDIR/job.${CLUSTER}.${PROCESS}.out" 2>/dev/null || true
  cp -f "$ERRFILE" "$LOGDIR/job.${CLUSTER}.${PROCESS}.err" 2>/dev/null || true
}
term_handler() {
  echo "Received termination signal. Forwarding SIGINT to prof2-tune..."

  if [ -n "$prof2_tune_pid" ]; then
    kill -INT "$prof2_tune_pid" 2>/dev/null
    wait "$prof2_tune_pid" 2>/dev/null || true
  fi
  echo ""
  print_end_time
  echo ""
  echo "Copying output files back to shared filesystem..."
  {
    flock -x 200
    printf "[REMOVED] ${CLUSTER}.${PROCESS} | DIR: %s | OUT: %s | Job was removed/terminated externally!\n" "$WORKDIR" "$OUTPUT_TARGET" >> "$STATUS_LOG"
  } 200>"$STATUS_LOG.lock"
  rm -f "$STATUS_LOG.lock"
  exit 143
}
trap cleanup EXIT
trap term_handler SIGTERM SIGINT SIGQUIT

# Record the start time
start_epoch=$(date +%s)
start_time=$(date '+%Y-%m-%d %H:%M:%S')
echo "Job ${CLUSTER}.${PROCESS} started on $(hostname) at: $start_time"
echo ""

### --------------------------------------------------- ###

for i in "${!TUNE_ARGS[@]}"; do
  if { [ "${TUNE_ARGS[$i]}" = "-o" ] || [ "${TUNE_ARGS[$i]}" = "--outdir" ]; } \
     && [ $((i + 1)) -lt "${#TUNE_ARGS[@]}" ]; then
    OUTPUT_TARGET="${TUNE_ARGS[$((i + 1))]}"
  fi
done
if [ -z "$OUTPUT_TARGET" ]; then
  OUTPUT_TARGET="tunes"
fi

CMD=("$PROF2_TUNE" "${TUNE_ARGS[@]}")

echo "PROF2_TUNE : $PROF2_TUNE"
echo "RIVET_ENV  : $RIVET_ENV"
echo "WORKDIR    : $WORKDIR"
echo "OUTPUT     : $OUTPUT_TARGET"
echo "LOGDIR     : $LOGDIR"
echo "MAXRUNTIME : $MAXRUNTIME seconds"
echo "COMMAND    : ${CMD[*]}"
echo ""

DESIRED_WALL_TIME_1=$((MAXRUNTIME * 3 / 2))
DESIRED_WALL_TIME_2=$((MAXRUNTIME + 86400))
if [ $DESIRED_WALL_TIME_1 -le $DESIRED_WALL_TIME_2 ]; then
  DESIRED_WALL_TIME=$DESIRED_WALL_TIME_1
else
  DESIRED_WALL_TIME=$DESIRED_WALL_TIME_2
fi

QUEUE_LIMIT=0
if [ "$MAXRUNTIME" -le 3600 ]; then
  QUEUE_LIMIT=3600
  QUEUE_NAME="1h queue"
elif [ "$MAXRUNTIME" -le 86400 ]; then
  QUEUE_LIMIT=86400
  QUEUE_NAME="24h queue"
else
  QUEUE_LIMIT=$((28 * 86400))
  QUEUE_NAME="28 days queue"
fi

if [ $DESIRED_WALL_TIME -le $QUEUE_LIMIT ]; then
  WALL_TIME_LIMIT=$DESIRED_WALL_TIME
else
  WALL_TIME_LIMIT=$QUEUE_LIMIT
fi

TIMEOUT=$((WALL_TIME_LIMIT - 120))
echo "Job runs in the -- $QUEUE_NAME -- with a wall time limit of $WALL_TIME_LIMIT seconds [i.e. min(1.5 x $MAXRUNTIME, $QUEUE_LIMIT)]."
echo "PROF2-TUNE will be terminated after $TIMEOUT seconds (2 minutes before wall time limit)!"
echo ""

echo "Starting prof2-tune..."
echo ""
tune_start_epoch=$(date +%s)

timeout --foreground -s INT -k 60 "$TIMEOUT" "${CMD[@]}" &
prof2_tune_pid=$!
exit_code=0
wait "$prof2_tune_pid" || exit_code=$?

if [ $exit_code -ne 0 ]; then
  tune_elapsed=$(( $(date +%s) - tune_start_epoch ))
  echo ""
  if { [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ] || [ $exit_code -eq 130 ]; } && [ $tune_elapsed -ge $TIMEOUT ]; then
    echo "prof2-tune was terminated after reaching the time limit of $TIMEOUT seconds!"
    echo ""
    print_end_time
    echo ""
    {
      flock -x 200
      printf "[TIMEOUT] ${CLUSTER}.${PROCESS} | DIR: %s | OUT: %s | Hit wall time limit of %s seconds!\n" "$WORKDIR" "$OUTPUT_TARGET" "$TIMEOUT" >> "$STATUS_LOG"
    } 200>"$STATUS_LOG.lock"
    rm -f "$STATUS_LOG.lock"
    exit $exit_code
  else
    exit_reason="$exit_code"
    if [ $exit_code -gt 128 ]; then
      exit_reason="$exit_code (SIG$(kill -l $((exit_code - 128)) 2>/dev/null || echo '?'))"
    fi
    echo "prof2-tune failed with exit code $exit_reason after $tune_elapsed seconds"
    echo ""
    print_end_time
    echo ""
    {
      flock -x 200
      printf "[FAILED] ${CLUSTER}.${PROCESS} | DIR: %s | OUT: %s | Exit code: %s\n" "$WORKDIR" "$OUTPUT_TARGET" "$exit_reason" >> "$STATUS_LOG"
    } 200>"$STATUS_LOG.lock"
    rm -f "$STATUS_LOG.lock"
    exit $exit_code
  fi
fi

echo ""
echo "prof2-tune completed successfully."
echo ""
print_end_time
echo ""
echo "Copying output files back to shared filesystem..."
echo ""
{
  flock -x 200
  printf "[COMPLETE] ${CLUSTER}.${PROCESS} | DIR: %s | OUT: %s \n" "$WORKDIR" "$OUTPUT_TARGET" >> "$STATUS_LOG"
} 200>"$STATUS_LOG.lock"
rm -f "$STATUS_LOG.lock"
