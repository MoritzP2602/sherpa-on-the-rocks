# Configuration Parameters

## Required Parameters

### INPUT_DIR1
- **Required Fields**:
  - `PATH`: Path to the first input directory
  - `EVENTS`: Number of events for tuning (supports suffixes: k, m, g, e.g., "500k", "10M", "1G")
  - `EVENTS_VALIDATION`: Number of events for validation (same format as EVENTS)
- **Optional Fields**:
  - `REWEIGHTING`: Whether to use reweighting for the entire event generation (default: "off", values: on/off/true/false)

### INPUT_DIR2, INPUT_DIR3, ... (INPUT_DIRX)
- Any number of additional input directories (processes) may be given as `INPUT_DIR2`, `INPUT_DIR3`, ... The numbering must be contiguous and start at 1: e.g. providing `INPUT_DIR1` and `INPUT_DIR3` without `INPUT_DIR2` is an error.
- **Required Fields** (per block, when present):
  - `PATH`: Path to the input directory
  - `EVENTS`: Number of events for tuning
  - `EVENTS_VALIDATION`: Number of events for validation
- **Optional Fields**:
  - `REWEIGHTING`: Whether to use reweighting for the entire event generation (default: "off", values: on/off/true/false)

**The input directories must contain the following**:
- `template.yaml` - template for a Sherpa runcard
- `parameter.json` (only INPUT_DIR1) - contains the parameter ranges
- `nominal.json` (only if REWEIGHTING is enabled) - contains the nominal parameter values
- `init/` - directory containing Sherpa integration results (`Process` and `Results.zip`) (obtained from e.g. `Sherpa -e 0 ...`)
- `weights.txt` - contains the weights for all observables (can be created using `app-tools-write_weights`)
- `data.json` (**only if `APPRENTICE` is configured**) - contains reference data for the relevant analyses (can be created using `app-datadirtojson`). Professor loads reference data automatically via `prof2-tune -R`, so it is not required for Professor-only runs.
- `custom.weights.txt` (**only INPUT_DIR1, and only if `COMBINE_MODE: custom`**) - hand-supplied merged weight file used for the merged tunes (see `COMBINE_MODE`).

### N_GRID
- **Type**: Integer
- **Description**: Number of grid points for surrogate model training. Must be at least as large as the minimum required by the surrogate order and number of parameters. Minimum recommended value is 2× the theoretical minimum for stable fitting.

### Tuning backends (APPRENTICE / PROFESSOR)
- **Condition**: **At least one** of `APPRENTICE` or `PROFESSOR` must be configured. Each block, when present, activates that backend.
- **Combined execution**: If both are configured, each backend gets its own nodes in phases P5-P9 and they run in parallel. Each backend writes to its own `Apprentice/` and `Professor/` output folder.

#### APPRENTICE
- `ORDER` (**required**): String `k_p,k_q` (e.g. `2,1`), or a **list** of such strings (e.g. `ORDER: ["2,0", "3,0"]`). Two comma-separated integers giving the orders of the numerator/denominator surrogate polynomials used by `app-build`. In a list, every entry **must be quoted** — unquoted `[2,0]` is parsed by YAML as two integers, not one order. With a list, the per-input-dir build/tune (P5, P6) and the merged build/tune (P8, P9) run one job per order; every order gets its own surrogate, tune directories, and merged weight files (`weights.<order>.txt` / `err.weights.<order>.txt` in `MERGED_DIR/Apprentice`).
- `REPEAT` (optional, default `1`): Positive integer. How often each `app-tune2` job of P6 and P9 is submitted. `app-tune2` starts from a different random survey every time, so N repeats are N shots at the minimum. Repeat *k* writes `Apprentice/repeats/<tune name>.repeat-k`, and when the node has finished, the repeat with the lowest objective is linked back as `Apprentice/<tune name>`, the name every later phase uses, so P7, P10 and P13 always work with the best of the N.
- `APP_BUILD_OPTIONS` (optional): Free-form CLI option string appended to every `app-build` call (only if non-empty). Use this for any optional Apprentice build flags. It may not repeat anything the workflow sets itself (`--order`, `-w`, `-o`, `--errs`); doing so is an error at startup.
- `APP_TUNE2_OPTIONS` (optional): Free-form CLI option string appended to every `app-tune2` call (only if non-empty). For example `-s 500 -r 20` sets the survey size and number of restarts. It may not repeat `-o` or `-e`.

