from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BACKENDS = {
    "app": {
        "runcard"      : "APPRENTICE",
        "label"        : "Apprentice",
        "state_key"    : "apprentice",
        "folder"       : "Apprentice",
        "install_cfg"  : "APPRENTICE_INSTALLATION",
        "install_key"  : "apprentice_installation",
        "build_worker" : "apprentice/run_app-build.sh",
        "build_bin"    : "app-build",
        "tune_worker"  : "apprentice/run_app-tune2.sh",
        "tune_bin"     : "app-tune2",
        "options"      : (("APP_BUILD_OPTIONS", "build_options"),
                          ("APP_TUNE2_OPTIONS", "tune2_options")),
        "merged_build" : True,
    },
    "prof": {
        "runcard"      : "PROFESSOR",
        "label"        : "Professor",
        "state_key"    : "professor",
        "folder"       : "Professor",
        "install_cfg"  : "PROFESSOR_INSTALLATION",
        "install_key"  : "professor_installation",
        "build_worker" : "professor/run_prof2-ipol.sh",
        "build_bin"    : "prof2-ipol",
        "tune_worker"  : "professor/run_prof2-tune.sh",
        "tune_bin"     : "prof2-tune",
        "options"      : (("PROF2_IPOL_OPTIONS", "ipol_options"),
                          ("PROF2_TUNE_OPTIONS", "tune_options")),
        "merged_build" : False,
    },
}

REPEATS_DIRNAME = "repeats"


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #

@dataclass
class Node:
    """One HTCondor DAG node: what to submit, with which macros, after what."""

    name: str
    phase: str
    submit: str
    vars: dict
    parents: tuple = ()
    joblist: tuple | None = None
    timed_by_dag: bool = False
    retry: int | None = None


# --------------------------------------------------------------------------- #
# Plan: the state, and the naming conventions the phases share
# --------------------------------------------------------------------------- #

