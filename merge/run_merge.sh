#!/bin/bash
set -e

MERGE_SCRIPT="$1"
RIVET_ENV="$2"
shift 2

export PATH=/usr/bin:$PATH
if [ -z "$MERGE_SCRIPT" ]; then
  echo "ERROR: No merge script provided as first argument!" >&2
  exit 1
fi
MERGE_SCRIPT="$(realpath "$MERGE_SCRIPT")"
if [ ! -f "$MERGE_SCRIPT" ]; then
  echo "ERROR: merge script not found: $MERGE_SCRIPT" >&2
  exit 1
fi
if [ -n "$RIVET_ENV" ]; then
  if [ ! -f "$RIVET_ENV" ]; then
    echo "ERROR: RIVET_ENV not found: $RIVET_ENV" >&2
    exit 1
  fi
  . "$RIVET_ENV"
fi

NPROC="$1"
LOGDIR="$2"
CLUSTER="$3"
PROCESS="$4"
MAXRUNTIME="${5:-86400}"
shift 5
MERGE_ARGS=("$@")

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

FOLDER_LIST=""
cleanup() {
  cp -f "$OUTFILE" "$LOGDIR/job.${CLUSTER}.${PROCESS}.out" 2>/dev/null || true
  cp -f "$ERRFILE" "$LOGDIR/job.${CLUSTER}.${PROCESS}.err" 2>/dev/null || true
}
term_handler() {
  echo "Received termination signal. Forwarding SIGINT to the merge script..."

  if [ -n "$merge_pid" ]; then
    kill -INT "$merge_pid" 2>/dev/null
    wait "$merge_pid" 2>/dev/null || true
  fi
  echo ""
  print_end_time
  echo ""
  echo "Copying output files back to shared filesystem..."
  {
    flock -x 200
    printf "[REMOVED] ${CLUSTER}.${PROCESS} | DIR: %s | FOLDERS: %s | Job was removed/terminated externally!\n" "$WORKDIR" "$FOLDER_LIST" >&200
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

FOLDERS=()
skip_next=false
for arg in "${MERGE_ARGS[@]}"; do
  if [ "$skip_next" = true ]; then
    skip_next=false
    continue
  fi
  case "$arg" in
    --chunked|--nmax|-o|--output)
      skip_next=true ;;
    -*)
      ;;
    *)
      FOLDERS+=("$arg") ;;
  esac
done
FOLDER_LIST="${FOLDERS[*]}"

if [ "${#FOLDERS[@]}" -eq 0 ]; then
  echo "ERROR: no folder to merge given!" >&2
  exit 1
fi

missing=0
for folder in "${FOLDERS[@]}"; do
  if [ ! -d "$folder" ]; then
    echo "ERROR: no directory named $folder" >&2
    missing=1
  elif ! find "$folder" -name '*.yoda*' -print -quit 2>/dev/null | grep -q .; then
    echo "ERROR: no YODA files found in $folder" >&2
    missing=1
  fi
done
if [ "$missing" -ne 0 ]; then
  {
    flock -x 200
    printf "[FAILED] ${CLUSTER}.${PROCESS} | DIR: %s | FOLDERS: %s | Missing inputs\n" "$WORKDIR" "$FOLDER_LIST" >&200
  } 200>>"$STATUS_LOG"
  exit 1
fi

CMD=(bash "$MERGE_SCRIPT" "${MERGE_ARGS[@]}" "$NPROC")

echo "MERGE_SCRIPT : $MERGE_SCRIPT"
echo "RIVET_ENV    : $RIVET_ENV"
echo "WORKDIR      : $WORKDIR"
echo "FOLDERS      : $FOLDER_LIST"
echo "LOGDIR       : $LOGDIR"
echo "NPROC        : $NPROC"
echo "MAXRUNTIME   : $MAXRUNTIME seconds"
echo "COMMAND      : ${CMD[*]}"
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
echo "The merge will be terminated after $TIMEOUT seconds (2 minutes before wall time limit)!"
echo ""

echo "Starting merge..."
echo ""
merge_start_epoch=$(date +%s)

timeout --foreground -s INT -k 60 "$TIMEOUT" "${CMD[@]}" &
merge_pid=$!
exit_code=0
wait "$merge_pid" || exit_code=$?

if [ $exit_code -ne 0 ]; then
  merge_elapsed=$(( $(date +%s) - merge_start_epoch ))
  echo ""
  if { [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ] || [ $exit_code -eq 130 ]; } && [ $merge_elapsed -ge $TIMEOUT ]; then
    echo "The merge was terminated after reaching the time limit of $TIMEOUT seconds!"
    echo "Some folders may be merged and others not; with --rm the corresponding"
    echo "subdirectories of the merged ones are already gone."
    echo ""
    print_end_time
    echo ""
    {
      flock -x 200
      printf "[TIMEOUT] ${CLUSTER}.${PROCESS} | DIR: %s | FOLDERS: %s | Hit wall time limit of %s seconds!\n" "$WORKDIR" "$FOLDER_LIST" "$TIMEOUT" >&200
    } 200>>"$STATUS_LOG"
    exit $exit_code
  else
    exit_reason="$exit_code"
    if [ $exit_code -gt 128 ]; then
      exit_reason="$exit_code (SIG$(kill -l $((exit_code - 128)) 2>/dev/null || echo '?'))"
    fi
    echo "The merge failed with exit code $exit_reason after $merge_elapsed seconds"
    echo ""
    print_end_time
    echo ""
    {
      flock -x 200
      printf "[FAILED] ${CLUSTER}.${PROCESS} | DIR: %s | FOLDERS: %s | Exit code: %s\n" "$WORKDIR" "$FOLDER_LIST" "$exit_reason" >&200
    } 200>>"$STATUS_LOG"
    exit $exit_code
  fi
fi

echo ""
echo "Merge completed successfully."
echo ""
print_end_time
echo ""
echo "Copying output files back to shared filesystem..."
echo ""
{
  flock -x 200
  printf "[COMPLETE] ${CLUSTER}.${PROCESS} | DIR: %s | FOLDERS: %s \n" "$WORKDIR" "$FOLDER_LIST" >&200
} 200>>"$STATUS_LOG"
