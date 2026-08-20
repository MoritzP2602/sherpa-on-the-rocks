# Merging YODA files on ROCKS

This directory provides a helper script and an HTCondor job description file for running [`yodamerge_runs.sh`](../yodamerge_runs.sh) and [`rivet-merge_runs.sh`](../rivet-merge_runs.sh) on the cluster instead of on the login node.

It works the same way as the SHERPA submission described in [../README.md](../README.md): a plain-text list is created first, and HTCondor then runs one job per line of it. Here each line is a complete merge command line, so anything the merge scripts accept can go in it.


## Preparation

These steps only need to be performed once to set up and configure the scripts.

### 1. Configure the HTCondor submit files

There is one submit file per merge script: `rivet-merge.jdf` runs `rivet-merge_runs.sh`, `yodamerge.jdf` runs `yodamerge_runs.sh`. They are identical apart from that one line, and **both need the same edit below**.

`USERNAME` on the second line is filled in automatically from the account you submit with, so you do not need to change it:

```bash
USERNAME     = $ENV(USER)
```

Set the path to your Rivet environment script (relative to your ROCKS home directory).

Example:

```bash
RIVET_ENV    = /home/$(USERNAME)/Programs/local/rivetenv.sh
```


### 2. (Optional) Make the scripts executable

```bash
chmod +x ~/sherpa-on-the-rocks/merge/prepare_merges.sh
```


## 1. Preparing and submitting a merge job

### 1.1 Create a working directory

Work in a directory containing the folders you want to merge:

```bash
cd <run_dir>
ls
# newscan/   validation/
```

Each of those holds one subdirectory per run, with the subrun YODA files inside.

### 1.2 Create the merge list

```bash
bash ~/sherpa-on-the-rocks/merge/prepare_merges.sh --options "--rm --gz" newscan validation
```

This writes `merges.txt` and creates `condor_output`:

```
--rm --gz newscan
--rm --gz validation
```

- One job per folder, so several folders merge in parallel on different nodes.
- `--together` puts all folders on one line instead, i.e. one job for all of them.
- `--options "..."` is prepended verbatim to every line and is the only way to reach the merge script. Everything it accepts goes here: `--rm`, `--quiet`, `--chunked N`, `--nmax`, `--gz`, `-o DIR`.
- `--add` appends to an existing `merges.txt` instead of overwriting it, and `--dry` shows what would be written without writing it.

The number of parallel jobs comes from `NPROC` at submit time.

Run `prepare_merges.sh` without arguments to see all available options.

### 1.3 Submit all merges

From the same directory:

```bash
condor_submit ~/sherpa-on-the-rocks/merge/rivet-merge.jdf
```

The submit file will create one job per line of `merges.txt`.

Pick the merge script by picking the submit file (`merge/yodamerge.jdf` runs `yodamerge_runs.sh`). `NPROC` chooses how many merges each job runs in parallel:

```bash
NPROC=16 condor_submit ~/sherpa-on-the-rocks/merge/rivet-merge.jdf
```

Each job then requests 16 cores and passes 16 as the job count to the merge script. Both values are written into each job's `.out` file.


## 2. Monitoring jobs

Exactly as for SHERPA jobs, see [../README.md](../README.md#2-monitoring-jobs). Once a job is finished, the .out, .err and .log files are stored in `condor_output` (e.g. `job.<job-id>.out`). A summary of all finished jobs can be found in `condor_output/overview.<cluster>.log`, including the final status of each job (COMPLETE, TIMEOUT, FAILED or REMOVED).

These jobs also appear on the [job dashboard](../condor-dashboard/README.md), tagged `Merge`.


## 3. The merged files

The merge scripts write in place: each run directory gets a single `<name>.yoda` alongside (or instead of, with `--rm`) its subrun subdirectories. See [../README.md](../README.md) for what the merge scripts do in detail.