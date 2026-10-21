# condor-dashboard

A static overview of your HTCondor jobs on ROCKS, published on your institute webpage. A systemd timer on an always-on institute host (`ds9`) polls ROCKS over SSH every five minutes and writes plain HTML; nothing runs on the cluster.

It reads the `overview.<cluster>.log` files written by this repository's workers (`run_sherpa.sh`, `merge/run_merge.sh`, `apprentice/`, `professor/`, and the `tune/` workflow, whose logs sit one level deeper under `condor_output/<DAG node>/`), so it only reports on jobs submitted with them. For each cluster it shows job counts by final status, the number of generated events, runtime and CPU-efficiency histograms, and the jobs that failed.

**Requirements:** `python3` 3.7 or newer on `ds9`, and passwordless SSH from the institute network to `rocks`.


## Setup

### 1. Webspace (on ds9)

```bash
ln -s /share/scratch1/$USER/www ~/www
mkdir -p ~/www/condor/icons
chmod a+rX ~/www ~/www/condor
cp -n ~/sherpa-on-the-rocks/condor-dashboard/icons/* ~/www/condor/icons/
```

Apache only follows the symlink if `~/.htaccess` contains `Options FollowSymLinks`. If your webspace is elsewhere, skip the symlink and set `OUT_DIR` instead.

### 2. Configure

The `CONFIGURATION` block at the top of `generate.py` works as is at the institute:

- `USERNAME`: shown in the index subtitle. Defaults to the current account; set it if your ROCKS username differs.
- `SSH_HOST`: the cluster, `rocks`.
- `DASH_DIR`: where the scripts live, for the copy-to-clipboard commands on the pages. Derived from the file's location.
- `OUT_DIR`: where the pages are written, `~/www/condor`.

Badges after a cluster's name come from `~/www/condor/icons/badges.txt`, one `<word> <icon> <label>` per line: a cluster whose submit-file name contains the word gets the pill. The icon is an emoji or a file in `~/www/condor/icons/`, and `-` leaves the icon or label out. Merge, Apprentice and Professor jobs are recognised without it.

### 3. Record submissions (on ROCKS)

`condor_q` forgets finished jobs and never knows the submit file, so wrap `condor_submit` in your ROCKS `~/.bashrc`. Each submission appends cluster id, submit directory, time and submit file to `~/.condor-registry`; output and exit status are unchanged.

```bash
# --- condor dashboard: record cluster id, submit dir and submit file ---
_condor_register() {
  local cmd="$1"; shift
  local out rc cid sf a
  out=$(command "$cmd" "$@"); rc=$?
  printf '%s\n' "$out"
  [ $rc -eq 0 ] || return $rc
  cid=$(printf '%s' "$out" | sed -n 's/.*submitted to cluster \([0-9][0-9]*\).*/\1/p' | tail -n 1)
  sf=""
  for a in "$@"; do
    case "$a" in
      -*) ;;
      *.jdf|*.sub|*.submit|*.dag) sf="$(basename "$a")" ;;
    esac
  done
  if [ -n "$cid" ]; then
    { flock -x 200
      printf '%s\t%s\t%s\t%s\n' "$cid" "$PWD" "$(date -Is)" "$sf" >> "$HOME/.condor-registry"
    } 200>>"$HOME/.condor-registry.lock"
  fi
  return $rc
}
condor_submit()     { _condor_register condor_submit "$@"; }
```

### 4. Schedule (on ds9)

`~/.config/systemd/user/condor-dashboard.service` (adjust `ExecStart` if the repository is not in your home directory):

```ini
[Unit]
Description=Regenerate the Condor job dashboard
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 %h/sherpa-on-the-rocks/condor-dashboard/generate.py
```

`~/.config/systemd/user/condor-dashboard.timer`:

```ini
[Unit]
Description=Refresh the Condor job dashboard every 5 minutes

[Timer]
OnCalendar=*:0/5:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable it, keep it running while you are logged out, and generate once to check:

```bash
systemctl --user daemon-reload
systemctl --user enable --now condor-dashboard.timer
loginctl enable-linger $USER
systemctl --user start condor-dashboard.service
```

`~/www/condor/` now holds `index.html` and, in `clusters/`, a page and a copy of the overview log per cluster. The dashboard is at `https://www.theorie.physik.uni-goettingen.de/~$USER/condor/`.


## Usage

```bash
~/sherpa-on-the-rocks/condor-dashboard/generate.py         # refresh now
~/sherpa-on-the-rocks/condor-dashboard/forget.py <cluster> # hide a cluster
~/sherpa-on-the-rocks/condor-dashboard/forget.py --all     # hide everything not in the queue
```

Clusters drop off on their own `RETENTION_DAYS` (7) days after submission. `forget.py` hides one earlier by adding its id to `~/.config/condor-dashboard/forgotten` on `ds9`, and refuses a cluster that still has jobs in the queue. To bring one back, delete its line and rerun `generate.py`.

Pages warn when they are more than 30 minutes old. If you change the timer's `OnCalendar` step, set `REFRESH_MINUTES` in `generate.py` to match, so the countdown on the index page stays right.
