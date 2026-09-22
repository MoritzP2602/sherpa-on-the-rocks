#!/usr/bin/env python3
"""Generate a static dashboard of HTCondor job status.

Runs on an always-on institute host (ds9) and publishes into ~/www/condor.

Disclaimer: entire script written by claude opus
"""

from __future__ import annotations

import getpass
import html
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import astuple, dataclass, field
from datetime import datetime, timedelta, timezone

def _tilde(path):
    """Shorten a leading home directory to ~, so the commands shown on the
    generated pages stay short and readable.
    """
    path = os.path.abspath(path)
    home = os.path.expanduser("~")
    for candidate in (home, os.path.realpath(home)):
        if path == candidate:
            return "~"
        if path.startswith(candidate + os.sep):
            return "~" + path[len(candidate):]
    return path


# ============================== CONFIGURATION ==============================
# Your ROCKS username. Only used for the subtitle on the index page. Defaults
# to the account running this script; set it to a literal string if your ROCKS
# username differs from your institute one.
USERNAME = getpass.getuser()

# The cluster. Resolves through the institute DNS search domain, so no
# ~/.ssh/config entry is needed. Passwordless SSH to it is required.
SSH_HOST = "rocks"

# The always-on host this script runs on. Appears in the click-to-copy commands
# shown on the generated pages.
DASH_HOST = "ds9"

# Where this script lives, used in those same commands. Derived from the file's
# own location, so a copy placed anywhere is correct without editing.
DASH_DIR = _tilde(os.path.dirname(os.path.abspath(__file__)))

# Where the generated pages are written. Usually to your Institute web space.
OUT_DIR = os.path.expanduser("~/www/condor")
# ===========================================================================

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
STATE_FILE = os.path.expanduser("~/.cache/condor-dashboard/state.json")
HISTORY_FILE = os.path.expanduser("~/.cache/condor-dashboard/history.csv")
HISTORY_DAYS = 400
REGISTRY_PATH = "$HOME/.condor-registry"

FORGOTTEN_FILE = os.path.expanduser("~/.config/condor-dashboard/forgotten")
RETENTION_DAYS = 7
STALE_MINUTES = 30
# How often the systemd timer runs this script; drives the countdown on the
# index page, so keep it equal to the timer's OnCalendar step.
REFRESH_MINUTES = 5
SSH_TIMEOUT = 120

FILE_MARKER = "@@CONDOR-DASH-FILE@@"

# Icons in JOB_KINDS may be an emoji, or the name of an image file placed in
# OUT_DIR/<ICON_DIR>/ (e.g. ~/www/condor/icons/sherpa.png).
ICON_DIR = "icons"
ICON_SUFFIXES = (".png", ".svg", ".jpg", ".jpeg", ".webp", ".gif", ".avif")

CLUSTER_DIR = "clusters"

FORGET_COMMAND = "{}/forget.py {{cluster}}".format(DASH_DIR)
FORGET_GENERIC_COMMAND = "{}/forget.py CLUSTER_ID".format(DASH_DIR)
FORGET_ALL_COMMAND = "{}/forget.py --all".format(DASH_DIR)
REFRESH_COMMAND = "{}/generate.py".format(DASH_DIR)

STATUS_IDLE = 1
STATUS_RUNNING = 2
STATUS_HELD = 5

# ---------------------------------------------------------------- data model


@dataclass
class Entry:
    """One line of an overview.<cluster>.log file."""

    status: str
    cluster: str
    proc: str
    dir: str | None = None
    events: str | None = None
    detail: str | None = None
    totaltime: int | None = None
    waittime: int | None = None
    wall_limit: int | None = None
    cputime: int | None = None
    nproc: int | None = None
    host: str | None = None
    seed: str | None = None
    copyfail: str | None = None


@dataclass
class JobTiming:
    """The per-job numbers the runtime plots need, in seconds."""

    status: str
    totaltime: int | None = None
    waittime: int | None = None
    wall_limit: int | None = None
    cputime: int | None = None
    nproc: int | None = None

    @property
    def efficiency(self):
        """CPU time per requested core-second, or None without the inputs."""
        if self.cputime is None or not self.totaltime:
            return None
        return self.cputime / (self.totaltime * (self.nproc or 1))


@dataclass
class OverviewSummary:
    """Aggregate of one overview log."""

    done: int = 0
    ok: int = 0
    failed: int = 0
    timeout: int = 0
    removed: int = 0
    unparsed: int = 0
    restarted: int = 0
    problems: list = field(default_factory=list)
    timings: list = field(default_factory=list)


@dataclass
class RegistryEntry:
    cluster: str
    dir: str
    submitted: datetime | None = None
    submit_file: str | None = None


@dataclass
class QueueState:
    cluster: str
    running: int = 0
    idle: int = 0
    held: int = 0
    other: int = 0
    iwd: str | None = None
    args: str | None = None
    cmd: str | None = None

    @property
    def total(self):
        return self.running + self.idle + self.held + self.other

    @property
    def cmdline(self):
        return " ".join(p for p in (self.cmd, self.args) if p)


@dataclass
class Selection:
    cluster: str
    submit_dir: str | None
    timestamp: datetime | None
    queue: QueueState | None
    submit_file: str | None = None
    cmdline: str | None = None


@dataclass
class InventoryItem:
    cluster: str
    mtime: int
    path: str


# ---------------------------------------------------------------- parsing

_HEAD = re.compile(r"^\[(COMPLETE|FAILED|TIMEOUT|REMOVED)\]\s+(\d+)\.(\d+)$")
_WALL_LIMIT = re.compile(r"Hit wall time limit of\s+(\S+)\s+seconds")
_COUNTER = {"COMPLETE": "ok", "FAILED": "failed", "TIMEOUT": "timeout",
            "REMOVED": "removed"}
_FIELDS = {"DIR": "dir", "EVENTS": "events", "Exit code": "detail",
           "HOST": "host", "SEED": "seed", "TOTALTIME": "totaltime",
           "WAITTIME": "waittime", "WALLTIME_LIMIT": "wall_limit",
           "CPUTIME": "cputime", "NPROC": "nproc", "COPY": "copyfail"}
_INT_FIELDS = {"totaltime", "waittime", "wall_limit", "cputime", "nproc"}


def _int_or_none(text):
    try:
        return int(text)
    except ValueError:
        return None


def parse_overview_line(line):
    """Parse one overview log line, or return None if it is not one."""
    segments = [s.strip() for s in line.split("|")]
    head = _HEAD.match(segments[0])
    if not head:
        return None

    entry = Entry(status=head.group(1), cluster=head.group(2), proc=head.group(3))
    for segment in segments[1:]:
        key, colon, value = segment.partition(":")
        attr = _FIELDS.get(key) if colon else None
        if attr is None:
            wall = _WALL_LIMIT.search(segment)
            if wall:
                entry.detail = wall.group(1)
        elif attr in _INT_FIELDS:
            setattr(entry, attr, _int_or_none(value))
        else:
            setattr(entry, attr, value.strip())
    return entry


def _timing(entry):
    """The entry's JobTiming, or None when its line carried no timing at all."""
    values = (entry.totaltime, entry.waittime, entry.wall_limit, entry.cputime,
              entry.nproc)
    if all(v is None for v in values):
        return None
    return JobTiming(entry.status, *values)


def parse_overview(text):
    """Summarise a whole overview log. Never raises on malformed content."""
    summary = OverviewSummary()
    latest = {}
    order = []
    for line in text.splitlines():
        if not line.strip():
            continue
        entry = parse_overview_line(line)
        if entry is None:
            summary.unparsed += 1
            continue
        key = (entry.cluster, entry.proc)
        previous = latest.get(key)
        if previous is None:
            order.append(key)
        else:
            summary.restarted += 1
            if entry.status == "REMOVED" and previous.status != "REMOVED":
                continue
        latest[key] = entry
    for key in order:
        entry = latest[key]
        summary.done += 1
        counter = _COUNTER[entry.status]
        setattr(summary, counter, getattr(summary, counter) + 1)
        if entry.status != "COMPLETE":
            summary.problems.append(entry)
        timing = _timing(entry)
        if timing is not None:
            summary.timings.append(timing)
    return summary


