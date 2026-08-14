#!/usr/bin/env python3
"""Hide clusters from the Condor dashboard.

This appends the cluster id to ~/.config/condor-dashboard/forgotten on this host,
drops its cached state, and (on the next generator run) removes its page and
copied overview log from ~/www/condor.

Nothing is deleted, and nothing is written to the cluster: ~/.condor-registry on
rocks keeps its record of every submission, and the job output there -- the real
<submitdir>/condor_output/ and its overview.<cluster>.log -- is left alone. To
bring a cluster back, delete its line from the forget list and rerun generate.py.

Usage:
    forget.py <cluster> [<cluster> ...]
    forget.py --all              everything the dashboard currently lists
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import generate


def validate_clusters(clusters):
    """Cluster ids must be digits -- they are interpolated into a shell script."""
    if not clusters:
        raise ValueError("no cluster ids given")
    bad = [c for c in clusters if not str(c).isdigit()]
    if bad:
        raise ValueError("not a cluster id: {}".format(", ".join(map(str, bad))))
    return [str(c) for c in clusters]


def record_forgotten(clusters, path=None):
    """Append the given ids to the local forget list, skipping known ones.

    A plain append, with no lock: this file is written only by this script, on
    the one host that generates the dashboard. Returns the ids actually added.
    """
    path = path or generate.FORGOTTEN_FILE
    known = generate.load_forgotten(path)
    added = [c for c in clusters if c not in known]
    if not added:
        return []
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as handle:
        for cluster in added:
            handle.write(cluster + "\n")
    return added


def listed_clusters(output, now=None):
    """The clusters the dashboard is currently showing, from one inventory fetch.

    Runs the generator's own selection rather than reading the state cache, so
    --all clears exactly what the pages list. Going by the cache would miss a
    cluster the registry has but the last run did not see, and it would come
    straight back on the next run.
    """
    registry = generate.parse_registry(generate._section(output, "REGISTRY"))
    queue = generate.parse_condor_q(generate._section(output, "QUEUE"))
    forgotten = generate.load_forgotten()
    inventory = generate.parse_inventory(generate._section(output, "LOGS"))
    mtimes = {cluster: datetime.fromtimestamp(item.mtime, timezone.utc)
              for cluster, item in inventory.items()}
    selections = generate.select_clusters(
        registry, queue, mtimes, now or datetime.now(timezone.utc),
        forgotten=forgotten)
    return [s.cluster for s in selections]


def forget_clusters(clusters, state=None, path=None):
    """Record the clusters as forgotten and drop their cached state.

    Returns (ok, message). The state cache is only touched once the forget list
    has been written, so a failed run leaves everything consistent.
    """
    clusters = validate_clusters(clusters)
    try:
        record_forgotten(clusters, path)
    except OSError as exc:
        return False, "[condor-dashboard] could not write the forget list: {}".format(exc)

    if state is not None:
        cached = state.get("clusters", {})
        for cluster in clusters:
            cached.pop(cluster, None)
    return True, "[condor-dashboard] forgot {}".format(", ".join(clusters))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    forget_all = argv == ["--all"]
    if not forget_all:
        try:
            clusters = validate_clusters(argv)
        except ValueError as exc:
            print("[condor-dashboard] error: {}".format(exc), file=sys.stderr)
            return 2

    ok, output = generate.run_remote(generate.inventory_script())
    queued = set(generate.parse_condor_q(generate._section(output, "QUEUE"))) if ok else set()

    if forget_all:
        if not ok:
            print("[condor-dashboard] error: could not reach rocks; nothing changed", file=sys.stderr)
            return 1
        listed = listed_clusters(output)
        clusters = sorted((c for c in listed if c not in queued), key=int)
        running = sorted((c for c in listed if c in queued), key=int)
        if running:
            print("[condor-dashboard] still in the queue, kept: {}".format(", ".join(running)))
        if not clusters:
            print("[condor-dashboard] nothing to forget")
            return 0
    else:
        still_live = [c for c in clusters if c in queued]
        if still_live:
            print("[condor-dashboard] error: still in the queue, forgetting would hide a running job: "
                  "{}".format(", ".join(still_live)), file=sys.stderr)
            print("[condor-dashboard]        remove the jobs first (condor_rm) or wait for them to finish.",
                  file=sys.stderr)
            return 3

    state = generate.load_state()
    ok, message = forget_clusters(clusters, state=state)
    print(message)
    if not ok:
        return 1
    generate.save_state(state)

    return generate.main()


if __name__ == "__main__":
    sys.exit(main())
