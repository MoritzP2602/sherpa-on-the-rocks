# app-build on HTCondor (with app-tools)

This directory provides files for running app-build jobs on the ROCKS cluster. An installation of `app-tools` (https://github.com/MoritzP2602/app-tools) and `apprentice` is required.


## Preparation

Before running, set the same kind of user-specific paths/configuration as described in [../README.md](../README.md):

1. In `run_app-build.sh`, set:
	- `APP_BUILD_INSTALLATION`
	- `RIVET_ENVIRONMENT`
2. In `build.jdf`, set:
	- `USERNAME`
	- optional: `NEWSCANDIR`, `LOGDIR`, `MAXRUNTIME`


## Workflow

### 1. Split a weight file for parallel jobs

Start by splitting the full weight list into multiple chunks with `app-tools-split_weights`.

```bash
app-tools-split_weights weights.txt <N_chunks>
```

This creates a directory with the split weight files (`files/00`, `files/01`, ...) and a `files.txt` file that is used by HTCondor when queueing the jobs.

### 2. Submit Condor jobs

Adjust the surrogate order in `build.jdf` to the desired value. Submit the jobs from the directory containing `files.txt`, `newscan/`, and `condor_output/` by running:

```bash
condor_submit ~/sherpa-on-the-rocks/app-build/build.jdf
```

The results are stored in app_<order> and err_<order> (e.g. app_5_0/00.json, app_5_0/01.json, ...).

Once a job is finished, the .out, .err and .log files are stored in `condor_output` (e.g. `job.<job-id>.out`). A summary of all finished jobs can be found in `condor_output/overview.<cluster>.log`.

### 3. Merge per-chunk JSON files

After all jobs have completed, merge the per-chunk JSON files with `app-tools-merge_surrogates`. Use one merge step for the normal surrogates and one for error surrogates.

```bash
app-tools-merge_surrogates app_5_0
app-tools-merge_surrogates err_5_0
```

If you want to keep the JSON directories (app_5_0, err_5_0) after merging:

```bash
app-tools-merge_surrogates app_5_0 --keep-dir -o app_5_0.json
app-tools-merge_surrogates err_5_0 --keep-dir -o err_5_0.json
```