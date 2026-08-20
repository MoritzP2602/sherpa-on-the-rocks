# Quick Start Guide

This folder contains three example steering files:

- `config1.yaml`
- `config2.yaml`
- `config3.yaml`

These three examples correspond to the three tutorials described in the app-tools wiki (https://github.com/MoritzP2602/app-tools/wiki/Tutorials).


## Requirements

Before running the script, make sure the following are installed and accessible on ROCKS:

- Rivet environment
- sherpa-on-the-rocks
- app-tools installation
- Apprentice and/or Professor installation
- Sherpa installation

These are configured in the steering files via `RIVET_ENV_SCRIPT`, `SHERPA_ON_THE_ROCKS_DIR`, `APP_TOOLS_INSTALLATION`, `APPRENTICE_INSTALLATION`, `PROFESSOR_INSTALLATION` and `SHERPA_BINARY`.

For the full list of available steering parameters, see `../PARAMETERS.md`.


## How to start

Initialize Sherpa and create the required process libraries:

```bash
unzip Drell-Yan.zip
cd Drell-Yan/init
Sherpa -I Sherpa.yaml && ./makelibs
cd ../..
unzip Jets.zip
cd Jets/init
Sherpa -I Sherpa.yaml && ./makelibs
cd ../..
```

Adjust the tuning ranges in `parameter.json` (and nominal values in `nominal.json` for `config3.yaml`):

```bash
cd Drell-Yan
nano parameter.json
cd ..
```

From the `example` directory (adjust the paths to the required installations before running), initialize the process and run the master script:

```bash
python3 ../tune.py config1.yaml
```


## What the master script does

The master script `../tune.py` runs the complete tuning workflow described in app-tools automatically.

It creates and submits an HTCondor DAG (DAGMan). Each phase becomes one or more DAG nodes with the correct dependencies, and a node may itself hold many HTCondor jobs — one per grid point, surrogate order or folder.

Phases:

- **P1**: create tuning grid and prepare Sherpa subruns
- **P2**: generate tuning events with Sherpa (one job per grid point)
- **P3**: merge tuning outputs (one job per input directory)
- **P4**: split reweighted variations into a grid (only for `REWEIGHTING: on`)
- **P5**: build the surrogate (one HTCondor job per surrogate order and per value/error variant)
- **P6**: optimize the parameters against it (same, one job each)
- **P7**: combine the weight files of all processes (multi-input setups only)
- **P8**: build the merged surrogate (multi-input Apprentice only)
- **P9**: optimize against the merged surrogate (multi-input setups only)
- **P10**: create validation grid from tune result
- **P11**: generate validation events with Sherpa (one job per grid point)
- **P12**: merge validation outputs (one job per input directory)
- **P13**: compute chi2 and plot the results (chi2 and tuned parameters)

Tune settings are customized in the steering files (e.g. `config1.yaml`, `config2.yaml`, `config3.yaml`).


## What the script creates

For each run, the script creates and manages:

- a `MASTER_DIR` with state files, DAG files, and condor logs
- tuning results in `Apprentice/` and `Professor/` folders (e.g. `tune.apprentice.*`, `tune.professor.*`)
- chi2 values (`chi2.json`) and plots (`chi2-plots/`) generated from the validation runs
- a forest plot of the tuned parameters and their fit errors (`params_forest.pdf`), one per input directory and one for `MERGED_DIR`

A quick summary can be read from the phase 13 output:

```bash
cat MASTER_DIR/condor_output/P13/job.*.out
```

Replace `MASTER_DIR` with your configured master directory (default is `INPUT_DIR1/master` unless set explicitly).


## Debugging and monitoring

Main places to inspect:

- Job logs, one directory per DAG node, named after it:
  - `MASTER_DIR/condor_output/P1_dir1/`
  - `MASTER_DIR/condor_output/P5_dir1_app/` (phase, input directory, backend)
  - `MASTER_DIR/condor_output/P13/`
- The job lists the nodes queue from, one line per HTCondor job:
  - `MASTER_DIR/joblists/P5_dir1_app.txt`
- DAG and DAGMan output in `MASTER_DIR`:
  - `tune.dag`
  - `tune.dag.*` (DAGMan runtime files)

If something fails, first check the corresponding `job.*.out`, `job.*.err`, `job.*.log` in the node's directory. Nodes that hold several jobs also write `overview.<cluster>.log` there, giving the final status of each job (`COMPLETE`, `TIMEOUT`, `FAILED` or `REMOVED`).

To repeat one failed job by hand, copy its line out of the job list and run the tool on it directly.