#### PROFESSOR
- `ORDER` (**required**): A single integer (e.g. `2`), or a **list** of integers (e.g. `ORDER: [2, 3, 4]`). Giving the order(s) of the surrogate polynomial used by `prof2-ipol`. With a list, the per-input-dir build/tune (P5, P6) and the merged build/tune (P8, P9) run one job per order; every order gets its own interpolation, tune directories, and merged weight files (`weights.<order>.txt` / `err.weights.<order>.txt` in `MERGED_DIR/Professor`).
- `REPEAT` (optional, default `1`): Positive integer. How often each `prof2-tune` job of P6 and P9 is submitted, exactly as for `APPRENTICE.REPEAT` above: the repeats go to `Professor/repeats/<tune name>.repeat-k` and the one with the lowest `# GOF` is linked back as `Professor/<tune name>`.
- `PROF2_IPOL_OPTIONS` (optional): Free-form CLI option string appended to every `prof2-ipol` call (only if non-empty). It may not repeat `--order`, `-w`, or `-j` (the thread count comes from `NPROC`).
- `PROF2_TUNE_OPTIONS` (optional): Free-form CLI option string appended to every `prof2-tune` call (only if non-empty). It may not repeat `-w`, `-o`, or `-R`.

### REWEIGHTING_PATTERN
- **Type**: String
- **Condition**: **Required** if any `INPUT_DIRX.REWEIGHTING` is `on`.
- **Description**: Pattern passed to `app-tools-split_reweighting` in phase P4 to split reweighted runs.

### RIVET_ENV_SCRIPT
- **Type**: Path
- **Description**: Path to the Rivet environment setup script (e.g., `rivetenv.sh`). 

### SHERPA_ON_THE_ROCKS_DIR
- **Type**: Path
- **Description**: Path to the sherpa-on-the-rocks directory. Everything the jobs run is resolved from it: the submit files in `SHERPA_ON_THE_ROCKS_DIR/tune/jobs`, the phase scripts in `SHERPA_ON_THE_ROCKS_DIR/tune/scripts`, and the workers of the standalone submission systems (`run_sherpa.sh`, `merge/`, `apprentice/`, `professor/`). Point it at the checkout you started `tune.py` from -- if the two differ, tune.py says so at startup and the cluster uses the one named here.

### APP_TOOLS_INSTALLATION
- **Type**: Path
- **Description**: Path to the app-tools installation directory. You can check the path using e.g. `which app-tools-create_grid`.

### APPRENTICE_INSTALLATION
- **Type**: Path
- **Condition**: **Required** when the `APPRENTICE` backend is configured.
- **Description**: Path to the Apprentice installation directory. You can check the path using e.g. `which app-build`.

### PROFESSOR_INSTALLATION
- **Type**: Path
- **Condition**: **Required** when the `PROFESSOR` backend is configured.
- **Description**: Path to the Professor (Professor2) installation directory. You can check the path using e.g. `which prof2-ipol`.

### SHERPA_BINARY
- **Type**: Path
- **Description**: Path to the Sherpa executable binary.

---

## Optional Parameters

### MPI_MODULE
- **Type**: String
- **Default**: "mpi/openmpi-x86_64"
- **Description**: HPC module name for MPI environment. This is required for the Apprentice jobs.

### NUMBA_DISABLE_JIT
- **Type**: Boolean-like string
- **Default**: `off`
- **Valid Values**: `on`, `off`, `true`, `false`
- **Description**: Sets `NUMBA_DISABLE_JIT=1` for phase jobs. This can suppress Numba JIT compilation warnings/errors in Apprentice workflows (especially in P4/P5), at the cost of slower execution.

