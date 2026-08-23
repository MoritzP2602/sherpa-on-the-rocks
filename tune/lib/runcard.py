from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from pathlib import Path

import phases

EVENT_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmMgG]?)\s*$")
TEMPLATE_EVENTS_RE = re.compile(r"^\s*EVENTS\s*:\s*(.+?)\s*$")

RESERVED_OPTIONS = {
    "APP_BUILD_OPTIONS" : ("--order", "-w", "--weights", "-o", "--output", "--errs"),
    "APP_TUNE2_OPTIONS" : ("-o", "--output", "-e"),
    "PROF2_IPOL_OPTIONS": ("--order", "-w", "--weights", "-j"),
    "PROF2_TUNE_OPTIONS": ("-w", "--weights", "-o", "--outdir", "-R"),
}

KNOWN_KEYS = {
    "N_GRID", "GRID_SAMPLING", "REWEIGHTING_PATTERN",
    "MERGE_MODE", "MERGE_OPTIONS", "COMBINE_MODE",
    "VALIDATION_ONLY_ERR", "VALIDATION_ONLY_MERGED",
    "START_PHASE", "END_PHASE",
    "NPROC", "MPI_MODULE", "NUMBA_DISABLE_JIT", "EMAIL",
    "MASTER_DIR", "MERGED_DIR",
    "RIVET_ENV_SCRIPT", "SHERPA_ON_THE_ROCKS_DIR", "APP_TOOLS_INSTALLATION",
    "SHERPA_BINARY",
}
KNOWN_KEYS |= {spec["runcard"] for spec in phases.BACKENDS.values()}
KNOWN_KEYS |= {spec["install_cfg"] for spec in phases.BACKENDS.values()}
KNOWN_KEY_PATTERNS = (re.compile(r"^INPUT_DIR\d+$"),
                      re.compile(r"^PHASE\d+_MAXRUNTIME$"))


# --------------------------------------------------------------------------- #
# Small value parsers
# --------------------------------------------------------------------------- #

def parse_event_value(value) -> int:
    raw = str(value).strip()
    m = EVENT_RE.match(raw)
    if not m:
        raise ValueError(f"Invalid event value '{value}'. Use forms like 500k, 20M, 1G.")
    factor = {"": 1, "K": 10**3, "M": 10**6, "G": 10**9}[m.group(2).upper()]
    return int(math.ceil(float(m.group(1)) * factor))


def parse_template_events(template_path: Path) -> int:
    """The event count one Sherpa subrun produces, from the runcard template."""
    for line in template_path.read_text(encoding="utf-8").splitlines():
        m = TEMPLATE_EVENTS_RE.match(line)
        if not m:
            continue
        value = m.group(1).split("#", 1)[0].strip().strip('"').strip("'")
        return parse_event_value(value)
    raise ValueError(f"Could not find EVENTS: in {template_path}")


def parse_on_off(value, key: str) -> bool:
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"on", "true"}:
        return True
    if raw in {"off", "false"}:
        return False
    raise ValueError(f"{key} entries must be one of: on/off/true/false, got '{value}'")


def parse_apprentice_order(value) -> tuple[int, int]:
    parts = [x.strip() for x in str(value).split(",")]
    if len(parts) != 2:
        raise ValueError("APPRENTICE.ORDER must have exactly two comma-separated integers, e.g. '2,1' "
                         "(in a list, quote each entry, e.g. ORDER: [\"2,0\", \"3,0\"])")
    try:
        k_p, k_q = int(parts[0]), int(parts[1])
    except ValueError as e:
        raise ValueError("APPRENTICE.ORDER must contain integers, e.g. '2,1'") from e
    if k_p < 0 or k_q < 0:
        raise ValueError("APPRENTICE.ORDER entries must be >= 0")
    return k_p, k_q