class Plan:
    """Read-only view of the run state, with the lookups the phases need."""

    def __init__(self, state: dict):
        self.state = state
        self.window = Window(state["start_phase"], state["end_phase"])
        self._nodes: list[Node] | None = None

    # -- input directories --------------------------------------------------
    @property
    def dirs(self) -> list[dict]:
        return self.state["input_dirs"]

    @property
    def n_dirs(self) -> int:
        return len(self.dirs)

    @property
    def indices(self) -> range:
        return range(1, self.n_dirs + 1)

    def dir_path(self, i: int) -> Path:
        return Path(self.dirs[i - 1]["path"])

    def reweight(self, i: int) -> bool:
        return bool(self.dirs[i - 1]["reweight"])

    @property
    def any_reweight(self) -> bool:
        return any(d["reweight"] for d in self.dirs)

    def weights(self, i: int) -> Path:
        return self.dir_path(i) / "weights.txt"

    def scan_dir(self, i: int) -> Path:
        """The grid directory app-build/prof2-ipol reads for one input dir."""
        return self.dir_path(i) / ("newscan.rew.split" if self.reweight(i) else "newscan")

    def merge_target(self, i: int) -> Path:
        """The grid directory the merge phase collapses in place."""
        return self.dir_path(i) / ("newscan.rew" if self.reweight(i) else "newscan")

    # -- backends -----------------------------------------------------------
    @property
    def backends(self) -> list[str]:
        return [b for b, spec in BACKENDS.items() if self.state.get(spec["state_key"])]

    def backend(self, key: str) -> dict:
        return self.state.get(BACKENDS[key]["state_key"]) or {}

    def orders(self, key: str) -> list[tuple[str, str]]:
        """(order, order_safe) pairs configured for one backend."""
        block = self.backend(key)
        return list(zip(block.get("orders", []), block.get("orders_safe", [])))

    def safe_orders(self, key: str) -> list[str]:
        """Just the filename-safe forms of one backend's orders."""
        return list(self.backend(key).get("orders_safe", []))

    def repeat(self, key: str) -> int:
        """How many times each of one backend's tunes is submitted."""
        return int(self.backend(key).get("repeat", 1) or 1)

    def options(self, key: str, which: str) -> str:
        return self.backend(key).get(which, "")

    # -- merged run ---------------------------------------------------------
    @property
    def merged(self) -> bool:
        return self.n_dirs >= 2 and bool(self.state["merged_dir"])

    @property
    def merged_dir(self) -> Path:
        return Path(self.state["merged_dir"])

    # -- surrogate and tune paths -------------------------------------------
    def surrogate(self, key: str, root: Path, safe: str, *, errs: bool) -> Path:
        """The file the build phase writes and the tune phase reads."""
        folder = root / BACKENDS[key]["folder"]
        if key == "app":
            return folder / (f"err.{safe}.json" if errs else f"app.{safe}.json")
        return folder / (f"ipol.err.{safe}.dat" if errs else f"ipol.{safe}.dat")

    def tune_name(self, key: str, safe: str, scope: str, *, errs: bool) -> str:
        name = BACKENDS[key]["state_key"]
        return f"tune.{name}.{'err.' if errs else ''}{safe}.{scope}"

    def tune_dirs(self, key: str, root: Path, safe: str, scope: str, *, errs: bool) -> list[Path]:
        """Where one tune writes: the plain name, or one directory per repeat."""
        folder = root / BACKENDS[key]["folder"]
        name = self.tune_name(key, safe, scope, errs=errs)
        repeat = self.repeat(key)
        if repeat <= 1:
            return [folder / name]
        return [folder / REPEATS_DIRNAME / f"{name}.repeat-{k}"
                for k in range(1, repeat + 1)]

    def tune_result(self, key: str, root: Path, safe: str, scope: str, *, errs: bool) -> Path:
        """The name later phases read, whether or not it is a link to a repeat."""
        return root / BACKENDS[key]["folder"] / self.tune_name(key, safe, scope, errs=errs)

    def merged_weights(self, key: str, safe: str, *, errs: bool) -> Path:
        folder = self.merged_dir / BACKENDS[key]["folder"]
        return folder / (f"err.weights.{safe}.txt" if errs else f"weights.{safe}.txt")

    # -- paths and settings the submit files need ---------------------------
    @property
    def rocks_dir(self) -> Path:
        return Path(self.state["sherpa_on_the_rocks_dir"])

    @property
    def tune_dir(self) -> Path:
        """This directory: where the submit files and the phase scripts live."""
        return self.rocks_dir / "tune"

    @property
    def submit_dir(self) -> Path:
        return self.tune_dir / "jobs"

    @property
    def script_dir(self) -> Path:
        return self.tune_dir / "scripts"

    @property
    def master_dir(self) -> Path:
        return Path(self.state["master_dir"])

    @property
    def condor_output(self) -> Path:
        return Path(self.state["condor_output"])

    @property
    def joblist_dir(self) -> Path:
        return Path(self.state["joblist_dir"])

    @property
    def state_path(self) -> str:
        return str((self.master_dir / "state.json").resolve())

    @property
    def post_script(self) -> str:
        return str((self.script_dir / "post.sh").resolve())

    @property
    def nproc(self) -> int:
        return int(self.state.get("nproc", 8))

    def maxruntime(self, phase_key: str) -> str:
        return str(self.state[f"{phase_key}_maxruntime"])

    @property
    def merge_script(self) -> str:
        """The merge script MERGE_MODE selects, as an absolute path."""
        name = "yodamerge_runs.sh" if self.state["merge_mode"] == "yoda" else "rivet-merge_runs.sh"
        return str(self.rocks_dir / name)

    @property
    def job_env(self) -> str:
        parts = []
        if self.state.get("numba_disable_jit"):
            parts.append("NUMBA_DISABLE_JIT=1")
        if self.state.get("mpi_module"):
            parts.append(f"MPI_MODULE={self.state['mpi_module']}")
        return " ".join(parts)

    # -- node constructors --------------------------------------------------
    def _log_dir(self, node: str) -> str:
        return str(self.condor_output / node)

    def script_node(self, name, phase, script, *, nproc, parents=(), index=None, backend=None):
        """A node running the scripts/ script named by PHASE_SCRIPT.

        ``index`` selects phase-per-dir.jdf, ``backend`` phase-per-backend.jdf,
        and neither phase-global.jdf. The macro order follows the submit file.
        """
        variables = {"PHASE_SCRIPT": str((self.script_dir / script).resolve()),
                     "STATE_JSON"  : self.state_path}
        if index is not None:
            variables["DIR_INDEX"] = str(index)
        variables.update({"NPROC"        : str(nproc),
                          "PHASE_LOG_DIR": self._log_dir(name),
                          "MAXRUNTIME"   : self.maxruntime(phase.key)})
        if backend is not None:
            variables["BACKEND"] = backend
        submit = ("phase-per-dir.jdf"     if index is not None else
                  "phase-per-backend.jdf" if backend is not None else
                  "phase-global.jdf")
        return Node(name, phase.key, submit, variables, tuple(parents))

    def worker_node(self, name, phase, *, worker, binary, joblist, parallel,
                    joblist_path=None, parents=(), job_env="", retry=None):
        """A node whose jobs come one per line of a job list.

        ``parallel`` picks the submit file: the multi-core workers are handed
        the process count on their command line, the single-process ones are
        not, so this is a property of the worker and never of NPROC. ``joblist``
        is the command lines tune.py writes; a node reading a job list produced
        by an earlier phase passes ``joblist_path`` instead.
        """
        path = joblist_path if joblist_path is not None else self.joblist_dir / f"{name}.txt"
        variables = {"WORKER"       : str(worker),
                     "BINARY"       : str(binary),
                     "RIVET_ENV"    : self.state["rivet_env_script"],
                     "NPROC"        : str(self.nproc) if parallel else "1",
                     "PHASE_LOG_DIR": self._log_dir(name),
                     "MAXRUNTIME"   : self.maxruntime(phase.key),
                     "JOBLIST"      : str(path),
                     "JOB_ENV"      : job_env}
        submit = "joblist-parallel.jdf" if parallel else "joblist-serial.jdf"
        return Node(name, phase.key, submit, variables, tuple(parents),
                    joblist=None if joblist is None else tuple(joblist),
                    timed_by_dag=True, retry=retry)

    # -- the pipeline -------------------------------------------------------
    @property
    def phases(self) -> list[Phase]:
        """The phases inside the configured window, in pipeline order."""
        return [p for p in PHASES if self.window.contains(p.key)]

    @property
    def active_phases(self) -> list[Phase]:
        """The phases inside the window that contribute at least one node."""
        return [p for p in self.phases if not p.skipped(self)]

    def nodes(self) -> list[Node]:
        """Every DAG node of the run, in submission order.

        Parents outside the window are dropped: a phase left out of a partial
        run has already been satisfied on disk, and the check in
        ``missing_inputs`` is what confirms it.
        """
        if self._nodes is None:
            built: list[Node] = []
            for phase in self.active_phases:
                built.extend(phase.nodes(self))
            present = {node.name for node in built}
            for node in built:
                node.parents = tuple(p for p in node.parents if p in present)
            self._nodes = built
        return self._nodes

    @property
    def job_names(self) -> list[str]:
        return [node.name for node in self.nodes()]

    def edges(self) -> list[tuple[str, str]]:
        return [(parent, node.name) for node in self.nodes() for parent in node.parents]

    def joblists(self) -> dict[str, tuple]:
        return {node.name: node.joblist
                for node in self.nodes() if node.joblist is not None}


