#!/bin/bash
set -euo pipefail

log_msg() {
  local phase="$1"
  local tag="$2"
  local msg="$3"
  if [[ -n "$tag" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Phase ${phase} | ${tag}] ${msg}"
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Phase ${phase}] ${msg}"
  fi
}

log_cmd() {
  local phase="$1"
  local tag="$2"
  shift 2
  log_msg "$phase" "$tag" "Running: $*"
}

run_cmd() {
  local phase="$1"
  local tag="$2"
  shift 2
  log_cmd "$phase" "$tag" "$@"
  "$@"
}

setup_tmp_logging() {
  local outdir="$1"
  local cluster="$2"
  local process="$3"

  mkdir -p "$outdir"
  CLEANUP_DONE=0
  TMP_LOG_OUT="${TMPDIR:-/tmp}/job.${cluster}.${process}.out"
  TMP_LOG_ERR="${TMPDIR:-/tmp}/job.${cluster}.${process}.err"
  TMP_LOG_DIR="$outdir"
  TMP_LOG_CLUSTER="$cluster"
  TMP_LOG_PROCESS="$process"
  exec >"$TMP_LOG_OUT" 2>"$TMP_LOG_ERR"

  cleanup_tmp_logging() {
    if [[ "${CLEANUP_DONE:-0}" -eq 1 ]]; then
      return
    fi
    CLEANUP_DONE=1
    cp -f "$TMP_LOG_OUT" "$TMP_LOG_DIR/job.${TMP_LOG_CLUSTER}.${TMP_LOG_PROCESS}.out" 2>/dev/null || true
    cp -f "$TMP_LOG_ERR" "$TMP_LOG_DIR/job.${TMP_LOG_CLUSTER}.${TMP_LOG_PROCESS}.err" 2>/dev/null || true
  }
  trap cleanup_tmp_logging EXIT ERR SIGTERM SIGINT SIGQUIT
}

