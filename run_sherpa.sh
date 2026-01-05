#!/bin/bash
set -e

SHERPA_INSTALLATION="$(realpath ~/PATH/TO/SHERPA/INSTALLATION/bin/Sherpa)"

DIRECTORY="$1"
LOGDIR="$2"
CLUSTER="$3"
PROCESS="$4"
MAXRUNTIME="${5:-86400}"

OUTFILE="$TMPDIR/job.${CLUSTER}.${PROCESS}.out"
ERRFILE="$TMPDIR/job.${CLUSTER}.${PROCESS}.err"
exec >"$OUTFILE" 2>"$ERRFILE"

LOGDIR=$(realpath "$LOGDIR")
STATUS_LOG="$LOGDIR/overview.${CLUSTER}.log"

cleanup() {
  echo ""
  if [ -f "$TMPDIR/Analysis.yoda.gz" ] && [ -d "$OUTDIR" ]; then
    if cp -f "$TMPDIR/Analysis.yoda.gz" "$OUTDIR/$YODA" 2>/dev/null; then
      echo "Successfully copied Analysis.yoda.gz to $OUTDIR/$YODA"
    else
      echo "Warning: Failed to copy Analysis.yoda.gz"
    fi
  else
    echo "Warning: Analysis.yoda.gz not found"
  fi

  cp -f "$OUTFILE" "$LOGDIR/job.${CLUSTER}.${PROCESS}.out" 2>/dev/null || true
  cp -f "$ERRFILE" "$LOGDIR/job.${CLUSTER}.${PROCESS}.err" 2>/dev/null || true
}
trap cleanup EXIT SIGTERM SIGINT SIGQUIT

# Record the start time
start_epoch=$(date +%s)
start_time=$(date '+%Y-%m-%d %H:%M:%S')
echo "Job ${CLUSTER}.${PROCESS} started on $(hostname)"
echo ""

### --------------------------------------------------- ###

INTEGRATION_RESULTS=""
HAS_RESULTS=false

for d in . ./*; do
  if [ -d "$d" ] && [ -d "$d/Process" ]; then
    INTEGRATION_RESULTS="$(realpath "$d")"
    if ls "$d"/Results.zip* >/dev/null 2>&1; then
      HAS_RESULTS=true
    fi
    break
  fi
done

if [ -z "$INTEGRATION_RESULTS" ]; then
  echo "ERROR: No Process directory found!"
  exit 1
fi

if [ "$HAS_RESULTS" = false ]; then
  echo "WARNING: No integration results (Results.zip*) found!"
  echo "WARNING: Integration might be performed for each run on the node (if required by process)."
  echo "WARNING: This may significantly increase runtime!"
  echo ""
fi

if [ ! -d "$DIRECTORY" ]; then
  echo "ERROR: Run directory $DIRECTORY not found!"
  exit 1
fi

YAML_FILE=$(find "$DIRECTORY" -maxdepth 1 -name "*.yaml" | head -n 1)
if [ -z "$YAML_FILE" ]; then
  YAML_FILE=$(find "$DIRECTORY/.." -maxdepth 1 -name "*.yaml" | head -n 1)
fi

if [ -z "$YAML_FILE" ]; then
  echo "ERROR: No YAML file found!"
  exit 1
fi

YAML=$(realpath "$YAML_FILE")
OUTDIR=$(realpath "$DIRECTORY")

YODA_BASENAME=$(basename "$DIRECTORY")
YODA="$YODA_BASENAME.yoda.gz"
SEED=$(od -An -N4 -tu4 < /dev/urandom | tr -d ' ')

echo "SHERPA_INSTALLATION : $SHERPA_INSTALLATION"
echo "INTEGRATION_RESULTS : $INTEGRATION_RESULTS"
echo "YAML                : $YAML"
echo "YODA                : $YODA"
echo "OUTDIR              : $OUTDIR"
echo "LOGDIR              : $LOGDIR"
echo "SEED                : $SEED"
echo "MAXRUNTIME          : $MAXRUNTIME seconds"
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
echo "Job runs in the -- $QUEUE_NAME -- with a wall time limit of $WALL_TIME_LIMIT seconds."
echo "SHERPA will be terminated after $TIMEOUT seconds (2 minutes before wall time limit)!"
echo ""

cp -r "$INTEGRATION_RESULTS/Process" "$TMPDIR"
if [ "$HAS_RESULTS" = true ]; then
  cp -r "$INTEGRATION_RESULTS"/Results.zip* "$TMPDIR"
else
  echo "Skipping copy of Results.zip* files (none found)."
  echo ""
fi

cd "$TMPDIR"

timeout -s TERM "$TIMEOUT" "$SHERPA_INSTALLATION" -f "$YAML" -R "$SEED" || {
  exit_code=$?
  if [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ]; then
    echo ""
    echo "SHERPA was terminated after reaching the time limit of $TIMEOUT seconds!"
    echo "This prevents the job from exceeding the wall time limit."
    echo "Copying output files back to shared filesystem..."
    {
      flock -x 200
      printf "[TIMEOUT] ${CLUSTER}.${PROCESS} | Hit wall time limit of $TIMEOUT seconds!\n" >> "$STATUS_LOG"
    } 200>"$STATUS_LOG.lock"
    rm -f "$STATUS_LOG.lock"
    exit 0
  else
    echo ""
    echo "SHERPA failed with exit code $exit_code"
    {
      flock -x 200
      printf "[FAILED] ${CLUSTER}.${PROCESS} | Exit code: $exit_code\n" >> "$STATUS_LOG"
    } 200>"$STATUS_LOG.lock"
    rm -f "$STATUS_LOG.lock"
    exit $exit_code
  fi
}

### --------------------------------------------------- ###

# Record end time
end_epoch=$(date +%s)
end_time=$(date '+%Y-%m-%d %H:%M:%S')
echo ""
echo "Job ended at:   $end_time"

# Calculate elapsed time
elapsed=$(( end_epoch - start_epoch ))

# Convert seconds to D-HH:MM:SS
days=$(( elapsed / 86400 ))
hours=$(( (elapsed % 86400) / 3600 ))
minutes=$(( (elapsed % 3600) / 60 ))
seconds=$(( elapsed % 60 ))

printf "Total elapsed time: %d-%02d:%02d:%02d\n" "$days" "$hours" "$minutes" "$seconds"
{
  flock -x 200
  printf "[COMPLETE] ${CLUSTER}.${PROCESS}\n" >> "$STATUS_LOG"
} 200>"$STATUS_LOG.lock"
rm -f "$STATUS_LOG.lock"