# --------------------------------------------------------------------------- #
# The phase window
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Window:
    """The slice of the pipeline a run covers, from START_PHASE to END_PHASE."""

    start: str
    end: str

    def contains(self, key: str) -> bool:
        return number(self.start) <= number(key) <= number(self.end)

    @property
    def full(self) -> bool:
        return self.start == PHASES[0].key and self.end == PHASES[-1].key

    def __str__(self) -> str:
        return self.start if self.start == self.end else f"{self.start}-{self.end}"


def number(key: str) -> int:
    return int(key[1:])


# --------------------------------------------------------------------------- #
# Phases
# --------------------------------------------------------------------------- #

class Phase:
    """One phase of the pipeline."""

    key: str = ""
    title: str = ""
    default_maxruntime: int = 86400

    @property
    def number(self) -> int:
        return number(self.key)

    def nodes(self, plan: Plan) -> list[Node]:
        """The DAG nodes this phase contributes, in submission order."""
        raise NotImplementedError

    def skipped(self, plan: Plan) -> str:
        """Why this phase contributes no node, for the overview table."""
        return ""

    def static_inputs(self, plan: Plan) -> list[Path]:
        """Files the user supplies. Checked for every phase in the window."""
        return []

    def upstream_inputs(self, plan: Plan) -> list[Path]:
        """What an earlier phase produces. Checked when the window starts here."""
        return []

    def artifacts(self, plan: Plan) -> list[str]:
        """Glob patterns this phase overwrites in the input directories."""
        return []