def parse_registry(text):
    """Read the append-only registry the condor_submit wrapper writes."""
    registry = {}
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) < 2 or not fields[0].strip().isdigit():
            continue
        submitted = None
        if len(fields) >= 3:
            try:
                submitted = datetime.fromisoformat(fields[2].strip())
            except ValueError:
                submitted = None
            if submitted is not None and submitted.tzinfo is None:
                submitted = submitted.astimezone()
        submit_file = fields[3].strip() if len(fields) >= 4 and fields[3].strip() else None
        cluster = fields[0].strip()
        registry[cluster] = RegistryEntry(cluster, fields[1].strip(), submitted, submit_file)
    return registry


def parse_forgotten(text):
    """Cluster ids recorded as forgotten, one per line."""
    return {line.strip() for line in text.splitlines() if line.strip().isdigit()}


def load_forgotten(path=None):
    """The forget list, or an empty set if it has never been written."""
    try:
        with open(path or FORGOTTEN_FILE) as handle:
            return parse_forgotten(handle.read())
    except OSError:
        return set()


def _field(fields, index):
    """Return a cleaned optional field, treating ClassAd 'undefined' as absent."""
    if len(fields) <= index:
        return None
    value = fields[index].strip()
    return None if not value or value == "undefined" else value


def parse_condor_q(text):
    """Parse `condor_q -af:t ClusterId ProcId JobStatus Iwd Args Cmd` output."""
    queue = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t") if "\t" in line else line.split(None, 3)
        if len(fields) < 3:
            continue
        cluster, status_text = fields[0].strip(), fields[2].strip()
        if not cluster.isdigit() or not status_text.isdigit():
            continue
        state = queue.setdefault(cluster, QueueState(cluster))
        status = int(status_text)
        if status == STATUS_RUNNING:
            state.running += 1
        elif status == STATUS_IDLE:
            state.idle += 1
        elif status == STATUS_HELD:
            state.held += 1
        else:
            state.other += 1
        if state.iwd is None:
            state.iwd = _field(fields, 3)
        if state.args is None:
            state.args = _field(fields, 4)
        if state.cmd is None:
            state.cmd = _field(fields, 5)
    return queue


JOB_KINDS = [
    ("run_app-build", "", "Apprentice"),
    ("app-build", "", "Apprentice"),
    ("run_app-tune2", "", "Apprentice"),
    ("app-tune", "", "Apprentice"),
    ("run_prof2-ipol", "", "Professor"),
    ("prof2-ipol", "", "Professor"),
    ("run_prof2-tune", "", "Professor"),
    ("prof2-tune", "", "Professor"),
    ("run_merge", "", "Merge"),
    ("yodamerge", "", "Merge"),
    ("rivet-merge", "", "Merge"),
    ("run_sherpa", "sherpa.png", "Sherpa"),
    ("sherpa", "sherpa.png", "Sherpa"),
]


def job_kind(cmdline=None, submit_file=None):
    """Guess what kind of job this is, as (icon, label). ("", "") if unknown."""
    haystack = "{} {}".format(cmdline or "", submit_file or "").lower()
    for needle, icon, label in JOB_KINDS:
        if needle in haystack:
            return icon, label
    return "", ""


def parse_inventory(text):
    """Parse the remote `cluster<TAB>mtime<TAB>path` overview-log listing."""
    inventory = {}
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) < 3 or not fields[0].isdigit() or not fields[1].strip().isdigit():
            continue
        inventory[fields[0]] = InventoryItem(fields[0], int(fields[1].strip()), fields[2].strip())
    return inventory


def split_fetched_logs(stream, marker=FILE_MARKER):
    """Split the concatenated log stream returned by the remote fetch."""
    files = {}
    current = None
    buffer = []
    for line in stream.splitlines(keepends=True):
        if line.startswith(marker + " "):
            if current is not None:
                files[current] = "".join(buffer)
            current = line[len(marker) + 1:].strip()
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        files[current] = "".join(buffer)
    return files


# ---------------------------------------------------------------- selection


def select_clusters(registry, queue, mtimes, now, retention_days=RETENTION_DAYS,
                    forgotten=()):
    """Choose which clusters to display, newest first."""
    cutoff = now - timedelta(days=retention_days)
    selections = []
    for cluster in set(registry) | set(queue):
        if cluster in forgotten:
            continue
        entry = registry.get(cluster)
        state = queue.get(cluster)

        timestamp = entry.submitted if entry else None
        if timestamp is None:
            timestamp = mtimes.get(cluster)

        submit_dir = entry.dir if entry else None
        if not submit_dir and state:
            submit_dir = state.iwd

        in_queue = state is not None and state.total > 0
        if not in_queue and (timestamp is None or timestamp < cutoff):
            continue
        selections.append(Selection(
            cluster, submit_dir, timestamp, state,
            submit_file=entry.submit_file if entry else None,
            cmdline=state.cmdline if state else None,
        ))

    selections.sort(key=lambda s: (s.timestamp is not None, s.timestamp), reverse=True)
    return selections


# ---------------------------------------------------------------- rendering

_CSS = """
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{font-family:'Segoe UI',Arial,sans-serif;background:#f6f8fa;color:#222;margin:0;padding:32px 16px}
.wrap{max-width:1100px;margin:0 auto}
h1{font-size:1.5em;margin:0 0 4px}
h2{font-size:1.05em;color:#444;margin:32px 0 10px;font-weight:600}
.sub{color:#8a949e;font-size:.85em;margin-bottom:8px}
.scroll{overflow-x:auto}
.sheet{background:#fff;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.07);
margin-bottom:8px}
table{width:100%;min-width:600px;border-collapse:separate;border-spacing:0}
th{background:#fff;font-size:.72em;text-transform:uppercase;letter-spacing:.05em;color:#777;
text-align:left;padding:11px 14px;border-bottom:1px solid #e1e6ea}
td{padding:10px 14px;border-top:1px solid #eef1f4;font-size:.93em;vertical-align:top}
tr:hover td{background:#f7fafd}
a{color:#1565c0;text-decoration:none}a:hover{text-decoration:underline}
.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.path{color:#8a949e;font-size:.86em;word-break:break-all}
.pill{display:inline-block;padding:2px 8px;border-radius:20px;font-size:.8em;font-weight:600}
.run{background:#e3f2ea;color:#1b7a43}.idle{background:#eef1f4;color:#667}
.bad{background:#fdecea;color:#b3261e}.warn{background:#fff4e5;color:#9a5b00}
.zero{background:#f4f6f8;color:#aeb6be}
.more td{border-top:none;padding:0 14px 11px;color:#8a949e;font-size:.85em}
.more .pill{font-size:.9em}
tr:hover+tr.more td{background:#f7fafd}
.none{color:#8a949e;font-style:italic;padding:14px 0}
.banner{background:#fdecea;color:#b3261e;padding:11px 14px;border-radius:8px;
font-size:.9em;margin-bottom:14px}
#stale{display:none;background:#fff4e5;color:#9a5b00;padding:11px 14px;border-radius:8px;
font-size:.9em;margin-bottom:14px}
.back{font-size:.9em;display:inline-block;margin-bottom:14px}
.kind{display:inline-block;font-size:.78em;color:#5a6570;background:#f1f4f7;
border-radius:20px;padding:2px 9px;margin-left:7px;white-space:nowrap}
.bar{height:4px;background:#eef1f4;border-radius:3px;margin-top:9px;overflow:hidden;max-width:190px}
.bar span{display:block;height:100%;background:#1b7a43}
.kicon{height:1.15em;width:auto;vertical-align:-.22em;border-radius:2px}
.card{background:#fff;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.07);
padding:12px 14px 8px;margin-bottom:16px}
.chart{display:block;width:100%;height:210px}
.legend{display:flex;gap:16px;flex-wrap:wrap;padding:2px 4px 4px;font-size:.8em;color:#5a6570}
.lg{display:inline-flex;align-items:center;gap:6px}
.lg i{width:14px;height:3px;border-radius:2px;display:inline-block}
.lg b{width:11px;height:11px;border-radius:2px;display:inline-block}
.stack{display:flex;height:22px;border-radius:6px;overflow:hidden;background:#eef1f4;
margin:6px 0 8px}
.stack span{display:block;height:100%}
/* Label, command and button are grid items, not inline text, so the three line
   up in columns however long an individual label or command is. */
.cmds{margin-top:26px;display:grid;grid-template-columns:auto auto auto;
justify-content:start;align-items:center;gap:7px 10px}
.cmd{display:contents;font-size:.85em;color:#5a6570}
.cmd code{background:#dedede;padding:3px 7px;border-radius:5px;word-break:break-all}
.copy{font:inherit;color:#5a6570;background:none;border:1px solid #cfd8e0;
border-radius:5px;padding:1.5px 10px;cursor:pointer}
.copy:hover{background:#dedede}
"""

