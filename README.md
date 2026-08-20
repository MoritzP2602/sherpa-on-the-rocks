<div align="center">
  <img src="logo.png" width="400"/>
</div>
<br>


# sherpa-on-the-rocks

This directory provides helper scripts and HTCondor job description files for running SHERPA jobs on the ROCKS cluster.


## Preparation

These steps only need to be performed once to set up and configure the scripts.

### 1. Copy tools to your ROCKS home

From your local machine, move the `sherpa-on-the-rocks` directory into your ROCKS home area:

```bash
mv sherpa-on-the-rocks /net/theorie/rocks/$USER
```

If you choose to move `sherpa-on-the-rocks` to a different directory, adjust all subsequent commands accordingly.

Note: It may be convenient to also keep a copy of `sherpa-on-the-rocks` in your local home directory, so you can run the exact same commands on your local machine and on the cluster, without having to adjust the paths in the commands below (run `cp -r /net/theorie/rocks/$USER/sherpa-on-the-rocks ~/`).

This local copy is required if you want the job dashboard described in [section 5](#5-monitoring-jobs-on-your-webpage).

### 2. Configure the HTCondor submit file

`USERNAME` on the second line is filled in automatically from the account you submit with, so you do not need to change it:

```bash
USERNAME    = $ENV(USER)
```

Set the path to your Sherpa binary (relative to your ROCKS home directory).

Example:

```bash
SHERPA      = /home/$(USERNAME)/Programs/sherpa/install/bin/Sherpa
```

If you moved `sherpa-on-the-rocks` to a different location in step 1.1, make sure to additionally update the path to `run_sherpa.sh` in the argument section.

`run_sherpa.sh` is called as:

```
run_sherpa.sh <SHERPA> <RIVET_ENV> <LOGDIR> <CLUSTER> <PROCESS> [MAXRUNTIME] <DIRECTORY> [INIT_DIR]
```

Everything up to `MAXRUNTIME` is fixed by the submit file; the trailing
arguments are one line of `runs.txt`, so what that file contains decides what
the job is told:

- `DIRECTORY` — the run directory. Relative by default, resolved against the
  directory you submit from. Use `prepare_runs.sh --absolute` when the jobs do
  not run from there, as the tuning workflow does.
- `INIT_DIR` — where the integration results live, added as a second field by
  `prepare_runs.sh --init`. Without it the job searches `.` and `./*` for a
  directory containing `Process`.

`RIVET_ENV` names a script to source before SHERPA runs. SHERPA's RPATH already
resolves everything a **built-in** Rivet analysis needs, so `sherpa.jdf` sets it
to `none`; point it at your `rivetenv.sh` only if your runcard uses a **custom**
analysis, which is found through `RIVET_ANALYSIS_PATH`. It must never be left
empty — HTCondor drops an empty macro from the argument list entirely and every
later argument shifts one place, which is what `none` avoids.

Whether one failed run stops the submission is not this script's decision: it
always exits with SHERPA's exit code. The tuning workflow keeps going because
its DAG post script decides the node's result, see [tune/](tune/).

### 3. (Optional) Make the scripts executable

You can make the scripts executable to run them without explicitly calling `bash`/`python3`:

```bash
chmod +x ~/sherpa-on-the-rocks/prepare_runs.sh
chmod +x ~/sherpa-on-the-rocks/yodamerge_runs.sh
chmod +x ~/sherpa-on-the-rocks/rivet-merge_runs.sh
chmod +x ~/sherpa-on-the-rocks/runtime.py
```


## 1. Preparing and submitting a SHERPA job

### 1.1 Create a working directory

Create a directory for your process and copy the YAML runcard there:

```bash
mkdir <process_dir>
cd <process_dir>
cp <path-to-runcard>/<runcard>.yaml .
```

Create a directory for the .log, .out and .err files:

```bash
mkdir condor_output
```

If you want to change the name of this directory, you also have to adjust `LOGDIR` in `sherpa.jdf`.

### 1.2 Initialize and integrate

Set up the process and perform the integration and library build in this directory (you can run these steps in a subdirectory of <process_dir>, i.e. <process_dir>/<initial_run_dir> to keep your workspace organized):

```bash
Sherpa -I <runcard>.yaml
./makelibs
Sherpa -e 0 <runcard>.yaml
```

This step prepares the integration results and builds the necessary libraries for event generation.

If you prefer to do this step in a subdirectory:

```bash
mkdir <initial_run_dir>
cd <initial_run_dir>
cp ../<runcard>.yaml .
Sherpa -I <runcard>.yaml
./makelibs
Sherpa -e 0 <runcard>.yaml
```

Note: If your local Sherpa installation differs in version from that on the cluster, you may need to run this setup on the cluster's login node to ensure compatibility.

### 1.3 Create production directory structure

Create a directory for production runs and place the runcard(s) there:

```bash
mkdir <production_dir>
cp <runcard>.yaml <production_dir>/
```

You can optionally organize different production configurations in subdirectories (all based on the same process, e.g. different values for UE parameters):

```bash
mkdir -p <production_dir>/<run_variant1> <production_dir>/<run_variant2>
cp <runcard1>.yaml <production_dir>/<run_variant1>/
cp <runcard2>.yaml <production_dir>/<run_variant2>/
```

Each (sub)directory that will be used for a run must contain a suitable `.yaml` file.

### 1.4 Split runs into subruns

To keep individual jobs within a chosen walltime (e.g. the 24‑hour queue), you can split each run directory into \(N\) subruns. Each subrun produces the full number of events specified in the runcard, so the total number of events scales with the number of subruns.

From the <process_dir> directory which contains the <production_dir> folder:

```bash
bash ~/sherpa-on-the-rocks/prepare_runs.sh <production_dir> <N_subruns>
```

- If `<production_dir>` has subdirectories, each of them will get `<N_subruns>` numbered subfolders.
- All created subrun directories are written to `runs.txt`, which is later used by HTCondor.

Note: If you run this command on your local machine and you do not have a copy of `sherpa-on-the-rocks` in your local home directory, you need to adjust the path in the command above (`/net/theorie/rocks/$USER/sherpa-on-the-rocks/prepare_runs.sh`).

### 1.5 Submit all subruns

From the <process_dir> directory which contains the `runs.txt` file submit the jobs using the provided job description file:

```bash
condor_submit ~/sherpa-on-the-rocks/sherpa.jdf
```

The submit file will create one job per line of `runs.txt`.

Note: You can only submit runs on the cluster and NOT from your local machine.


## 2. Monitoring jobs

List all your running jobs to find their IDs (`<job-id> = <cluster>.<process>`):

```bash
condor_q -run
```

To inspect a specific running job's output:

```bash
condor_ssh_to_job <job-id>
cat $TMPDIR/job.<job-id>.out
```

Once a job is finished, the .out, .err and .log files are stored in `condor_output` (e.g. `job.<job-id>.out`). A summary of all finished jobs can be found in `condor_output/overview.<cluster>.log`, including the final status of each job (COMPLETE, TIMEOUT or FAILED).


## 3. Merging YODA output

After all jobs have finished, merge the YODA output files from the subruns into a single file per run using `yodamerge`/`rivet-merge`.

From the directory containing your production runs:

```bash
bash ~/sherpa-on-the-rocks/yodamerge_runs.sh <production_dir>
```
or
```bash
bash ~/sherpa-on-the-rocks/rivet-merge_runs.sh <production_dir>
```

- If `<production_dir>` contains run subdirectories that themselves contain subrun subdirectories, each run subdirectory will get one merged `<run_variantX>.yoda` file.
- If `<production_dir>` only contains subrun directories, a single merged `<production_dir>.yoda` is produced.
- Optionally, add `--rm` to remove the subrun directories after a successful merge to free space:

```bash
bash ~/sherpa-on-the-rocks/yodamerge_runs.sh --rm <production_dir>
```

Note: If you run this command on your local machine, you need to adjust the path in the command above (`/net/theorie/rocks/$USER/sherpa-on-the-rocks/yodamerge_runs.sh`).

## 4. Generate runtime summary

The output of all runs is stored in `condor_output` per default. You can generate a summary (avg., min., max.) of the runtime for all different runcards by running:

```bash
python3 ~/sherpa-on-the-rocks/runtime.py condor_output
```

To generate this overview only for specific batch, use:

```bash
python3 ~/sherpa-on-the-rocks/runtime.py condor_output/job.<cluster>.*
```

Note: If you changed the condor output directory, you need to adjust the directory in the command above.

## 5. Monitoring jobs on your webpage

Instead of logging into the cluster to run `condor_q`, you can publish an overview of your jobs on your institute webpage: which clusters are running now, and what completed, failed or timed out over the last week.

It reads the `overview.<cluster>.log` files, so it only covers jobs submitted with the scripts in this repository. A timer on an always-on institute host refreshes it every five minutes.

See [condor-dashboard/README.md](condor-dashboard/README.md) for the setup.


This completes a typical Sherpa production cycle on ROCKS: initialize, split into subruns, submit via HTCondor, then merge the resulting YODA files. The scripts `prepare_runs.sh` and `yodamerge_runs.sh`/`rivet-merge_runs.sh` offer additional features. Run them without arguments to see all available options:

```bash
bash ~/sherpa-on-the-rocks/prepare_runs.sh
bash ~/sherpa-on-the-rocks/yodamerge_runs.sh
```

## 6. The other submission systems

Each of these works the same way as the SHERPA submission above: a plain-text job
list is created first, and HTCondor then runs one job per line of it.

| Directory | Runs | Guide |
| --- | --- | --- |
| [merge/](merge/) | `yodamerge_runs.sh` / `rivet-merge_runs.sh` on a node instead of the login node/local PC | [README.md](merge/README.md) |
| [apprentice/](apprentice/) | `app-build`, `app-tune2` | [build](apprentice/README.app-build.md), [tune](apprentice/README.app-tune2.md) |
| [professor/](professor/) | `prof2-ipol`, `prof2-tune` | [ipol](professor/README.prof2-ipol.md), [tune](professor/README.prof2-tune.md) |

The fully automatic tuning workflow in [tune/](tune/) chains all of them into one
HTCondor DAG, driving the same worker scripts rather than copies of them.

## License

MIT License