class TuningGrid(Phase):
    key, title = "P1", "Create tuning grid and prepare Sherpa subruns"
    default_maxruntime = 1800

    def nodes(self, plan):
        # Only the first input dir samples the grid; the others import it, so
        # they wait for it.
        return [plan.script_node(f"P1_dir{i}", self, "run_tuning_grid.sh",
                                 nproc=1, index=i,
                                 parents=() if i == 1 else ("P1_dir1",))
                for i in plan.indices]

    def static_inputs(self, plan):
        needed = []
        for i in plan.indices:
            needed.extend([plan.dir_path(i) / "template.yaml", plan.dir_path(i) / "init"])
            if i == 1:
                needed.append(plan.dir_path(i) / "parameter.json")
            if plan.reweight(i):
                needed.append(plan.dir_path(i) / "nominal.json")
        return needed

    def artifacts(self, plan):
        return ["newscan*"]


class TuningRuns(Phase):
    key, title = "P2", "Sherpa event generation for tuning grid"

    def nodes(self, plan):
        return [plan.worker_node(
                    f"P2_dir{i}", self,
                    worker=plan.rocks_dir / "run_sherpa.sh",
                    binary=plan.state["sherpa_binary"],
                    joblist=None, parallel=False,
                    joblist_path=plan.dir_path(i) / "runs.txt",
                    parents=(f"P1_dir{i}",),
                    # A Sherpa run that crashes must not be retried: it is
                    # reported by post.sh and the merge phase carries on with
                    # whatever the other subruns produced.
                    retry=0)
                for i in plan.indices]

    def upstream_inputs(self, plan):
        return [plan.dir_path(i) / "runs.txt" for i in plan.indices]


class MergeTuningRuns(Phase):
    key, title = "P3", "Merge results of Sherpa subruns using yodamerge/rivet-merge"

    def nodes(self, plan):
        options = plan.state.get("merge_options", "")
        return [plan.worker_node(
                    f"P3_dir{i}", self,
                    worker=plan.rocks_dir / "merge" / "run_merge.sh",
                    binary=plan.merge_script,
                    parallel=True,
                    joblist=[join(options, plan.merge_target(i))],
                    parents=(f"P2_dir{i}",))
                for i in plan.indices]

    def upstream_inputs(self, plan):
        return [plan.merge_target(i) for i in plan.indices]


class SplitReweighting(Phase):
    key, title = "P4", "Split reweighted variations into a grid"

    def nodes(self, plan):
        return [plan.script_node(f"P4_dir{i}", self, "run_split_reweighting.sh",
                                 nproc=plan.nproc, index=i,
                                 parents=(f"P3_dir{i}",))
                for i in plan.indices if plan.reweight(i)]

    def skipped(self, plan):
        return "" if plan.any_reweight else "no input directory uses reweighting"

    def upstream_inputs(self, plan):
        needed = []
        for i in plan.indices:
            if plan.reweight(i):
                needed.extend([plan.dir_path(i) / "newscan.rew",
                               plan.dir_path(i) / "newscan.rew.var.dat"])
        return needed


class BuildSurrogate(Phase):
    key, title = "P5", "Build surrogate model (one job per order and variant)"

    def nodes(self, plan):
        built = []
        for i in plan.indices:
            head = f"P4_dir{i}" if plan.reweight(i) else f"P3_dir{i}"
            for key in plan.backends:
                spec = BACKENDS[key]
                built.append(plan.worker_node(
                    f"P5_dir{i}_{key}", self,
                    worker=plan.rocks_dir / spec["build_worker"],
                    binary=Path(plan.state[spec["install_key"]]) / spec["build_bin"],
                    parallel=True,
                    joblist=build_lines(plan, key, plan.scan_dir(i), plan.weights(i),
                                        plan.dir_path(i)),
                    parents=(head,), job_env=plan.job_env))
        return built

    def static_inputs(self, plan):
        return [plan.weights(i) for i in plan.indices]

    def upstream_inputs(self, plan):
        return [plan.scan_dir(i) for i in plan.indices]

    def artifacts(self, plan):
        return [BACKENDS[key]["folder"] for key in plan.backends]