_STALE_JS = """
(function(){
  var el=document.getElementById('stale');
  if(!el)return;
  var gen=new Date(el.dataset.generated).getTime();
  var age=(Date.now()-gen)/60000;
  if(age>%(minutes)d){
    el.textContent='This page was generated '+Math.round(age)+' minutes ago and may be out of date.';
    el.style.display='block';
  }
})();
(function(){
  var el=document.getElementById('next'),st=document.getElementById('stale');
  if(!el||!st)return;
  var step=%(refresh)d*60000,grace=20000,now=Date.now();
  var gen=new Date(st.dataset.generated).getTime();
  var due=Math.floor(gen/step)*step+step;
  var overdue=now>due+grace;
  var reloadAt=overdue?(now-due<step?now+60000:Math.ceil(now/step)*step+grace):due+grace;
  var reloading=false;
  function pad(n){return (n<10?'0':'')+n;}
  function hm(t){var d=new Date(t);return pad(d.getHours())+':'+pad(d.getMinutes());}
  function tick(){
    var now=Date.now(),left=Math.max(0,Math.round((due-now)/1000)),m=Math.floor(left/60);
    if(now<due)el.textContent=' \u00b7 next refresh at '+hm(due)+' (in '+m+':'+pad(left-60*m)+')';
    else if(overdue)el.textContent=' \u00b7 refresh overdue, retrying at '+hm(reloadAt);
    else el.textContent=' \u00b7 refreshing\u2026';
    if(now>=reloadAt&&!reloading){reloading=true;location.reload();}
  }
  tick();setInterval(tick,1000);
})();
(function(){
  document.querySelectorAll('.copy').forEach(function(b){
    b.addEventListener('click',function(){
      navigator.clipboard.writeText(b.dataset.cmd).then(function(){
        b.textContent='copied';
        setTimeout(function(){b.textContent='copy';},1200);
      });
    });
  });
})();
"""


def _esc(value):
    return html.escape(str(value)) if value is not None else ""


def _name(selection):
    """The job's name: the submit file it was submitted with, without the
    extension, e.g. sherpa-01.jdf -> sherpa-01.
    """
    if selection.submit_file:
        return os.path.splitext(os.path.basename(selection.submit_file.strip()))[0]
    if selection.submit_dir:
        return os.path.basename(selection.submit_dir.rstrip("/"))
    return "unknown"


def _icon_html(icon, prefix=""):
    """Render an icon that is either an emoji or an image file in ICON_DIR."""
    if not icon:
        return ""
    if icon.lower().endswith(ICON_SUFFIXES):
        return f'<img class="kicon" src="{prefix}{ICON_DIR}/{_esc(icon)}" alt="">'
    return _esc(icon)


def _badge(selection, prefix=""):
    """A small pill naming the job type, e.g. Sherpa-logo for Sherpa."""
    icon, label = job_kind(selection.cmdline, selection.submit_file)
    if not label:
        return ""
    rendered = _icon_html(icon, prefix)
    return f'<span class="kind">{rendered}{" " if rendered else ""}{_esc(label)}</span>'


COUNTERS = [("done", "idle"), ("ok", "run"), ("timeout", "warn"),
            ("removed", "warn"), ("failed", "bad"), ("restarted", "warn")]


def _count(value, css):
    """A count as a coloured pill. Zero stays neutral grey whatever the column,
    so an empty failure column does not read as an alarm from across the room.
    """
    return f"<span class='pill {css if value else 'zero'}'>{value}</span>"


def _counts(summary):
    """Every counter as a labelled pill, for use outside a table column."""
    return " &middot; ".join(f"{_count(getattr(summary, field), css)} {field}"
                             for field, css in COUNTERS)


def _table(rows):
    """A table, in the scroll box that keeps a wide one off the rest of the page."""
    return '<div class="scroll sheet"><table>' + "".join(rows) + "</table></div>"


def _command(label, command):
    """One click-to-copy command row: three grid items the .cmds grid aligns
    into columns. The label needs its own element to be one of them.
    """
    return (f'<p class="cmd"><span>{_esc(label)}</span>'
            f"<code>{_esc(command)}</code>"
            f'<button class="copy" data-cmd="{_esc(command)}">copy</button></p>')


def _when(moment):
    return moment.astimezone().strftime("%Y-%m-%d %H:%M") if moment else "unknown"


def _page(title, body, generated_at):
    return (
        "<!DOCTYPE html>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{_esc(title)}</title>\n<style>{_CSS}</style>\n"
        f'<div class="wrap">\n'
        f'<div id="stale" data-generated="{generated_at.isoformat()}"></div>\n'
        f"{body}\n\n"
        f'<p class="sub">Generated {_when(generated_at)}</p>\n'
        f"</div>\n"
        f"<script>{_STALE_JS % {'minutes': STALE_MINUTES, 'refresh': REFRESH_MINUTES}}"
        "</script>\n"
    )


# ------------------------------------------------------------- load history

DAY_BIN_MINUTES = 15
DAY_BINS = 100     # 15 minutes each: the last 24 hours, plus the hour ahead
TOD_BINS = 24 * 60 // DAY_BIN_MINUTES   # time-of-day bins backing the average
WEEK_DAYS = 8      # the last 7 days, plus tomorrow
WEEK_BINS = WEEK_DAYS * 24   # one per hour


def parse_sample(text):
    """Parse the #SAMPLE section into (epoch, total, mine), or None."""
    for line in text.splitlines():
        fields = line.strip().split("\t")
        if len(fields) == 3 and all(f.isdigit() for f in fields):
            return tuple(int(f) for f in fields)
    return None


def load_history(path=HISTORY_FILE):
    """Read every recorded sample. Malformed lines are skipped, never fatal."""
    rows = []
    try:
        with open(path) as fh:
            for line in fh:
                fields = line.strip().split(",")
                if len(fields) != 3:
                    continue
                try:
                    rows.append((int(fields[0]), int(fields[1]), int(fields[2])))
                except ValueError:
                    continue
    except OSError:
        return []
    return rows


