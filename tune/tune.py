#!/usr/bin/env python3
import argparse
import json
import math
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError as e:
    raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from e

EVENT_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmMgG]?)\s*$")
TEMPLATE_EVENTS_RE = re.compile(r"^\s*EVENTS\s*:\s*(.+?)\s*$")


def parse_event_value(value: str) -> int:
    raw = str(value).strip()
    m = EVENT_RE.match(raw)
    if not m:
        raise ValueError(f"Invalid event value '{value}'. Use forms like 500k, 20M, 1G.")
    num = float(m.group(1))
    suffix = m.group(2).upper()
    factor = 1
    if suffix == "K":
        factor = 10**3
    elif suffix == "M":
        factor = 10**6
    elif suffix == "G":
        factor = 10**9
    return int(math.ceil(num * factor))

def parse_template_events(template_path: Path) -> int:
    for line in template_path.read_text(encoding="utf-8").splitlines():
        m = TEMPLATE_EVENTS_RE.match(line)
        if not m:
            continue
        value = m.group(1).split("#", 1)[0].strip().strip('"').strip("'")
        return parse_event_value(value)
    raise ValueError(f"Could not find EVENTS: in {template_path}")


def ensure_required_inputs(input_dir: Path) -> None:
    required_files = ["parameter.json", "data.json", "template.yaml", "weights.txt"]
    for fname in required_files:
        path = input_dir / fname
        if not path.exists():
            raise FileNotFoundError(f"Missing required file: {path}")
    init_dir = input_dir / "init"
    if not init_dir.is_dir():
        raise FileNotFoundError(f"Missing required directory: {init_dir}")


def stack_json_values(left, right):
    if isinstance(left, list) and isinstance(right, list):
        return left + right
    if isinstance(left, dict) and isinstance(right, dict):
        merged = dict(left)
        for key, value in right.items():
            if key in merged:
                merged[key] = stack_json_values(merged[key], value)
            else:
                merged[key] = value
        return merged
    if left == right:
        return left
    return [left, right]

def write_stacked_json_values(input_dirs: list[Path], merged_dir: Path) -> None:
    if len(input_dirs) != 2:
        return
    left_path = input_dirs[0] / "data.json"
    right_path = input_dirs[1] / "data.json"
    target_path = merged_dir / "data.json"

    left_data = json.loads(left_path.read_text(encoding="utf-8"))
    right_data = json.loads(right_path.read_text(encoding="utf-8"))
    stacked = stack_json_values(left_data, right_data)
    target_path.write_text(json.dumps(stacked, indent=2), encoding="utf-8")


def phase_overview(state):
    n_dirs = len(state["input_dirs"])
    phases = []
    phases.extend([
                ("P1", "Create tuning grid and prepare Sherpa subruns"),
                ("P2", "Sherpa event generation for tuning grid"),
                ("P3", "Merge results of Sherpa subruns using yodamerge/rivet-merge"),
                ("P4", "Build surrogate model and optimize parameters using Apprentice"),
                  ])
    if n_dirs == 1: 
        phases.append(("P5", "SKIPPED"))
    else: 
        phases.append(("P5", "Combine results from different processes and repeat the tuning procedure"))
    phases.extend([
                ("P6", "Create validation grid from tune results and prepare Sherpa subruns"),
                ("P7", "Sherpa event generation for validation grid"),
                ("P8", "Merge validation results using yodamerge/rivet-merge"),
                  ])
    phases.append(("P9", "Compute and plot chi-squared values."))
    return phases


def get_list_value(cfg, key, n_dirs):
    if key not in cfg:
        raise KeyError(f"Missing required key: {key}")
    val = cfg[key]
    if isinstance(val, list):
        values = val
    else:
        values = [val]
    if len(values) == 0:
        raise ValueError(f"{key} must not be empty")
    if len(values) == 1 and n_dirs == 2:
        return [values[0], values[0]]
    if len(values) != n_dirs:
        raise ValueError(f"{key} must have {n_dirs} entries (or 1 entry to broadcast)")
    return values