class TuneSurrogate(Phase):
    key, title = "P6", "Optimize parameters (one job per order and variant)"

    def nodes(self, plan):
        built = []
        for i in plan.indices:
            for key in plan.backends:
                spec = BACKENDS[key]
                built.append(plan.worker_node(
                    f"P6_dir{i}_{key}", self,
                    worker=plan.rocks_dir / spec["tune_worker"],
                    binary=Path(plan.state[spec["install_key"]]) / spec["tune_bin"],
                    parallel=False,
                    joblist=tune_lines(plan, key, plan.dir_path(i), plan.weights(i),
                                       f"dir{i}"),
                    parents=(f"P5_dir{i}_{key}",), job_env=plan.job_env))
        return built

    def static_inputs(self, plan):
        needed = [plan.weights(i) for i in plan.indices]
        if "app" in plan.backends:
            needed.extend(plan.dir_path(i) / "data.json" for i in plan.indices)
        return needed

    def upstream_inputs(self, plan):
        return [plan.surrogate(key, plan.dir_path(i), safe, errs=errs)
                for i in plan.indices
                for key in plan.backends
                for safe in plan.safe_orders(key)
                for errs in (False, True)]

    def artifacts(self, plan):
        return [BACKENDS[key]["folder"] for key in plan.backends]


class CombineWeights(Phase):
    key, title = "P7", "Combine the weight files of all processes"
    default_maxruntime = 1800

    def nodes(self, plan):
        return [plan.script_node(f"P7_{key}", self, "run_combine_weights.sh",
                                 nproc=1, backend=key,
                                 parents=tuple(f"P6_dir{i}_{key}" for i in plan.indices))
                for key in plan.backends]

    def skipped(self, plan):
        return "" if plan.merged else "single input directory"

    def static_inputs(self, plan):
        needed = [plan.weights(i) for i in plan.indices]
        if plan.state["combine_mode"] == "custom":
            needed.append(plan.dir_path(1) / "custom.weights.txt")
        return needed

    def upstream_inputs(self, plan):
        if plan.state["combine_mode"] != "weighted":
            return []
        return [plan.tune_result(key, plan.dir_path(i), safe, f"dir{i}", errs=errs)
                for i in plan.indices
                for key in plan.backends
                for safe in plan.safe_orders(key)
                for errs in (False, True)]


class BuildMergedSurrogate(Phase):
    key, title = "P8", "Build merged surrogate model"

    def nodes(self, plan):
        built = []
        for key in plan.backends:
            spec = BACKENDS[key]
            if not spec["merged_build"]:
                continue
            built.append(plan.worker_node(
                f"P8_{key}", self,
                worker=plan.rocks_dir / spec["build_worker"],
                binary=Path(plan.state[spec["install_key"]]) / spec["build_bin"],
                parallel=True,
                joblist=merged_build_lines(plan, key),
                parents=(f"P7_{key}",), job_env=plan.job_env))
        return built

    def skipped(self, plan):
        if not plan.merged:
            return "single input directory"
        if not any(BACKENDS[key]["merged_build"] for key in plan.backends):
            return "only Apprentice rebuilds a merged surrogate"
        return ""

    def upstream_inputs(self, plan):
        needed = []
        for key in plan.backends:
            if not BACKENDS[key]["merged_build"]:
                continue
            needed.extend(plan.scan_dir(i) for i in plan.indices)
            needed.extend(plan.merged_weights(key, safe, errs=errs)
                          for safe in plan.safe_orders(key) for errs in (False, True))
        return needed


class TuneMergedSurrogate(Phase):
    key, title = "P9", "Optimize parameters against the merged surrogate"

    def nodes(self, plan):
        built = []
        for key in plan.backends:
            spec = BACKENDS[key]
            parent = f"P8_{key}" if spec["merged_build"] else f"P7_{key}"
            built.append(plan.worker_node(
                f"P9_{key}", self,
                worker=plan.rocks_dir / spec["tune_worker"],
                binary=Path(plan.state[spec["install_key"]]) / spec["tune_bin"],
                parallel=False,
                joblist=merged_tune_lines(plan, key),
                parents=(parent,), job_env=plan.job_env))
        return built

    def skipped(self, plan):
        return "" if plan.merged else "single input directory"

    def static_inputs(self, plan):
        if "app" not in plan.backends:
            return []
        return [plan.dir_path(i) / "data.json" for i in plan.indices]

    def upstream_inputs(self, plan):
        needed = []
        for key in plan.backends:
            needed.extend(plan.merged_weights(key, safe, errs=errs)
                          for safe in plan.safe_orders(key) for errs in (False, True))
            if BACKENDS[key]["merged_build"]:
                needed.extend(plan.surrogate(key, plan.merged_dir, safe, errs=errs)
                              for safe in plan.safe_orders(key) for errs in (False, True))
            else:
                needed.extend(plan.surrogate(key, plan.dir_path(i), safe, errs=errs)
                              for i in plan.indices
                              for safe in plan.safe_orders(key) for errs in (False, True))
        return needed


