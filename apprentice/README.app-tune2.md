# app-tune2 on ROCKS

This directory provides helper scripts and an HTCondor job description file for running [apprentice](https://github.com/HEPonHPC/apprentice)'s `app-tune2` on the ROCKS cluster.

It is the counterpart to [../app-build](../app-build/README.md), which produces the surrogates this step tunes against, and it works the same way as the SHERPA submission described in [../README.md](../README.md): a plain-text list is created first, and HTCondor then runs one job per line of it. Here each line is a complete `app-tune2` command line.


## Preparation

These steps only need to be performed once to set up and configure the scripts.

### 1. Configure the HTCondor submit file

`USERNAME` on the second line is filled in automatically from the account you submit with, so you do not need to change it:

```bash
USERNAME     = $ENV(USER)
```

Set the path to your `app-tune2` binary and to your Rivet environment script (both relative to your ROCKS home directory).

Example:

```bash
APP_TUNE2    = /home/$(USERNAME)/Programs/local/bin/app-tune2
RIVET_ENV    = /home/$(USERNAME)/Programs/local/rivetenv.sh
```


### 2. (Optional) Make the scripts executable

```bash
chmod +x ~/sherpa-on-the-rocks/apprentice/prepare_app-tunes.sh
```


## 1. Preparing and submitting a tune job

### 1.1 Create a working directory

Work in the directory where you built the surrogates:

```bash
cd <tune_input_dir>
ls
# weights.txt   data.json   2_0.app.json   2_0.err.json
```

`data.json` holds the reference data and is not produced by `app-build`; create it once with `app-datadirtojson`.

### 1.2 Create the tune list

The weight file, the reference data and the surrogates are all named explicitly:

```bash
bash ~/sherpa-on-the-rocks/apprentice/prepare_app-tunes.sh -w weights.txt -d data.json \
     --surrogates 2_0.app.json 2_0.err.json 2_0 \
     --surrogates 3_0.app.json 3_0.err.json 3_0
```

This writes `tunes.txt` and creates `condor_output`:

```
weights.txt data.json 2_0.app.json -o tune.apprentice.2_0 -s 500 -r 20
weights.txt data.json 2_0.app.json -e 2_0.err.json -o tune.apprentice.err.2_0 -s 500 -r 20
weights.txt data.json 3_0.app.json -o tune.apprentice.3_0 -s 500 -r 20
weights.txt data.json 3_0.app.json -e 3_0.err.json -o tune.apprentice.err.3_0 -s 500 -r 20
```

- `-w` and `-d` are required.
- `--surrogates` takes a value surrogate and, optionally, an error surrogate, optionally followed by the output label. It is repeatable, and each occurrence is one tune set. Give a value surrogate on its own and no error tune is listed for that set:

  ```bash
  bash ~/sherpa-on-the-rocks/apprentice/prepare_app-tunes.sh -w weights.txt -d data.json \
       --surrogates 2_0.app.json 2_0
  ```

- Surrogates must end in `.json`; the label is the one trailing argument that does not, and it must come last. The tune directories are always named `tune.apprentice.<label>` and `tune.apprentice.err.<label>`
- The two surrogates need not come from the same order, so a 3,0 value surrogate can be tuned against a 2,1 error surrogate:

  ```bash
  bash ~/sherpa-on-the-rocks/apprentice/prepare_app-tunes.sh -w weights.txt -d data.json \
       --surrogates 3_0.app.json 2_1.err.json mix30_21
  ```

  which gives `tune.apprentice.mix30_21` and `tune.apprentice.err.mix30_21`.
- `--only-errs` lists only the error tunes; sets given without an error surrogate produce nothing. There is no `--no-errs`: to skip an error tune, simply do not give an error surrogate for that set.
- `--options "..."` can be used to set additional `app-tune2` flags (e.g. `-s 500 -r 20`). It may not repeat anything the script already sets (`-o`, `-e`), which is checked up front. The output directories come from the label, not from `-o`.
- `--repeat N` lists every tune N times, repeat *k* writing `tune.apprentice.<label>.repeat-k`.
- `--add` appends to an existing `tunes.txt` instead of overwriting it, and `--dry` shows what would be written without writing it.

Note: within a `--surrogates` set the `.json` suffix is what separates the surrogates from the label, so a typo in a surrogate name is reported as `Warning: <name> not found` rather than as an unknown argument, and a surrogate whose name does not end in `.json` is silently taken as the label instead.

Every line is a complete `app-tune2` command line, so you can edit `tunes.txt` freely afterwards and pass any other flags.

Run `prepare_app-tunes.sh` without arguments to see all available options.

### 1.3 Submit all tunes

From the same directory, submit the jobs using the provided job description file:

```bash
condor_submit ~/sherpa-on-the-rocks/apprentice/app-tune2.jdf
```

The submit file will create one job per line of `tunes.txt`.

There is no `NPROC` here: `app-tune2` is a single-process minimisation, so each job gets one core and the parallelism comes from having several lines in `tunes.txt`.


## 2. Monitoring jobs

Exactly as for SHERPA jobs, see [../README.md](../README.md#2-monitoring-jobs). Once a job is finished, the .out, .err and .log files are stored in `condor_output` (e.g. `job.<job-id>.out`). A summary of all finished jobs can be found in `condor_output/overview.<cluster>.log`, including the final status of each job (COMPLETE, TIMEOUT, FAILED or REMOVED).

These jobs also appear on the [job dashboard](../condor-dashboard/README.md), tagged `Apprentice`.


## 3. Collecting the results

Each job writes its `-o` directory into the working directory:

```
tune.apprentice.2_0/       tune.apprentice.err.2_0/
tune.apprentice.3_0/       tune.apprentice.err.3_0/
```

`app-tune2` writes its output directory here directly, as `app-build` does with its JSON. Only the job's `.out` and `.err` go to node-local scratch, and are copied back at exit.