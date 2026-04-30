# Configuration Parameters

## Required Parameters

### INPUT_DIR1
- **Required Fields**:
  - `PATH`: Path to the first input directory
  - `EVENTS`: Number of events for tuning (supports suffixes: k, m, g, e.g., "500k", "10M", "1G")
  - `EVENTS_VALIDATION`: Number of events for validation (same format as EVENTS)
- **Optional Fields**:
  - `REWEIGHTING`: Whether to use reweighting for the entire event generation (default: "off", values: on/off/true/false)
  - `VALIDATION_REWEIGHTING`: Whether to create an additional reweighting runcard during validation (default: "off", values: on/off/true/false)

### INPUT_DIR2
- **Required Fields** (when present):
  - `PATH`: Path to the second input directory
  - `EVENTS`: Number of events for tuning
  - `EVENTS_VALIDATION`: Number of events for validation
- **Optional Fields**:
  - `REWEIGHTING`: Whether to use reweighting for the entire event generation (default: "off", values: on/off/true/false)
  - `VALIDATION_REWEIGHTING`: Whether to create an additional reweighting runcard during validation (default: "off", values: on/off/true/false)

**The input directories must contain the following**:
- `template.json` - template for a Sherpa runcard
- `parameter.json` (only INPUT_DIR1) - contains the parameter ranges
- `nominal.json` (only if REWEIGHTING or VALIDATION_REWEIGHTING is enabled) - contains the nominal parameter values
- `init/` - directory containing Sherpa integration results (`Process` and `Results.zip`) (obtained from e.g. `Sherpa -e 0 ...`)
- `weights.txt` - contains the weights for all observables (can be created using `app-tools-write_weights`)
- `data.json` - contains reference data for the relevant analyses (can be created using `app-datadirtojson`)

### N_GRID
- **Type**: Integer
- **Description**: Number of grid points for surrogate model training. Must be at least as large as the minimum required by the surrogate order and number of parameters. Minimum recommended value is 2× the theoretical minimum for stable fitting.

### SURROGATE_ORDER
- **Type**: String (format: k_p,k_q)
- **Example**: `2,1` or `"2,1"`
- **Description**: Polynomial order for the surrogate model used by `app-build`. Specify as two comma-separated integers representing the orders for the primary and secondary surrogates. The minimum required grid size is determined by combinatorial formulas based on this order and the number of parameters.

### PATTERN
- **Type**: String
- **Condition**: **Required** if `INPUT_DIR1.REWEIGHTING` or `INPUT_DIR2.REWEIGHTING` is `on`.
- **Description**: Pattern passed to `app-tools-split_reweighting` in phase P4 to split reweighted runs.
- **Note**: Not required when only `VALIDATION_REWEIGHTING` is enabled.

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
- **Description**: Path to the Apprentice installation directory. You can check the path using e.g. `which app-build`.

### SHERPA_BINARY
- **Type**: Path
- **Description**: Path to the Sherpa executable binary.

---

## Optional Parameters

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

### MERGE_MODE
- **Type**: String
- **Default**: `yoda`
- **Valid Values**: `yoda`, `rivet`
- **Description**: Merging method to use for combining Sherpa subrun results in phases P3 and P8 (`SHERPA_ON_THE_ROCKS_DIR/yodamerge_runs.sh` and `SHERPA_ON_THE_ROCKS_DIR/rivet-merge_runs.sh`).

### COMBINE_MODE
- **Type**: String
- **Default**: `weighted`
- **Valid Values**: `weighted`, `equal` (only for two-input runs)
- **Description**: Method for combining tuning results from two processes. If `weighted` is used, the weights are automatically rescaled to balance the contribution to the global chi2 of each process, `equal` rescales all weights by 1.0.

### START_POINT_SURVEY
- **Type**: Integer
- **Default**: 500
- **Description**: Survey size used by `app-tune2` to determine a start point for the chi2 minimization.

### RESTARTS
- **Type**: Integer
- **Default**: 20
- **Description**: Number of restarts used by `app-tune2`, the best result out of all is returned.

### MPI_MODULE
- **Type**: String
- **Default**: "mpi/openmpi-x86_64"
- **Description**: HPC module name for MPI environment. This is required for the Apprentice jobs.

### NUMBA_DISABLE_JIT
- **Type**: Boolean-like string
- **Default**: `off`
- **Valid Values**: `on`, `off`, `true`, `false`
- **Description**: Sets `NUMBA_DISABLE_JIT=1` for phase jobs. This can suppress Numba JIT compilation warnings/errors in Apprentice workflows (especially in P4/P5), at the cost of slower execution.

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
