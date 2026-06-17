# Configuration Parameters

## Required Parameters

### INPUT_DIR1
- **Required Fields**:
  - `PATH`: Path to the first input directory
  - `EVENTS`: Number of events for tuning (supports suffixes: k, m, g, e.g., "500k", "10M", "1G")
  - `EVENTS_VALIDATION`: Number of events for validation (same format as EVENTS)
- **Optional Fields**:
  - `REWEIGHTING`: Whether to use reweighting for the entire event generation (default: "off", values: on/off/true/false)

### INPUT_DIR2
- **Required Fields** (when present):
  - `PATH`: Path to the second input directory
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

### N_GRID
- **Type**: Integer
- **Description**: Number of grid points for surrogate model training. Must be at least as large as the minimum required by the surrogate order and number of parameters. Minimum recommended value is 2× the theoretical minimum for stable fitting.

### Tuning backends (APPRENTICE / PROFESSOR)
- **Condition**: **At least one** of `APPRENTICE` or `PROFESSOR` must be configured. Each block, when present, activates that backend.
- **Combined execution**: If both are configured, phases P4 and P5 run Apprentice first, then Professor. Each backend writes to its own `Apprentice/` and `Professor/` output folder.

#### APPRENTICE
- `ORDER` (**required**): String `k_p,k_q` (e.g. `2,1`). Two comma-separated integers giving the orders of the numerator/denominator surrogate polynomials used by `app-build`.
- `APP_BUILD_OPTIONS` (optional): Free-form CLI option string appended to every `app-build` call (only if non-empty). Use this for any optional Apprentice build flags.
- `APP_TUNE2_OPTIONS` (optional): Free-form CLI option string appended to every `app-tune2` call (only if non-empty). For example `-s 500 -r 20` sets the survey size and number of restarts.

#### PROFESSOR
- `ORDER` (**required**): A single integer (e.g. `2`). Giving the order of the surrogate polynomial used by `prof2-ipol`.
- `PROF2_IPOL_OPTIONS` (optional): Free-form CLI option string appended to every `prof2-ipol` call (only if non-empty).
- `PROF2_TUNE_OPTIONS` (optional): Free-form CLI option string appended to every `prof2-tune` call (only if non-empty).

### PATTERN
- **Type**: String
- **Condition**: **Required** if `INPUT_DIR1.REWEIGHTING` or `INPUT_DIR2.REWEIGHTING` is `on`.
- **Description**: Pattern passed to `app-tools-split_reweighting` in phase P4 to split reweighted runs.

### RIVET_ENV_SCRIPT
- **Type**: Path
- **Description**: Path to the Rivet environment setup script (e.g., `rivetenv.sh`). 

### SHERPA_ON_THE_ROCKS_DIR
- **Type**: Path
- **Description**: Path to the sherpa-on-the-rocks directory. If not otherwise specified using `JOB_DIR`, the job submission files are loaded from `SHERPA_ON_THE_ROCKS_DIR/tune`.

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
- **Description**: If set, sends email notifications via the `mail` command on the submission node. An initial email is sent when the DAG starts, and a follow-up email is sent after each phase completes.

### JOB_DIR
- **Type**: Path
- **Default**: `SHERPA_ON_THE_ROCKS_DIR/tune`
- **Description**: Directory containing phase submission files (.jdf) and bash scripts (.sh). 

### MASTER_DIR
- **Type**: Path
- **Default**: `INPUT_DIR1/master`
- **Description**: Master working directory where state, phase times, DAG files, and condor output are stored.

### MERGED_DIR
- **Type**: Path
- **Default**: `INPUT_DIR1/merged` (only for two-input runs)
- **Description**: Directory for combined reference data and tune results when using two input directories. Only used if `INPUT_DIR2` is specified.

### GRID_SAMPLING
- **Type**: String
- **Default**: `random`
- **Valid Values**: `random`, `uniform`
- **Description**: Sampling strategy used by `app-tools-create_grid` in phase P1 when generating the tuning grid for `INPUT_DIR1`. `random` draws points uniformly at random within the parameter ranges; `uniform` lays points on a regular grid. Note: `uniform` is incompatible with dynamic parameter bounds (`app-tools-create_grid` will error in that case).

### MERGE_MODE
- **Type**: String
- **Default**: `rivet`
- **Valid Values**: `rivet`, `yoda`
- **Description**: Merging method to use for combining Sherpa subrun results in phases P3 and P8 (`SHERPA_ON_THE_ROCKS_DIR/rivet-merge_runs.sh` and `SHERPA_ON_THE_ROCKS_DIR/yodamerge_runs.sh`).

### COMBINE_MODE
- **Type**: String
- **Default**: `weighted`
- **Valid Values**: `weighted`, `equal` (only for two-input runs)
- **Description**: Method for combining tuning results from two processes. Applied per backend in P5. If `weighted` is used, the weights are automatically rescaled to balance the contribution to the global chi2 of each process, `equal` rescales all weights by 1.0.

### VALIDATION_ONLY_ERR
- **Type**: Boolean-like string
- **Default**: `off`
- **Valid Values**: `on`, `off`, `true`, `false`
- **Description**: If `on`, the validation grid (phase P6) is built only from the error tune results (`tune.<backend>.err.*`), skipping the nominal tune results. Applied to every active backend. Can be combined with `VALIDATION_ONLY_MERGED`.

### VALIDATION_ONLY_MERGED
- **Type**: Boolean-like string
- **Default**: `off`
- **Valid Values**: `on`, `off`, `true`, `false`
- **Condition**: Requires two input directories (errors at startup otherwise, since no merged tune exists for a single input).
- **Description**: If `on`, the validation grid (phase P6) is built only from the merged tune results (`*.merged`), skipping the per-input-directory tune results. If both `VALIDATION_ONLY_ERR` and `VALIDATION_ONLY_MERGED` are `on`, only the merged error tune seeds the validation grid (a single validation subdir).

### MAX_CPUS
- **Type**: Integer
- **Default**: 8
- **Description**: Number of CPUs requested for the multi-threaded phases (P3, P4, P5, P8, P9). Sets `request_cpus` in the HTCondor submit files and the merge parallelism (`MERGE_NPROC`) used by the merge scripts in P3/P8. The single-threaded phases (P1, P2, P6, P7) are unaffected.

### PHASE1_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 1800
- **Description**: Maximum runtime for Phase 1 jobs in the HTCondor DAG.

### PHASE2_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 2 jobs in the HTCondor DAG.

### PHASE3_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 3 jobs in the HTCondor DAG.

### PHASE4_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 4 jobs in the HTCondor DAG.

### PHASE5_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 5 jobs in the HTCondor DAG.

### PHASE6_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 1800
- **Description**: Maximum runtime for Phase 6 jobs in the HTCondor DAG.

### PHASE7_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 7 jobs in the HTCondor DAG.

### PHASE8_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 86400
- **Description**: Maximum runtime for Phase 8 jobs in the HTCondor DAG.

### PHASE9_MAXRUNTIME
- **Type**: Integer (seconds)
- **Default**: 1800
- **Description**: Maximum runtime for Phase 9 jobs in the HTCondor DAG.

---

## Notes

- **Path Expansion**: All path parameters support `~` for home directory expansion and can be relative (expanded relative to the config file location) or absolute.
- **Event Suffixes**: Event counts accept multipliers: `k` (* 10^3), `M` (* 10^6), `G` (* 10^9).
- **Examples**: Steering files for different use cases are provided in the `examples/` directory.