def update_history(sample, path=HISTORY_FILE):
    """Record `sample` and return the full series, pruned to HISTORY_DAYS."""
    rows = load_history(path)
    if sample is None:
        return rows
    rows.append(sample)
    cutoff = sample[0] - HISTORY_DAYS * 86400
    kept = [r for r in rows if r[0] >= cutoff]
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if len(kept) != len(rows):
            atomic_write(path, "".join("%d,%d,%d\n" % r for r in kept))
        else:
            with open(path, "a") as fh:
                fh.write("%d,%d,%d\n" % sample)
    except OSError:
        pass
    return kept


def _bin_averages(buckets):
    """Mean per bin, or None for a bin nothing landed in (drawn as a gap)."""
    return [round(sum(b) / len(b), 1) if b else None for b in buckets]


def _local(epoch):
    """Samples are binned by local wall-clock time, which is what a reader means
    by '14:00' or 'Tuesday'."""
    return datetime.fromtimestamp(epoch)


def day_window_start(now):
    """The first bin edge of the daily chart: 24 hours before the bin `now`
    falls in, so the whole axis slides forward with the clock."""
    edge = _local(now.timestamp()).replace(second=0, microsecond=0)
    edge -= timedelta(minutes=edge.minute % DAY_BIN_MINUTES)
    return edge - timedelta(hours=24)


def day_bin_starts(now):
    """Wall-clock start of every bin on the daily axis."""
    start = day_window_start(now)
    return [start + timedelta(minutes=DAY_BIN_MINUTES * i)
            for i in range(DAY_BINS)]


def _tod_index(stamp):
    """Which time-of-day bin a wall-clock moment belongs to."""
    return (stamp.hour * 60 + stamp.minute) // DAY_BIN_MINUTES


def daily_series(rows, now):
    """(mine, total, average) over 15-minute bins spanning the last 24 hours
    plus the hour ahead.
    """
    starts = day_bin_starts(now)
    window_start = starts[0]
    window_end = starts[-1] + timedelta(minutes=DAY_BIN_MINUTES)
    cur_mine = [[] for _ in range(DAY_BINS)]
    cur_total = [[] for _ in range(DAY_BINS)]
    past_total = [[] for _ in range(TOD_BINS)]
    for epoch, total, mine in rows:
        stamp = _local(epoch)
        if window_start <= stamp < window_end:
            offset = (stamp - window_start).total_seconds()
            index = int(offset) // (DAY_BIN_MINUTES * 60)
            cur_mine[index].append(mine)
            cur_total[index].append(total)
        else:
            past_total[_tod_index(stamp)].append(total)
    average = _bin_averages(past_total)
    return (_bin_averages(cur_mine), _bin_averages(cur_total),
            [average[_tod_index(start)] for start in starts])


def week_bin_dates(now):
    """The days on the weekly axis: the last seven, then tomorrow."""
    start = _local(now.timestamp()).date() - timedelta(days=WEEK_DAYS - 2)
    return [start + timedelta(days=index) for index in range(WEEK_DAYS)]


def weekly_series(rows, now):
    """(mine, total, average) over hourly bins spanning the last 7 days, plus
    tomorrow.
    """
    dates = week_bin_dates(now)
    cur_mine = [[] for _ in range(WEEK_BINS)]
    cur_total = [[] for _ in range(WEEK_BINS)]
    past_total = [[] for _ in range(7 * 24)]
    for epoch, total, mine in rows:
        stamp = _local(epoch)
        day = (stamp.date() - dates[0]).days
        if 0 <= day < WEEK_DAYS:
            cur_mine[day * 24 + stamp.hour].append(mine)
            cur_total[day * 24 + stamp.hour].append(total)
        else:
            past_total[stamp.weekday() * 24 + stamp.hour].append(total)
    average = _bin_averages(past_total)
    return (_bin_averages(cur_mine), _bin_averages(cur_total),
            [average[date.weekday() * 24 + hour]
             for date in dates for hour in range(24)])


# ------------------------------------------------------------- load charts

_PLOT_W, _PLOT_H = 1040, 210
_PLOT_L, _PLOT_R, _PLOT_T, _PLOT_B = 46, 12, 12, 30

MINE_COLOUR = "#1565c0"
TOTAL_COLOUR = "#EE3333"
AVG_COLOUR = "#F2A2A2"


def _nice_max(values):
    """A round y-axis maximum comfortably above the data."""
    peak = max([v for v in values if v is not None] or [0])
    if peak <= 0:
        return 1
    step = 10 ** (len(str(int(peak))) - 1)
    return int(step * (int(peak / step) + 1))


def _series_svg(values, colour, dashed, x_of, y_of):
    """One series, broken into segments wherever bins have no data.

    A lone sample surrounded by gaps has no line to draw, so it gets a dot --
    otherwise the very first refresh of the day would render nothing at all.
    """
    out, run = [], []
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    for index, value in enumerate(values):
        if value is None:
            if run:
                out.append(run)
                run = []
        else:
            run.append((x_of(index), y_of(value)))
    if run:
        out.append(run)

    pieces = []
    for segment in out:
        if len(segment) == 1:
            x, y = segment[0]
            pieces.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="{colour}"/>')
        else:
            points = " ".join(f"{x:.1f},{y:.1f}" for x, y in segment)
            pieces.append(f'<polyline points="{points}" fill="none" stroke="{colour}" '
                          f'stroke-width="2" stroke-linejoin="round" '
                          f'stroke-linecap="round"{dash}/>')
    return "".join(pieces)


def render_chart(series, x_labels):
    """A small multi-line SVG chart.

    series is [(name, colour, dashed, values)]; every values list must be the
    same length, one entry per bin, None where there is no data.
    """
    bins = len(series[0][3])
    plot_w = _PLOT_W - _PLOT_L - _PLOT_R
    plot_h = _PLOT_H - _PLOT_T - _PLOT_B
    top = _nice_max([v for _, _, _, values in series for v in values])

    step = plot_w / bins
    def x_of(index):
        return _PLOT_L + (index + 0.5) * step
    def y_of(value):
        return _PLOT_T + plot_h - (value / top) * plot_h

    parts = [f'<svg class="chart" style="min-width:{_PLOT_W}px" '
             f'viewBox="0 0 {_PLOT_W} {_PLOT_H}" '
             f'role="img" preserveAspectRatio="none">']

    # horizontal grid + y labels
    for fraction in (0, 0.5, 1):
        y = _PLOT_T + plot_h - fraction * plot_h
        parts.append(f'<line x1="{_PLOT_L}" y1="{y:.1f}" x2="{_PLOT_W - _PLOT_R}" '
                     f'y2="{y:.1f}" stroke="#e1e6ea" stroke-width="1"/>')
        parts.append(f'<text x="{_PLOT_L - 8}" y="{y + 4:.1f}" text-anchor="end" '
                     f'font-size="11" fill="#8a949e">{int(top * fraction)}</text>')

    # x labels
    for index, label in enumerate(x_labels):
        if not label:
            continue
        parts.append(f'<text x="{x_of(index):.1f}" y="{_PLOT_H - 10}" '
                     f'text-anchor="middle" font-size="11" fill="#8a949e">'
                     f'{_esc(label)}</text>')

    for _, colour, dashed, values in series:
        parts.append(_series_svg(values, colour, dashed, x_of, y_of))

    parts.append("</svg>")
    legend = "".join(
        f'<span class="lg"><i style="background:{colour}'
        f'{";opacity:.55" if dashed else ""}"></i>{_esc(name)}</span>'
        for name, colour, dashed, _ in series)
    return (f'<div class="scroll">{"".join(parts)}</div>'
            f'<div class="legend">{legend}</div>')