def parse_professor_order(value) -> int:
    raw = str(value).strip()
    if "," in raw or len(raw.split()) != 1:
        raise ValueError("PROFESSOR.ORDER must be a single integer, e.g. '2'")
    try:
        k = int(raw)
    except ValueError as e:
        raise ValueError("PROFESSOR.ORDER must be a single integer, e.g. '2'") from e
    if k < 0:
        raise ValueError("PROFESSOR.ORDER must be >= 0")
    return k


def parse_order_list(value, key: str, parse_single, canonicalize) -> list[str]:
    items = value if isinstance(value, list) else [value]
    if not items:
        raise KeyError(f"Missing required key: {key}")
    orders = []
    for item in items:
        raw = str(item).strip()
        if not raw:
            raise ValueError(f"{key} entries must be non-empty")
        orders.append(canonicalize(parse_single(raw)))
    if len(set(orders)) != len(orders):
        raise ValueError(f"{key} contains duplicate orders: {orders}")
    return orders


def parse_repeat(value, key: str) -> int:
    """How many times each tune of a backend is submitted."""
    try:
        n = int(str(value).strip())
    except ValueError as e:
        raise ValueError(f"{key} must be a positive integer, e.g. '5'") from e
    if n < 1:
        raise ValueError(f"{key} must be >= 1")
    return n


def parse_backend_options(block: dict, key: str) -> str:
    value = block.get(key)
    if value is None:
        return ""
    text = str(value).strip()
    for token in text.split():
        name = token.split("=", 1)[0]
        if name in RESERVED_OPTIONS.get(key, ()):
            raise ValueError(f"{key} may not contain '{name}': tune.py sets it on every job")
    return text


def parse_phase_key(value, key: str) -> str:
    """A phase name from the runcard: 'P5' or plain '5'."""
    raw = str(value).strip().upper()
    if not raw.startswith("P"):
        raw = f"P{raw}"
    if raw not in phases.PHASE_KEYS:
        raise ValueError(f"{key} must be one of {', '.join(phases.PHASE_KEYS)}, got '{value}'")
    return raw


def resolve_cfg_path(value, config_path: Path) -> Path:
    p = Path(os.path.expanduser(str(value)))
    if p.is_absolute():
        return p.resolve()
    return (config_path.parent / p).resolve()


