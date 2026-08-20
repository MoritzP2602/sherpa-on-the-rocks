# app-build on ROCKS

This directory provides helper scripts and an HTCondor job description file for building [apprentice](https://github.com/HEPonHPC/apprentice) surrogates on the ROCKS cluster.

It works the same way as the SHERPA submission described in [../README.md](../README.md): a plain-text list is created first, and HTCondor then runs one job per line of it. Here each line is a complete `app-build` command line, so anything `app-build` accepts can go in it.


## Preparation

These steps only need to be performed once to set up and configure the scripts.

### 1. Configure the HTCondor submit file

`USERNAME` on the second line is filled in automatically from the account you submit with, so you do not need to change it:

```bash
USERNAME     = $ENV(USER)
```

Set the path to your `app-build` binary and to your Rivet environment script (both relative to your ROCKS home directory).

Example:

```bash
APP_BUILD    = /home/$(USERNAME)/Programs/local/bin/app-build
RIVET_ENV    = /home/$(USERNAME)/Programs/local/rivetenv.sh
```


### 2. (Optional) Make the scripts executable

```bash
chmod +x ~/sherpa-on-the-rocks/apprentice/prepare_app-builds.sh
```


## 1. Preparing and submitting a build job

### 1.1 Create a working directory

Work in a directory containing the grid you want to build a surrogate from:

```bash
cd <tune_input_dir>
ls
# newscan/   weights.txt
```

### 1.2 Create the build list

```bash
bash ~/sherpa-on-the-rocks/apprentice/prepare_app-builds.sh --order 2,0 2_0 --order 3,0 3_0 newscan
```

This writes `builds.txt` and creates `condor_output`:

```
newscan --order 2,0 -o 2_0.app.json
newscan --order 2,0 -o 2_0.err.json --errs
newscan --order 3,0 -o 3_0.app.json
newscan --order 3,0 -o 3_0.err.json --errs
```

- Each order produces two builds: the value surrogate and the error surrogate.
- The bare word after each order is the **output prefix**: `--order 2,0 2_0` writes `2_0.app.json` and `2_0.err.json`. The `.app.json` / `.err.json` postfix is always appended by the script and must not be part of the prefix. Leave the prefix out and the surrogates are plain `app.json` and `err.json`, which is fine for a single order but makes every prefix-less line write the same files, so give one as soon as you list more than one order. An existing directory is never taken as a prefix &mdash; that is how `<scan_dir>` is told apart.
- `--only-vals` lists only the value surrogates, `--only-errs` only the error ones. Using both at once is an error.
- `-w <weightfile>` adds a weight file to every line. Without it `app-build` is called with no `-w` and uses every observable it finds.
- Several scan directories may be given at once; they are passed to `app-build` together, which builds one combined surrogate over all of them.
- `--options "..."` is appended verbatim to every line, for flags such as `--mode`, `--ftol` or `-s`. It may not repeat anything the script already sets (`--order`, `-w`, `-o`, `--errs`), which is checked up front. The output names come from the prefix, not from `-o`.
- `--add` appends to an existing `builds.txt` instead of overwriting it, and `--dry` shows what would be written without writing it.

Every line is a complete `app-build` command line, so you can edit `builds.txt` freely afterwards: add or remove jobs, reorder them, or pass any other `app-build` flags.

Run `prepare_app-builds.sh` without arguments to see all available options.

### 1.3 Submit all builds

From the same directory, submit the jobs using the provided job description file:

```bash
condor_submit ~/sherpa-on-the-rocks/apprentice/app-build.jdf
```

The submit file will create one job per line of `builds.txt`.

`app-build` is MPI-parallel: it splits the bins across ranks and gathers them into a single output file. To use several cores of one node, set `NPROC`, which is the only value you ever need to override:

```bash
NPROC=16 condor_submit ~/sherpa-on-the-rocks/apprentice/app-build.jdf
```

Each job then runs `mpirun -np 16 app-build ...` and requests 16 cores.


## 2. Monitoring jobs

Exactly as for SHERPA jobs, see [../README.md](../README.md#2-monitoring-jobs). Once a job is finished, the .out, .err and .log files are stored in `condor_output` (e.g. `job.<job-id>.out`). A summary of all finished jobs can be found in `condor_output/overview.<cluster>.log`, including the final status of each job (COMPLETE, TIMEOUT, FAILED or REMOVED).

These jobs also appear on the [job dashboard](../condor-dashboard/README.md), tagged `Apprentice`.


## 3. Collecting the surrogates

Each job writes its `-o` target into the working directory:

```
2_0.app.json   2_0.err.json
3_0.app.json   3_0.err.json
```

`app-build` writes the surrogate directly here. It produces no output until the very end, when it dumps the whole JSON in one go. Only the job's `.out` and `.err` are written to scratch and copied back at exit.

These files are the input to the tuning step, see [README.app-tune2.md](README.app-tune2.md).