def render_load_charts(history, now):
    """The two load charts, or a placeholder until samples exist."""
    if not history:
        return ('<h2>Cluster load</h2>'
                '<p class="none">No samples recorded yet &mdash; the charts appear '
                'after the first refresh.</p>')

    mine_day, total_day, avg_day = daily_series(history, now)
    mine_week, total_week, avg_week = weekly_series(history, now)

    starts = day_bin_starts(now)
    hours = [start.strftime("%H:00")
             if start.minute == 0 and start.hour % 2 == 0 else ""
             for start in starts]
    dates = week_bin_dates(now)
    days = [date.strftime("%a %d") if hour == 0 else ""
            for date in dates for hour in range(24)]

    day_end = starts[-1] + timedelta(minutes=DAY_BIN_MINUTES)
    day_note = (f"{_esc(starts[0].strftime('%a %d %b %H:%M'))} &ndash; "
                f"{_esc(day_end.strftime('%a %d %b %H:%M'))}")
    week_note = (f"{_esc(dates[0].strftime('%a %d %b'))} &ndash; "
                 f"{_esc(dates[-1].strftime('%a %d %b'))}")

    return "".join([
        "<h2>Cluster load</h2>",
        f'<p class="sub">Running jobs over the last 24 hours: {day_note}, '
        "15 minute bins. The average covers that time of day on every earlier "
        "day on record."
        "ahead.</p>",
        '<div class="card">',
        render_chart([("you", MINE_COLOUR, False, mine_day),
                      ("all users", TOTAL_COLOUR, False, total_day),
                      ("all users (average)", AVG_COLOUR, True, avg_day)],
                     hours),
        "</div>",
        f'<p class="sub">Running jobs over the last 7 days: {week_note}, '
        "hourly means. The average covers that weekday and hour on every earlier "
        "day on record.</p>",
        '<div class="card">',
        render_chart([("you", MINE_COLOUR, False, mine_week),
                      ("all users", TOTAL_COLOUR, False, total_week),
                      ("all users (average)", AVG_COLOUR, True, avg_week)],
                     days),
        "</div>",
    ])


# ------------------------------------------------------------- runtime plots

STATUS_ORDER = ["COMPLETE", "FAILED", "TIMEOUT", "REMOVED"]
STATUS_COLOURS = {"COMPLETE": "#1b7a43", "FAILED": "#b3261e",
                  "TIMEOUT": "#9a5b00", "REMOVED": "#d9a24a"}
WAIT_COLOUR = "#aeb6be"
HIST_BINS = 40
BAR_GAP = 0.15
BAR_RADIUS = 3
_TIME_STEPS = [60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200,
               86400, 172800, 345600, 604800]
_PERCENT_STEPS = [25, 50, 100, 200, 500]


def _hm(seconds):
    """A duration as h:mm, for axis labels."""
    seconds = int(round(seconds))
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}"


def _hms(seconds):
    """A duration as h:mm:ss, for tables."""
    seconds = int(round(seconds))
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def _ticks(xmax, steps, label, fallback):
    """(value, label) axis ticks at the smallest round step in `steps` that
    keeps them to eight or fewer, else at a multiple of `fallback`."""
    step = next((s for s in steps if xmax / s <= 8), None)
    if step is None:
        step = fallback * math.ceil(xmax / (8 * fallback))
    return [(v, label(v)) for v in range(0, int(xmax) + 1, step)]


def _basis(n, total):
    """The 'based on N of M jobs' note, empty when every job counted."""
    return f" Based on {n} of {total} jobs." if n < total else ""


def _mean_std(values):
    """(N, mean, sample standard deviation); std is None below two values."""
    n = len(values)
    if n == 0:
        return 0, None, None
    mean = sum(values) / n
    if n < 2:
        return n, mean, None
    return n, mean, math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


def _mode(values):
    """The most common value, the largest winning a tie."""
    return max(set(values), key=lambda v: (values.count(v), v))


def _histogram(values, xmax, bins):
    """Per-status counts over `bins` equal bins spanning [0, xmax], from
    [(x, status)]. A value at xmax itself lands in the last bin."""
    counts = {status: [0] * bins for status in STATUS_ORDER}
    for x, status in values:
        counts[status][min(max(int(x / xmax * bins), 0), bins - 1)] += 1
    return counts


def _svg_open():
    return (f'<svg class="chart" style="min-width:{_PLOT_W}px" '
            f'viewBox="0 0 {_PLOT_W} {_PLOT_H}" role="img" preserveAspectRatio="none">')


def _x_axis(ticks, x_of):
    """Tick labels along the bottom edge; one at the right margin hugs it."""
    parts = []
    for value, label in ticks:
        x = x_of(value)
        anchor = "end" if x > _PLOT_W - _PLOT_R - 14 else "middle"
        parts.append(f'<text x="{x:.1f}" y="{_PLOT_H - 10}" text-anchor="{anchor}" '
                     f'font-size="11" fill="#8a949e">{_esc(label)}</text>')
    return "".join(parts)


def _y_axis(labels):
    """Three horizontal grid lines with their labels, bottom to top."""
    plot_h = _PLOT_H - _PLOT_T - _PLOT_B
    parts = []
    for fraction, label in zip((0, 0.5, 1), labels):
        y = _PLOT_T + plot_h - fraction * plot_h
        parts.append(f'<line x1="{_PLOT_L}" y1="{y:.1f}" x2="{_PLOT_W - _PLOT_R}" '
                     f'y2="{y:.1f}" stroke="#e1e6ea" stroke-width="1"/>')
        parts.append(f'<text x="{_PLOT_L - 8}" y="{y + 4:.1f}" text-anchor="end" '
                     f'font-size="11" fill="#8a949e">{_esc(label)}</text>')
    return "".join(parts)


def _marker(x, label):
    """A labelled dashed vertical line, for the wall time limit."""
    return (f'<line x1="{x:.1f}" y1="{_PLOT_T}" x2="{x:.1f}" y2="{_PLOT_H - _PLOT_B}" '
            f'stroke="#8a949e" stroke-width="1.2" stroke-dasharray="5 4"/>'
            f'<text x="{x - 5:.1f}" y="{_PLOT_T + 11}" text-anchor="end" '
            f'font-size="11" fill="#8a949e" paint-order="stroke" stroke="#fff" '
            f'stroke-width="3">{_esc(label)}</text>')


def _status_legend(counts):
    """A colour square and job count per status present."""
    return '<div class="legend">' + "".join(
        f'<span class="lg"><b style="background:{STATUS_COLOURS[s]}"></b>{s} ({n})</span>'
        for s, n in counts.items() if n) + "</div>"


def _rounded_top(x, y, w, h, radius):
    """Path for a rectangle whose top two corners are rounded."""
    r = min(radius, w / 2, h)
    return (f"M{x:.1f},{y + h:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}"
            f"H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}"
            f"V{y + h:.1f}Z")


def render_histogram(counts, xmax, ticks, marker=None, fmt=str):
    """A stacked-bar SVG histogram in the style of render_chart."""
    bins = len(next(iter(counts.values())))
    plot_w = _PLOT_W - _PLOT_L - _PLOT_R
    plot_h = _PLOT_H - _PLOT_T - _PLOT_B
    totals = [sum(counts[s][i] for s in counts) for i in range(bins)]
    top = _nice_max(totals)
    top += top % 2
    def x_of(value):
        return _PLOT_L + value / xmax * plot_w
    def y_of(value):
        return _PLOT_T + plot_h - value / top * plot_h

    parts = [_svg_open(), _y_axis([str(int(top * f)) for f in (0, 0.5, 1)]),
             _x_axis(ticks, x_of)]
    slot = plot_w / bins
    width = max(slot * (1 - BAR_GAP), 1)
    for index in range(bins):
        if not totals[index]:
            continue
        lo, hi = index * xmax / bins, (index + 1) * xmax / bins
        title = f"{fmt(lo)} \u2013 {fmt(hi)}: " + ", ".join(
            f"{counts[s][index]} {s}" for s in STATUS_ORDER if counts[s][index])
        parts.append(f"<g><title>{_esc(title)}</title>")
        x = x_of(lo) + (slot - width) / 2
        stack = [(s, counts[s][index]) for s in STATUS_ORDER if counts[s][index]]
        running = 0
        for position, (status, count) in enumerate(stack):
            y_top, y_bottom = y_of(running + count), y_of(running)
            if position == len(stack) - 1:
                shape = (f'<path d="'
                         f'{_rounded_top(x, y_top, width, y_bottom - y_top, BAR_RADIUS)}"')
            else:
                shape = (f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{width:.1f}" '
                         f'height="{y_bottom - y_top:.1f}"')
            parts.append(f'{shape} fill="{STATUS_COLOURS[status]}"/>')
            running += count
        parts.append("</g>")
    if marker:
        parts.append(_marker(x_of(marker[0]), marker[1]))
    parts.append("</svg>")
    return f'<div class="scroll">{"".join(parts)}</div>'


