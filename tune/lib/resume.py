from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Decision:
    """What to do with the master directory, and which jobs to submit."""

    resume: bool = False
    jobs: set = field(default_factory=set)
    #: Fields carried over from the saved run, so the DAG keeps its identity.
    carried: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Comparing a saved run against the current configuration
# --------------------------------------------------------------------------- #

INCIDENTAL = ("created_at", "dag_cluster_id", "config_path", "email",
              "condor_ids_file", "phase_times_file", "dag_path", "joblist_dir")


def orders_of(block) -> list[str]:
    if not isinstance(block, dict):
        return []
    if "orders" in block:
        return list(block["orders"])
    if block.get("order"):
        return [block["order"]]
    return []


def comparable(state: dict) -> dict:
    normalized = json.loads(json.dumps(state))
    for key in INCIDENTAL:
        normalized.pop(key, None)
    for backend in ("apprentice", "professor"):
        block = normalized.get(backend)
        if isinstance(block, dict):
            orders = orders_of(block)
            normalized[backend] = ({"orders": orders,
                                    "repeat": int(block.get("repeat", 1) or 1)}
                                   if orders else {})
    return normalized


def diff_states(saved, current, path="") -> list[str]:
    diffs: list[str] = []
    if isinstance(saved, dict) and isinstance(current, dict):
        for key in sorted(set(saved) | set(current), key=str):
            sub = f"{path}.{key}" if path else str(key)
            if key not in saved:
                diffs.append(f"{sub}: only in current config (value {current[key]!r})")
            elif key not in current:
                diffs.append(f"{sub}: only in saved run (value {saved[key]!r})")
            else:
                diffs.extend(diff_states(saved[key], current[key], sub))
    elif isinstance(saved, list) and isinstance(current, list):
        if len(saved) != len(current):
            diffs.append(f"{path}: saved has {len(saved)} entries, current has {len(current)}")
        for i, (s, c) in enumerate(zip(saved, current), start=1):
            diffs.extend(diff_states(s, c, f"{path}[{i}]"))
    elif saved != current:
        diffs.append(f"{path}: saved {saved!r}, current {current!r}")
    return diffs


def structural_changes(saved: dict, current: dict) -> list[str]:
    """Changes that redefine which jobs exist, so no saved end time survives."""
    reasons: list[str] = []
    saved_dirs = [d["path"] for d in saved.get("input_dirs", [])]
    current_dirs = [d["path"] for d in current.get("input_dirs", [])]
    if len(saved_dirs) != len(current_dirs):
        reasons.append(f"number of input directories changed: "
                       f"{len(saved_dirs)} -> {len(current_dirs)}")
    else:
        for i, (s, c) in enumerate(zip(saved_dirs, current_dirs), start=1):
            if s != c:
                reasons.append(f"INPUT_DIR{i} path changed: {s} -> {c}")
    if saved.get("merged_dir", "") != current.get("merged_dir", ""):
        reasons.append(f"merged directory changed: '{saved.get('merged_dir', '')}' "
                       f"-> '{current.get('merged_dir', '')}'")
    for key, label in (("apprentice", "APPRENTICE"), ("professor", "PROFESSOR")):
        saved_orders, current_orders = orders_of(saved.get(key)), orders_of(current.get(key))
        if saved_orders != current_orders:
            reasons.append(f"{label}.ORDER changed: {saved_orders} -> {current_orders} "
                           f"(the order set defines the P5/P8 job lists; a completed build "
                           f"node would never produce the new order's surrogate)")
        saved_repeat = int((saved.get(key) or {}).get("repeat", 1) or 1)
        current_repeat = int((current.get(key) or {}).get("repeat", 1) or 1)
        if saved_orders and current_orders and saved_repeat != current_repeat:
            reasons.append(f"{label}.REPEAT changed: {saved_repeat} -> {current_repeat} "
                           f"(the repeat count defines the P6/P9 job lists and where they "
                           f"write; a completed tune node holds the old set of repeats)")
    return reasons


# --------------------------------------------------------------------------- #
# Which jobs still have to run
# --------------------------------------------------------------------------- #

def completed_jobs(plan, phase_times: dict) -> set[str]:
    return {name for name in plan.job_names
            if (phase_times.get(name) or {}).get("end_time")}


def jobs_to_resume(plan, phase_times: dict) -> set[str]:
    """The unfinished jobs, plus everything downstream of them.

    A node that finished before one of its ancestors is re-run does not count as
    finished any more: its inputs are about to be rewritten.
    """
    done = completed_jobs(plan, phase_times)
    include = {name for name in plan.job_names if name not in done}
    edges = plan.edges()
    changed = True
    while changed:
        changed = False
        for parent, child in edges:
            if parent in include and child not in include:
                include.add(child)
                changed = True
    return include


