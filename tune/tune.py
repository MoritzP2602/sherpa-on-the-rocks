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


def ensure_required_inputs(input_dir: Path, *, require_parameter: bool, require_nominal: bool) -> None:
    required_files = ["data.json", "template.yaml", "weights.txt"]
    if require_parameter:
        required_files.append("parameter.json")
    for fname in required_files:
        path = input_dir / fname
        if not path.exists():
            raise FileNotFoundError(f"Missing required file: {path}")
    if require_nominal:
        nominal_path = input_dir / "nominal.json"
        if not nominal_path.exists():
            raise FileNotFoundError(f"Missing required file: {nominal_path}")
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


def get_n_parameters(parameter_json_path: Path) -> int:
    data = json.loads(parameter_json_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "parameters" in data:
            p = data["parameters"]
            if isinstance(p, dict):
                return len(p)
            if isinstance(p, list):
                return len(p)
        return len(data)
    if isinstance(data, list):
        return len(data)
    raise ValueError(f"Could not obtain number of parameters from {parameter_json_path}")

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


def parse_on_off(value, key: str) -> bool:
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"on", "true"}:
        return True
    if raw in {"off", "false"}:
        return False
    raise ValueError(f"{key} entries must be one of: on/off/true/false, got '{value}'")

def parse_surrogate_order(value: str) -> tuple[int, int]:
    parts = [x.strip() for x in str(value).split(",")]
    if len(parts) != 2:
        raise ValueError("SURROGATE_ORDER must have exactly two comma-separated integers, e.g. '2,1'")
    try:
        k_p = int(parts[0])
        k_q = int(parts[1])
    except ValueError as e:
        raise ValueError("SURROGATE_ORDER must contain integers, e.g. '2,1'") from e
    if k_p < 0 or k_q < 0:
        raise ValueError("SURROGATE_ORDER entries must be >= 0")
    return k_p, k_q

def parse_input_dir_blocks(cfg, config_path: Path):
    blocks = []
    for key in ("INPUT_DIR1", "INPUT_DIR2"):
        if key not in cfg:
            continue
        block = cfg[key]
        if not isinstance(block, dict):
            raise ValueError(f"{key} must be a mapping")
        if "PATH" not in block:
            raise KeyError(f"Missing required key: {key}.PATH")
        if "EVENTS" not in block:
            raise KeyError(f"Missing required key: {key}.EVENTS")

        if "EVENTS_VALIDATION" in block:
            events_validation_raw = block["EVENTS_VALIDATION"]
        else:
            raise KeyError(f"Missing required key: {key}.EVENTS_VALIDATION")

        blocks.append({
                "path"                 : resolve_cfg_path(block["PATH"], config_path),
                "events_raw"           : block["EVENTS"],
                "events_validation_raw": events_validation_raw,
                "reweight"             : parse_on_off(block.get("REWEIGHTING", "off"), f"{key}.REWEIGHTING"),
                "validation_reweight"  : parse_on_off(block.get("VALIDATION_REWEIGHTING", "off"), 
                                                      f"{key}.VALIDATION_REWEIGHTING")
                      })
    if not blocks:
        raise KeyError("Missing required key: INPUT_DIR1")
    return blocks


