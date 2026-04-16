#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists(): return {}
    try: 
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return {}


def parse_key(key: str) -> tuple[int, int, str]:
    m = re.fullmatch(r"P(\d+)(?:_dir(\d+))?", key)
    if not m:
        return (999, 999, key)
    phase = int(m.group(1))
    directory = int(m.group(2)) if m.group(2) else 0
    return (phase, directory, key)


def append_files(lines: list[str], title: str, paths: list[Path]) -> None:
    lines.append(f"  - {title}:")
    if not paths:
        lines.append("    n/a")
        return
    for path in paths:
        lines.append(f"    FILE: {path}\n")
        lines.append("    ----- BEGIN -----")
        try:
            content = path.read_text(encoding="utf-8", errors="replace").rstrip()
            if content:
                for line in content.splitlines():
                    lines.append(f"    {line}")
            else:
                lines.append("    [empty file]")
        except Exception as exc:
            lines.append(f"    [error reading file: {exc}]")
        lines.append("    ----- END -------")
        lines.append("")


def append_file_paths(lines: list[str], title: str, paths: list[Path]) -> None:
    lines.append(f"  - {title}:")
    if not paths:
        lines.append("    - n/a")
        return
    for path in paths:
        lines.append(f"    - {path}")


def summarize(master_dir: Path, include_file_content: bool) -> str:
    condor_ids = load_json(master_dir / "condor_ids.json")
    phase_times = load_json(master_dir / "phase_times.json")
    condor_output = master_dir / "condor_output"

    keys = sorted(set(condor_ids.keys()) | set(phase_times.keys()), key=parse_key)
    lines: list[str] = []
    lines.append(f"Master directory: {master_dir}")
    lines.append("")
    dagman_id = (condor_ids.get("dagman") or {}).get("cluster_id", "n/a")
    lines.append(f"DAGMan cluster ID: {dagman_id}")
    lines.append("")

    for key in keys:
        if key == "dagman":
            continue

        entry_c    = condor_ids.get(key) or {}
        entry_t    = phase_times.get(key) or {}
        cluster_id = entry_c.get("cluster_id", "n/a")
        start_time = entry_t.get("start_time", "n/a")
        end_time   = entry_t.get("end_time", "n/a")

        log_dir    = condor_output / key
        m = re.match(r"^(P\d+)", key)
        phase_name = m.group(1) if m else key

        lines.append(f"[{key}]")
        lines.append(f"  - Condor ID: {cluster_id}")
        lines.append(f"  - Start time: {start_time}")
        lines.append(f"  - End time: {end_time}")
        if phase_name in {"P2", "P7"}:
            overview_logs = sorted(log_dir.glob("overview.*.log")) if log_dir.exists() else []
            if include_file_content:
                append_files(lines, "Overview logs", overview_logs)
            else:
                append_file_paths(lines, "Overview logs", overview_logs)
        else:
            out_files = sorted(log_dir.glob("job.*.out")) if log_dir.exists() else []
            err_files = sorted(log_dir.glob("job.*.err")) if log_dir.exists() else []
            if include_file_content:
                append_files(lines, "Job output files", out_files)
                append_files(lines, "Job error files", err_files)
            else:
                append_file_paths(lines, "Job output files", out_files)
                append_file_paths(lines, "Job error files", err_files)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("master_dir", help="Path to MASTER_DIR")
    args = parser.parse_args()

    master_dir = Path(args.master_dir).expanduser().resolve()
    if not master_dir.exists() or not master_dir.is_dir():
        raise SystemExit(f"MASTER_DIR not found or not a directory: {master_dir}")

    terminal_report = summarize(master_dir, include_file_content=False)
    print(terminal_report, end="")
    out_path = master_dir / "output.txt"
    file_report = summarize(master_dir, include_file_content=True)
    out_path.write_text(file_report, encoding="utf-8")
    print(f"\nWrote report to: {out_path}")


if __name__ == "__main__":
    main()