def render_time_split(waiting, completed, lost):
    """One stacked bar of the cluster's total time, in three segments."""
    segments = [("waiting in queue", waiting, WAIT_COLOUR),
                ("running, completed", completed, STATUS_COLOURS["COMPLETE"]),
                ("running, lost", lost, STATUS_COLOURS["TIMEOUT"])]
    total = sum(value for _, value, _ in segments) or 1
    bar = "".join(
        f'<span style="width:{100 * value / total:.2f}%;background:{colour}" '
        f'title="{_esc(name)}: {value / 3600:.1f} h"></span>'
        for name, value, colour in segments if value > 0)
    legend = "".join(
        f'<span class="lg"><b style="background:{colour}"></b>{_esc(name)}: '
        f"{value / 3600:.1f} h ({100 * value / total:.0f}%)</span>"
        for name, value, colour in segments)
    return (f'<div class="stack">{bar}</div><div class="legend">{legend}</div>'
            '<div class="legend">A restarted job&rsquo;s waiting time includes its '
            "earlier attempts.</div>")


def render_runtime_stats(timings):
    """N, mean and sample standard deviation of every timing quantity."""
    def present(values):
        return [v for v in values if v is not None]
    rows = [
        ("Runtime, all jobs", present(t.totaltime for t in timings), _hms),
        ("Runtime, COMPLETE jobs only",
         present(t.totaltime for t in timings if t.status == "COMPLETE"), _hms),
        ("CPU time", present(t.cputime for t in timings), _hms),
        ("CPU efficiency", present(t.efficiency for t in timings),
         lambda v: f"{100 * v:.1f}%"),
        ("Wait in queue", present(t.waittime for t in timings), _hms),
    ]
    out = ["<tr><th></th><th class='num'>N</th><th class='num'>Mean</th>"
           "<th class='num'>Std</th></tr>"]
    for label, values, fmt in rows:
        n, mean, std = _mean_std(values)
        out.append(f"<tr><td>{_esc(label)}</td><td class='num'>{n}</td>"
                   f"<td class='num'>{fmt(mean) if mean is not None else '&ndash;'}</td>"
                   f"<td class='num'>{fmt(std) if std is not None else '&ndash;'}</td></tr>")
    return _table(out)