def get_n_parameters(parameter_json_path: Path) -> int:
    data = json.loads(parameter_json_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if "parameters" in data:
            return len(data["parameters"])
        return len(data)
    if isinstance(data, list):
        return len(data)
    raise ValueError(f"Could not obtain number of parameters from {parameter_json_path}")


# --------------------------------------------------------------------------- #
# Blocks
# --------------------------------------------------------------------------- #

def unknown_keys(cfg: dict) -> list[str]:
    return sorted(str(key) for key in cfg
                  if str(key) not in KNOWN_KEYS
                  and not any(p.match(str(key)) for p in KNOWN_KEY_PATTERNS))


def parse_input_dir_blocks(cfg: dict, config_path: Path) -> list[dict]:
    indices = sorted(int(m.group(1)) for key in cfg
                     if (m := re.fullmatch(r"INPUT_DIR(\d+)", str(key))))
    if not indices:
        raise KeyError("Missing required key: INPUT_DIR1")
    if indices[0] < 1:
        raise KeyError(f"INPUT_DIR numbering starts at 1, got INPUT_DIR{indices[0]}")
    expected = list(range(1, len(indices) + 1))
    if indices != expected:
        missing = next(i for i in expected if i not in indices)
        raise KeyError(f"INPUT_DIR keys must be numbered contiguously from 1: "
                       f"found INPUT_DIR{max(indices)} but INPUT_DIR{missing} is missing")
    blocks = []
    for idx in indices:
        key = f"INPUT_DIR{idx}"
        block = cfg[key]
        if not isinstance(block, dict):
            raise ValueError(f"{key} must be a mapping")
        for field in ("PATH", "EVENTS", "EVENTS_VALIDATION"):
            if field not in block:
                raise KeyError(f"Missing required key: {key}.{field}")
        blocks.append({
            "path"                 : resolve_cfg_path(block["PATH"], config_path),
            "events_raw"           : block["EVENTS"],
            "events_validation_raw": block["EVENTS_VALIDATION"],
            "reweight"             : parse_on_off(block.get("REWEIGHTING", "off"),
                                                  f"{key}.REWEIGHTING"),
        })
    return blocks


ORDERS = {
    "app" : (parse_apprentice_order, lambda kq: f"{kq[0]},{kq[1]}"),
    "prof": (parse_professor_order, str),
}


def parse_backend_block(cfg: dict, key: str, config_path: Path) -> tuple[dict, str]:
    """One backend's settings, plus the installation path it needs."""
    spec = phases.BACKENDS[key]
    name, install_cfg = spec["runcard"], spec["install_cfg"]
    parse_single, canonicalize = ORDERS[key]

    block = cfg[name]
    if not isinstance(block, dict):
        raise ValueError(f"{name} must be a mapping with at least an ORDER key")
    if "ORDER" not in block:
        raise KeyError(f"Missing required key: {name}.ORDER")
    if install_cfg not in cfg:
        raise KeyError(f"Missing required key: {install_cfg} "
                       f"(required when {name} is configured)")
    installation = resolve_cfg_path(cfg[install_cfg], config_path)
    if not installation.exists():
        raise FileNotFoundError(f"{install_cfg} does not exist: {installation}")

    orders = parse_order_list(block["ORDER"], f"{name}.ORDER", parse_single, canonicalize)
    settings = {"orders"     : orders,
                "orders_safe": [o.replace(",", "_") for o in orders],
                "repeat"     : parse_repeat(block.get("REPEAT", 1), f"{name}.REPEAT")}
    for option_name, state_key in spec["options"]:
        settings[state_key] = parse_backend_options(block, option_name)
    return settings, str(installation)


def minimum_grid_size(key: str, orders: list[str], n_params: int) -> int:
    """The smallest grid the largest configured surrogate order can be fitted on."""
    smallest = 0
    for order in orders:
        if key == "app":
            k_p, k_q = parse_apprentice_order(order)
            need = math.comb(n_params + k_p, k_p) + math.comb(n_params + k_q, k_q)
        else:
            k = parse_professor_order(order)
            need = math.comb(n_params + k, k)
        smallest = max(smallest, need)
    return smallest


# --------------------------------------------------------------------------- #
# The state
# --------------------------------------------------------------------------- #

def build_state(cfg: dict, config_path: Path) -> tuple[dict, list[str]]:
    """The run state, and the warnings worth showing before it is used."""
    warnings: list[str] = []

    stray = unknown_keys(cfg)
    if stray:
        warnings.append("Ignoring unrecognised runcard key(s): " + ", ".join(stray))

    for key in ("INPUT_DIR1", "N_GRID", "SHERPA_ON_THE_ROCKS_DIR",
                "APP_TOOLS_INSTALLATION", "SHERPA_BINARY", "RIVET_ENV_SCRIPT"):
        if key not in cfg:
            raise KeyError(f"Missing required key: {key}")
    if not any(spec["runcard"] in cfg for spec in phases.BACKENDS.values()):
        raise KeyError("Provide at least one backend: "
                       + " and/or ".join(spec["runcard"] for spec in phases.BACKENDS.values()))

    # -- input directories --------------------------------------------------
    blocks = parse_input_dir_blocks(cfg, config_path)
    n_dirs = len(blocks)
    for idx, block in enumerate(blocks, start=1):
        if not block["path"].is_dir():
            raise FileNotFoundError(
                f"INPUT_DIR{idx} does not exist or is not a directory: {block['path']}")

    # -- paths --------------------------------------------------------------
    resolved = {}
    for key in ("RIVET_ENV_SCRIPT", "SHERPA_ON_THE_ROCKS_DIR",
                "APP_TOOLS_INSTALLATION", "SHERPA_BINARY"):
        resolved[key] = resolve_cfg_path(cfg[key], config_path)
        if not resolved[key].exists():
            raise FileNotFoundError(f"{key} does not exist: {resolved[key]}")
    if not resolved["SHERPA_ON_THE_ROCKS_DIR"].is_dir():
        raise FileNotFoundError("SHERPA_ON_THE_ROCKS_DIR does not exist or is not a "
                                f"directory: {resolved['SHERPA_ON_THE_ROCKS_DIR']}")

    master_dir = (resolve_cfg_path(cfg["MASTER_DIR"], config_path) if "MASTER_DIR" in cfg
                  else (blocks[0]["path"] / "master").resolve())
    if n_dirs >= 2:
        merged_dir = str(resolve_cfg_path(cfg["MERGED_DIR"], config_path)
                         if str(cfg.get("MERGED_DIR", "")).strip()
                         else (blocks[0]["path"] / "merged").resolve())
    else:
        merged_dir = ""

    # -- backends -----------------------------------------------------------
    backends = {key: {} for key in phases.BACKENDS}
    installations = {key: "" for key in phases.BACKENDS}
    for key, spec in phases.BACKENDS.items():
        if spec["runcard"] in cfg:
            backends[key], installations[key] = parse_backend_block(cfg, key, config_path)

    # -- grid ---------------------------------------------------------------
    n_grid = int(cfg["N_GRID"])
    if n_grid <= 0:
        raise ValueError("N_GRID must be > 0")
    grid_sampling = str(cfg.get("GRID_SAMPLING", "random")).strip().lower()
    if grid_sampling not in {"random", "uniform"}:
        raise ValueError("GRID_SAMPLING must be 'random' or 'uniform'")

    parameter_json = blocks[0]["path"] / "parameter.json"
    if not parameter_json.exists():
        raise FileNotFoundError(f"Missing required file: {parameter_json}")
    n_params = get_n_parameters(parameter_json)
    smallest = max([minimum_grid_size(key, block["orders"], n_params)
                    for key, block in backends.items() if block] or [0])
    if n_grid < smallest:
        raise ValueError(f"N_GRID = {n_grid} is too small. Minimum required is "
                         f"{smallest} with N_p = {n_params} for the configured "
                         "polynomial order(s).")
    if n_grid < 2 * smallest:
        warnings.append(f"N_GRID = {n_grid} is < 2 * minimum = {2 * smallest}. Using at "
                        "least double the minimum is recommended for stable surrogate fitting.")

    # -- everything else ----------------------------------------------------
    pattern = str(cfg.get("REWEIGHTING_PATTERN", "")).strip()
    if any(b["reweight"] for b in blocks) and not pattern:
        raise KeyError("Missing required key: REWEIGHTING_PATTERN (required when INPUT_DIRx.REWEIGHTING is on)")

    merge_mode = str(cfg.get("MERGE_MODE", "rivet")).strip().lower()
    if merge_mode not in {"rivet", "yoda"}:
        raise ValueError("MERGE_MODE must be 'rivet' or 'yoda'")

    combine_mode = str(cfg.get("COMBINE_MODE", "weighted")).strip().lower()
    if n_dirs >= 2 and combine_mode not in {"weighted", "simple", "custom"}:
        raise ValueError("COMBINE_MODE must be 'weighted', 'simple' or 'custom' for multi-input tunes")

    validation_only_err = parse_on_off(cfg.get("VALIDATION_ONLY_ERR", "off"), "VALIDATION_ONLY_ERR")
    validation_only_merged = parse_on_off(cfg.get("VALIDATION_ONLY_MERGED", "off"),
                                          "VALIDATION_ONLY_MERGED")
    if validation_only_merged and n_dirs < 2:
        raise ValueError("VALIDATION_ONLY_MERGED requires at least two input directories "
                         "(no merged tune exists for a single input)")

    nproc = int(cfg.get("NPROC", 8))
    if nproc <= 0:
        raise ValueError("NPROC must be > 0")

    start_phase = parse_phase_key(cfg.get("START_PHASE", phases.PHASE_KEYS[0]), "START_PHASE")
    end_phase = parse_phase_key(cfg.get("END_PHASE", phases.PHASE_KEYS[-1]), "END_PHASE")
    if phases.number(start_phase) > phases.number(end_phase):
        raise ValueError(f"START_PHASE ({start_phase}) must not come after END_PHASE ({end_phase})")

    # -- per-directory subrun counts ----------------------------------------
    input_states = []
    for i, block in enumerate(blocks, start=1):
        template = block["path"] / "template.yaml"
        per_subrun = parse_template_events(template) if template.exists() else 0
        events = parse_event_value(block["events_raw"])
        events_validation = parse_event_value(block["events_validation_raw"])
        input_states.append({
            "path"             : str(block["path"]),
            "reweight"         : block["reweight"],
            "grid_mode"        : "sample" if i == 1 else "import",
            "events"           : events,
            "events_validation": events_validation,
            "template_events"  : per_subrun,
            "n_subruns"        : int(math.ceil(events / per_subrun)) if per_subrun else 0,
            "n_val_subruns"    : int(math.ceil(events_validation / per_subrun)) if per_subrun else 0,
        })

    state = {
        "created_at"              : datetime.now().isoformat(timespec="seconds"),
        "config_path"             : str(config_path.resolve()),
        "rivet_env_script"        : str(resolved["RIVET_ENV_SCRIPT"]),
        "sherpa_on_the_rocks_dir" : str(resolved["SHERPA_ON_THE_ROCKS_DIR"]),
        "app_tools_installation"  : str(resolved["APP_TOOLS_INSTALLATION"]),
        "apprentice_installation" : installations["app"],
        "professor_installation"  : installations["prof"],
        "sherpa_binary"           : str(resolved["SHERPA_BINARY"]),
        "mpi_module"              : str(cfg.get("MPI_MODULE", "mpi/openmpi-x86_64")).strip(),
        "numba_disable_jit"       : parse_on_off(cfg.get("NUMBA_DISABLE_JIT", "off"),
                                                 "NUMBA_DISABLE_JIT"),
        "email"                   : str(cfg.get("EMAIL", "")).strip(),
        "condor_ids_file"         : str((master_dir / "condor_ids.json").resolve()),
        "phase_times_file"        : str((master_dir / "phase_times.json").resolve()),
        "dag_path"                : str((master_dir / "tune.dag").resolve()),
        "master_dir"              : str(master_dir),
        "condor_output"           : str((master_dir / "condor_output").resolve()),
        "joblist_dir"             : str((master_dir / "joblists").resolve()),
        "input_dirs"              : input_states,
        "n_grid"                  : n_grid,
        "grid_sampling"           : grid_sampling,
        "apprentice"              : backends["app"],
        "professor"               : backends["prof"],
        "pattern"                 : pattern,
        "combine_mode"            : combine_mode,
        "merged_dir"              : merged_dir,
        "merge_mode"              : merge_mode,
        "merge_options"           : str(cfg.get("MERGE_OPTIONS", "--rm --quiet")).strip(),
        "validation_only_err"     : validation_only_err,
        "validation_only_merged"  : validation_only_merged,
        "nproc"                   : nproc,
        "start_phase"             : start_phase,
        "end_phase"               : end_phase,
    }
    for phase in phases.PHASES:
        key = f"PHASE{phase.number}_MAXRUNTIME"
        state[f"{phase.key}_maxruntime"] = int(cfg.get(key, phase.default_maxruntime))
    return state, warnings
