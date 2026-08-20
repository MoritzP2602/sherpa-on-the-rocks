# prof2-tune on ROCKS

This directory provides helper scripts and an HTCondor job description file for running [Professor](https://professor.hepforge.org/) tunes on the ROCKS cluster.

It is the counterpart to [README.prof2-ipol.md](README.prof2-ipol.md), which produces the ipols this step tunes against, and it works the same way as the SHERPA submission described in [../README.md](../README.md): a plain-text list is created first, and HTCondor then runs one job per line of it. Here each line is a complete `prof2-tune` command line.


## Preparation

These steps only need to be performed once to set up and configure the scripts.

### 1. Configure the HTCondor submit file

`USERNAME` on the second line is filled in automatically from the account you submit with, so you do not need to change it:

```bash
USERNAME     = $ENV(USER)
```

Set the path to your `prof2-tune` binary and to your Rivet environment script (both relative to your ROCKS home directory).

Example:

```bash
PROF2_TUNE   = /home/$(USERNAME)/Programs/local/bin/prof2-tune
RIVET_ENV    = /home/$(USERNAME)/Programs/local/rivetenv.sh
```


### 2. (Optional) Make the scripts executable

```bash
chmod +x ~/sherpa-on-the-rocks/professor/prepare_prof2-tunes.sh
```


## 1. Preparing and submitting a tune job

### 1.1 Create a working directory

Work in the directory where you built the ipols:

```bash
cd <tune_input_dir>
ls
# weights.txt   3.ipol.dat   4.ipol.dat
```

### 1.2 Create the tune list

The weight file, the reference data and the ipols are all named explicitly:

```bash
bash ~/sherpa-on-the-rocks/professor/prepare_prof2-tunes.sh -w weights.txt -R \
     --ipols 3.ipol.dat 3 \
     --ipols 4.ipol.dat 4
```

This writes `tunes.txt` and creates `condor_output`:

```
3.ipol.dat -w weights.txt -R -o tune.professor.3
4.ipol.dat -w weights.txt -R -o tune.professor.4
```

- `-w` is required, and so is exactly one of `-R` (take the reference data from Rivet's API) or `-d <refdir>` (take it from a directory).
- `--ipols` takes **one or more** ipol files, all fitted together in a single tune, optionally followed by the output label. It is repeatable, and each occurrence is one tune.
- Ipol files must end in `.dat`; the label is the one trailing argument that does not, and it must come last. The tune directory is always named `tune.professor.<label>`.
- This is how several input scans are combined, build one ipol per scan and then list them together:

  ```bash
  bash ~/sherpa-on-the-rocks/professor/prepare_prof2-tunes.sh -w weights.txt -R \
       --ipols DY/3.ipol.dat Jets/3.ipol.dat combined3
  ```

  which gives `tune.professor.combined3`.

- `--options "..."` is appended verbatim to every line, for flags such as `--limits`, `--minos`, `--gof-name` or `--theory-err`. It may not repeat anything the script already sets (`-w`, `-o`, `-R`, `-d`), which is checked up front. The output directory comes from the label, not from `-o`.
- `--repeat N` lists every tune N times, repeat *k* writing `tune.professor.<label>.repeat-k`.
- `--add` appends to an existing `tunes.txt` instead of overwriting it, and `--dry` shows what would be written without writing it.

Every line is a complete `prof2-tune` command line, so you can edit `tunes.txt` freely afterwards.

Run `prepare_prof2-tunes.sh` without arguments to see all available options.

### 1.3 Submit all tunes

From the same directory, submit the jobs using the provided job description file:

```bash
condor_submit ~/sherpa-on-the-rocks/professor/prof2-tune.jdf
```

The submit file will create one job per line of `tunes.txt`.


## 2. Monitoring jobs

Exactly as for SHERPA jobs, see [../README.md](../README.md#2-monitoring-jobs). Once a job is finished, the .out, .err and .log files are stored in `condor_output` (e.g. `job.<job-id>.out`). A summary of all finished jobs can be found in `condor_output/overview.<cluster>.log`, including the final status of each job (COMPLETE, TIMEOUT, FAILED or REMOVED).


## 3. Collecting the results

Each job writes its `-o` directory into the working directory:

```
tune.professor.3/       tune.professor.4/
```

`prof2-tune` writes its output directory here directly; only the job's `.out` and `.err` go to node-local scratch, and are copied back at exit.