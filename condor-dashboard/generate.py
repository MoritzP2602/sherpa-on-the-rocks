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
# Every value below is a working default at the institute. Most users change
# nothing here.

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
REGISTRY_PATH = "$HOME/.condor-registry"
RETENTION_DAYS = 7
STALE_MINUTES = 30
SSH_TIMEOUT = 120

FILE_MARKER = "@@CONDOR-DASH-FILE@@"

# Icons in JOB_KINDS may be an emoji, or the name of an image file placed in
# OUT_DIR/<ICON_DIR>/ (e.g. ~/www/condor/icons/sherpa.png).
ICON_DIR = "icons"
ICON_SUFFIXES = (".png", ".svg", ".jpg", ".jpeg", ".webp", ".gif", ".avif")

# Shown on each cluster page as click-to-copy commands. Static hosting cannot act
# on its own, so the page offers the command and the CLI does the work.
FORGET_COMMAND = "ssh {} '{}/forget.py {{cluster}}'".format(DASH_HOST, DASH_DIR)
REFRESH_COMMAND = "ssh {} '{}/generate.py'".format(DASH_HOST, DASH_DIR)

# HTCondor JobStatus codes.
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

_HEAD = re.compile(r"^\[(COMPLETE|FAILED|TIMEOUT)\]\s+(\d+)\.(\d+)$")
_WALL_LIMIT = re.compile(r"Hit wall time limit of\s+(\S+)\s+seconds")
_COUNTER = {"COMPLETE": "ok", "FAILED": "failed", "TIMEOUT": "timeout"}


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


