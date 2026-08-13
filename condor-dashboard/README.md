# condor-dashboard

This directory generates a static overview of your HTCondor jobs and publishes it
on your institute webpage, so you can check on a production run from anywhere
without logging into the cluster.

The index page lists every cluster running right now, and everything submitted in
the last 7 days with its completed/failed/timeout counts. Each cluster links to a
detail page listing the jobs that failed or hit the wall time limit, plus the raw
`overview.<cluster>.log`.

It reads the `overview.<cluster>.log` files written by `run_sherpa.sh`, so it
only reports on jobs submitted with the scripts in this repository.

Nothing runs on the cluster. A timer on an always-on institute host (`ds9`) polls
ROCKS over SSH every five minutes and writes plain HTML into your webspace.

**Requirements:** `python3` 3.7 or newer on `ds9`, and passwordless SSH from the
institute network to `rocks` — which you already have if you are submitting jobs
with this repository.


## Setup

Four steps, on two different machines. Do them in order.

### 1. Prepare your webspace (on ds9)

Institute webpages are served from `/share/scratch1/$USER/www`. Link it into your
home directory, since that is where the generator writes by default:

```bash
ln -s /share/scratch1/$USER/www ~/www
```

Apache will not follow that symlink unless you allow it. Create `~/.htaccess`
containing:

```
Options FollowSymLinks
```

Then create the output directory and make it world-readable, and install the
Sherpa badge icon:

```bash
mkdir -p ~/www/condor/icons
chmod a+rX ~/www ~/www/condor
cp ~/sherpa-on-the-rocks/condor-dashboard/icons/sherpa.png ~/www/condor/icons/
```

Note: if your webspace is somewhere else, skip the symlink and point `OUT_DIR` at
it directly in step 2.

### 2. Configure

Open `generate.py` and look at the `CONFIGURATION` block near the top. Every
value is a working default at the institute, so **most users change nothing
here**. Two cases need an edit:

- Your webspace is not reachable at `~/www/condor` — set `OUT_DIR`.
- Your ROCKS username differs from your institute username — set `USERNAME` to
  the ROCKS one. It is only used for the subtitle on the index page.

`USERNAME` otherwise defaults to the account running the script, and `DASH_DIR`
works out where this directory is on its own, so a copy placed anywhere is
correct without editing.

### 3. Record submissions (on ROCKS)

`condor_q` only knows about jobs that are still in the queue, and it cannot tell
you which submit file a job came from. To keep that information after a job
finishes, wrap `condor_submit` so it records each submission.

Add to your ROCKS `~/.bashrc`:

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

This appends one tab-separated line per submission to `~/.condor-registry` on
ROCKS, holding the cluster id, the submit directory, the timestamp and the submit
file name. `condor_submit` behaves exactly as before, and its exit status is
passed through unchanged.

Jobs you submitted before adding this still show up while they are in the queue,
just without a name or submit directory.

### 4. Schedule regeneration (on ds9)

Create `~/.config/systemd/user/condor-dashboard.service`:

```ini
[Unit]
Description=Regenerate the Condor job dashboard
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 %h/sherpa-on-the-rocks/condor-dashboard/generate.py
```

Adjust `ExecStart` if you put this repository somewhere other than your home
directory.

Create `~/.config/systemd/user/condor-dashboard.timer`:

```ini
[Unit]
Description=Refresh the Condor job dashboard every 5 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
```

Enable it, and allow it to keep running when you are not logged in:

```bash
systemctl --user daemon-reload
systemctl --user enable --now condor-dashboard.timer
loginctl enable-linger $USER
```

Then generate the pages once by hand to check everything works:

```bash
systemctl --user start condor-dashboard.service
ls -l ~/www/condor/
```

You should see `index.html` and one `<cluster>.html` plus
`overview.<cluster>.log` per recent cluster. Your dashboard is now at
`https://www.theorie.physik.uni-goettingen.de/~$USER/condor/`.


## Usage

The pages regenerate every five minutes on their own. Each page carries the time
it was generated, and shows a warning banner if it is more than 30 minutes old.

```bash
ssh ds9 '~/sherpa-on-the-rocks/condor-dashboard/generate.py'         # refresh now
ssh ds9 '~/sherpa-on-the-rocks/condor-dashboard/forget.py <cluster>' # drop a cluster
```

`forget.py` removes a cluster from the dashboard: its line in `~/.condor-registry`
on ROCKS, its cached state, and its page and copied log. It does **not** touch
your job output: the real `condor_output/` and its `overview.<cluster>.log` on
the cluster are left alone. It refuses to forget a cluster that still has jobs in
the queue, since `condor_q` would just put it straight back.

Clusters disappear from the dashboard on their own 7 days after submission, so
`forget.py` is only for clearing something out early. Change `RETENTION_DAYS` in
`generate.py` if you want a different window.