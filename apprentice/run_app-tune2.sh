#!/bin/bash
set -e

APP_TUNE2="$1"
RIVET_ENV="$2"
shift 2

export PATH=/usr/bin:$PATH
if [ -z "$APP_TUNE2" ]; then
  echo "ERROR: No app-tune2 provided as first argument!" >&2
  exit 1
fi
APP_TUNE2="$(realpath "$APP_TUNE2")"
if [ ! -x "$APP_TUNE2" ]; then
  echo "ERROR: app-tune2 not found or not executable: $APP_TUNE2" >&2
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
  echo "Received termination signal. Forwarding SIGINT to app-tune2..."

  if [ -n "$app_tune2_pid" ]; then
    kill -INT "$app_tune2_pid" 2>/dev/null
    wait "$app_tune2_pid" 2>/dev/null || true
  fi
  echo ""
  print_end_time
  echo ""
  echo "Copying output files back to shared filesystem..."
  {
    flock -x 200
    printf "[REMOVED] ${CLUSTER}.${PROCESS} | DIR: %s | OUT: %s | Job was removed/terminated externally!\n" "$WORKDIR" "$OUTPUT_TARGET" >&200
  } 200>>"$STATUS_LOG"
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
  if [ "${TUNE_ARGS[$i]}" = "-o" ] && [ $((i + 1)) -lt "${#TUNE_ARGS[@]}" ]; then
    OUTPUT_TARGET="${TUNE_ARGS[$((i + 1))]}"
  fi
done
if [ -z "$OUTPUT_TARGET" ]; then
  OUTPUT_TARGET="tune"
fi

CMD=("$APP_TUNE2" "${TUNE_ARGS[@]}")

echo "APP_TUNE2  : $APP_TUNE2"
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
echo "APP-TUNE2 will be terminated after $TIMEOUT seconds (2 minutes before wall time limit)!"
echo ""

echo "Loading module ${MPI_MODULE:-mpi/openmpi-x86_64}..."
echo ""
if ! command -v module >/dev/null 2>&1; then
  [ -f /etc/profile.d/modules.sh ] && source /etc/profile.d/modules.sh
fi
if command -v module >/dev/null 2>&1; then
  module load "${MPI_MODULE:-mpi/openmpi-x86_64}" 2>/dev/null || true
fi

echo "Starting app-tune2..."
echo ""
tune_start_epoch=$(date +%s)

timeout --foreground -s INT -k 60 "$TIMEOUT" "${CMD[@]}" &
app_tune2_pid=$!
exit_code=0
wait "$app_tune2_pid" || exit_code=$?

if [ $exit_code -ne 0 ]; then
  tune_elapsed=$(( $(date +%s) - tune_start_epoch ))
  echo ""
  if { [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ] || [ $exit_code -eq 130 ]; } && [ $tune_elapsed -ge $TIMEOUT ]; then
    echo "app-tune2 was terminated after reaching the time limit of $TIMEOUT seconds!"
    echo ""
    print_end_time
    echo ""
    {
      flock -x 200
      printf "[TIMEOUT] ${CLUSTER}.${PROCESS} | DIR: %s | OUT: %s | Hit wall time limit of %s seconds!\n" "$WORKDIR" "$OUTPUT_TARGET" "$TIMEOUT" >&200
    } 200>>"$STATUS_LOG"
    exit $exit_code
  else
    exit_reason="$exit_code"
    if [ $exit_code -gt 128 ]; then
      exit_reason="$exit_code (SIG$(kill -l $((exit_code - 128)) 2>/dev/null || echo '?'))"
    fi
    echo "app-tune2 failed with exit code $exit_reason after $tune_elapsed seconds"
    echo ""
    print_end_time
    echo ""
    {
      flock -x 200
      printf "[FAILED] ${CLUSTER}.${PROCESS} | DIR: %s | OUT: %s | Exit code: %s\n" "$WORKDIR" "$OUTPUT_TARGET" "$exit_reason" >&200
    } 200>>"$STATUS_LOG"
    exit $exit_code
  fi
fi

echo ""
echo "app-tune2 completed successfully."
echo ""
print_end_time
echo ""
echo "Copying output files back to shared filesystem..."
echo ""
{
  flock -x 200
  printf "[COMPLETE] ${CLUSTER}.${PROCESS} | DIR: %s | OUT: %s \n" "$WORKDIR" "$OUTPUT_TARGET" >&200
} 200>>"$STATUS_LOG"
