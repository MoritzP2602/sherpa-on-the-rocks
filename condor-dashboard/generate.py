#!/usr/bin/env python3
"""Generate a static dashboard of HTCondor job status.

Runs on an always-on institute host (ds9) and publishes into ~/www/condor.
"""

from __future__ import annotations

import getpass
import html
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

def _tilde(path):
    """Shorten a leading home directory to ~, so the commands shown on the
    generated pages stay short and readable.

    Checks $HOME both as-is and resolved, because on the institute machines they
    differ as strings: $HOME is /home/<user> while a file under it resolves to
    /net/theorie/home/<user>. The same directory reached two ways, so a plain
    prefix test against one of them alone silently fails.

    Does not resolve `path` itself: this is called on the directory this script
    was reached through, and that apparent location is the answer we want.
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


@dataclass
class OverviewSummary:
    """Aggregate of one overview log.

    done counts jobs that reached a terminal state and reported. It is NOT the
    number submitted -- that is unknowable here, since the queue only reports
    jobs that have not yet left it.
    """

    done: int = 0
    ok: int = 0
    failed: int = 0
    timeout: int = 0
    removed: int = 0
    unparsed: int = 0
    problems: list = field(default_factory=list)


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


def parse_overview_line(line):
    """Parse one overview log line, or return None if it is not one.

    Every field except the leading tag is optional: run_app-build.sh omits DIR,
    and EVENTS may be the literal string "unknown".
    """
    segments = [s.strip() for s in line.split("|")]
    head = _HEAD.match(segments[0])
    if not head:
        return None

    entry = Entry(status=head.group(1), cluster=head.group(2), proc=head.group(3))
    for segment in segments[1:]:
        if segment.startswith("DIR:"):
            entry.dir = segment[len("DIR:"):].strip()
        elif segment.startswith("EVENTS:"):
            entry.events = segment[len("EVENTS:"):].strip()
        elif segment.startswith("Exit code:"):
            entry.detail = segment[len("Exit code:"):].strip()
        else:
            wall = _WALL_LIMIT.search(segment)
            if wall:
                entry.detail = wall.group(1)
    return entry


def parse_overview(text):
    """Summarise a whole overview log. Never raises on malformed content."""
    summary = OverviewSummary()
    for line in text.splitlines():
        if not line.strip():
            continue
        entry = parse_overview_line(line)
        if entry is None:
            summary.unparsed += 1
            continue
        summary.done += 1
        counter = _COUNTER[entry.status]
        setattr(summary, counter, getattr(summary, counter) + 1)
        if entry.status != "COMPLETE":
            summary.problems.append(entry)
    return summary


def parse_registry(text):
    """Read the append-only registry the condor_submit wrapper writes.

    Malformed lines are skipped rather than fatal: an interactive shell appends
    to this file and must never be able to break the dashboard.
    """
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
    """Cluster ids recorded as forgotten, one per line.

    Anything that is not a bare number is ignored, so the file can be commented
    and hand-edited: deleting a line here brings a cluster back.
    """
    return {line.strip() for line in text.splitlines() if line.strip().isdigit()}


def load_forgotten(path=None):
    """The forget list, or an empty set if it has never been written.

    Resolves the path when called rather than binding it as a default, so a test
    that redirects FORGOTTEN_FILE is actually obeyed.
    """
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
    """Parse `condor_q -af:t ClusterId ProcId JobStatus Iwd Args Cmd` output.

    Tab separation matters: Iwd and Args both contain spaces, so whitespace
    splitting cannot tell them apart. Falls back to whitespace splitting so
    output from a plain `-af` still parses.
    """
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
    """Choose which clusters to display, newest first.

    A cluster is shown if it has jobs in the queue right now, or was submitted
    within the retention window, and has not been forgotten. Forgetting is a
    filter applied here rather than a deletion from the registry, so the record
    of what was submitted survives.
    """
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

    Falls back to the submit directory for clusters known only from condor_q,
    which does not report which file was submitted.
    """
    if selection.submit_file:
        return os.path.splitext(os.path.basename(selection.submit_file.strip()))[0]
    if selection.submit_dir:
        return os.path.basename(selection.submit_dir.rstrip("/"))
    return "unknown"


def _icon_html(icon, prefix=""):
    """Render an icon that is either an emoji or an image file in ICON_DIR.

    `prefix` is how far the page is below OUT_DIR ("../" for a cluster page):
    icons/ sits at the top level and every page reaches it relatively.
    """
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
            ("removed", "warn"), ("failed", "bad")]


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
        f"<script>{_STALE_JS % {'minutes': STALE_MINUTES}}</script>\n"
    )


# ------------------------------------------------------------- load history

DAY_BINS = 96      # 15 minutes each, 00:00 -> 24:00
WEEK_BINS = 7      # one per weekday, Monday first


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
    """Record `sample` and return the full series, pruned to HISTORY_DAYS.

    Appends in the common case; only rewrites the file on the rare refresh where
    pruning actually drops something.
    """
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


