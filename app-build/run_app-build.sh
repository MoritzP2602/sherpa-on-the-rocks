#!/bin/bash
set -e

APP_BUILD_INSTALLATION="$(realpath ~/PATH/TO/APP-BUILD/INSTALLATION/bin/app-build)"
RIVET_ENVIRONMENT="$(realpath ~/PATH/TO/RIVET/ENVIRONMENT/rivetenv.sh)"

WEIGHT_FILE="$1"
NEWSCAN_DIR="$2"
ORDER="$3"
LOGDIR="$4"
CLUSTER="$5"
PROCESS="$6"
MAXRUNTIME="${7:-86400}"

ORDER_CLEAN=$(echo "$ORDER" | tr ',' '_')
weight_basename=$(basename "$WEIGHT_FILE")
weight_stem="${weight_basename%.*}"
OUTPUT_FILENAME="${weight_stem}.json"

OUTFILE="$TMPDIR/job.${CLUSTER}.${PROCESS}.out"
ERRFILE="$TMPDIR/job.${CLUSTER}.${PROCESS}.err"
exec >"$OUTFILE" 2>"$ERRFILE"

LOGDIR=$(realpath "$LOGDIR")
STATUS_LOG="$LOGDIR/overview.${CLUSTER}.log"

cleanup() {
  echo ""
  if [ -f "$TMPDIR/app.json" ] && [ -d "$APP_OUTDIR" ]; then
    if cp -f "$TMPDIR/app.json" "$APP_OUTDIR/$OUTPUT_FILENAME" 2>/dev/null; then
      echo "Successfully copied app.json to $APP_OUTDIR/$OUTPUT_FILENAME"
    else
      echo "Warning: Failed to copy app.json to $APP_OUTDIR/$OUTPUT_FILENAME"
    fi
  else
    echo "Warning: app.json not found"
  fi
  if [ -f "$TMPDIR/err.json" ] && [ -d "$ERR_OUTDIR" ]; then
    if cp -f "$TMPDIR/err.json" "$ERR_OUTDIR/$OUTPUT_FILENAME" 2>/dev/null; then
      echo "Successfully copied err.json to $ERR_OUTDIR/$OUTPUT_FILENAME"
    else
      echo "Warning: Failed to copy err.json to $ERR_OUTDIR/$OUTPUT_FILENAME"
    fi
  else 
    echo "Warning: err.json not found"
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

source "$RIVET_ENVIRONMENT"
source /etc/profile.d/modules.sh
module load mpi/openmpi-x86_64
export PATH=/usr/bin:$PATH

if [ -z "$WEIGHT_FILE" ] || [ ! -f "$WEIGHT_FILE" ]; then
  echo "ERROR: Weight file not found: $WEIGHT_FILE"
  exit 1
fi

if [ -z "$NEWSCAN_DIR" ] || [ ! -d "$NEWSCAN_DIR" ]; then
  echo "ERROR: Newscan directory not found: $NEWSCAN_DIR"
  exit 1
fi

WEIGHT_FILE=$(realpath "$WEIGHT_FILE")
NEWSCAN_DIR=$(realpath "$NEWSCAN_DIR")
OUTDIR=$(realpath "$PWD")

APP_OUTDIR="$OUTDIR/app_${ORDER_CLEAN}"
ERR_OUTDIR="$OUTDIR/err_${ORDER_CLEAN}"
mkdir -p "$APP_OUTDIR"
mkdir -p "$ERR_OUTDIR"

echo "APP_BUILD_INSTALLATION : $APP_BUILD_INSTALLATION"
echo "RIVET_ENVIRONMENT      : $RIVET_ENVIRONMENT"
echo "WEIGHT_FILE            : $WEIGHT_FILE"
echo "NEWSCAN_DIR            : $NEWSCAN_DIR"
echo "ORDER                  : $ORDER"
echo "APP_OUTDIR             : $APP_OUTDIR"
echo "ERR_OUTDIR             : $ERR_OUTDIR"
echo "LOGDIR                 : $LOGDIR"
echo "MAXRUNTIME             : $MAXRUNTIME seconds"
echo ""

cd "$TMPDIR"
echo "Running app-build..."
"$APP_BUILD_INSTALLATION" -w "$WEIGHT_FILE" "$NEWSCAN_DIR" --order "$ORDER" -o app.json 
echo ""
echo "Running app-build --errs..."
"$APP_BUILD_INSTALLATION" -w "$WEIGHT_FILE" "$NEWSCAN_DIR" --order "$ORDER" -o "err.json" --errs

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
  printf "[COMPLETE] ${CLUSTER}.${PROCESS} \n" >> "$STATUS_LOG"
} 200>"$STATUS_LOG.lock"
rm -f "$STATUS_LOG.lock"