def build_state(cfg, config_path: Path):
    required_keys = [
        "INPUT_DIR1",
        "N_GRID",
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

    input_dir_blocks = parse_input_dir_blocks(cfg, config_path)
    input_dirs = [b["path"] for b in input_dir_blocks]
    n_dirs = len(input_dirs)
    if n_dirs not in (1, 2):
        raise ValueError("Provide one or two input directories via INPUT_DIR1[/INPUT_DIR2]")

    merge_mode = str(cfg.get("MERGE_MODE", "yoda")).strip().lower()
    if merge_mode not in {"yoda", "rivet"}:
        raise ValueError("MERGE_MODE must be 'yoda' or 'rivet'")

    start_point_survey = int(cfg.get("START_POINT_SURVEY", 500))
    restarts = int(cfg.get("RESTARTS", 20))
    if start_point_survey <= 0:
        raise ValueError("START_POINT_SURVEY must be > 0")
    if restarts < 0:
        raise ValueError("RESTARTS must be >= 0")

    combine_mode = str(cfg.get("COMBINE_MODE", "weighted")).strip().lower()
    if n_dirs == 2 and combine_mode not in {"weighted", "equal"}:
        raise ValueError("COMBINE_MODE must be 'weighted' or 'equal' for two-input tunes")

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
    
    if "JOB_DIR" in cfg:
        job_dir = resolve_cfg_path(cfg["JOB_DIR"], config_path)
    else: job_dir = (sherpa_on_the_rocks_dir / "tune").resolve()

    n_grid = int(cfg["N_GRID"])
    if n_grid <= 0:
        raise ValueError("N_GRID must be > 0")
    
    surrogate_order = str(cfg["SURROGATE_ORDER"]).strip()
    if not surrogate_order:
        raise ValueError("SURROGATE_ORDER must not be empty")
    
    k_p, k_q     = parse_surrogate_order(surrogate_order)
    grid_warning = ""
    n_params     = get_n_parameters(input_dirs[0] / "parameter.json")
    min_grid     = math.comb(n_params + k_p, k_p) + math.comb(n_params + k_q, k_q)
    if n_grid < min_grid:
        raise ValueError(f"N_GRID = {n_grid} is too small. Minimum required is "
                         f"{min_grid} with N_p = {n_params} and order = {surrogate_order}.")
    if n_grid < 2 * min_grid:
        grid_warning = (f"WARNING: N_GRID = {n_grid} is < 2 * minimum = {2 * min_grid}. "
                        f"Using at least double the minimum is recommended for stable surrogate fitting.")

    input_states = []
    for i, block in enumerate(input_dir_blocks, start=1):
        idir = block["path"]
        reweight = block["reweight"]
        validation_reweight = block["validation_reweight"]
        ensure_required_inputs(idir, require_parameter=(i == 1), require_nominal=(reweight or validation_reweight))

        grid_mode       = "sample" if i == 1 else "import"
        req_events      = parse_event_value(block["events_raw"])
        req_events_val  = parse_event_value(block["events_validation_raw"])
        template_events = parse_template_events(idir / "template.yaml")
        n_subruns       = int(math.ceil(req_events / template_events))
        n_val_subruns   = int(math.ceil(req_events_val / template_events))

        input_states.append({
                "path"               : str(idir),
                "reweight"           : reweight,
                "validation_reweight": validation_reweight,
                "grid_mode"          : grid_mode,
                "events"             : req_events,
                "events_validation"  : req_events_val,
                "template_events"    : template_events,
                "n_subruns"          : n_subruns,
                "n_val_subruns"      : n_val_subruns,
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
        "start_point_survey"      : start_point_survey,
        "restarts"                : restarts,
        "combine_mode"            : combine_mode,
        "merged_dir"              : merged_dir,
        "merge_mode"              : merge_mode,
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
    return state, grid_warning


def dag_jobs(n_dirs: int) -> list[str]:
    jobs: list[str] = []
    for i in range(1, n_dirs + 1):
        jobs.extend([f"P1_dir{i}", f"P2_dir{i}", f"P3_dir{i}", f"P4_dir{i}"])
    if n_dirs == 2:
        jobs.append("P5")
    for i in range(1, n_dirs + 1):
        jobs.extend([f"P6_dir{i}", f"P7_dir{i}", f"P8_dir{i}"])
    jobs.append("P9")
    return jobs


def dag_dependencies(n_dirs: int) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for i in range(1, n_dirs + 1):
        edges.extend([
                (f"P1_dir{i}", f"P2_dir{i}"),
                (f"P2_dir{i}", f"P3_dir{i}"),
                (f"P3_dir{i}", f"P4_dir{i}"),
                     ])
    if n_dirs == 2:
        edges.extend([
                ("P4_dir1", "P5"),
                ("P4_dir2", "P5"),
                ("P5", "P6_dir1"),
                ("P5", "P6_dir2"),
                ("P6_dir1", "P7_dir1"),
                ("P6_dir2", "P7_dir2"),
                ("P7_dir1", "P8_dir1"),
                ("P7_dir2", "P8_dir2"),
                ("P8_dir1", "P9"),
                ("P8_dir2", "P9"),
                     ])
    else:
        edges.extend([
                ("P4_dir1", "P6_dir1"),
                ("P6_dir1", "P7_dir1"),
                ("P7_dir1", "P8_dir1"),
                ("P8_dir1", "P9"),
                     ])
    return edges


def completed_jobs_from_phase_times(phase_times: dict, n_dirs: int) -> set[str]:
    completed: set[str] = set()
    for job in dag_jobs(n_dirs):
        if (phase_times.get(job) or {}).get("end_time"):
            completed.add(job)
    return completed


def jobs_to_resume(phase_times: dict, n_dirs: int) -> set[str]:
    all_jobs = dag_jobs(n_dirs)
    completed = completed_jobs_from_phase_times(phase_times, n_dirs)
    include: set[str] = {job for job in all_jobs if job not in completed}

    changed = True
    edges = dag_dependencies(n_dirs)
    while changed:
        changed = False
        for parent, child in edges:
            if parent in include and child not in include:
                include.add(child)
                changed = True
    return include


def reset_phase_output(state: dict, jobs: set[str]) -> list[Path]:
    croot = Path(state["condor_output"])
    recreated: list[Path] = []
    for job in sorted(jobs):
        if "_dir" in job:
            phase, dir_idx = job.split("_dir", 1)
            target = croot / f"{phase}_dir{dir_idx}"
        else:
            target = croot / job
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        recreated.append(target)
    return recreated


def cleanup_dagman_files(master_dir: Path, dag_path: Path) -> None:
    base_name = dag_path.name
    for p in sorted(master_dir.glob(f"{base_name}.rescue*")):
        if p.is_file():
            p.unlink()
    lock_path = master_dir / f"{base_name}.lock"
    if lock_path.exists() and lock_path.is_file():
        lock_path.unlink()
    blocking_files = [
        f"{base_name}.condor.sub",
        f"{base_name}.lib.out",
        f"{base_name}.lib.err",
        f"{base_name}.dagman.log",
        f"{base_name}.metrics",
        f"{base_name}.nodes.log",
    ]
    for fname in blocking_files:
        p = master_dir / fname
        if p.exists() and p.is_file():
            p.unlink()
    for p in sorted(master_dir.glob(f"{base_name}.dagman.out*")):
        if p.is_file():
            p.unlink()
    print(f"Removed existing DAGMan files in {master_dir}")
    return


def handle_resume(current_state: dict) -> tuple[dict, Path, bool, set[str]]:
    state = current_state
    resume_mode = False
    resume_jobs: set[str] = set()
    master_dir = Path(state["master_dir"])

    if master_dir.exists():
        if not master_dir.is_dir():
            raise SystemExit(f"Master path exists but is not a directory: {master_dir}")

        saved_state_path = master_dir / "state.json"
        saved_phase_times_path = master_dir / "phase_times.json"
        if saved_state_path.exists() and saved_phase_times_path.exists():
            try:
                saved_state = json.loads(saved_state_path.read_text(encoding="utf-8"))
                phase_times = json.loads(saved_phase_times_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Found existing run metadata but could not parse it for resume: {e}")
            else:
                if comparable_state(saved_state) == comparable_state(state):
                    n_dirs_saved = len(saved_state["input_dirs"])
                    resume_jobs_candidate = jobs_to_resume(phase_times, n_dirs_saved)
                    if not resume_jobs_candidate:
                        print("Detected existing completed run (all phases have end_time).")
                    else:
                        completed_jobs = completed_jobs_from_phase_times(phase_times, n_dirs_saved)
                        print(f"Detected resumable run in: {master_dir}")
                        print(f"Completed jobs: {len(completed_jobs)} / {len(dag_jobs(n_dirs_saved))}. "
                              f"Will submit remaining jobs: {len(resume_jobs_candidate)}")
                        answer = input("Resume at job level and keep existing outputs? [y/N]: ").strip().lower()
                        if answer in {"y", "yes"}:
                            resume_mode = True
                            state = saved_state
                            resume_jobs = resume_jobs_candidate
                            master_dir = Path(state["master_dir"])
                        else: print("Resume declined.")
                else: print("Existing run state does not match current config-derived state. Resume is disabled.")
        if not resume_mode:
            answer = input(f"Master directory already exists: {master_dir}\nRemove it and continue? [y/N]: ").strip().lower()
            if answer not in {"y", "yes"}:
                raise SystemExit("Aborted.")
            shutil.rmtree(master_dir)
    if not resume_mode:
        master_dir.mkdir(parents=True, exist_ok=False)
        print(f"Created master directory: {master_dir}\n")
    else:
        print(f"Using existing master directory: {master_dir}\n")
        print("Resume mode: keeping existing state, condor IDs, phase times, and outputs.")
        if resume_jobs:
            recreated = reset_phase_output(state, resume_jobs)
            print(f"Reset condor output directories for {len(recreated)} uncompleted job(s).")
            cleanup_dagman_files(master_dir, Path(state["dag_path"]))
    return state, master_dir, resume_mode, resume_jobs


def comparable_state(state: dict) -> dict:
    normalized = json.loads(json.dumps(state))
    normalized.pop("created_at", None)
    normalized.pop("dag_cluster_id", None)
    normalized.pop("config_path", None)
    normalized.pop("condor_ids_file", None)
    normalized.pop("phase_times_file", None)
    normalized.pop("dag_path", None)
    return normalized


def create_dag(state, include_jobs: set[str]):
    master_dir = Path(state["master_dir"]) 
    croot      = Path(state["condor_output"]) 
    job_dir    = Path(state["job_dir"]) 
    state_path = str((master_dir / "state.json").resolve())
    n_dirs     = len(state["input_dirs"])

    def include_job(job_name: str) -> bool:
        return job_name in include_jobs

    lines = []
    lines.append("# Auto-generated by tune.py")
    def v(name, submit, vars_map):
        lines.append(f"JOB {name} {(job_dir / submit).resolve()}")
        vars_str = " ".join([f'{k}="{v}"' for k, v in vars_map.items()])
        lines.append(f"VARS {name} {vars_str}")
    for i in range(1, n_dirs + 1):
        if include_job(f"P1_dir{i}"):
            v(f"P1_dir{i}",
              f"P1.jdf",
                {"JOB_DIR"       : str(job_dir),
                 "STATE_JSON"    : state_path,
                 "DIR_INDEX"     : str(i),
                 "PHASE_LOG_DIR" : str(croot / f"P1_dir{i}"),
                 "MAXRUNTIME"    : str(state["P1_maxruntime"])})
        if include_job(f"P2_dir{i}"):
            v(f"P2_dir{i}",
              f"P2.jdf",
                {"JOB_DIR"       : str(job_dir),
                 "STATE_JSON"    : state_path,
                 "DIR_INDEX"     : str(i),
                 "PHASE_LOG_DIR" : str(croot / f"P2_dir{i}"),
                 "RUNS_FILE"     : str(Path(state["input_dirs"][i - 1]["path"]) / "runs.txt"),
                 "RUN_DIR"       : state["input_dirs"][i - 1]["path"],
                 "MAXRUNTIME"    : str(state["P2_maxruntime"]),
                 "PHASE_KEY"     : "P2"})
        if include_job(f"P3_dir{i}"):
            v(f"P3_dir{i}",
              f"P3.jdf",
                {"JOB_DIR"       : str(job_dir),
                 "STATE_JSON"    : state_path,
                 "DIR_INDEX"     : str(i),
                 "PHASE_LOG_DIR" : str(croot / f"P3_dir{i}"),
                 "MAXRUNTIME"    : str(state["P3_maxruntime"])})
        if include_job(f"P4_dir{i}"):
            v(f"P4_dir{i}",
              f"P4.jdf",
                {"JOB_DIR"       : str(job_dir),
                 "STATE_JSON"    : state_path,
                 "DIR_INDEX"     : str(i),
                 "PHASE_LOG_DIR" : str(croot / f"P4_dir{i}"),
                 "MAXRUNTIME"    : str(state["P4_maxruntime"])})
    if include_job("P5"):
            v(f"P5",
              f"P5.jdf",
                {"JOB_DIR"       : str(job_dir),
                 "STATE_JSON"    : state_path,
                 "PHASE_LOG_DIR" : str(croot / f"P5"),
                 "MAXRUNTIME"    : str(state["P5_maxruntime"])})
    for i in range(1, n_dirs + 1):
        if include_job(f"P6_dir{i}"):
            v(f"P6_dir{i}",
              f"P6.jdf",
                {"JOB_DIR"       : str(job_dir),
                 "STATE_JSON"    : state_path,
                 "DIR_INDEX"     : str(i),
                 "PHASE_LOG_DIR" : str(croot / f"P6_dir{i}"),
                 "MAXRUNTIME"    : str(state["P6_maxruntime"])})
        if include_job(f"P7_dir{i}"):
            v(f"P7_dir{i}",
              f"P7.jdf",
                {"JOB_DIR"       : str(job_dir),
                 "STATE_JSON"    : state_path,
                 "DIR_INDEX"     : str(i),
                 "RUN_DIR"       : state["input_dirs"][i - 1]["path"],
                 "RUNS_FILE"     : str(Path(state["input_dirs"][i - 1]["path"]) / "runs.txt"),
                 "PHASE_LOG_DIR" : str(croot / f"P7_dir{i}"),
                 "MAXRUNTIME"    : str(state["P7_maxruntime"]),
                 "PHASE_KEY"     : "P7"})
        if include_job(f"P8_dir{i}"):
            v(f"P8_dir{i}",
              f"P8.jdf",
                {"JOB_DIR"       : str(job_dir),
                 "STATE_JSON"    : state_path,
                 "DIR_INDEX"     : str(i),
                 "PHASE_LOG_DIR" : str(croot / f"P8_dir{i}"),
                 "MAXRUNTIME"    : str(state["P8_maxruntime"])})
    if include_job("P9"):
            v(f"P9",
              f"P9.jdf",
                {"JOB_DIR"       : str(job_dir),
                 "STATE_JSON"    : state_path,
                 "PHASE_LOG_DIR" : str(croot / f"P9"),
                 "MAXRUNTIME"    : str(state["P9_maxruntime"])})
    for i in range(1, n_dirs + 1):
        if include_job(f"P2_dir{i}"):
            lines.append(f"RETRY P2_dir{i} 0")
            lines.append(f"SCRIPT POST P2_dir{i} /bin/true")
        if include_job(f"P7_dir{i}"):
            lines.append(f"RETRY P7_dir{i} 0")
            lines.append(f"SCRIPT POST P7_dir{i} /bin/true")
    for parent, child in dag_dependencies(n_dirs):
        if include_job(parent) and include_job(child):
            lines.append(f"PARENT {parent} CHILD {child}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Master orchestration for Sherpa + Apprentice tuning")
    parser.add_argument("config", help="Path to YAML steering file")
    args = parser.parse_args()

    print("Starting Initialisation...\n")

    config_path = Path(os.path.expanduser(args.config)).resolve()
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")
    print(f"Using config: {config_path}\n")

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise SystemExit("Config must be a YAML mapping")
    state, grid_warning = build_state(cfg, config_path)
    state, master_dir, resume_mode, resume_jobs = handle_resume(state)

    print("Overview:")
    print(f"  - Input directories:")
    for idx, item in enumerate(state['input_dirs'], start=1):
        output = f"      Input {idx}: {item['path']} | grid = {item['grid_mode']} | "
        if item['reweight']:
            output += "reweighting = on | "
        output += f"subruns = {item['n_subruns']} | "
        if item['validation_reweight']:
            output += "validation reweighting = on | "
        output += f"validation subruns = {item['n_val_subruns']}"
        print(output)
    print(f"  - Sherpa binary: {state.get('sherpa_binary', '<unset>')}")
    print(f"  - app-tools installation: {state.get('app_tools_installation', '<unset>')}")
    print(f"  - Apprentice installation: {state.get('apprentice_installation', '<unset>')}")
    print(f"  - Rivet environment script: {state['rivet_env_script']}")
    if grid_warning:
        print()
        print(grid_warning)
    print()
    print("  - Phases:")
    for phase, label in phase_overview(state):
        if phase != "P5": 
            print(f"    {phase} | {label} (maxruntime = {state.get(f'{phase}_maxruntime', 'n/a')})")
        else: 
            print(f"    {phase} | {label}")
    if resume_mode: print("  - Resuming jobs: " + ", ".join(sorted(resume_jobs)))
    print()

    state_path = master_dir / "state.json"
    condor_ids = None
    if not resume_mode:
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

    dag_content = create_dag(state, include_jobs=resume_jobs if resume_mode else set(dag_jobs(len(state["input_dirs"]))))
    dag_path = Path(state["dag_path"])
    dag_path.write_text(dag_content, encoding="utf-8")
    if resume_mode:
        print(f"Created DAG file for job-level resume ({len(resume_jobs or set())} jobs): {dag_path}")
    else:
        print(f"Created DAG file: {dag_path}")

    print()
    answer = input("Proceed with DAG submission now? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        print(f"Submission cancelled. You can review generated files in: {master_dir}")
        print(f"Submit manually with: cd {master_dir} && condor_submit_dag {dag_path.name}")
        print(f"\nInitialization complete!")
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
    if state_path.exists():
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    if condor_ids is None:
        condor_ids = {}
        condor_ids_path = Path(state["condor_ids_file"])
        if condor_ids_path.exists():
            try:
                condor_ids = json.loads(condor_ids_path.read_text(encoding="utf-8"))
            except Exception:
                condor_ids = {}
    condor_ids["dagman"] = {"cluster_id": dag_cluster_id}
    Path(state["condor_ids_file"]).write_text(json.dumps(condor_ids, indent=2), encoding="utf-8")

    print(f"\nInitialization complete!")


if __name__ == "__main__":
    main()