def get_required_cfg_value(cfg, *keys):
    for key in keys:
        if key in cfg and str(cfg[key]).strip():
            return cfg[key]
    raise KeyError(f"Missing required key: one of {', '.join(keys)}")

def resolve_cfg_path(value, config_path: Path) -> Path:
    p = Path(os.path.expanduser(str(value)))
    if p.is_absolute():
        return p.resolve()
    return (config_path.parent / p).resolve()


def build_state(cfg, config_path: Path):
    required_keys = [
        "INPUT_DIRS",
        "N_GRID",
        "EVENTS",
        "EVENTS_VALIDATION",
        "MERGE_MODE",
        "SURROGATE_ORDER",
        "SHERPA_ON_THE_ROCKS_DIR",
        "APP_TOOLS_INSTALLATION",
        "APPRENTICE_INSTALLATION",
        "SHERPA_BINARY",
        "RIVET_ENV_SCRIPT",
    ]
    for key in required_keys:
        if key not in cfg:
            raise KeyError(f"Missing required key: {key}")

    input_dirs_raw = cfg["INPUT_DIRS"]
    if isinstance(input_dirs_raw, list):
        input_dirs_list = input_dirs_raw
    else:
        input_dirs_list = [input_dirs_raw]
    if len(input_dirs_list) not in (1, 2):
        raise ValueError("INPUT_DIRS must contain one or two entries")

    input_dirs = [resolve_cfg_path(p, config_path) for p in input_dirs_list]
    n_dirs = len(input_dirs)

    merge_mode = str(cfg["MERGE_MODE"]).strip().lower()
    if merge_mode not in {"yoda", "rivet"}:
        raise ValueError("MERGE_MODE must be 'yoda' or 'rivet'")

    combine_mode = str(cfg.get("COMBINE_MODE", "weighted")).strip().lower()
    if n_dirs == 2 and combine_mode not in {"weighted", "equal"}:
        raise ValueError("COMBINE_MODE must be 'weighted' or 'equal' for two-input tunes")

    if "JOB_DIR" in cfg:
        job_dir = resolve_cfg_path(cfg["JOB_DIR"], config_path)
    else:
        job_dir = Path(os.path.expanduser("~/sherpa-on-the-rocks/tune")).resolve()

    rivet_env_script        = resolve_cfg_path(cfg["RIVET_ENV_SCRIPT"], config_path)
    sherpa_on_the_rocks_dir = resolve_cfg_path(cfg["SHERPA_ON_THE_ROCKS_DIR"], config_path)
    app_tools_installation  = resolve_cfg_path(cfg["APP_TOOLS_INSTALLATION"], config_path)
    apprentice_installation = resolve_cfg_path(cfg["APPRENTICE_INSTALLATION"], config_path)
    sherpa_binary           = resolve_cfg_path(cfg["SHERPA_BINARY"], config_path)

    if not rivet_env_script.exists():
        raise FileNotFoundError(f"RIVET_ENV_SCRIPT does not exist: {rivet_env_script}")
    if not sherpa_on_the_rocks_dir.exists() or not sherpa_on_the_rocks_dir.is_dir():
        raise FileNotFoundError(f"SHERPA_ON_THE_ROCKS_DIR does not exist or is not a directory: {sherpa_on_the_rocks_dir}")
    if not app_tools_installation.exists():
        raise FileNotFoundError(f"APP_TOOLS_INSTALLATION does not exist: {app_tools_installation}")
    if not apprentice_installation.exists():
        raise FileNotFoundError(f"APPRENTICE_INSTALLATION does not exist: {apprentice_installation}")
    if not sherpa_binary.exists():
        raise FileNotFoundError(f"SHERPA_BINARY does not exist: {sherpa_binary}")

    events_list = get_list_value(cfg, "EVENTS", n_dirs)
    events_val_list = get_list_value(cfg, "EVENTS_VALIDATION", n_dirs)

    n_grid = int(cfg["N_GRID"])
    if n_grid <= 0:
        raise ValueError("N_GRID must be > 0")

    surrogate_order = str(cfg["SURROGATE_ORDER"]).strip()
    if not surrogate_order:
        raise ValueError("SURROGATE_ORDER must not be empty")

    input_states = []
    for i, idir in enumerate(input_dirs, start=1):
        ensure_required_inputs(idir)
        has_nominal     = (idir / "nominal.json").exists()
        grid_mode       = "sample" if i == 1 else "import"
        req_events      = parse_event_value(events_list[i - 1])
        req_events_val  = parse_event_value(events_val_list[i - 1])
        template_events = parse_template_events(idir / "template.yaml")
        n_subruns       = int(math.ceil(req_events / template_events))
        n_val_subruns   = int(math.ceil(req_events_val / template_events))

        input_states.append({
                "path": str(idir),
                "reweight"         : bool(has_nominal),
                "grid_mode"        : grid_mode,
                "events"           : req_events,
                "events_validation": req_events_val,
                "template_events"  : template_events,
                "n_subruns"        : n_subruns,
                "n_val_subruns"    : n_val_subruns,
                            })

    if "MASTER_DIR" in cfg:
        master_dir = resolve_cfg_path(cfg["MASTER_DIR"], config_path)
    else:
        master_dir = (input_dirs[0] / "master").resolve()
    condor_output = str((master_dir / "condor_output").resolve())
    if n_dirs == 2:
        if "MERGED_DIR" in cfg and str(cfg["MERGED_DIR"]).strip():
            merged_dir = str(resolve_cfg_path(cfg["MERGED_DIR"], config_path))
        else:
            merged_dir = str((input_dirs[0] / "merged").resolve())
    else:
        merged_dir = ""

    state = {
        "created_at"              : datetime.now().isoformat(timespec="seconds"),
        "config_path"             : str(config_path.resolve()),
        "rivet_env_script"        : str(rivet_env_script),
        "sherpa_on_the_rocks_dir" : str(sherpa_on_the_rocks_dir),
        "app_tools_installation"  : str(app_tools_installation),
        "apprentice_installation" : str(apprentice_installation),
        "sherpa_binary"           : str(sherpa_binary),
        "mpi_module"              : str(cfg.get("MPI_MODULE", "mpi/openmpi-x86_64")).strip(),
        "job_dir"                 : str(job_dir),
        "master_dir"              : str(master_dir),
        "condor_output"           : condor_output,
        "input_dirs"              : input_states,
        "n_grid"                  : n_grid,
        "surrogate_order"         : surrogate_order,
        "surrogate_order_safe"    : surrogate_order.replace(",", "_"),
        "merge_mode"              : merge_mode,
        "combine_mode"            : combine_mode,
        "merged_dir"              : merged_dir,
        "P1_maxruntime"           : int(cfg.get("PHASE1_MAXRUNTIME", 1800)),
        "P2_maxruntime"           : int(cfg.get("PHASE2_MAXRUNTIME", 86400)),
        "P3_maxruntime"           : int(cfg.get("PHASE3_MAXRUNTIME", 86400)),
        "P4_maxruntime"           : int(cfg.get("PHASE4_MAXRUNTIME", 86400)),
        "P5_maxruntime"           : int(cfg.get("PHASE5_MAXRUNTIME", 86400)),
        "P6_maxruntime"           : int(cfg.get("PHASE6_MAXRUNTIME", 1800)),
        "P7_maxruntime"           : int(cfg.get("PHASE7_MAXRUNTIME", 86400)),
        "P8_maxruntime"           : int(cfg.get("PHASE8_MAXRUNTIME", 86400)),
        "P9_maxruntime"           : int(cfg.get("PHASE9_MAXRUNTIME", 1800)),
        "condor_ids_file"         : str((master_dir / "condor_ids.json").resolve()),
        "phase_times_file"        : str((master_dir / "phase_times.json").resolve()),
        "dag_path"                : str((master_dir / "tune.dag").resolve()),
    }
    return state