class ValidationGrid(Phase):
    key, title = "P10", "Create validation grid from tune results and prepare subruns"
    default_maxruntime = 1800

    def nodes(self, plan):
        if plan.merged:
            parents = tuple(f"P9_{key}" for key in plan.backends)
        else:
            parents = tuple(f"P6_dir1_{key}" for key in plan.backends)
        return [plan.script_node(f"P10_dir{i}", self, "run_validation_grid.sh",
                                 nproc=1, index=i, parents=parents)
                for i in plan.indices]

    def static_inputs(self, plan):
        return [path
                for i in plan.indices
                for path in (plan.dir_path(i) / "template.yaml", plan.dir_path(i) / "init")]

    def upstream_inputs(self, plan):
        return [plan.tune_result(key, root, safe, scope, errs=errs)
                for key in plan.backends
                for root, scope in self._sources(plan)
                for safe in plan.safe_orders(key)
                for errs in self._variants(plan)]

    def _sources(self, plan):
        sources = []
        if not plan.state["validation_only_merged"]:
            sources.extend((plan.dir_path(i), f"dir{i}") for i in plan.indices)
        if plan.merged:
            sources.append((plan.merged_dir, "merged"))
        return sources

    def _variants(self, plan):
        return (True,) if plan.state["validation_only_err"] else (False, True)

    def artifacts(self, plan):
        return ["validation"]


class ValidationRuns(Phase):
    key, title = "P11", "Sherpa event generation for validation grid"

    def nodes(self, plan):
        return [plan.worker_node(
                    f"P11_dir{i}", self,
                    worker=plan.rocks_dir / "run_sherpa.sh",
                    binary=plan.state["sherpa_binary"],
                    joblist=None, parallel=False,
                    joblist_path=plan.dir_path(i) / "runs.txt",
                    parents=(f"P10_dir{i}",), retry=0)
                for i in plan.indices]

    def upstream_inputs(self, plan):
        return [plan.dir_path(i) / "runs.txt" for i in plan.indices]


class MergeValidationRuns(Phase):
    key, title = "P12", "Merge validation results using yodamerge/rivet-merge"

    def nodes(self, plan):
        options = plan.state.get("merge_options", "")
        return [plan.worker_node(
                    f"P12_dir{i}", self,
                    worker=plan.rocks_dir / "merge" / "run_merge.sh",
                    binary=plan.merge_script,
                    parallel=True,
                    joblist=[join(options, plan.dir_path(i) / "validation")],
                    parents=(f"P11_dir{i}",))
                for i in plan.indices]

    def upstream_inputs(self, plan):
        return [plan.dir_path(i) / "validation" for i in plan.indices]


class PlotResults(Phase):
    key, title = "P13", "Compute chi-squared and plot the tune results"
    default_maxruntime = 1800

    def nodes(self, plan):
        return [plan.script_node("P13", self, "run_plot_results.sh",
                                 nproc=plan.nproc,
                                 parents=tuple(f"P12_dir{i}" for i in plan.indices))]

    def static_inputs(self, plan):
        return [plan.weights(i) for i in plan.indices]

    def upstream_inputs(self, plan):
        return [plan.dir_path(i) / "validation" for i in plan.indices]

    def artifacts(self, plan):
        return ["chi2.json", "chi2-plots"]


PHASES: list[Phase] = [
    TuningGrid(), TuningRuns(), MergeTuningRuns(), SplitReweighting(),
    BuildSurrogate(), TuneSurrogate(), CombineWeights(),
    BuildMergedSurrogate(), TuneMergedSurrogate(),
    ValidationGrid(), ValidationRuns(), MergeValidationRuns(), PlotResults(),
]

PHASE_KEYS = [phase.key for phase in PHASES]


# --------------------------------------------------------------------------- #
# Job list command lines
# --------------------------------------------------------------------------- #

def join(*parts) -> str:
    return " ".join(str(p) for p in parts if str(p))


