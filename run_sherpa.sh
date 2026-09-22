#!/bin/bash
set -e

SHERPA="$1"
RIVET_ENV="$2"
shift 2

if [ -z "$SHERPA" ]; then
  echo "ERROR: No SHERPA binary provided as first argument!" >&2
  exit 1
fi
SHERPA="$(realpath "$SHERPA")"
if [ ! -x "$SHERPA" ]; then
  echo "ERROR: SHERPA binary not found or not executable: $SHERPA" >&2
  exit 1
fi

LOGDIR="$1"
CLUSTER="$2"
PROCESS="$3"
MAXRUNTIME="${4:-86400}"
if [ "$#" -ge 4 ]; then shift 4; else shift "$#"; fi

DIRECTORY="${1:-}"
INIT_DIR="${2:-}"

if [ -z "$DIRECTORY" ]; then
  echo "ERROR: No run directory given!" >&2
  exit 1
fi

if [ "$RIVET_ENV" = "none" ]; then
  RIVET_ENV=""
fi
if [ -n "$RIVET_ENV" ]; then
  if [ ! -f "$RIVET_ENV" ]; then
    echo "ERROR: RIVET_ENV not found: $RIVET_ENV" >&2
    exit 1
  fi
  . "$RIVET_ENV"
fi

OUTFILE="$TMPDIR/job.${CLUSTER}.${PROCESS}.out"
ERRFILE="$TMPDIR/job.${CLUSTER}.${PROCESS}.err"
exec >"$OUTFILE" 2>"$ERRFILE"

mkdir -p "$LOGDIR"
LOGDIR=$(realpath "$LOGDIR")
STATUS_LOG="$LOGDIR/overview.${CLUSTER}.log"

get_last_event_count() {
  local last_event
  last_event=$(grep -Eo 'Event[[:space:]]+[0-9]+' "$OUTFILE" | awk '{print $2}' | tail -n 1)
  if [ -n "$last_event" ]; then
    echo "$last_event"
  else
    echo "unknown"
  fi
}

