# Automatic Tuning Workflow on ROCKS

This folder contains scripts for a fully automatic tuning workflow on the ROCKS cluster.

For a quick guide, see the `example/` directory. All parameters are listed in `PARAMETERS.md`.

`tune.py` reads a YAML steering file and submits one HTCondor DAG covering the whole procedure, from event generation to the chi2 and parameter plots. Most phases run the scripts of the standalone submission systems (`../run_sherpa.sh`, `../merge/`, `../apprentice/`, `../professor/`).

Set `START_PHASE` and/or `END_PHASE` in the steering file to run only a slice of the pipeline; tune.py checks that everything the first phase needs is already on disk before it submits anything.

| Path | What it holds |
| --- | --- |
| `tune.py` | the entry point: reads the steering file, prepares the master directory, writes the DAG and submits it |
| `lib/runcard.py` | the steering file to the run state that is saved as `state.json` |
| `lib/phases.py` | the phases, as objects: their nodes, dependencies, job lists and required inputs |
| `lib/resume.py` | what an existing master directory means for a new invocation |
| `jobs/*.jdf` | the five HTCondor submit files the phases share |
| `scripts/run_*.sh` | the phase scripts those submit files run, plus `utils.sh` and the DAG's `post.sh` |
| `example/` | a worked example and its steering files |