def build_lines(plan: Plan, key: str, scan, weights, root: Path) -> list[str]:
    """app-build / prof2-ipol, for one input directory."""
    lines = []
    for order, safe in plan.orders(key):
        value = plan.surrogate(key, root, safe, errs=False)
        error = plan.surrogate(key, root, safe, errs=True)
        if key == "app":
            options = plan.options(key, "build_options")
            lines.append(join(scan, "--order", order, "-w", weights, "-o", value, options))
            lines.append(join(scan, "--order", order, "-w", weights, "-o", error,
                              "--errs", options))
        else:
            options = plan.options(key, "ipol_options")
            # prof2-ipol names its output as the second positional argument.
            lines.append(join(scan, value, "--order", order, "-w", weights,
                              "--ierr", "none", options))
            lines.append(join(scan, error, "--order", order, "-w", weights, options))
    return lines


def tune_lines(plan: Plan, key: str, root: Path, weights, scope: str) -> list[str]:
    """app-tune2 / prof2-tune, for one input directory."""
    lines = []
    for safe in plan.safe_orders(key):
        value = plan.surrogate(key, root, safe, errs=False)
        error = plan.surrogate(key, root, safe, errs=True)
        if key == "app":
            options = plan.options(key, "tune2_options")
            data = root / "data.json"
            for out in plan.tune_dirs(key, root, safe, scope, errs=False):
                lines.append(join(weights, data, value, "-o", out, options))
            for out in plan.tune_dirs(key, root, safe, scope, errs=True):
                lines.append(join(weights, data, value, "-e", error, "-o", out, options))
        else:
            options = plan.options(key, "tune_options")
            for out in plan.tune_dirs(key, root, safe, scope, errs=False):
                lines.append(join(value, "-w", weights, "-R", "-o", out, options))
            for out in plan.tune_dirs(key, root, safe, scope, errs=True):
                lines.append(join(error, "-w", weights, "-R", "-o", out, options))
    return lines


def merged_build_lines(plan: Plan, key: str) -> list[str]:
    """app-build over every input directory's grid at once."""
    scans = [plan.scan_dir(i) for i in plan.indices]
    options = plan.options(key, "build_options")
    lines = []
    for order, safe in plan.orders(key):
        lines.append(join(*scans, "--order", order,
                          "-w", plan.merged_weights(key, safe, errs=False),
                          "-o", plan.surrogate(key, plan.merged_dir, safe, errs=False),
                          options))
        lines.append(join(*scans, "--order", order,
                          "-w", plan.merged_weights(key, safe, errs=True),
                          "-o", plan.surrogate(key, plan.merged_dir, safe, errs=True),
                          "--errs", options))
    return lines


def merged_tune_lines(plan: Plan, key: str) -> list[str]:
    """app-tune2 against the merged surrogate, prof2-tune against every ipol."""
    lines = []
    for safe in plan.safe_orders(key):
        weights = plan.merged_weights(key, safe, errs=False)
        weights_err = plan.merged_weights(key, safe, errs=True)
        if key == "app":
            options = plan.options(key, "tune2_options")
            data = plan.merged_dir / "data.json"
            value = plan.surrogate(key, plan.merged_dir, safe, errs=False)
            error = plan.surrogate(key, plan.merged_dir, safe, errs=True)
            for out in plan.tune_dirs(key, plan.merged_dir, safe, "merged", errs=False):
                lines.append(join(weights, data, value, "-o", out, options))
            for out in plan.tune_dirs(key, plan.merged_dir, safe, "merged", errs=True):
                lines.append(join(weights_err, data, value, "-e", error, "-o", out, options))
        else:
            options = plan.options(key, "tune_options")
            ipols = [plan.surrogate(key, plan.dir_path(i), safe, errs=False) for i in plan.indices]
            ipols_err = [plan.surrogate(key, plan.dir_path(i), safe, errs=True) for i in plan.indices]
            for out in plan.tune_dirs(key, plan.merged_dir, safe, "merged", errs=False):
                lines.append(join(*ipols, "-w", weights, "-R", "-o", out, options))
            for out in plan.tune_dirs(key, plan.merged_dir, safe, "merged", errs=True):
                lines.append(join(*ipols_err, "-w", weights_err, "-R", "-o", out, options))
    return lines


# --------------------------------------------------------------------------- #
# What the plan produces
# --------------------------------------------------------------------------- #