def render_runtime(summary):
    """The Runtime section of a cluster page, or "" when no job reported timing."""
    timings = summary.timings
    if not timings:
        return ""
    total = summary.done
    parts = ["<h2>Runtime</h2>"]

    limits = [t.wall_limit for t in timings if t.wall_limit is not None]
    limit = _mode(limits) if limits else None
    timed = [t for t in timings if t.totaltime is not None]
    if timed:
        xmax = max(max(t.totaltime for t in timed), limit or 0, 1)
        ticks = _ticks(xmax, _TIME_STEPS, _hm, 86400)
        marker = (limit, f"limit {_hm(limit)}") if limit else None
        counts = _histogram([(t.totaltime, t.status) for t in timed], xmax, HIST_BINS)
        parts += [
            '<p class="sub">Runtime of every finished job (h:mm), stacked by final '
            "status. The dashed line is the wall time limit."
            f"{_basis(len(timed), total)}</p>",
            '<div class="card">',
            render_histogram(counts, xmax, ticks, marker, _hm),
            _status_legend({s: sum(counts[s]) for s in STATUS_ORDER}),
            "</div>",
        ]

    waited = [t for t in timings if t.waittime is not None and t.totaltime is not None]
    if waited:
        parts += [
            '<p class="sub">Where the time went, summed over jobs: waiting in the '
            "queue, running to completion, and running without completing."
            f"{_basis(len(waited), total)}</p>",
            '<div class="card">',
            render_time_split(sum(max(t.waittime, 0) for t in waited),
                              sum(t.totaltime for t in waited if t.status == "COMPLETE"),
                              sum(t.totaltime for t in waited if t.status != "COMPLETE")),
            "</div>",
        ]

    efficient = [(100 * t.efficiency, t.status) for t in timings
                 if t.efficiency is not None]
    if efficient:
        emax = max(100, 5 * math.ceil(max(e for e, _ in efficient) / 5))
        counts = _histogram(efficient, emax, emax // 5)
        parts += [
            '<p class="sub">CPU efficiency per job: CPU time over runtime &times; '
            "requested cores, in 5% bins. Above 100% a job used more cores than it "
            f"requested.{_basis(len(efficient), total)}</p>",
            '<div class="card">',
            render_histogram(counts, emax, _ticks(emax, _PERCENT_STEPS, "{}%".format, 100),
                             (100, "100%") if emax > 100 else None, "{:.0f}%".format),
            _status_legend({s: sum(counts[s]) for s in STATUS_ORDER}),
            "</div>",
        ]

    parts += [
        '<p class="sub">Mean and sample standard deviation. The mean runtime ignores '
        "the jobs that were cut off, so it is too low when jobs time out.</p>",
        render_runtime_stats(timings),
    ]
    return "\n".join(parts)


def render_index(selections, summaries, generated_at, queue_ok=True, history=None):
    """Render the dashboard index."""
    running = [s for s in selections if s.queue and s.queue.total > 0]
    finished = [s for s in selections if not (s.queue and s.queue.total > 0)]

    parts = ["<h1>HTCondor jobs overview</h1>",
             f'<p class="sub">{_esc(USERNAME)} on {_esc(SSH_HOST)}'
             f' &middot; Generated {_when(generated_at)}<span id="next"></span></p>\n']

    parts.append("<h2>Running now</h2>")
    if not queue_ok:
        parts.append('<div class="banner">queue unreachable &mdash; could not reach rocks. '
                     "Counts below are from the last successful update.</div>")
    elif not running:
        parts.append('<p class="none">No jobs running.</p>')
    else:
        totals = [sum(s.queue.running for s in running),
                  sum(s.queue.idle for s in running),
                  sum(s.queue.held for s in running)]
        parts.append(f'<p class="sub">{totals[0]} running, {totals[1]} idle, {totals[2]} held '
                     f"across {len(running)} cluster(s).</p>")
        rows = ["<tr><th>Cluster</th><th>Name</th><th class='num'>Running</th>"
                "<th class='num'>Idle</th><th class='num'>Held</th><th>Directory</th></tr>"]
        for sel in running:
            pct = 100 * sel.queue.running // sel.queue.total if sel.queue.total else 0
            name = _esc(_name(sel))
            if sel.cluster in summaries:
                name = f"<a href='{CLUSTER_DIR}/{_esc(sel.cluster)}.html'>{name}</a>"
            rows.append(
                f"<tr><td>{_esc(sel.cluster)}</td>"
                f"<td>{name}{_badge(sel)}"
                f"<div class='bar'><span style='width:{pct}%'></span></div></td>"
                f"<td class='num'><span class='pill run'>{sel.queue.running}</span></td>"
                f"<td class='num'><span class='pill idle'>{sel.queue.idle}</span></td>"
                f"<td class='num'>{sel.queue.held or ''}</td>"
                f"<td class='path'>{_esc(sel.submit_dir)}</td></tr>"
            )
            progress = summaries.get(sel.cluster)
            if progress and progress.done:
                rows.append("<tr class='more'><td></td>"
                            f"<td colspan='5'>so far {_counts(progress)}</td></tr>")
        parts.append(_table(rows))

    heading = "Finished" if queue_ok else "Recent"
    parts.append(f"<h2>{heading} (last {RETENTION_DAYS} days)</h2>")
    if not finished:
        parts.append('<p class="none">Nothing finished in the last '
                     f"{RETENTION_DAYS} days.</p>")
    else:
        entry = "entry" if len(finished) == 1 else "entries"
        parts.append(f'<p class="sub">{len(finished)} {entry} in the history.</p>')
        rows = ["<tr><th>Cluster</th><th>Name</th><th class='num'>Done</th>"
                "<th class='num'>OK</th><th class='num'>Timeout</th>"
                "<th class='num'>Removed</th><th class='num'>Failed</th>"
                "<th class='num'>Restarted</th>"
                "<th>Submitted</th><th>Directory</th></tr>"]
        for sel in finished:
            summary = summaries.get(sel.cluster)
            name = _esc(_name(sel))
            badge = _badge(sel)
            if summary is None:
                cells = (f"<td>{name}{badge}</td>"
                         f"<td colspan='{len(COUNTERS)}' class='none'>no overview file</td>")
            else:
                link = (f"<a href='{CLUSTER_DIR}/{_esc(sel.cluster)}.html'>{name}</a>"
                        f"{badge}")
                counts = "".join(
                    f"<td class='num'>{_count(getattr(summary, field), css)}</td>"
                    for field, css in COUNTERS
                )
                cells = f"<td>{link}</td>{counts}"
            rows.append(f"<tr><td>{_esc(sel.cluster)}</td>{cells}"
                        f"<td>{_when(sel.timestamp)}</td>"
                        f"<td class='path'>{_esc(sel.submit_dir)}</td></tr>")
        parts.append(_table(rows))

    parts.append(
        '<div class="cmds">'
        + _command("Update this dashboard now", REFRESH_COMMAND)
        + _command("Remove an entry from the dashboard", FORGET_GENERIC_COMMAND)
        + _command(f"Empty the whole {RETENTION_DAYS} day history", FORGET_ALL_COMMAND)
        + "</div>"
    )

    parts.append(render_load_charts(history or [], generated_at))

    return _page("HTCondor jobs overview", "\n".join(parts), generated_at)


def render_cluster(selection, summary, log_name, generated_at):
    """Render the per-cluster detail page: counts plus the problem entries."""
    parts = [
        '<a class="back" href="../index.html">&larr; all clusters</a>',
        f"<h1>Cluster {_esc(selection.cluster)}</h1>",
        f'<p class="sub">{_esc(_name(selection))}{_badge(selection, "../")} &middot; '
        f"submitted {_when(selection.timestamp)}</p>",
        f'<p class="path">{_esc(selection.submit_dir)}</p>',
        '<p class="sub">' + _counts(summary)
        + (f" &middot; <span class='pill idle'>{summary.unparsed}</span> unparsed" if summary.unparsed else "")
        + f' &middot; <a href="{_esc(log_name)}">raw {_esc(log_name)}</a></p>',
    ]

    parts.append(render_runtime(summary))

    if not summary.problems:
        parts.append("<h2>Problems</h2>")
        parts.append('<p class="none">No failures or timeouts.</p>')
    else:
        parts.append(f"<h2>Problems ({len(summary.problems)})</h2>")
        timed = any(e.totaltime is not None for e in summary.problems)
        hosted = any(e.host for e in summary.problems)
        rows = ["<tr><th>Job</th><th>Status</th><th class='num'>Events</th>"
                + ("<th class='num'>Runtime</th>" if timed else "")
                + "<th>Detail</th>" + ("<th>Host</th>" if hosted else "")
                + "<th>Directory</th></tr>"]
        for entry in summary.problems:
            css = "bad" if entry.status == "FAILED" else "warn"
            if entry.status == "TIMEOUT":
                detail = f"wall limit {_esc(entry.detail)}s"
            elif entry.status == "FAILED" and entry.detail:
                detail = f"exit {_esc(entry.detail)}"
            else:
                detail = ""
            if entry.copyfail:
                detail += f'<div class="path">copy failed: {_esc(entry.copyfail)}</div>'
            if entry.seed:
                detail += f'<div class="path">seed {_esc(entry.seed)}</div>'
            runtime = _hms(entry.totaltime) if entry.totaltime is not None else ""
            rows.append(
                f"<tr><td>{_esc(entry.cluster)}.{_esc(entry.proc)}</td>"
                f"<td><span class='pill {css}'>{_esc(entry.status)}</span></td>"
                f"<td class='num'>{_esc(entry.events)}</td>"
                + (f"<td class='num'>{runtime}</td>" if timed else "")
                + f"<td>{detail}</td>"
                + (f"<td>{_esc(entry.host)}</td>" if hosted else "")
                + f"<td class='path'>{_esc(entry.dir)}</td></tr>"
            )
        parts.append(_table(rows))
        if hosted:
            by_host = {}
            for entry in summary.problems:
                if entry.host and not entry.copyfail:
                    by_host[entry.host] = by_host.get(entry.host, 0) + 1
            ranked = sorted(by_host.items(), key=lambda item: (-item[1], item[0]))
            if by_host:
                parts.append('<p class="sub">By host: ' + ", ".join(
                    f"{_esc(host)} &times;{n}" for host, n in ranked[:10])
                    + (f", and {len(ranked) - 10} more" if len(ranked) > 10 else "")
                    + "</p>")

    forget = FORGET_COMMAND.format(cluster=selection.cluster)
    parts.append('<div class="cmds">'
                 + _command("Remove this cluster from the dashboard", forget)
                 + "</div>")

    return _page(f"Cluster {selection.cluster}", "\n".join(parts), generated_at)


def build_pages(selections, summaries, raw_logs, generated_at, queue_ok=True,
                history=None):
    """Produce {filename: content} for everything that should be written."""
    pages = {"index.html": render_index(selections, summaries, generated_at, queue_ok,
                                        history)}
    for sel in selections:
        summary = summaries.get(sel.cluster)
        if summary is None:
            continue
        log_name = f"overview.{sel.cluster}.log"
        pages[f"{CLUSTER_DIR}/{sel.cluster}.html"] = render_cluster(
            sel, summary, log_name, generated_at)
        if sel.cluster in raw_logs:
            pages[f"{CLUSTER_DIR}/{log_name}"] = raw_logs[sel.cluster]
    return pages


# ---------------------------------------------------------------- output

_GENERATED = re.compile(r"^(index\.html|\d+\.html|overview\.\d+\.log)$")


def atomic_write(path, content):
    """Write via a temp file and rename, so a reader never sees a partial page."""
    directory = os.path.dirname(path) or "."
    if not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
        os.chmod(directory, 0o755)
    handle, temp = tempfile.mkstemp(dir=directory, prefix=".tmp-")
    try:
        with os.fdopen(handle, "w") as fh:
            fh.write(content)
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def prune(directory, keep):
    """Delete generated files no longer wanted. Leaves unrelated files alone."""
    for sub in ("", CLUSTER_DIR):
        folder = os.path.join(directory, sub)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if _GENERATED.match(name) and os.path.join(sub, name) not in keep:
                try:
                    os.unlink(os.path.join(folder, name))
                except OSError:
                    pass


# ---------------------------------------------------------------- remote access

_INVENTORY_SCRIPT = r"""
set -u
REG="%(registry)s"
echo "#QUEUE"
Q=$(condor_q -af:t ClusterId ProcId JobStatus Iwd Args Cmd 2>/dev/null || true)
if [ -n "$Q" ]; then printf '%%s\n' "$Q"; fi
echo "#REGISTRY"
R=$(cat "$REG" 2>/dev/null || true)
if [ -n "$R" ]; then printf '%%s\n' "$R"; fi
echo "#SAMPLE"
printf '%%s\t%%s\t%%s\n' "$(date +%%s)" \
  "$(condor_q -all -constraint 'JobStatus==2' -af ClusterId 2>/dev/null | wc -l)" \
  "$(condor_q      -constraint 'JobStatus==2' -af ClusterId 2>/dev/null | wc -l)"
echo "#LOGS"
{
  if [ -n "$R" ]; then
    printf '%%s\n' "$R" | awk -F'\t' 'NF>=2 && $1 ~ /^[0-9]+$/ {print $1"\t"$2}'
  fi
  if [ -n "$Q" ]; then
    printf '%%s\n' "$Q" | awk -F'\t' 'NF>=4 && $1 ~ /^[0-9]+$/ {print $1"\t"$4}'
  fi
} | sort -u | while IFS=$'\t' read -r cid dir; do
  [ -n "${cid:-}" ] || continue
  f="$dir/condor_output/overview.$cid.log"
  if [ ! -f "$f" ]; then
    f=$(ls "$dir"/condor_output/*/overview."$cid".log 2>/dev/null | head -n1)
  fi
  if [ -n "${f:-}" ] && [ -f "$f" ]; then printf '%%s\t%%s\t%%s\n' "$cid" "$(stat -c %%Y "$f")" "$f"; fi
done
echo "#END"
"""


def inventory_script():
    """The one-round-trip inventory fetch, with its paths filled in.

    A function rather than a formatted constant so adding a path cannot leave a
    caller behind with a KeyError.
    """
    return _INVENTORY_SCRIPT % {"registry": REGISTRY_PATH}


def run_remote(script, host=SSH_HOST, timeout=SSH_TIMEOUT):
    """Run a bash script on the cluster. Returns (ok, stdout)."""
    try:
        done = subprocess.run(
            ["ssh", *SSH_OPTS, host, "bash", "-s"],
            input=script, capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False, ""
    if done.returncode != 0:
        return False, done.stdout
    return True, done.stdout


def _section(text, name):
    """Extract one #SECTION block from the inventory output."""
    lines = text.splitlines()
    try:
        start = lines.index("#" + name) + 1
    except ValueError:
        return ""
    out = []
    for line in lines[start:]:
        if line.startswith("#") and line[1:] in ("QUEUE", "REGISTRY", "SAMPLE", "LOGS", "END"):
            break
        out.append(line)
    return "\n".join(out)


def fetch_logs(paths, remote=run_remote):
    """Fetch the contents of the given remote log files in one round trip."""
    if not paths:
        return {}
    script = "\n".join(
        f"printf '%s %s\\n' {shlex.quote(FILE_MARKER)} {shlex.quote(p)}; "
        f"cat {shlex.quote(p)} 2>/dev/null || true"
        for p in paths
    )
    ok, out = remote(script)
    return split_fetched_logs(out) if ok else {}


# ---------------------------------------------------------------- state cache


def load_state(path=STATE_FILE):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(state, path=STATE_FILE):
    try:
        atomic_write(path, json.dumps(state))
    except OSError:
        pass


def summary_to_dict(summary):
    return {
        "done": summary.done, "ok": summary.ok, "failed": summary.failed,
        "timeout": summary.timeout, "removed": summary.removed,
        "unparsed": summary.unparsed, "restarted": summary.restarted,
        "problems": [list(astuple(p)) for p in summary.problems],
        "timings": [list(astuple(t)) for t in summary.timings],
    }


def summary_from_dict(data):
    """Rebuild a summary from the cache."""
    summary = OverviewSummary(
        done=data.get("done", 0), ok=data.get("ok", 0), failed=data.get("failed", 0),
        timeout=data.get("timeout", 0), removed=data.get("removed", 0),
        unparsed=data.get("unparsed", 0), restarted=data.get("restarted", 0),
    )
    summary.problems = [Entry(*p) for p in data.get("problems", [])]
    summary.timings = [JobTiming(*t) for t in data.get("timings", [])]
    return summary


def cached(record, mtime):
    """Whether a cluster's cached summary can be reused: the log has not changed
    since it was parsed."""
    return (record.get("mtime") == mtime)


# ---------------------------------------------------------------- main


def main():
    now = datetime.now(timezone.utc)
    state = load_state()
    clusters = state.get("clusters", {})

    ok, output = run_remote(inventory_script())

    if ok:
        history = update_history(parse_sample(_section(output, "SAMPLE")))
        queue = parse_condor_q(_section(output, "QUEUE"))
        registry = parse_registry(_section(output, "REGISTRY"))
        forgotten = load_forgotten()
        inventory = parse_inventory(_section(output, "LOGS"))
        mtimes = {c: datetime.fromtimestamp(i.mtime, timezone.utc)
                  for c, i in inventory.items()}
        selections = select_clusters(registry, queue, mtimes, now,
                                     forgotten=forgotten)

        stale = [inventory[s.cluster].path for s in selections
                 if s.cluster in inventory
                 and not cached(clusters.get(s.cluster, {}), inventory[s.cluster].mtime)]
        fetched = fetch_logs(stale)

        summaries, raw_logs = {}, {}
        for sel in selections:
            item = inventory.get(sel.cluster)
            if item is None:
                continue
            if item.path in fetched:
                summary = parse_overview(fetched[item.path])
                raw_logs[sel.cluster] = fetched[item.path]
                clusters[sel.cluster] = {"mtime": item.mtime,
                                         "summary": summary_to_dict(summary)}
            elif sel.cluster in clusters and "summary" in clusters[sel.cluster]:
                summary = summary_from_dict(clusters[sel.cluster]["summary"])
            else:
                continue
            summaries[sel.cluster] = summary

        for sel in selections:
            record = clusters.setdefault(sel.cluster, {})
            record["submit_dir"] = sel.submit_dir
            record["timestamp"] = sel.timestamp.isoformat() if sel.timestamp else None
            if sel.submit_file:
                record["submit_file"] = sel.submit_file
            if sel.cmdline:
                record["cmdline"] = sel.cmdline
        for gone in set(clusters) - {s.cluster for s in selections}:
            del clusters[gone]
    else:
        history = load_history()
        selections, summaries, raw_logs = [], {}, {}
        for cluster, record in clusters.items():
            stamp = record.get("timestamp")
            selections.append(Selection(
                cluster, record.get("submit_dir"),
                datetime.fromisoformat(stamp) if stamp else None, None,
                submit_file=record.get("submit_file"), cmdline=record.get("cmdline")))
            if "summary" in record:
                summaries[cluster] = summary_from_dict(record["summary"])
        selections.sort(key=lambda s: (s.timestamp is not None, s.timestamp), reverse=True)

    pages = build_pages(selections, summaries, raw_logs, now, queue_ok=ok,
                        history=history)
    for name, content in pages.items():
        atomic_write(os.path.join(OUT_DIR, name), content)

    keep = {"index.html"}
    for sel in selections:
        if sel.cluster in summaries:
            keep.add(os.path.join(CLUSTER_DIR, f"{sel.cluster}.html"))
            keep.add(os.path.join(CLUSTER_DIR, f"overview.{sel.cluster}.log"))
    prune(OUT_DIR, keep)

    save_state({"clusters": clusters})
    print ("[condor-dashboard] generated at %s" % datetime.now())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