# Ordered most specific first: the hera/lep entries must win over plain "sherpa".
JOB_KINDS = [
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


def select_clusters(registry, queue, mtimes, now, retention_days=RETENTION_DAYS):
    """Choose which clusters to display, newest first.

    A cluster is shown if it has jobs in the queue right now, or was submitted
    within the retention window.
    """
    cutoff = now - timedelta(days=retention_days)
    selections = []
    for cluster in set(registry) | set(queue):
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
body{font-family:'Segoe UI',Arial,sans-serif;background:#f6f8fa;color:#222;margin:0;padding:32px 16px}
.wrap{max-width:1100px;margin:0 auto}
h1{font-size:1.5em;margin:0 0 4px}
h2{font-size:1.05em;color:#444;margin:32px 0 10px;font-weight:600}
.sub{color:#8a949e;font-size:.85em;margin-bottom:8px}
table{width:100%;background:#fff;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,.07);
border-collapse:separate;border-spacing:0;overflow:hidden;margin-bottom:8px}
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
.cmds{margin-top:26px}
.cmd{margin:0 0 8px;font-size:.85em;color:#5a6570}
.cmd code{background:#f1f4f7;padding:3px 7px;border-radius:5px;word-break:break-all}
.copy{margin-left:7px;font:inherit;color:#1565c0;background:none;border:1px solid #cfd8e0;
border-radius:5px;padding:2px 10px;cursor:pointer}
.copy:hover{background:#f1f4f7}
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


def _icon_html(icon):
    """Render an icon that is either an emoji or an image file in ICON_DIR."""
    if not icon:
        return ""
    if icon.lower().endswith(ICON_SUFFIXES):
        return f'<img class="kicon" src="{ICON_DIR}/{_esc(icon)}" alt="">'
    return _esc(icon)


def _badge(selection):
    """A small pill naming the job type, e.g. Sherpa-logo for Sherpa."""
    icon, label = job_kind(selection.cmdline, selection.submit_file)
    if not label:
        return ""
    rendered = _icon_html(icon)
    return f'<span class="kind">{rendered}{" " if rendered else ""}{_esc(label)}</span>'


def _when(moment):
    return moment.astimezone().strftime("%Y-%m-%d %H:%M") if moment else "unknown"


def _page(title, body, generated_at):
    return (
        f"<title>{_esc(title)}</title>\n<style>{_CSS}</style>\n"
        f'<div class="wrap">\n'
        f'<div id="stale" data-generated="{generated_at.isoformat()}"></div>\n'
        f"{body}\n"
        f'<p class="sub">Generated {_when(generated_at)}</p>\n'
        f"</div>\n"
        f"<script>{_STALE_JS % {'minutes': STALE_MINUTES}}</script>\n"
    )


def render_index(selections, summaries, generated_at, queue_ok=True):
    """Render the dashboard index."""
    running = [s for s in selections if s.queue and s.queue.total > 0]

    parts = ["<h1>Condor jobs</h1>",
             f'<p class="sub">{_esc(USERNAME)} on {_esc(SSH_HOST)}</p>']

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
                     f"across {len(running)} cluster(s)</p>")
        rows = ["<tr><th>Cluster</th><th>Name</th><th class='num'>Running</th>"
                "<th class='num'>Idle</th><th class='num'>Held</th><th>Directory</th></tr>"]
        for sel in running:
            pct = 100 * sel.queue.running // sel.queue.total if sel.queue.total else 0
            rows.append(
                f"<tr><td>{_esc(sel.cluster)}</td>"
                f"<td>{_esc(_name(sel))}{_badge(sel)}"
                f"<div class='bar'><span style='width:{pct}%'></span></div></td>"
                f"<td class='num'><span class='pill run'>{sel.queue.running}</span></td>"
                f"<td class='num'><span class='pill idle'>{sel.queue.idle}</span></td>"
                f"<td class='num'>{sel.queue.held or ''}</td>"
                f"<td class='path'>{_esc(sel.submit_dir)}</td></tr>"
            )
        parts.append("<table>" + "".join(rows) + "</table>")

    parts.append(f"<h2>Recent (last {RETENTION_DAYS} days)</h2>")
    if not selections:
        parts.append('<p class="none">Nothing submitted in the last '
                     f"{RETENTION_DAYS} days.</p>")
    else:
        rows = ["<tr><th>Cluster</th><th>Name</th><th class='num'>Done</th>"
                "<th class='num'>OK</th><th class='num'>Failed</th>"
                "<th class='num'>Timeout</th><th>Submitted</th><th>Directory</th></tr>"]
        for sel in selections:
            summary = summaries.get(sel.cluster)
            name = _esc(_name(sel))
            badge = _badge(sel)
            if summary is None:
                cells = (f"<td>{name}{badge}</td>"
                         f"<td colspan='4' class='none'>no overview file</td>")
            else:
                link = f"<a href='{_esc(sel.cluster)}.html'>{name}</a>{badge}"
                failed = (f"<span class='pill bad'>{summary.failed}</span>"
                          if summary.failed else "0")
                timeout = (f"<span class='pill warn'>{summary.timeout}</span>"
                           if summary.timeout else "0")
                cells = (f"<td>{link}</td><td class='num'>{summary.done}</td>"
                         f"<td class='num'>{summary.ok}</td>"
                         f"<td class='num'>{failed}</td><td class='num'>{timeout}</td>")
            rows.append(f"<tr><td>{_esc(sel.cluster)}</td>{cells}"
                        f"<td>{_when(sel.timestamp)}</td>"
                        f"<td class='path'>{_esc(sel.submit_dir)}</td></tr>")
        parts.append("<table>" + "".join(rows) + "</table>")

    parts.append(
        '<div class="cmds"><p class="cmd">Update this dashboard now '
        f'<code>{_esc(REFRESH_COMMAND)}</code>'
        f'<button class="copy" data-cmd="{_esc(REFRESH_COMMAND)}">copy</button></p></div>'
    )

    return _page("Condor jobs", "\n".join(parts), generated_at)


def render_cluster(selection, summary, log_name, generated_at):
    """Render the per-cluster detail page: counts plus the problem entries."""
    parts = [
        '<a class="back" href="index.html">&larr; all clusters</a>',
        f"<h1>Cluster {_esc(selection.cluster)}</h1>",
        f'<p class="sub">{_esc(_name(selection))}{_badge(selection)} &middot; '
        f"submitted {_when(selection.timestamp)}</p>",
        f'<p class="path">{_esc(selection.submit_dir)}</p>',
        f'<p class="sub">{summary.done} reported &middot; {summary.ok} ok &middot; '
        f"{summary.failed} failed &middot; {summary.timeout} timeout"
        + (f" &middot; {summary.unparsed} unparsed" if summary.unparsed else "")
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
            detail = (f"exit {_esc(entry.detail)}" if entry.status == "FAILED"
                      else f"wall limit {_esc(entry.detail)}s")
            rows.append(
                f"<tr><td>{_esc(entry.cluster)}.{_esc(entry.proc)}</td>"
                f"<td><span class='pill {css}'>{_esc(entry.status)}</span></td>"
                f"<td class='num'>{_esc(entry.events)}</td><td>{detail}</td>"
                f"<td class='path'>{_esc(entry.dir)}</td></tr>"
            )
        parts.append("<table>" + "".join(rows) + "</table>")

    forget = FORGET_COMMAND.format(cluster=selection.cluster)
    parts.append(
        '<div class="cmds">'
        '<p class="cmd">Remove this cluster from the dashboard '
        f'<code>{_esc(forget)}</code>'
        f'<button class="copy" data-cmd="{_esc(forget)}">copy</button></p>'
        '</div>'
    )

    return _page(f"Cluster {selection.cluster}", "\n".join(parts), generated_at)


def build_pages(selections, summaries, raw_logs, generated_at, queue_ok=True):
    """Produce {filename: content} for everything that should be written."""
    pages = {"index.html": render_index(selections, summaries, generated_at, queue_ok)}
    for sel in selections:
        summary = summaries.get(sel.cluster)
        if summary is None:
            continue
        log_name = f"overview.{sel.cluster}.log"
        pages[f"{sel.cluster}.html"] = render_cluster(sel, summary, log_name, generated_at)
        if sel.cluster in raw_logs:
            pages[log_name] = raw_logs[sel.cluster]
    return pages


# ---------------------------------------------------------------- output

_GENERATED = re.compile(r"^(index\.html|\d+\.html|overview\.\d+\.log)$")


def atomic_write(path, content):
    """Write via a temp file and rename, so a reader never sees a partial page."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=directory, prefix=".tmp-")
    try:
        with os.fdopen(handle, "w") as fh:
            fh.write(content)
        # mkstemp creates 0600; the web server must be able to read the result.
        os.chmod(temp, 0o644)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise


def prune(directory, keep):
    """Delete generated files no longer wanted. Leaves unrelated files alone."""
    if not os.path.isdir(directory):
        return
    for name in os.listdir(directory):
        if _GENERATED.match(name) and name not in keep:
            try:
                os.unlink(os.path.join(directory, name))
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
  if [ -f "$f" ]; then printf '%%s\t%%s\t%%s\n' "$cid" "$(stat -c %%Y "$f")" "$f"; fi
done
echo "#END"
"""


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
        if line.startswith("#") and line[1:] in ("QUEUE", "REGISTRY", "LOGS", "END"):
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
        "timeout": summary.timeout, "unparsed": summary.unparsed,
        "problems": [[p.status, p.cluster, p.proc, p.dir, p.events, p.detail]
                     for p in summary.problems],
    }


def summary_from_dict(data):
    summary = OverviewSummary(
        done=data.get("done", 0), ok=data.get("ok", 0), failed=data.get("failed", 0),
        timeout=data.get("timeout", 0), unparsed=data.get("unparsed", 0),
    )
    summary.problems = [Entry(*p) for p in data.get("problems", [])]
    return summary


# ---------------------------------------------------------------- main


def main():
    now = datetime.now(timezone.utc)
    state = load_state()
    clusters = state.get("clusters", {})

    ok, output = run_remote(_INVENTORY_SCRIPT % {"registry": REGISTRY_PATH})

    if ok:
        queue = parse_condor_q(_section(output, "QUEUE"))
        registry = parse_registry(_section(output, "REGISTRY"))
        inventory = parse_inventory(_section(output, "LOGS"))
        mtimes = {c: datetime.fromtimestamp(i.mtime, timezone.utc)
                  for c, i in inventory.items()}
        selections = select_clusters(registry, queue, mtimes, now)

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

    pages = build_pages(selections, summaries, raw_logs, now, queue_ok=ok)
    for name, content in pages.items():
        atomic_write(os.path.join(OUT_DIR, name), content)

    keep = {"index.html"}
    for sel in selections:
        if sel.cluster in summaries:
            keep.add(f"{sel.cluster}.html")
            keep.add(f"overview.{sel.cluster}.log")
    prune(OUT_DIR, keep)

    save_state({"clusters": clusters})
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
