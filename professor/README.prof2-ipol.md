# prof2-ipol on ROCKS

This directory provides helper scripts and an HTCondor job description file for building [Professor](https://professor.hepforge.org/) interpolations (*ipols*) on the ROCKS cluster.

It works the same way as the SHERPA submission described in [../README.md](../README.md): a plain-text list is created first, and HTCondor then runs one job per line of it. Here each line is a complete `prof2-ipol` command line, so anything `prof2-ipol` accepts can go in it.


## Preparation

These steps only need to be performed once to set up and configure the scripts.

### 1. Configure the HTCondor submit file

`USERNAME` on the second line is filled in automatically from the account you submit with, so you do not need to change it:

```bash
USERNAME     = $ENV(USER)
```

Set the path to your `prof2-ipol` binary and to your Rivet environment script (both relative to your ROCKS home directory).

Example:

```bash
PROF2_IPOL   = /home/$(USERNAME)/Programs/local/bin/prof2-ipol
RIVET_ENV    = /home/$(USERNAME)/Programs/local/rivetenv.sh
```


### 2. (Optional) Make the scripts executable

```bash
chmod +x ~/sherpa-on-the-rocks/professor/prepare_prof2-ipols.sh
```


## 1. Preparing and submitting an ipol job

### 1.1 Create a working directory

Work in a directory containing the grid you want to interpolate:

```bash
cd <tune_input_dir>
ls
# newscan/   weights.txt
```

`newscan/` holds one subdirectory per grid point.

### 1.2 Create the ipol list

```bash
bash ~/sherpa-on-the-rocks/professor/prepare_prof2-ipols.sh --order 3 3 --order 4 4 -w weights.txt newscan
```

This writes `ipols.txt` and creates `condor_output`:

```
newscan 3.ipol.dat --order 3 -w weights.txt
newscan 4.ipol.dat --order 4 -w weights.txt
```

- The bare word after each order is the **output prefix**: `--order 3 3` writes `3.ipol.dat`. The `.ipol.dat` postfix is always appended by the script and must not be part of the prefix. Leave the prefix out and the ipol is plain `ipol.dat`, which is fine for a single build but makes every prefix-less line write the same file, so give one as soon as you list more than one ipol. An existing directory is never taken as a prefix.
- Use `--options` to set additional flags. It may not repeat anything the script already sets (`--order`, `-w`, `-j`), which is checked up front:

  ```bash
  # a lower order for the error parametrisation than for the values
  ... --order 4 --options "--eorder 2"
  # no error parametrisation at all
  ... --order 4 --options "--ierr none"
  ```

- `-w <weightfile>` restricts the build to a subset of bins. Without it `prof2-ipol` is called with no `-w`.
- `--add` appends to an existing `ipols.txt` instead of overwriting it, and `--dry` shows what would be written without writing it.

Note the argument order: `prof2-ipol` names its output as the **second positional argument**, not with `-o`. Keep `<scan_dir> <ipolfile>` first if you edit `ipols.txt` by hand, or the worker will report the wrong output name in the status log.

Otherwise every line is a complete `prof2-ipol` command line, so you can edit it freely and pass any other flags.

Run `prepare_prof2-ipols.sh` without arguments to see all available options.

### 1.3 Submit all ipols

From the same directory, submit the jobs using the provided job description file:

```bash
condor_submit ~/sherpa-on-the-rocks/professor/prof2-ipol.jdf
```

The submit file will create one job per line of `ipols.txt`.

`prof2-ipol` is threaded. To use several cores of one node, set `NPROC`:

```bash
NPROC=16 condor_submit ~/sherpa-on-the-rocks/professor/prof2-ipol.jdf
```

Each job then requests 16 cores and appends `-j 16` to the command. `NPROC` is the only way to set it: passing `-j` through `--options` is rejected with a message pointing you here. The value actually used is written into each job's `.out` file.


## 2. Monitoring jobs

Exactly as for SHERPA jobs, see [../README.md](../README.md#2-monitoring-jobs). Once a job is finished, the .out, .err and .log files are stored in `condor_output` (e.g. `job.<job-id>.out`). A summary of all finished jobs can be found in `condor_output/overview.<cluster>.log`, including the final status of each job (COMPLETE, TIMEOUT, FAILED or REMOVED).


## 3. Collecting the ipols

Each job writes its ipol into the working directory:

```
3.ipol.dat   4.ipol.dat
```

`prof2-ipol` writes the file directly here; only the job's `.out` and `.err` go to node-local scratch, and are copied back at exit.

These files are the input to the tuning step, see [README.prof2-tune.md](README.prof2-tune.md).