<div align="center">
  <img src="logo.png" width="400"/>
</div>
<br>


This directory provides helper scripts and HTCondor job description files for running SHERPA jobs on the ROCKS cluster.


## Preparation

These steps only need to be performed once to set up and configure the scripts.

### 1. Copy tools to your ROCKS home

From your local machine, move the `sherpa_on_rocks` directory into your ROCKS home area:

```bash
mv sherpa_on_rocks /net/theorie/rocks/$USER
```

If you choose to move `sherpa_on_rocks` to a different directory, adjust all subsequent commands accordingly.

### 2. Configure the Sherpa installation path

Edit `run_sherpa.sh` and set the path to your Sherpa binary (relative to your ROCKS home directory) near the top of the file.

Example:

```bash
SHERPA_INSTALLATION="~/Programs/sherpa/install/bin/Sherpa"
```

### 3. Configure the HTCondor submit file

Edit `sherpa.jdf` and replace `YOUR_USERNAME` with your actual ROCKS username on the second line.

Example:

```bash
USERNAME    = moritz.pabst
```

If you moved `sherpa_on_rocks` to a different location in step 1.1, make sure to additionally update the path to `run_sherpa.sh` in the argument section.


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
bash ~/sherpa_on_rocks/prepare_runs.sh <production_dir> <N_subruns>
```

- If `<production_dir>` has subdirectories, each of them will get `<N_subruns>` numbered subfolders.
- All created subrun directories are written to `runs.txt`, which is later used by HTCondor.

Note: If you run this command on a local machine, you need to adjust the path in the command above (`/net/theorie/rocks/$USER/sherpa_on_rocks/prepare_runs.sh`)

### 1.5 Submit all subruns

From the <process_dir> directory which contains the `runs.txt` file submit the jobs using the provided job description file:

```bash
condor_submit ~/sherpa_on_rocks/sherpa.jdf
```

The submit file will create one job per line of `runs.txt`.

Note: You can only submit runs on the cluster and NOT from your local machine.


## 2. Monitoring Jobs

List all your running jobs to find their IDs (`<cluster>.<process>`):

```bash
condor_q -run
```

To inspect a specific job's output:

```bash
condor_ssh_to_job <job-id>
cat $TMPDIR/job.<cluster>.<process>.out
```


## 3. Merging YODA output

After all jobs have finished, merge the YODA output files into a single file per run using `yodamerge`.

From the directory containing your production runs:

```bash
bash ~/sherpa_on_rocks/yodamerge_runs.sh <production_dir>
```

- If `<production_dir>` contains run subdirectories that themselves contain subrun subdirectories, each run subdirectory will get one merged `<run>.yoda` file.
- If `<production_dir>` only contains subrun directories, a single merged `<production_dir>.yoda` is produced.
- Optionally, add `--rm` to remove the subrun directories after a successful merge and free space:

```bash
bash ~/sherpa_on_rocks/yodamerge_runs.sh --rm <production_dir>
```

Note: If you run this command on a local machine, you need to adjust the path in the command above (`/net/theorie/rocks/$USER/sherpa_on_rocks/yodamerge_runs.sh`)


This completes a typical Sherpa production cycle on ROCKS: initialize, split into subruns, submit via HTCondor, then merge the resulting YODA files. The scripts `yodamerge_runs.sh` and `prepare_runs.sh` include additional features. Run them without arguments to see all available options:

```bash
bash ~/sherpa_on_rocks/yodamerge_runs.sh
bash ~/sherpa_on_rocks/prepare_runs.sh
```
