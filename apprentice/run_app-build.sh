#!/bin/bash
set -e

APP_BUILD="$1"
RIVET_ENV="$2"
shift 2

export PATH=/usr/bin:$PATH
if [ -z "$APP_BUILD" ]; then
  echo "ERROR: No app-build provided as first argument!" >&2
  exit 1
fi
APP_BUILD="$(realpath "$APP_BUILD")"
if [ ! -x "$APP_BUILD" ]; then
  echo "ERROR: app-build not found or not executable: $APP_BUILD" >&2
  exit 1
fi
if [ -n "$RIVET_ENV" ]; then
  if [ ! -f "$RIVET_ENV" ]; then
    echo "ERROR: RIVET_ENV not found: $RIVET_ENV" >&2
    exit 1
  fi
  source "$RIVET_ENV"
fi

NPROC="$1"
LOGDIR="$2"
CLUSTER="$3"
PROCESS="$4"
MAXRUNTIME="${5:-86400}"
shift 5
APP_ARGS=("$@")

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
  echo "Received termination signal. Forwarding SIGINT to app-build..."

  if [ -n "$app_build_pid" ]; then
    kill -INT "$app_build_pid" 2>/dev/null
    wait "$app_build_pid" 2>/dev/null || true
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

for i in "${!APP_ARGS[@]}"; do
  if [ "${APP_ARGS[$i]}" = "-o" ] && [ $((i + 1)) -lt "${#APP_ARGS[@]}" ]; then
    OUTPUT_TARGET="${APP_ARGS[$((i + 1))]}"
  fi
done
if [ -z "$OUTPUT_TARGET" ]; then
  OUTPUT_TARGET="approx.json"
fi

CMD=("$APP_BUILD" "${APP_ARGS[@]}")
if [ "$NPROC" -gt 1 ]; then
  read -r -a APP_BUILD_SHEBANG <<<"$(sed -n '1s/^#!//p' "$APP_BUILD")"
  PY_INTERP="${APP_BUILD_SHEBANG[0]:-}"
  if [ "$(basename "$PY_INTERP" 2>/dev/null)" = "env" ]; then
    PY_INTERP="$(command -v "${APP_BUILD_SHEBANG[1]:-}" 2>/dev/null || true)"
  fi
  if [ -n "$PY_INTERP" ] && [ -x "$PY_INTERP" ]; then
    CMD=(mpirun -np "$NPROC" "$PY_INTERP" -m mpi4py "$APP_BUILD" "${APP_ARGS[@]}")
  else
    echo "WARNING: could not read a usable interpreter from the shebang of $APP_BUILD."
    echo "         Falling back to a plain mpirun: a crash in one rank will hang"
    echo "         the job until the time limit instead of failing it."
    echo ""
    CMD=(mpirun -np "$NPROC" "${CMD[@]}")
  fi
fi

echo "APP_BUILD  : $APP_BUILD"
echo "RIVET_ENV  : $RIVET_ENV"
echo "WORKDIR    : $WORKDIR"
echo "OUTPUT     : $OUTPUT_TARGET"
echo "LOGDIR     : $LOGDIR"
echo "NPROC      : $NPROC"
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
echo "APP-BUILD will be terminated after $TIMEOUT seconds (2 minutes before wall time limit)!"
echo ""

echo "Loading module ${MPI_MODULE:-mpi/openmpi-x86_64}..."
echo ""
if ! command -v module >/dev/null 2>&1; then
  [ -f /etc/profile.d/modules.sh ] && source /etc/profile.d/modules.sh
fi
if command -v module >/dev/null 2>&1; then
  module load "${MPI_MODULE:-mpi/openmpi-x86_64}" 2>/dev/null || true
fi

if command -v mpirun >/dev/null 2>&1; then
  MPI_LIBDIRS="$(mpirun --showme:libdirs 2>/dev/null || true)"
  if [ -n "$MPI_LIBDIRS" ]; then
    OLD_IFS="$IFS"
    IFS=':'
    for d in $MPI_LIBDIRS; do
      if [ -d "$d" ]; then
        export LD_LIBRARY_PATH="$d${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
      fi
    done
    IFS="$OLD_IFS"
  fi
fi

echo "Starting app-build..."
echo ""
build_start_epoch=$(date +%s)

timeout --foreground -s INT -k 60 "$TIMEOUT" "${CMD[@]}" &
app_build_pid=$!
exit_code=0
wait "$app_build_pid" || exit_code=$?

if [ $exit_code -ne 0 ]; then
  build_elapsed=$(( $(date +%s) - build_start_epoch ))
  echo ""
  if { [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ] || [ $exit_code -eq 130 ]; } && [ $build_elapsed -ge $TIMEOUT ]; then
    echo "app-build was terminated after reaching the time limit of $TIMEOUT seconds!"
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
    echo "app-build failed with exit code $exit_reason after $build_elapsed seconds"
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
echo "app-build completed successfully."
echo ""
print_end_time
echo ""
echo "Copying output files back to shared filesystem..."
echo ""
{
  flock -x 200
  printf "[COMPLETE] ${CLUSTER}.${PROCESS} | DIR: %s | OUT: %s \n" "$WORKDIR" "$OUTPUT_TARGET" >&200
} 200>>"$STATUS_LOG"