record_condor_id() {
  local state_json="$1"
  local key="$2"
  local cluster="$3"
  local process="${4:-}"

  local condor_ids_file
  condor_ids_file=$(python3 - "$state_json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    s = json.load(f)
print(s['condor_ids_file'])
PY
)
  local lockfile="${condor_ids_file}.lock"
  (
    flock -x 200
    python3 - "$condor_ids_file" "$key" "$cluster" "$process" <<'PY'
import json, os, sys, tempfile
path, key, cluster, process = sys.argv[1:5]
if os.path.exists(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    data = {}
entry = data.get(key, {})
entry['cluster_id'] = cluster
if process:
    entry['last_process_id'] = process
data[key] = entry
dir_name = os.path.dirname(path) or '.'
base_name = os.path.basename(path)
fd, tmp_path = tempfile.mkstemp(prefix=f'.{base_name}.', suffix='.tmp', dir=dir_name)
try:
  with os.fdopen(fd, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.flush()
    os.fsync(f.fileno())
  os.replace(tmp_path, path)
finally:
  if os.path.exists(tmp_path):
    os.unlink(tmp_path)
PY
  ) 200>"$lockfile"
  rm -f "$lockfile"
}

record_phase_time() {
  local state_json="$1"
  local key="$2"
  local which="$3"

  local phase_times_file
  phase_times_file=$(python3 - "$state_json" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    s = json.load(f)
print(s['phase_times_file'])
PY
)
  local lockfile="${phase_times_file}.lock"
  (
    flock -x 200
    python3 - "$phase_times_file" "$key" "$which" <<'PY'
import json, os, sys, datetime, tempfile
path, key, which = sys.argv[1:4]
if os.path.exists(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    data = {}
entry = data.get(key, {})
now = datetime.datetime.now().isoformat(timespec='seconds')
entry[f'{which}_time'] = now
data[key] = entry
dir_name = os.path.dirname(path) or '.'
base_name = os.path.basename(path)
fd, tmp_path = tempfile.mkstemp(prefix=f'.{base_name}.', suffix='.tmp', dir=dir_name)
try:
  with os.fdopen(fd, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.flush()
    os.fsync(f.fileno())
  os.replace(tmp_path, path)
finally:
  if os.path.exists(tmp_path):
    os.unlink(tmp_path)
PY
  ) 200>"$lockfile"
  rm -f "$lockfile"
}

load_environment() {
  if [[ -n "${APP_TOOLS_INSTALLATION:-}" ]]; then
    export PATH="$APP_TOOLS_INSTALLATION:$PATH"
  fi
  if [[ -n "${APPRENTICE_INSTALLATION:-}" ]]; then
    export PATH="$APPRENTICE_INSTALLATION:$PATH"
  fi
  if [[ -n "${RIVET_ENV_SCRIPT:-}" ]]; then
    if [[ ! -f "$RIVET_ENV_SCRIPT" ]]; then
      echo "ERROR: RIVET_ENV_SCRIPT not found: $RIVET_ENV_SCRIPT"
      exit 1
    fi
    local had_nounset=0
    if [[ $- == *u* ]]; then
      had_nounset=1
      set +u
    fi
    source "$RIVET_ENV_SCRIPT"
    if [[ $had_nounset -eq 1 ]]; then
      set -u
    fi
  fi
  if ! command -v module >/dev/null 2>&1; then
    local had_nounset=0
    if [[ $- == *u* ]]; then
      had_nounset=1
      set +u
    fi
    [[ -f /etc/profile.d/modules.sh ]] && source /etc/profile.d/modules.sh
    [[ -f /usr/share/Modules/init/bash ]] && source /usr/share/Modules/init/bash
    if [[ $had_nounset -eq 1 ]]; then
      set -u
    fi
  fi
  if command -v module >/dev/null 2>&1; then
    module load "${MPI_MODULE:-mpi/openmpi-x86_64}" 2>/dev/null || true
  fi
  if command -v mpirun >/dev/null 2>&1; then
    local mpi_libdirs
    mpi_libdirs="$(mpirun --showme:libdirs 2>/dev/null || true)"
    if [[ -n "$mpi_libdirs" ]]; then
      local old_ifs="$IFS"
      IFS=':'
      for d in $mpi_libdirs; do
        if [[ -d "$d" ]]; then
          export LD_LIBRARY_PATH="$d${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        fi
      done
      IFS="$old_ifs"
    fi
  fi
  if [[ "$NUMBA_DISABLE_JIT" == "1" ]]; then
    export NUMBA_DISABLE_JIT=1
  else
    unset NUMBA_DISABLE_JIT 2>/dev/null || true
  fi
}

load_global_state() {
  local state_json="$1"
  eval "$(python3 - "$state_json" <<'PY'
import json, shlex, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    s = json.load(f)

def emit(k, v):
    print(f"{k}={shlex.quote(str(v))}")

emit('RIVET_ENV_SCRIPT', s['rivet_env_script'])
emit('SHERPA_ON_THE_ROCKS_DIR', s['sherpa_on_the_rocks_dir'])
emit('APP_TOOLS_INSTALLATION', s['app_tools_installation'])
emit('APPRENTICE_INSTALLATION', s['apprentice_installation'])
emit('SHERPA_BINARY', s['sherpa_binary'])
emit('MPI_MODULE', s['mpi_module'])
emit('NUMBA_DISABLE_JIT', int(bool(s['numba_disable_jit'])))
emit('MASTER_DIR', s['master_dir'])
emit('CONDOR_OUTPUT', s['condor_output'])
emit('N_INPUT_DIRS', len(s['input_dirs']))
emit('N_GRID', s['n_grid'])
emit('SURROGATE_ORDER', s['surrogate_order'])
emit('SURROGATE_ORDER_SAFE', s['surrogate_order_safe'])
emit('PATTERN', s.get('pattern', ''))
emit('START_POINT_SURVEY', s['start_point_survey'])
emit('RESTARTS', s['restarts'])
emit('COMBINE_MODE', s['combine_mode'])
emit('MERGED_DIR', s['merged_dir'])
emit('MERGE_MODE', s['merge_mode'])
for idx, d in enumerate(s['input_dirs'], start=1):
  emit(f'INPUT_DIR_{idx}', d['path'])
  emit(f'WEIGHTS_{idx}', f"{d['path']}/weights.txt")
  emit(f'REWEIGHT_{idx}', int(bool(d['reweight'])))
PY
)"
  load_environment
}

load_dir_state() {
  local state_json="$1"
  local dir_index="$2"
  eval "$(python3 - "$state_json" "$dir_index" <<'PY'
import json, os, shlex, sys
state_path = sys.argv[1]
dir_idx = int(sys.argv[2])
with open(state_path, 'r', encoding='utf-8') as f:
    s = json.load(f)
d = s['input_dirs'][dir_idx - 1]

def emit(k, v):
    print(f"{k}={shlex.quote(str(v))}")

emit('INPUT_DIR', d['path'])
emit('REWEIGHT', int(bool(d['reweight'])))
emit('VALIDATION_REWEIGHT', int(bool(d['validation_reweight'])))
emit('N_SUBRUNS', d['n_subruns'])
emit('N_VAL_SUBRUNS', d['n_val_subruns'])
emit('GRID_MODE', d['grid_mode'])
PY
)"
}