def write_joblists(plan: Plan) -> Path:
    """Write every node's job list and create the directories the jobs write into."""
    plan.joblist_dir.mkdir(parents=True, exist_ok=True)

    roots = [plan.dir_path(i) for i in plan.indices]
    if plan.state["merged_dir"]:
        roots.append(plan.merged_dir)
    for root in roots:
        for key in plan.backends:
            folder = root / BACKENDS[key]["folder"]
            folder.mkdir(parents=True, exist_ok=True)
            if plan.repeat(key) > 1:
                (folder / REPEATS_DIRNAME).mkdir(exist_ok=True)

    for name, lines in plan.joblists().items():
        (plan.joblist_dir / f"{name}.txt").write_text(
            "".join(f"{line}\n" for line in lines), encoding="utf-8")
    return plan.joblist_dir


def pre_script_args(plan: Plan, done_jobs: set, resume_mode: bool) -> dict[str, str]:
    """The PRE script argument list per node, keyed by node name.

    A job-list node gets its start time recorded here because it never touches
    state.json itself. The first node of the run additionally carries the
    'init'/'resume' notification, whether or not it is a job-list node.
    """
    args = {node.name: f"{node.name} start"
            for node in plan.nodes() if node.timed_by_dag}
    if plan.state.get("email"):
        first = next((name for name in plan.job_names if name not in done_jobs), None)
        if first is not None:
            mode = "resume" if resume_mode else "init"
            args[first] = f"{first} start {mode}" if first in args else f"{mode} 0"
    return args


def dag_text(plan: Plan, done_jobs: set, resume_mode: bool) -> str:
    """The complete DAG description."""
    nodes = plan.nodes()
    pre = pre_script_args(plan, done_jobs, resume_mode)
    post = f"/bin/bash {plan.post_script} {plan.state_path}"

    lines = ["# Auto-generated by tune.py"]
    for node in nodes:
        done = " DONE" if node.name in done_jobs else ""
        lines.append(f"JOB {node.name} {(plan.submit_dir / node.submit).resolve()}{done}")
        lines.append(f"VARS {node.name} "
                     + " ".join(f'{k}="{v}"' for k, v in node.vars.items()))
    for node in nodes:
        if node.name in pre:
            lines.append(f"SCRIPT PRE {node.name} {post} {pre[node.name]}")
    for node in nodes:
        if node.retry is not None:
            lines.append(f"RETRY {node.name} {node.retry}")
        lines.append(f"SCRIPT POST {node.name} {post} {node.name} $RETURN")
    for parent, child in plan.edges():
        lines.append(f"PARENT {parent} CHILD {child}")
    return "\n".join(lines) + "\n"


def missing_inputs(plan: Plan) -> list[tuple[str, Path, str]]:
    """(phase key, path, why) for everything the run needs but cannot find.

    Every phase in the window is asked for the files the user has to supply.
    The first phase that actually runs is asked, on top of that, for what its
    upstream phases would have produced -- that is what makes it safe to start
    a run in the middle of the pipeline.
    """
    missing = []
    seen = set()

    def check(phase_key, paths, why):
        for path in paths:
            if str(path) in seen:
                continue
            seen.add(str(path))
            if not Path(path).exists():
                missing.append((phase_key, Path(path), why))

    active = plan.active_phases
    for phase_ in active:
        check(phase_.key, phase_.static_inputs(plan), "input file")
    if active:
        check(active[0].key, active[0].upstream_inputs(plan),
              "produced by an earlier phase")
    return missing


def artifact_patterns(plan: Plan) -> list[str]:
    """The patterns the phases in this run overwrite, for the cleanup prompt."""
    patterns = []
    for phase_ in plan.active_phases:
        for pattern in phase_.artifacts(plan):
            if pattern not in patterns:
                patterns.append(pattern)
    return patterns


def overview_rows(plan: Plan) -> list[tuple[str, str, str]]:
    """(phase key, what it does, maxruntime or why it is skipped)."""
    rows = []
    for phase_ in PHASES:
        if not plan.window.contains(phase_.key):
            rows.append((phase_.key, phase_.title, "not in phase window"))
            continue
        reason = phase_.skipped(plan)
        rows.append((phase_.key, phase_.title,
                     f"skipped: {reason}" if reason
                     else f"maxruntime = {plan.maxruntime(phase_.key)}"))
    return rows