### EMAIL
- **Type**: String (email address)
- **Default**: None (no emails sent)
- **Description**: If set, sends email notifications via the `mail` command on the submission node. An initial email is sent when the DAG starts, and a follow-up email after each DAG node finishes — so one per node, not one per phase. A node holding several jobs reports a status summary; a single-job node reports its full output. All of them are threaded under the initial email.

### MASTER_DIR
- **Type**: Path
- **Default**: `INPUT_DIR1/master`
- **Description**: Master working directory where state, phase times, DAG files, and condor output are stored.

### MERGED_DIR
- **Type**: Path
- **Default**: `INPUT_DIR1/merged` (only for multi-input runs)
- **Description**: Directory for combined reference data and tune results when using multiple input directories. Only used if more than one `INPUT_DIRX` is specified.

### GRID_SAMPLING
- **Type**: String
- **Default**: `random`
- **Valid Values**: `random`, `uniform`
- **Description**: Sampling strategy used by `app-tools-create_grid` in phase P1 when generating the tuning grid for `INPUT_DIR1`. `random` draws points uniformly at random within the parameter ranges; `uniform` lays points on a regular grid. Note: `uniform` is incompatible with dynamic parameter bounds (`app-tools-create_grid` will error in that case).

### MERGE_MODE
- **Type**: String
- **Default**: `rivet`
- **Valid Values**: `rivet`, `yoda`
- **Description**: Merging method to use for combining Sherpa subrun results in phases P3 and P12. Selects which script `merge/run_merge.sh` is handed: `SHERPA_ON_THE_ROCKS_DIR/rivet-merge_runs.sh` or `SHERPA_ON_THE_ROCKS_DIR/yodamerge_runs.sh`.

### MERGE_OPTIONS
- **Type**: String
- **Default**: `--rm --quiet`
- **Description**: Free-form CLI option string prepended to every merge command line in phases P3 and P12. Everything the merge script accepts goes here: `--rm`, `--quiet`, `--chunked N`, `--nmax N`, `--gz`. Set it to an empty string to pass no flags at all. Two things must not go in it: `-o`/`--output`, because the later phases read the merged YODA files in place from `newscan/` (or `newscan.rew/`), and a bare number, which the merge scripts read as the job count — that comes from `NPROC`, appended by `merge/run_merge.sh`. Reweighted grids hold far more YODA files per grid point, so adding `--chunked 10` is worth it when `INPUT_DIRx.REWEIGHTING` is on; it is **not** added automatically.

### COMBINE_MODE
- **Type**: String
- **Default**: `weighted`
- **Valid Values**: `weighted`, `simple`, `custom` (only for multi-input runs)
- **Description**: Method for combining tuning results from all processes. Applied per backend and per surrogate order in P7 (each order gets its own combined weight files, since the per-process best-tune results differ per order).
  - `weighted`: the per-process weight files are combined and automatically rescaled to balance the contribution to the global chi2 of each process.
  - `simple`: a plain concatenation of the per-process weight files (each rescaled by 1.0), with no chi2 balancing.
  - `custom`: use a hand-supplied merged weight file instead of combining the per-process weights. `INPUT_DIR1` must contain a file named `custom.weights.txt`; during initialisation it is copied into `MERGED_DIR/custom.weights.txt` and then used (for both the nominal and error tunes) by every merged tune in P9, across all backends and surrogate orders.