print_end_time() {
  local end_time elapsed days hours minutes seconds
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

log_fields() {
  local cpu host times_file="$TMPDIR/times.${CLUSTER}.${PROCESS}"
  FIELDS="DIR: $OUTDIR"
  if [ -n "$1" ]; then
    FIELDS="$FIELDS | EVENTS: $1"
  fi
  if [ -n "$start_epoch" ]; then
    FIELDS="$FIELDS | TOTALTIME: $(( $(date +%s) - start_epoch ))"
  fi
  times >"$times_file"
  cpu=$(awk 'NR == 2 { for (i = 1; i <= 2; i++) { split($i, t, /[ms]/); s += t[1] * 60 + t[2] }; printf "%d", s + 0.5 }' "$times_file")
  if [ -n "$cpu" ]; then
    FIELDS="$FIELDS | CPUTIME: $cpu"
  fi
  if [ -n "$start_epoch" ] && [ -n "$qdate" ]; then
    FIELDS="$FIELDS | WAITTIME: $(( start_epoch - qdate ))"
  fi
  if [ -n "$WALL_TIME_LIMIT" ]; then
    FIELDS="$FIELDS | WALLTIME_LIMIT: $WALL_TIME_LIMIT"
  fi
  host=$(hostname -s 2>/dev/null || true)
  if [ -n "$host" ]; then
    FIELDS="$FIELDS | HOST: $host"
  fi
  if [ -n "$SEED" ]; then
    FIELDS="$FIELDS | SEED: $SEED"
  fi
}

OUTDIR=""
YODA=""
COPY_ERROR=""
COPY_DONE=""
STATUS_WRITTEN=""

copy_results() {
  local src="$TMPDIR/Analysis.yoda.gz" dst size before after err item
  if [ -n "$COPY_DONE" ]; then
    return 0
  fi
  COPY_DONE=1

  if [ -n "$OUTDIR" ] && [ -d "$OUTDIR" ] && [ -f "$src" ]; then
    dst="$OUTDIR/$YODA"
    before=$(stat -c %Y:%s "$dst" 2>/dev/null || echo none)
    if err=$(cp -f "$src" "$dst" 2>&1); then
      err=""
      size=$(stat -c %s "$src" 2>/dev/null || echo "")
      if [ -n "$size" ]; then
        if [ "$(stat -c %s "$dst" 2>/dev/null)" != "$size" ]; then
          err="destination does not match source"
        elif [ "$size" -le 536870912 ] && command -v gzip >/dev/null 2>&1; then
          gzip -t "$dst" 2>/dev/null || err="destination is not a valid gzip file"
        fi
      fi
    fi
    if [ -n "$err" ]; then
      after=$(stat -c %Y:%s "$dst" 2>/dev/null || echo none)
      if [ "$after" != "$before" ]; then
        rm -f "$dst" 2>/dev/null || true
      fi
      COPY_ERROR=$(printf '%s' "$err" | tr '\n|' '; ' | sed -E "s/^cp: [^']*'.*': //" | cut -c1-160)
      if [ -z "$COPY_ERROR" ]; then
        COPY_ERROR="copy failed"
      fi
      echo "ERROR: Failed to copy Analysis.yoda.gz to $dst: $COPY_ERROR"
    else
      echo "Successfully copied Analysis.yoda.gz to $dst"
    fi
  else
    echo "Warning: Analysis.yoda.gz not found in $TMPDIR"
  fi

  if [ -n "$OUTDIR" ] && [ -d "$OUTDIR" ]; then
    for item in "$TMPDIR"/*.dat "$TMPDIR"/*_Histograms; do
      [ -e "$item" ] || continue
      if cp -r "$item" "$OUTDIR" 2>/dev/null; then
        echo "Copied $(basename "$item") to $OUTDIR"
      else
        echo "Warning: Failed to copy $(basename "$item")"
      fi
    done
  fi
  return 0
}

write_status() {
  local copy=""
  STATUS_WRITTEN=1
  if [ -n "$COPY_ERROR" ]; then
    copy=" | COPY: $COPY_ERROR"
  fi
  {
    flock -x 200
    printf '[%s] %s.%s | %s%s%s\n' "$1" "$CLUSTER" "$PROCESS" "$FIELDS" "$2" "$copy" >&200
  } 200>>"$STATUS_LOG" || echo "ERROR: could not append status to $STATUS_LOG"
}

cleanup() {
  local rc=$?
  copy_results || true
  if [ -z "$STATUS_WRITTEN" ] && [ -n "$STATUS_LOG" ]; then
    log_fields "$last_event" || true
    write_status FAILED " | Exit code: $rc | No status written before exit"
  fi
  cp -f "$OUTFILE" "$LOGDIR/job.${CLUSTER}.${PROCESS}.out" 2>/dev/null || true
  cp -f "$ERRFILE" "$LOGDIR/job.${CLUSTER}.${PROCESS}.err" 2>/dev/null || true
}
term_handler() {
  echo "Received termination signal. Forwarding SIGINT to Sherpa..."

  if [ -n "$sherpa_pid" ]; then
    kill -INT "$sherpa_pid" 2>/dev/null
    wait "$sherpa_pid" 2>/dev/null || true
  fi
  last_event=$(get_last_event_count)
  echo ""
  print_end_time
  echo ""
  echo "Copying output files back to shared filesystem..."
  log_fields "$last_event"
  write_status REMOVED " | Job was removed/terminated externally!"
  exit 143
}
trap cleanup EXIT
trap term_handler SIGTERM SIGINT SIGQUIT

# Record the start time
start_epoch=$(date +%s)
qdate=$(awk '$1 == "QDate" {print $3}' "${_CONDOR_JOB_AD:-/dev/null}" 2>/dev/null || true)
start_time=$(date '+%Y-%m-%d %H:%M:%S')
echo "Job ${CLUSTER}.${PROCESS} started on $(hostname) at: $start_time"
echo ""

### --------------------------------------------------- ###

INTEGRATION_RESULTS=""
HAS_RESULTS=false
if [ -n "$INIT_DIR" ]; then
  SEARCH_DIRS="$INIT_DIR"
else
  SEARCH_DIRS=". ./*"
fi
for d in $SEARCH_DIRS; do
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
QUOTA_INFO=$(timeout 10 quota -p -w 2>/dev/null | awk '$2 ~ /^[0-9]+$/ {printf "%.1f GiB used, soft %.1f GiB, hard %.1f GiB", $2/1048576, $3/1048576, $4/1048576; exit}' || true)

echo "SHERPA              : $SHERPA"
echo "INTEGRATION_RESULTS : $INTEGRATION_RESULTS"
echo "YAML                : $YAML"
echo "YODA                : $YODA"
echo "OUTDIR              : $OUTDIR"
echo "LOGDIR              : $LOGDIR"
echo "SEED                : $SEED"
echo "MAXRUNTIME          : $MAXRUNTIME seconds"
echo "QUOTA               : ${QUOTA_INFO:-unknown}"
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

echo "Starting SHERPA..."
echo ""
sherpa_start_epoch=$(date +%s)

timeout --foreground -s INT -k 60 "$TIMEOUT" "$SHERPA" -f "$YAML" -R "$SEED" &
sherpa_pid=$!
exit_code=0
wait "$sherpa_pid" || exit_code=$?
last_event=$(get_last_event_count)

if [ $exit_code -ne 0 ]; then
  sherpa_elapsed=$(( $(date +%s) - sherpa_start_epoch ))
  echo ""
  if { [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ] || [ $exit_code -eq 130 ]; } && [ $sherpa_elapsed -ge $TIMEOUT ]; then
    echo "SHERPA was terminated after reaching the time limit of $TIMEOUT seconds!"
    echo "This prevents the job from exceeding the wall time limit."
    echo ""
    print_end_time
    echo ""
    echo "Copying output files back to shared filesystem..."
    log_fields "$last_event"
    copy_results || true
    write_status TIMEOUT " | Hit wall time limit of $TIMEOUT seconds!"
    exit 0
  else
    exit_reason="$exit_code"
    if [ $exit_code -gt 128 ]; then
      exit_reason="$exit_code (SIG$(kill -l $((exit_code - 128)) 2>/dev/null || echo '?'))"
    fi
    echo "SHERPA failed with exit code $exit_reason after $sherpa_elapsed seconds"
    echo ""
    print_end_time
    echo ""
    echo "Copying output files back to shared filesystem..."
    log_fields "$last_event"
    copy_results || true
    write_status FAILED " | Exit code: $exit_reason"
    exit $exit_code
  fi
fi

echo ""
echo "SHERPA completed successfully."
echo ""
print_end_time
echo ""
echo "Copying output files back to shared filesystem..."
log_fields "$last_event"
copy_results || true
if [ -n "$COPY_ERROR" ]; then
  write_status FAILED ""
else
  write_status COMPLETE ""
fi
