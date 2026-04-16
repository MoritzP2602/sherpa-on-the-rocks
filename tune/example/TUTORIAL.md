# Quick Start Guide

This folder contains three example steering files:

- [config1.yaml](config1.yaml)
- [config2.yaml](config2.yaml)
- [config3.yaml](config3.yaml)

These three examples correspond to the three tutorials described in the app-tools wiki.

## Requirements

Before running the script, make sure the following are installed and accessible on ROCKS:

- Rivet environment
- sherpa-on-the-rocks
- app-tools installation
- Apprentice installation
- Sherpa installation

These are configured in the steering files via `RIVET_ENV_SCRIPT`, `SHERPA_ON_THE_ROCKS_DIR`, `APP_TOOLS_INSTALLATION`, `APPRENTICE_INSTALLATION` and `SHERPA_BINARY`.

For the full list of available steering parameters, see [../PARAMETERS.md](../PARAMETERS.md).

## What the master script does

The master script [../tune.py](../tune.py) runs the complete tuning workflow described in app-tools automatically.

It creates and submits an HTCondor DAG (DAGMan), where each phase is a DAG job stage with the correct dependencies.

Phases:

- **P1**: create tuning grid and prepare Sherpa subruns
- **P2**: generate tuning events with Sherpa
- **P3**: merge tuning outputs
- **P4**: train surrogate and run optimization (Apprentice)
- **P5**: combine two-process tuning results (only for 2-input setups)
- **P6**: create validation grid from tune result
- **P7**: generate validation events with Sherpa
- **P8**: merge validation outputs
- **P9**: compute and plot chi2

Tune settings are customized in the steering files (e.g. [config1.yaml](config1.yaml), [config2.yaml](config2.yaml), [config3.yaml](config3.yaml)).

## How to start

From the `example` directory (adjust the paths to the required installations before running):

```bash
python3 tune.py config1.yaml
```

## What the script creates

For each run, the script creates and manages:

- a `MASTER_DIR` with state files, DAG files, and condor logs
- tuning results in `tune.*` folders
- chi2 plots (`chi2.plots`) generated from validation runs

A quick summary can be read from phase 9 output:

```bash
cat MASTER_DIR/condor_output/P9/job.*.out
```

Replace `MASTER_DIR` with your configured master directory (default is `INPUT_DIR1/master` unless set explicitly).

An extensive summary of the phase outputs can be generated using the `output.py` script:

```bash
python3 ../output.py MASTER_DIR
```

## Debugging and monitoring

Main places to inspect:

- Job logs for each phase and input:
  - `MASTER_DIR/condor_output/P1_dir1/`
  - ...
  - `MASTER_DIR/condor_output/P9/`
- DAG and DAGMan output in `MASTER_DIR`:
  - `tune.dag`
  - `tune.dag.*` (DAGMan runtime files)

If something fails, first check the corresponding `job.*.out`, `job.*.err`, `job.*.log` in the condor output directory.