### START_PHASE / END_PHASE
- **Type**: Phase name (`P5`) or plain phase number (`5`)
- **Default**: `P1` and `P13`, i.e. the whole pipeline
- **Description**: Restrict the run to a slice of the pipeline. Only the phases from `START_PHASE` to `END_PHASE` get DAG nodes; the phases outside the window are not submitted, and the dependencies pointing into them are dropped. The phases in between cannot be picked individually -- a window is contiguous.

  Before anything is created, tune.py checks that the window can actually start where it says: every phase in the window is checked for the files you supply (`template.yaml`, `weights.txt`, `data.json`, ...), and the first phase that runs is additionally checked for everything its upstream phases would have produced (`newscan/`, the surrogate files, the tune result directories, ...). A missing input is reported with the phase that wants it, and nothing is written.

  Useful for re-doing part of a finished tune (`START_PHASE: P10` to rebuild the validation grid and the plots from existing tune results), for stopping before a long stage (`END_PHASE: P6`), or for running one stage with different settings. Running a window whose jobs have all finished before offers to run it again; widening the window later resumes as usual, keeping the finished phases.

### VALIDATION_ONLY_ERR
- **Type**: Boolean-like string
- **Default**: `off`
- **Valid Values**: `on`, `off`, `true`, `false`
- **Description**: If `on`, the validation grid (phase P10) is built only from the error tune results (`tune.<backend>.err.*`), skipping the nominal tune results. Applied to every active backend. Can be combined with `VALIDATION_ONLY_MERGED`.

### VALIDATION_ONLY_MERGED
- **Type**: Boolean-like string
- **Default**: `off`
- **Valid Values**: `on`, `off`, `true`, `false`
- **Condition**: Requires at least two input directories (errors at startup otherwise, since no merged tune exists for a single input).
- **Description**: If `on`, the validation grid (phase P10) is built only from the merged tune results (`*.merged`), skipping the per-input-directory tune results. If both `VALIDATION_ONLY_ERR` and `VALIDATION_ONLY_MERGED` are `on`, only the merged error tune seeds the validation grid (a single validation subdir).

### NPROC
- **Type**: Integer
- **Default**: 8
- **Description**: Number of CPUs requested for the phases that can use them: the merge job count in P3/P12, `app-build` (`mpirun -np NPROC`) and `prof2-ipol` (`-j NPROC`) in P5/P8, and P4 and P13. The `app-tune2` and `prof2-tune` jobs are single-process and always request one core, so they no longer occupy a whole multi-core slot. The single-threaded phases (P1, P2, P7, P10, P11) are unaffected. P4 and P13 request the cores but are handed no count on the command line, so they only benefit if the tool parallelises on its own. The name matches the `NPROC` environment variable the standalone submissions use, and inside every submit file the value arrives as the `$(NPROC)` macro.

### PHASE<n>_MAXRUNTIME
Every phase accepts a `PHASE<n>_MAXRUNTIME` key, where `<n>` is its number in the table under *The phases*. The individual defaults are listed below.

### PHASE1_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 1800
- **Description**: Maximum runtime for Phase 1 jobs in the HTCondor DAG. Create the tuning grid and prepare the Sherpa subruns.

### PHASE2_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 2 jobs in the HTCondor DAG. Sherpa event generation for the tuning grid. Per Sherpa run.

### PHASE3_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 3 jobs in the HTCondor DAG. Merge the Sherpa subrun results.

### PHASE4_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 4 jobs in the HTCondor DAG. Split reweighted variations into a grid (`app-tools-split_reweighting`). Only submitted for input dirs with `REWEIGHTING: on`.

### PHASE5_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 5 jobs in the HTCondor DAG. Build the surrogate for one input directory (`app-build` / `prof2-ipol`). **Per job**: one job per surrogate order and per value/error variant.

### PHASE6_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 6 jobs in the HTCondor DAG. Optimize the parameters for one input directory (`app-tune2` / `prof2-tune`). **Per job**, as for P5.

### PHASE7_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 1800
- **Description**: Maximum runtime for Phase 7 jobs in the HTCondor DAG. Combine the weight files of all processes (`app-tools-combine_weights`). Multi-input runs only.

### PHASE8_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 8 jobs in the HTCondor DAG. Build the merged surrogate (`app-build`). Multi-input Apprentice runs only; Professor reuses the P5 interpolations. **Per job**.