def create_dag(state):
    master_dir = Path(state["master_dir"]) 
    croot = Path(state["condor_output"]) 
    job_dir = Path(state["job_dir"]) 
    state_path = str((master_dir / "state.json").resolve())
    n_dirs = len(state["input_dirs"])

    lines = []
    lines.append("# Auto-generated by tune.py")

    def v(name, submit, vars_map):
        lines.append(f"JOB {name} {(job_dir / submit).resolve()}")
        vars_str = " ".join([f'{k}="{v}"' for k, v in vars_map.items()])
        lines.append(f"VARS {name} {vars_str}")

    for i in range(1, n_dirs + 1):
        v(
            f"P1_D{i}",
            "P1.jdf",
            {
                "JOB_DIR"       : str(job_dir),
                "STATE_JSON"    : state_path,
                "DIR_INDEX"     : str(i),
                "PHASE_LOG_DIR" : str(croot / f"P1_dir{i}"),
                "MAXRUNTIME"    : str(state["P1_maxruntime"]),
            },
        )
        v(
            f"P2_D{i}",
            "P2.jdf",
            {
                "JOB_DIR"       : str(job_dir),
                "STATE_JSON"    : state_path,
                "DIR_INDEX"     : str(i),
                "PHASE_LOG_DIR" : str(croot / f"P2_dir{i}"),
                "RUNS_FILE"     : str(Path(state["input_dirs"][i - 1]["path"]) / "runs.txt"),
                "RUN_DIR"       : state["input_dirs"][i - 1]["path"],
                "MAXRUNTIME"    : str(state["P2_maxruntime"]),
                "PHASE_KEY"     : "P2",
            },
        )
        v(
            f"P3_D{i}",
            "P3.jdf",
            {
                "JOB_DIR"       : str(job_dir),
                "STATE_JSON"    : state_path,
                "DIR_INDEX"     : str(i),
                "PHASE_LOG_DIR" : str(croot / f"P3_dir{i}"),
                "MAXRUNTIME"    : str(state["P3_maxruntime"]),
            },
        )
        v(
            f"P4_D{i}",
            "P4.jdf",
            {
                "JOB_DIR"       : str(job_dir),
                "STATE_JSON"    : state_path,
                "DIR_INDEX"     : str(i),
                "PHASE_LOG_DIR" : str(croot / f"P4_dir{i}"),
                "MAXRUNTIME"    : str(state["P4_maxruntime"]),
            },
        )
    if n_dirs == 2:
        v(
            f"P5",
            "P5.jdf",
            {
                "JOB_DIR"       : str(job_dir),
                "STATE_JSON"    : state_path,
                "PHASE_LOG_DIR" : str(croot / f"P5"),
                "MAXRUNTIME"    : str(state["P5_maxruntime"]),
            },
        )
    for i in range(1, n_dirs + 1):
        v(
            f"P6_D{i}",
            "P6.jdf",
            {
                "JOB_DIR"       : str(job_dir),
                "STATE_JSON"    : state_path,
                "DIR_INDEX"     : str(i),
                "PHASE_LOG_DIR" : str(croot / f"P6_dir{i}"),
                "MAXRUNTIME"    : str(state["P6_maxruntime"]),
            },
        )
        v(
            f"P7_D{i}",
            "P7.jdf",
            {
                "JOB_DIR"       : str(job_dir),
                "STATE_JSON"    : state_path,
                "DIR_INDEX"     : str(i),
                "RUN_DIR"       : state["input_dirs"][i - 1]["path"],
                "RUNS_FILE"     : str(Path(state["input_dirs"][i - 1]["path"]) / "runs.txt"),
                "PHASE_LOG_DIR" : str(croot / f"P7_dir{i}"),
                "MAXRUNTIME"    : str(state["P7_maxruntime"]),
                "PHASE_KEY"     : "P7",
            },
        )
        v(
            f"P8_D{i}",
            "P8.jdf",
            {
                "JOB_DIR"       : str(job_dir),
                "STATE_JSON"    : state_path,
                "DIR_INDEX"     : str(i),
                "PHASE_LOG_DIR" : str(croot / f"P8_dir{i}"),
                "MAXRUNTIME"    : str(state["P8_maxruntime"]),
            },
        )
    v(
            f"P9",
            "P9.jdf",
            {
                "JOB_DIR"       : str(job_dir),
                "STATE_JSON"    : state_path,
                "PHASE_LOG_DIR" : str(croot / f"P9"),
                "MAXRUNTIME"    : str(state["P9_maxruntime"]),
            },
    )

    for i in range(1, n_dirs + 1):
        lines.append(f"RETRY P2_D{i} 0")
        lines.append(f"SCRIPT POST P2_D{i} /bin/true")
        lines.append(f"RETRY P7_D{i} 0")
        lines.append(f"SCRIPT POST P7_D{i} /bin/true")

    for i in range(1, n_dirs + 1):
        lines.append(f"PARENT P1_D{i} CHILD P2_D{i}")
        lines.append(f"PARENT P2_D{i} CHILD P3_D{i}")
        lines.append(f"PARENT P3_D{i} CHILD P4_D{i}")
    if n_dirs == 2:
        lines.append("PARENT P4_D1 P4_D2 CHILD P5")
        lines.append("PARENT P5 CHILD P6_D1 P6_D2")
        lines.append("PARENT P6_D1 CHILD P7_D1")
        lines.append("PARENT P6_D2 CHILD P7_D2")
        lines.append("PARENT P7_D1 CHILD P8_D1")
        lines.append("PARENT P7_D2 CHILD P8_D2")
        lines.append("PARENT P8_D1 P8_D2 CHILD P9")
    else:
        lines.append("PARENT P4_D1 CHILD P6_D1")
        lines.append("PARENT P6_D1 CHILD P7_D1")
        lines.append("PARENT P7_D1 CHILD P8_D1")
        lines.append("PARENT P8_D1 CHILD P9")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Master orchestration for Sherpa + Apprentice tuning")
    parser.add_argument("config", help="Path to YAML steering file")
    parser.add_argument("--dry-run", action="store_true", help="Render files and stop before submitting the DAG")
    args = parser.parse_args()

    print("Starting Initialisation...\n")

    config_path = Path(os.path.expanduser(args.config)).resolve()
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")
    print(f"Using config: {config_path}\n")

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise SystemExit("Config must be a YAML mapping")
    state = build_state(cfg, config_path)

    master_dir = Path(state["master_dir"])
    if master_dir.exists():
        if not master_dir.is_dir():
            raise SystemExit(f"Master path exists but is not a directory: {master_dir}")
        answer = input(f"Master directory already exists: {master_dir}\nRemove it and continue? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            raise SystemExit("Aborted.")
        shutil.rmtree(master_dir)
    master_dir.mkdir(parents=True, exist_ok=False)
    print(f"Created master directory: {master_dir}\n")

    print("Overview:")
    print(f"  - Input directories:")
    for idx, item in enumerate(state['input_dirs'], start=1):
        print(f"      Input {idx}: {item['path']} | grid = {item['grid_mode']} | "
              f"subruns = {item['n_subruns']} | validation subruns = {item['n_val_subruns']}")
    print(f"  - Sherpa binary: {state.get('sherpa_binary', '<unset>')}")
    print(f"  - app-tools installation: {state.get('app_tools_installation', '<unset>')}")
    print(f"  - Apprentice installation: {state.get('apprentice_installation', '<unset>')}")
    print(f"  - Rivet environment script: {state['rivet_env_script']}")
    print()
    print("  - Phases:")
    for phase, label in phase_overview(state):
        if phase != "P5": 
            print(f"    {phase} | {label} (maxruntime = {state.get(f'{phase}_maxruntime', 'n/a')})")
        else: 
            print(f"    {phase} | {label}")
    print()

    condor_output = Path(state["condor_output"])
    condor_output.mkdir(parents=True, exist_ok=True)
    for phase in ["P1", "P2", "P3", "P4", "P6", "P7", "P8"]:
        for i in range(1, len(state["input_dirs"]) + 1):
            (condor_output / f"{phase}_dir{i}").mkdir(parents=True, exist_ok=True)
    if len(state["input_dirs"]) == 2:
        (condor_output / "P5").mkdir(parents=True, exist_ok=True)
    (condor_output / "P9").mkdir(parents=True, exist_ok=True)
    print(f"Created condor output directories: {condor_output}")

    if state["merged_dir"]:
        merged_dir = Path(state["merged_dir"])
        if merged_dir.exists():
            raise SystemExit(f"Merged directory already exists: {merged_dir}")
        merged_dir.mkdir(parents=True, exist_ok=False)
        print(f"Created merged directory: {merged_dir}")
        if len(state["input_dirs"]) == 2:
            input_dir_paths = [Path(item["path"]) for item in state["input_dirs"]]
            write_stacked_json_values(input_dir_paths, merged_dir)
            print(f"Created combined reference data JSON:{merged_dir / 'data.json'}")
    state_path = master_dir / "state.json"
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Created state file: {state_path}")

    condor_ids = {"dagman": {"cluster_id": None}}
    for i in range(1, len(state["input_dirs"]) + 1):
        for p in [1, 2, 3, 4, 6, 7, 8]:
            condor_ids[f"P{p}_dir{i}"] = {"cluster_id": None}
    if len(state["input_dirs"]) == 2:
        condor_ids["P5"] = {"cluster_id": None}
    condor_ids["P9"] = {"cluster_id": None}
    Path(state["condor_ids_file"]).write_text(json.dumps(condor_ids, indent=2), encoding="utf-8")
    print(f"Created condor IDs file: {state['condor_ids_file']}")

    Path(state["phase_times_file"]).write_text("{}\n", encoding="utf-8")
    print(f"Created phase times file: {state['phase_times_file']}")

    dag_content = create_dag(state)
    dag_path = Path(state["dag_path"])
    dag_path.write_text(dag_content, encoding="utf-8")
    print(f"Created DAG file: {dag_path}")
    
    print()
    if args.dry_run:
        print(f"Dry run requested, not submitting DAGMan. Inspect the generated file at {dag_path}")
        return

    print(f"Submitting DAG: condor_submit_dag {dag_path.name}")
    proc = subprocess.run(
        ["condor_submit_dag", dag_path.name],
        cwd=str(master_dir),
        check=False,
        text=True,
        capture_output=True)
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.stderr:
        print(proc.stderr.strip())
    if proc.returncode != 0:
        raise SystemExit(f"condor_submit_dag failed with return code {proc.returncode}")
    m = re.search(r"submitted to cluster\s+(\d+)", (proc.stdout or "") + "\n" + (proc.stderr or ""), re.IGNORECASE)
    dag_cluster_id = m.group(1) if m else "unknown"
    state["dag_cluster_id"] = dag_cluster_id
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    condor_ids["dagman"] = {"cluster_id": dag_cluster_id}
    Path(state["condor_ids_file"]).write_text(json.dumps(condor_ids, indent=2), encoding="utf-8")

    print(f"\nInitialization complete!")


if __name__ == "__main__":
    main()
