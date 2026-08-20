#!/usr/bin/env python3
"""Submit the whole tuning procedure to HTCondor as one DAG."""

from __future__ import annotations

import argparse
import functools
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError as e:
    raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from e

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import phases
import resume as resume_module
import runcard


# --------------------------------------------------------------------------- #
# Printing
# --------------------------------------------------------------------------- #

def table(rows, indent: str = "    ") -> None:
    """A left-aligned '- key : value' block, skipping rows with no value."""
    rows = [(key, value) for key, value in rows if value is not None]
    if not rows:
        return
    width = max(len(key) for key, _ in rows)
    for key, value in rows:
        print(f"{indent}- {key:<{width}} : {value}")


def ask(prompt: str) -> bool:
    return input(prompt).strip().lower() in {"y", "yes"}


def check_mpi_module_available(module_name: str) -> bool:
    script = ('[ -f /etc/profile.d/modules.sh ] && . /etc/profile.d/modules.sh 2>/dev/null; '
              '[ -f /usr/share/Modules/init/bash ] && . /usr/share/Modules/init/bash 2>/dev/null; '
              'command -v module >/dev/null 2>&1 || exit 1; '
              'module load "$1" >/dev/null 2>&1')
    try:
        r = subprocess.run(["bash", "-c", script, "_", module_name],
                           capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def print_overview(plan, resume_jobs: set) -> None:
    state = plan.state
    print("Overview:\n")

    mpi = state.get("mpi_module", "")
    available = "available" if mpi and check_mpi_module_available(mpi) else "NOT available"
    print("  General settings:")
    table([("Sherpa binary", state["sherpa_binary"]),
           ("app-tools installation", state["app_tools_installation"]),
           ("Apprentice installation", state["apprentice_installation"] or None),
           ("Professor installation", state["professor_installation"] or None),
           ("Rivet environment script", state["rivet_env_script"]),
           ("MPI module", f"{mpi} ({available})"),
           ("Email notifications", state["email"] or None)])
    print()

    print("  Input directories:")
    for i in plan.indices:
        item = plan.dirs[i - 1]
        print(f"    Input {i}: {item['path']}")
        table([("grid mode", item["grid_mode"]),
               ("reweighting", "on" if item["reweight"] else None),
               ("subruns", item["n_subruns"]),
               ("validation subruns", item["n_val_subruns"])], indent="      ")
    print()

    validation = "all tune(s)"
    if state["validation_only_err"] and state["validation_only_merged"]:
        validation = "only merged error tune"
    elif state["validation_only_err"]:
        validation = "only error tune(s)"
    elif state["validation_only_merged"]:
        validation = "only merged tune(s)"
    print("  Grid settings:")
    table([("N_GRID", state["n_grid"]),
           ("GRID_SAMPLING", state["grid_sampling"]),
           ("validation grid", validation)])
    print()

    for key in plan.backends:
        spec = phases.BACKENDS[key]
        repeat = plan.repeat(key)
        rows = [("ORDER", ", ".join(order for order, _ in plan.orders(key))),
                ("REPEAT", f"{repeat} (best of, by objective)" if repeat > 1 else "1")]
        rows += [(name, plan.options(key, state_key) or "(none)")
                 for name, state_key in spec["options"]]
        if key == "app" and plan.any_reweight:
            rows.append(("PATTERN (split_reweighting.py)", state["pattern"]))
        print(f"  {spec['label']} settings:")
        table(rows)
        print()

    if plan.merged:
        print("  Merged weights settings:")
        table([("COMBINE_MODE", state["combine_mode"])])
        print()

    print("  Phases:")
    rows = phases.overview_rows(plan)
    key_width = max(len(key) for key, _, _ in rows)
    title_width = max(len(title) for _, title, _ in rows)
    for key, title, note in rows:
        print(f"    {key:<{key_width}} | {title:<{title_width}} | {note}")
    if resume_jobs:
        print("  - Resuming jobs: " + ", ".join(sorted(resume_jobs)))
    print()


# --------------------------------------------------------------------------- #
# The merged reference data
# --------------------------------------------------------------------------- #

def stack_json_values(left, right):
    if isinstance(left, list) and isinstance(right, list):
        return left + right
    if isinstance(left, dict) and isinstance(right, dict):
        merged = dict(left)
        for key, value in right.items():
            merged[key] = stack_json_values(merged[key], value) if key in merged else value
        return merged
    if left == right:
        return left
    return [left, right]


def warn_refdata_overlap(datasets: list) -> None:
    """Say so when two processes contribute the same reference bins."""
    owners: dict[str, list[int]] = {}
    for idx, data in enumerate(datasets, start=1):
        if not isinstance(data, dict):
            continue
        for binid in data:
            owners.setdefault(str(binid), []).append(idx)
    overlaps: dict[tuple[str, tuple[int, ...]], int] = {}
    for binid, holders in owners.items():
        if len(holders) < 2:
            continue
        key = (binid.rsplit("#", 1)[0], tuple(holders))
        overlaps[key] = overlaps.get(key, 0) + 1
    if not overlaps:
        return
    print()
    print("WARNING: reference data overlap in combined data.json:")
    for (histname, holders), n_bins in sorted(overlaps.items()):
        dirs = ", ".join(f"INPUT_DIR{i}" for i in holders)
        print(f"  {histname} ({n_bins} bin{'s' if n_bins != 1 else ''}) present in {dirs}")
    print()


def setup_merged_dir(plan) -> None:
    """Create the merged directory and the inputs the merged phases read."""
    if not plan.merged:
        return
    merged_dir = plan.merged_dir
    if merged_dir.exists() and plan.window.full:
        raise SystemExit(f"Merged directory already exists: {merged_dir}")
    merged_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created merged directory: {merged_dir}")

    if "app" in plan.backends:
        datasets = [json.loads((plan.dir_path(i) / "data.json").read_text(encoding="utf-8"))
                    for i in plan.indices]
        warn_refdata_overlap(datasets)
        (merged_dir / "data.json").write_text(
            json.dumps(functools.reduce(stack_json_values, datasets), indent=2),
            encoding="utf-8")
        print(f"Created combined reference data JSON: {merged_dir / 'data.json'}")

    if plan.state["combine_mode"] == "custom":
        shutil.copy2(plan.dir_path(1) / "custom.weights.txt",
                     merged_dir / "custom.weights.txt")
        print(f"Copied custom merged weights: {merged_dir / 'custom.weights.txt'}")


def cleanup_input_artifacts(plan) -> None:
    """Offer to remove what the phases of this run are about to overwrite."""
    patterns = phases.artifact_patterns(plan)
    found = sorted(artifact
                   for i in plan.indices
                   for pattern in patterns
                   for artifact in plan.dir_path(i).glob(pattern))
    if not found:
        return
    print("Found existing tune artifacts in input directories:")
    for artifact in found:
        print(f"  - {artifact}")
    print()
    if not ask("Remove these artifacts before starting fresh tune? [y/N]: "):
        print("Proceeding without removing artifacts (may cause conflicts).\n")
        return
    for artifact in found:
        shutil.rmtree(artifact) if artifact.is_dir() else artifact.unlink()
    print(f"Removed {len(found)} artifact(s).\n")


# --------------------------------------------------------------------------- #
# The master directory
# --------------------------------------------------------------------------- #

def prepare_master_dir(plan):
    """Resume, wipe or create the master directory. Returns the decision."""
    master_dir = plan.master_dir
    decision = resume_module.Decision()

    if master_dir.exists():
        if not master_dir.is_dir():
            raise SystemExit(f"Master path exists but is not a directory: {master_dir}")
        decision = resume_module.decide(plan, ask)
        if not decision.resume:
            if not ask(f"Master directory already exists: {master_dir}\n"
                       "Remove it and continue? [y/N]: "):
                raise SystemExit("Aborted.")
            shutil.rmtree(master_dir)

    if decision.resume:
        print(f"Using existing master directory: {master_dir}\n")
        print("Resume mode: keeping condor IDs, phase times, and completed outputs; "
              "adopting current configuration.")
        resume_module.apply(plan, decision)
    else:
        master_dir.mkdir(parents=True, exist_ok=False)
        print(f"Created master directory: {master_dir}\n")
    return decision


def initialise_run(plan) -> None:
    """Everything a fresh run needs on disk before the DAG is written."""
    for name in plan.job_names:
        (plan.condor_output / name).mkdir(parents=True, exist_ok=True)
    print(f"Created condor output directories: {plan.condor_output}")

    setup_merged_dir(plan)

    Path(plan.state["condor_ids_file"]).write_text(
        json.dumps({"dagman": {"cluster_id": None},
                    **{name: {"cluster_id": None} for name in plan.job_names}}, indent=2),
        encoding="utf-8")
    print(f"Created condor IDs file: {plan.state['condor_ids_file']}")

    Path(plan.state["phase_times_file"]).write_text("{}\n", encoding="utf-8")
    print(f"Created phase times file: {plan.state['phase_times_file']}")


def write_state(plan) -> Path:
    path = plan.master_dir / "state.json"
    path.write_text(json.dumps(plan.state, indent=2), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Submission
# --------------------------------------------------------------------------- #

def submit(plan, dag_path: Path) -> None:
    print(f"Submitting DAG: condor_submit_dag {dag_path.name}")
    proc = subprocess.run(["condor_submit_dag", dag_path.name], cwd=str(plan.master_dir),
                          check=False, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.stderr:
        print(proc.stderr.strip())
    if proc.returncode != 0:
        raise SystemExit(f"condor_submit_dag failed with return code {proc.returncode}")

    m = re.search(r"submitted to cluster\s+(\d+)",
                  f"{proc.stdout or ''}\n{proc.stderr or ''}", re.IGNORECASE)
    plan.state["dag_cluster_id"] = m.group(1) if m else "unknown"
    write_state(plan)

    condor_ids_path = Path(plan.state["condor_ids_file"])
    condor_ids = {}
    if condor_ids_path.exists():
        try:
            condor_ids = json.loads(condor_ids_path.read_text(encoding="utf-8"))
        except Exception:
            condor_ids = {}
    condor_ids["dagman"] = {"cluster_id": plan.state["dag_cluster_id"]}
    condor_ids_path.write_text(json.dumps(condor_ids, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", help="Path to YAML steering file")
    args = parser.parse_args()

    print("Starting initialisation...\n")
    config_path = Path(os.path.expanduser(args.config)).resolve()
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")
    print(f"Using config: {config_path}\n")

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise SystemExit("Config must be a YAML mapping")

    try:
        state, warnings = runcard.build_state(cfg, config_path)
    except (KeyError, ValueError, FileNotFoundError) as e:
        raise SystemExit(f"Error in {config_path}: {e.args[0] if e.args else e}") from None
    plan = phases.Plan(state)
    here = Path(__file__).resolve().parent
    if plan.tune_dir.resolve() != here:
        warnings.append(
            f"SHERPA_ON_THE_ROCKS_DIR points the jobs at {plan.tune_dir}, but this "
            f"is {here}. The submit files and phase scripts of the other checkout "
            "will be used.")
    for warning in warnings:
        print(f"WARNING: {warning}\n")

    if not plan.active_phases:
        raise SystemExit(f"Phase window {plan.window} contains no phase this "
                         "configuration runs.")

    missing = phases.missing_inputs(plan)
    if missing:
        print(f"Cannot start at {plan.active_phases[0].key}: the phases of window "
              f"{plan.window} are missing inputs.")
        for phase_key, path, why in missing:
            print(f"  - {phase_key} needs {path} ({why})")
        raise SystemExit("Aborted.")

    decision = prepare_master_dir(plan)
    print_overview(plan, decision.jobs if decision.resume else set())

    if not decision.resume:
        initialise_run(plan)
    state_path = write_state(plan)
    print(f"{'Updated' if decision.resume else 'Created'} state file: {state_path}")

    done_jobs = set(plan.job_names) - decision.jobs if decision.resume else set()
    dag_path = Path(plan.state["dag_path"])
    dag_path.write_text(phases.dag_text(plan, done_jobs, decision.resume), encoding="utf-8")
    if decision.resume:
        print(f"Created DAG file ({len(done_jobs)} of {len(plan.job_names)} "
              f"jobs already done): {dag_path}")
    else:
        print(f"Created DAG file: {dag_path}")
    print()

    if not decision.resume:
        cleanup_input_artifacts(plan)
    print(f"Created job lists: {phases.write_joblists(plan)}\n")

    if not ask("Proceed with DAG submission now? [y/N]: "):
        print(f"Submission cancelled. You can review generated files in: {plan.master_dir}")
        print(f"Submit manually with: cd {plan.master_dir} && "
              f"condor_submit_dag {dag_path.name}")
        print("\nInitialization complete!")
        return

    submit(plan, dag_path)
    print("\nInitialization complete!")


if __name__ == "__main__":
    main()