### PHASE9_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 9 jobs in the HTCondor DAG. Optimize the parameters against the merged surrogate. Multi-input runs only. **Per job**.

### PHASE10_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 1800
- **Description**: Maximum runtime for Phase 10 jobs in the HTCondor DAG. Create the validation grid from the tune results and prepare the subruns.

### PHASE11_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 11 jobs in the HTCondor DAG. Sherpa event generation for the validation grid. Per Sherpa run.

### PHASE12_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 12 jobs in the HTCondor DAG. Merge the validation results.

### PHASE13_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 1800
- **Description**: Maximum runtime for Phase 13 jobs in the HTCondor DAG. Compute the chi-squared values and plot the tune results.

---

## The phases

The workflow is split in 13 phases:

| Phase | What it does | Nodes |
| --- | --- | --- |
| P1 | `app-tools-create_grid sample/import`, `prepare_runs.sh` | `P1_dir<i>` |
| P2 | Sherpa event generation (tuning) | `P2_dir<i>` |
| P3 | Merge the subrun results | `P3_dir<i>` |
| P4 | `app-tools-split_reweighting` | `P4_dir<i>`, reweighted inputs only |
| P5 | Build the surrogate | `P5_dir<i>_app`, `P5_dir<i>_prof` |
| P6 | Optimize the parameters | `P6_dir<i>_app`, `P6_dir<i>_prof` |
| P7 | `app-tools-combine_weights` | `P7_app`, `P7_prof` |
| P8 | Build the merged surrogate | `P8_app` |
| P9 | Optimize against the merged surrogate | `P9_app`, `P9_prof` |
| P10 | `app-tools-create_grid tune`, `prepare_runs.sh` | `P10_dir<i>` |
| P11 | Sherpa event generation (validation) | `P11_dir<i>` |
| P12 | Merge the subrun results | `P12_dir<i>` |
| P13 | `app-tools-compute_chi2`, `app-tools-plot_chi2`, `app-tools-plot_params` | `P13` |

Each phase is one object in `lib/phases.py`, holding its title, its submit file, the nodes it contributes, what those nodes wait for, and the files it needs. The DAG, the job lists, the overview table, the artifact cleanup and the `START_PHASE`/`END_PHASE` check are all derived from that one list, so adding or renumbering a phase means editing one place.

The phases share five submit files in `tune/jobs`, and the `$(PHASE_SCRIPT)` phases run a script from `tune/scripts`:

| Submit file | Phases | Shape |
| --- | --- | --- |
| `phase-per-dir.jdf` | P1, P4, P10 | one job per input directory, running the `tune/scripts` script named by `$(PHASE_SCRIPT)` |
| `phase-global.jdf` | P13 | one job for the whole tune, same but with no `DIR_INDEX` |
| `phase-per-backend.jdf` | P7 | one job per active backend, same but with `$(BACKEND)` in place of `$(DIR_INDEX)` |
| `joblist-parallel.jdf` | P3, P5, P8, P12 | one job per line of the phase's job list, for workers handed a process count |
| `joblist-serial.jdf` | P2, P6, P9, P11 | the same, for the single-process workers, which take none |

P7 to P9 are skipped for a single input directory. P8 has no Professor node:
the merged Professor tune reuses the per-input-dir interpolations from P5 rather
than rebuilding them.

A Sherpa run that crashes is logged `[FAILED]` and the DAG carries on, one bad
grid point out of many must not halt the tune. Setup errors (no `Process`
directory, no runcard, missing binary) still stop the DAG.

---

## Notes

- **Path Expansion**: All path parameters support `~` for home directory expansion and can be relative (expanded relative to the config file location) or absolute.
- **Event Suffixes**: Event counts accept multipliers: `k` (* 10^3), `M` (* 10^6), `G` (* 10^9).
- **Examples**: Steering files for different use cases are provided in the `examples/` directory.
- **Unknown keys**: A top-level key that is not listed here is reported as a warning at startup and then ignored, so a typo does not silently change nothing.
