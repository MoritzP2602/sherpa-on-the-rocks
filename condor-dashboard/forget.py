#!/usr/bin/env python3
"""Remove clusters from the Condor dashboard.

This deletes the cluster's line from ~/.condor-registry on rocks, its cached
state, and (on the next generator run) its page and copied overview log from
~/www/condor.

It does NOT touch the job output on the cluster: the real
<submitdir>/condor_output/ and its overview.<cluster>.log are left alone.

Usage:
    forget.py <cluster> [<cluster> ...]
"""

from __future__ import annotations

import os
import sys

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


def forget_script(clusters):
    """Bash that drops the given clusters' registry lines, under the same lock
    the submit wrapper uses.

    Uses awk on field 1 rather than a grep regex: `grep -E` does not interpret
    \\t as a tab, which silently matched nothing and deleted nothing.
    """
    if not clusters:
        return ""
    ids = " ".join(clusters)
    return """
set -u
REG="$HOME/.condor-registry"
[ -f "$REG" ] || exit 0
{
  flock -x 200
  tmp=$(mktemp "${REG}.XXXXXX") || exit 1
  awk -F'\\t' -v ids='%(ids)s' \\
    'BEGIN{n=split(ids,a," ");for(i=1;i<=n;i++)drop[a[i]]=1} !($1 in drop)' \\
    "$REG" > "$tmp" && mv "$tmp" "$REG" || rm -f "$tmp"
} 200>>"$REG.lock"
""" % {"ids": ids}


def forget_clusters(clusters, remote=generate.run_remote, state=None):
    """Drop the clusters from the registry and the state cache.

    Returns (ok, message). The state cache is only modified once the remote
    edit has succeeded, so a failed run leaves everything consistent.
    """
    clusters = validate_clusters(clusters)
    ok, _ = remote(forget_script(clusters))
    if not ok:
        return False, "could not reach rocks to edit the registry; nothing changed"

    if state is not None:
        cached = state.get("clusters", {})
        for cluster in clusters:
            cached.pop(cluster, None)
    return True, "forgot {}".format(", ".join(clusters))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    try:
        clusters = validate_clusters(argv)
    except ValueError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2

    # A cluster with jobs still in the queue reappears from condor_q on the next
    # run, so forgetting it now would achieve nothing. Say so rather than lie.
    ok, output = generate.run_remote(
        generate._INVENTORY_SCRIPT % {"registry": generate.REGISTRY_PATH})
    if ok:
        queued = set(generate.parse_condor_q(generate._section(output, "QUEUE")))
        still_live = [c for c in clusters if c in queued]
        if still_live:
            print("error: still in the queue, would come straight back: {}".format(
                ", ".join(still_live)), file=sys.stderr)
            print("       remove the jobs first (condor_rm) or wait for them to finish.",
                  file=sys.stderr)
            return 3

    state = generate.load_state()
    ok, message = forget_clusters(clusters, state=state)
    print(message)
    if not ok:
        return 1
    generate.save_state(state)

    # Regenerate immediately so the pages and copied logs disappear now.
    return generate.main()


if __name__ == "__main__":
    sys.exit(main())