def daily_series(rows, now):
    """(mine_today, total_today, total_average) over 15-minute bins.

    The average deliberately excludes today: today is still partial, and mixing
    it in would drag the baseline toward the current moment.
    """
    today = _local(now.timestamp()).date()
    cur_mine = [[] for _ in range(DAY_BINS)]
    cur_total = [[] for _ in range(DAY_BINS)]
    past_total = [[] for _ in range(DAY_BINS)]
    for epoch, total, mine in rows:
        stamp = _local(epoch)
        index = (stamp.hour * 60 + stamp.minute) // 15
        if index >= DAY_BINS:
            continue
        if stamp.date() == today:
            cur_mine[index].append(mine)
            cur_total[index].append(total)
        else:
            past_total[index].append(total)
    return (_bin_averages(cur_mine), _bin_averages(cur_total),
            _bin_averages(past_total))


def weekly_series(rows, now):
    """(mine_week, total_week, total_average) over one bin per weekday.

    As with the daily chart the average covers every *other* week, so the
    current partial week does not skew it.
    """
    this_week = _local(now.timestamp()).isocalendar()[:2]
    cur_mine = [[] for _ in range(WEEK_BINS)]
    cur_total = [[] for _ in range(WEEK_BINS)]
    past_total = [[] for _ in range(WEEK_BINS)]
    for epoch, total, mine in rows:
        stamp = _local(epoch)
        index = stamp.weekday()
        if stamp.isocalendar()[:2] == this_week:
            cur_mine[index].append(mine)
            cur_total[index].append(total)
        else:
            past_total[index].append(total)
    return (_bin_averages(cur_mine), _bin_averages(cur_total),
            _bin_averages(past_total))


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


def render_chart(series, x_labels, label_every=1):
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
        if index % label_every:
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

    hours = [f"{index // 4:02d}:00" if index % 4 == 0 else "" for index in range(DAY_BINS)]
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    today = _local(now.timestamp())
    day_note = today.strftime("%A %d %b")
    year, week, _ = today.isocalendar()
    week_note = f"week {week}, {year}"

    return "".join([
        "<h2>Cluster load</h2>",
        f'<p class="sub">Running jobs today: {_esc(day_note)}, '
        "15 minute bins. The average covers every earlier day on record.</p>",
        '<div class="card">',
        render_chart([("you", MINE_COLOUR, False, mine_day),
                      ("all users", TOTAL_COLOUR, False, total_day),
                      ("all users (average)", AVG_COLOUR, True, avg_day)],
                     hours, label_every=8),
        "</div>",
        f'<p class="sub">Running jobs this week: {_esc(week_note)}, '
        "daily means. The average covers every earlier week on record.</p>",
        '<div class="card">',
        render_chart([("you", MINE_COLOUR, False, mine_week),
                      ("all users", TOTAL_COLOUR, False, total_week),
                      ("all users (average)", AVG_COLOUR, True, avg_week)],
                     days),
        "</div>",
    ])


def render_index(selections, summaries, generated_at, queue_ok=True, history=None):
    """Render the dashboard index."""
    running = [s for s in selections if s.queue and s.queue.total > 0]
    finished = [s for s in selections if not (s.queue and s.queue.total > 0)]

    parts = ["<h1>HTCondor jobs overview</h1>",
             f'<p class="sub">{_esc(USERNAME)} on {_esc(SSH_HOST)}'
             f' &middot Generated {_when(generated_at)}</p>\n']

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

    if not summary.problems:
        parts.append('<p class="none">No failures or timeouts.</p>')
    else:
        parts.append(f"<h2>Problems ({len(summary.problems)})</h2>")
        rows = ["<tr><th>Job</th><th>Status</th><th class='num'>Events</th>"
                "<th>Detail</th><th>Directory</th></tr>"]
        for entry in summary.problems:
            css = "bad" if entry.status == "FAILED" else "warn"
            if entry.status == "TIMEOUT":
                detail = f"wall limit {_esc(entry.detail)}s"
            elif entry.status == "FAILED":
                detail = f"exit {_esc(entry.detail)}"
            else: detail = _esc("")
            rows.append(
                f"<tr><td>{_esc(entry.cluster)}.{_esc(entry.proc)}</td>"
                f"<td><span class='pill {css}'>{_esc(entry.status)}</span></td>"
                f"<td class='num'>{_esc(entry.events)}</td><td>{detail}</td>"
                f"<td class='path'>{_esc(entry.dir)}</td></tr>"
            )
        parts.append(_table(rows))

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
    """Delete generated files no longer wanted. Leaves unrelated files alone.

    Sweeps the top level and the cluster subfolder, matching `keep` against the
    path relative to OUT_DIR. Sweeping the top level still matters after the move
    to a subfolder: it is what clears out pages left by the old flat layout.
    """
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
  # The tune workflow nests its logs one level deeper, under the DAG node name.
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
        "unparsed": summary.unparsed,
        "problems": [[p.status, p.cluster, p.proc, p.dir, p.events, p.detail]
                     for p in summary.problems],
    }


def summary_from_dict(data):
    summary = OverviewSummary(
        done=data.get("done", 0), ok=data.get("ok", 0), failed=data.get("failed", 0),
        timeout=data.get("timeout", 0), removed=data.get("removed", 0),
        unparsed=data.get("unparsed", 0),
    )
    summary.problems = [Entry(*p) for p in data.get("problems", [])]
    return summary


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
                 and clusters.get(s.cluster, {}).get("mtime") != inventory[s.cluster].mtime]
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
        # Cluster unreachable: re-render from cache rather than reporting zero.
        # No new sample, but the existing history is still worth drawing.
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
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