# --------------------------------------------------------------------------- #
# Preparing the master directory for a resume
# --------------------------------------------------------------------------- #

def reset_phase_output(plan, jobs: set) -> None:
    """Empty the condor output directory of every job about to be re-submitted."""
    root = plan.condor_output
    for job in sorted(jobs):
        target = root / job
        if target.exists():
            failed = False

            def on_error(func, path, exc_info):
                nonlocal failed
                failed = True

            shutil.rmtree(target, onerror=on_error)
            if failed:
                print(f"Couldn't remove all files from {target} "
                      f"(files may still be in use by running jobs); continuing.")
        target.mkdir(parents=True, exist_ok=True)


def reset_phase_times(plan, jobs: set) -> None:
    path = Path(plan.state["phase_times_file"])
    if not path.exists():
        return
    try:
        phase_times = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    for job in jobs:
        phase_times.pop(job, None)
    path.write_text(json.dumps(phase_times, indent=2, sort_keys=True), encoding="utf-8")


def cleanup_dagman_files(plan) -> None:
    """Remove the rescue files and logs of the previous submission."""
    dag_path = Path(plan.state["dag_path"])
    for path in sorted(plan.master_dir.glob(f"{dag_path.name}.*")):
        if path.is_file():
            path.unlink()


# --------------------------------------------------------------------------- #
# The decision
# --------------------------------------------------------------------------- #

def read_saved_run(master_dir: Path) -> tuple[dict, dict] | None:
    """The saved state and phase times of a previous run, if both are readable."""
    state_path = master_dir / "state.json"
    times_path = master_dir / "phase_times.json"
    if not (state_path.exists() and times_path.exists()):
        return None
    try:
        return (json.loads(state_path.read_text(encoding="utf-8")),
                json.loads(times_path.read_text(encoding="utf-8")))
    except Exception as e:
        print(f"Found existing run metadata but could not parse it for resume: {e}")
        return None


def decide(plan, ask) -> Decision:
    """Work out what to do with an existing master directory, asking as needed.

    ``ask`` is handed a prompt and returns True for yes. Returns the decision;
    the master directory is left untouched, ``apply`` acts on it.
    """
    saved = read_saved_run(plan.master_dir)
    if saved is None:
        return Decision()
    saved_state, phase_times = saved

    diff = diff_states(comparable(saved_state), comparable(plan.state))
    if diff:
        print("Existing run state differs from current config-derived state:")
        for line in diff:
            print(f"  - {line}")
        print()

    structural = structural_changes(saved_state, plan.state)
    if structural:
        print("Resume is not possible for this run because job identity is tied to the "
              "input directories, the surrogate order sets, and the split setting:")
        for line in structural:
            print(f"  - {line}")
        print()
        return Decision()

    jobs = jobs_to_resume(plan, phase_times)
    if not jobs:
        return _rerun_window(plan, ask, saved_state)

    done = completed_jobs(plan, phase_times)
    print(f"Detected resumable run in: {plan.master_dir}")
    if not plan.window.full:
        print(f"Only the jobs of phase window {plan.window} are considered.")
    print(f"Completed jobs: {len(done)} / {len(plan.job_names)}. "
          f"Will submit remaining jobs: {len(jobs)}")
    if diff:
        print("WARNING: Resuming applies the current configuration to the remaining jobs only;")
        print("         already-completed phases keep outputs produced with the previous settings.")
        prompt = ("Resume anyway with the current configuration ")
    else:
        prompt = "Resume this run "
    prompt += ("(keeps completed outputs; resets output dirs, phase times and "
               "DAGMan files of remaining jobs)? [y/N]: ")
    if not ask(prompt):
        print("Resume declined.")
        return Decision()
    return Decision(resume=True, jobs=jobs, carried=_carried(saved_state))


def _rerun_window(plan, ask, saved_state: dict) -> Decision:
    """Nothing left to resume. Offer a re-run when a phase window says so."""
    if plan.window.full:
        print("Detected existing completed run (all phases have end_time).")
        return Decision()
    print(f"Every job of phase window {plan.window} in {plan.master_dir} has already "
          f"finished ({len(plan.job_names)} jobs).")
    if not ask(f"Run phase window {plan.window} again "
               "(keeps the outputs of the phases outside the window)? [y/N]: "):
        print("Re-run declined.")
        return Decision()
    return Decision(resume=True, jobs=set(plan.job_names), carried=_carried(saved_state))


def _carried(saved_state: dict) -> dict:
    return {key: saved_state[key] for key in ("created_at", "dag_cluster_id")
            if key in saved_state}


def apply(plan, decision: Decision) -> None:
    """Clear the previous submission's traces for the jobs being re-submitted."""
    plan.state.update(decision.carried)
    reset_phase_output(plan, decision.jobs)
    reset_phase_times(plan, decision.jobs)
    cleanup_dagman_files(plan)
