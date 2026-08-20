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

require_inputs() {
  local phase="$1"
  local tag="$2"
  shift 2
  local missing=0
  local path
  for path in "$@"; do
    if [[ ! -e "$path" ]]; then
      log_msg "$phase" "$tag" "ERROR: Missing required input: $path"
      missing=1
    fi
  done
  if [[ "$missing" -eq 1 ]]; then
    log_msg "$phase" "$tag" "Skipping phase due to missing inputs."
    exit 1
  fi
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
else: data = {}
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
if which != 'start' or not entry.get('start_time'):
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
  if [[ -n "${PROFESSOR_INSTALLATION:-}" ]]; then
    export PATH="$PROFESSOR_INSTALLATION:$PATH"
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

mpi_prefix_for() {
  local np="${1:-1}"
  MPI_PREFIX=()
  if [[ "$np" -gt 1 ]] && command -v mpirun >/dev/null 2>&1; then
    MPI_PREFIX=(mpirun -np "$np")
  fi
}

select_repeat_winners() {
  local state_json="$1"
  local node="$2"
  python3 - "$state_json" "$node" <<'PY'
import json, os, re, sys
from pathlib import Path

REPEATS_DIRNAME = "repeats"
#: The tune result files, in the order app-tools' tuneresults prefers them, so
#: both agree on which file speaks for a tune.
CANDIDATE_GLOBS = ("minimum_*.txt", "results.txt", "tune.dat")
#: The objective, as Apprentice and as Professor2 write it.
OBJECTIVES = (re.compile(r"^\s*#\s*Objective value at best fit point:\s*([-+0-9.eE]+)"),
              re.compile(r"^\s*#\s*GOF\s+([-+0-9.eE]+)\s*$"))
#: backend -> (state key and tune name label, output folder).
BACKENDS = {"app": ("apprentice", "Apprentice"), "prof": ("professor", "Professor")}
NODE = re.compile(r"^P(?:6|9)(?:_dir(?P<dir>\d+))?_(?P<backend>app|prof)$")

state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
node  = NODE.match(sys.argv[2])
if node is None:
    sys.exit(0)

label, folder_name = BACKENDS[node.group("backend")]
block  = state.get(label) or {}
repeat = int(block.get("repeat", 1) or 1)
if repeat <= 1:
    sys.exit(0)

if node.group("dir"):
    index       = int(node.group("dir"))
    root, scope = Path(state["input_dirs"][index - 1]["path"]), f"dir{index}"
else:
    root, scope = Path(state["merged_dir"]), "merged"
folder = root / folder_name


def objective(directory):
    """(value, source name) for a finished repeat, or (None, why it is unusable)."""
    if not directory.is_dir():
        return None, "no output directory"
    for pattern in CANDIDATE_GLOBS:
        found = sorted(directory.glob(pattern))
        if found:
            break
    else:
        return None, "no tune result file"
    for line in found[0].read_text(encoding="utf-8", errors="replace").splitlines():
        for expression in OBJECTIVES:
            hit = expression.match(line)
            if hit:
                return float(hit.group(1)), found[0].name
    return None, f"no objective in {found[0].name}"


def publish(name, winner):
    """Point folder/name at the winning repeat, by a rename so it is never missing."""
    target, temporary = folder / name, folder / f".{name}.tmp"
    if temporary.is_symlink() or temporary.exists():
        temporary.unlink()
    os.symlink(os.path.join(REPEATS_DIRNAME, winner.name), temporary)
    if target.exists() and not target.is_symlink():
        # An earlier run without repeats left a real directory here. Renaming
        # onto it would fail, and removing it would throw away a tune that may
        # still be wanted, so say so instead of guessing.
        temporary.unlink()
        sys.exit(f"ERROR: {target} is a directory, not a link to a repeat. "
                 "Remove it and resume, or set REPEAT: 1.")
    os.replace(temporary, target)


print(f"Selecting the best of {repeat} repeats per tune in {folder}:")
unusable = []
for safe in block.get("orders_safe", []):
    for name in (f"tune.{label}.{safe}.{scope}", f"tune.{label}.err.{safe}.{scope}"):
        print(f"  {name}")
        usable = []
        for k in range(1, repeat + 1):
            directory     = folder / REPEATS_DIRNAME / f"{name}.repeat-{k}"
            value, source = objective(directory)
            if value is None:
                print(f"    {directory.name}: unusable ({source})")
                continue
            print(f"    {directory.name}: objective = {value:.6f} (from {source})")
            usable.append((value, directory))
        if not usable:
            unusable.append(name)
            print("    -> no usable repeat")
            continue
        winner = min(usable, key=lambda item: item[0])[1]
        publish(name, winner)
        print(f"    -> {winner.name} ({len(usable)}/{repeat} repeats usable)")

if unusable:
    sys.exit(f"ERROR: no repeat produced a usable result for: {', '.join(unusable)}")
PY
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
emit('PROFESSOR_INSTALLATION', s['professor_installation'])
emit('SHERPA_BINARY', s['sherpa_binary'])
emit('MPI_MODULE', s['mpi_module'])
emit('NUMBA_DISABLE_JIT', int(bool(s['numba_disable_jit'])))
emit('MASTER_DIR', s['master_dir'])
emit('CONDOR_OUTPUT', s['condor_output'])
emit('N_INPUT_DIRS', len(s['input_dirs']))
emit('N_GRID', s['n_grid'])
emit('GRID_SAMPLING', s['grid_sampling'])
def orders(block):
    if block.get('orders'):
        return list(block['orders'])
    if block.get('order'):
        return [block['order']]
    return []

app = s['apprentice']
if app:
  app_orders = orders(app)
  emit('APP_ORDERS', ' '.join(app_orders))
  emit('APP_ORDERS_SAFE', ' '.join(o.replace(',', '_') for o in app_orders))
  emit('APP_BUILD_OPTIONS', app.get('build_options', ''))
  emit('APP_TUNE2_OPTIONS', app.get('tune2_options', ''))
prof = s['professor']
if prof:
  emit('PROF_ORDERS', ' '.join(orders(prof)))
  emit('PROF2_IPOL_OPTIONS', prof.get('ipol_options', ''))
  emit('PROF2_TUNE_OPTIONS', prof.get('tune_options', ''))
emit('PATTERN', s['pattern'])
emit('COMBINE_MODE', s['combine_mode'])
emit('MERGED_DIR', s['merged_dir'])
emit('MERGE_MODE', s['merge_mode'])
emit('VALIDATION_ONLY_ERR', int(bool(s['validation_only_err'])))
emit('VALIDATION_ONLY_MERGED', int(bool(s['validation_only_merged'])))
emit('NPROC', s['nproc'])
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
emit('N_SUBRUNS', d['n_subruns'])
emit('N_VAL_SUBRUNS', d['n_val_subruns'])
emit('GRID_MODE', d['grid_mode'])
PY
)"
}
