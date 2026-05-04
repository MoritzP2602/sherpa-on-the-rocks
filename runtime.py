#!/usr/bin/env python3

import os
import re
import sys
from collections import defaultdict
from datetime import timedelta

def parse_time(timestr):
    # Format: d-hh:mm:ss or hh:mm:ss
    if '-' in timestr:
        d, hms = timestr.split('-')
        d = int(d)
    else:
        d = 0
        hms = timestr
    h, m, s = map(int, hms.split(':'))
    return timedelta(days=d, hours=h, minutes=m, seconds=s).total_seconds()

def main(paths):
    yaml_stats = defaultdict(lambda: {'events': 0, 'time': 0.0, 'time_no_init': 0.0, 'runs': 0, 'run_times_per_1M': [], 'run_times_no_init_per_1M': [], 'events_with_init': 0, 'events_no_init': 0})
    
    if len(paths) == 1 and os.path.isdir(paths[0]):
        folder = paths[0]
        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.out')]
        base_path = os.path.dirname(os.path.abspath(folder))
    else:
        files = [f for f in paths if f.endswith('.out')]
        if files:
            first_file_dir = os.path.dirname(os.path.abspath(files[0]))
            base_path = os.path.dirname(first_file_dir)
        else:
            base_path = os.getcwd()
    base_path =  base_path.split("/")[-1]
    
    total_files = len(files)
    for idx, filepath in enumerate(files, 1):
        print(f"\rProcessing {idx}/{total_files} files...", end='', flush=True)
        
        with open(filepath, encoding='utf-8', errors='replace') as f:
            content = f.read()
            
        # Extract YAML path
        yaml_match = re.search(r'YAML\s*:\s*(.*\.yaml)', content)
        if not yaml_match:
            continue
        yaml_path = yaml_match.group(1).strip()

        # Extract number of events
        events_match = re.search(r'Generated events:\s*(\d+)', content)
        if not events_match:
            events_match = re.search(r'Event\s+(\d+)\s+\(\s*(\d+)\s*s\s+total\s*\)', content)
            if not events_match:
                continue
            events = int(events_match.group(1))

            time_no_init = int(events_match.group(2))
            
            yaml_stats[yaml_path]['events'] += events
            yaml_stats[yaml_path]['time_no_init'] += time_no_init
            yaml_stats[yaml_path]['events_no_init'] += events
            yaml_stats[yaml_path]['runs'] += 1
            
            time_no_init_per_1M = (time_no_init / events) * 1e6 / 3600.0
            yaml_stats[yaml_path]['run_times_no_init_per_1M'].append(time_no_init_per_1M)
            continue
        events = int(events_match.group(1))
        
        # Extract elapsed time (with initialization)
        time_match = re.search(r'Total elapsed time:\s*([0-9\-:]+)', content)
        elapsed = None
        if time_match:
            elapsed = parse_time(time_match.group(1))
            yaml_stats[yaml_path]['time'] += elapsed
            yaml_stats[yaml_path]['events_with_init'] += events
            time_per_1M = (elapsed / events) * 1e6 / 3600.0
            yaml_stats[yaml_path]['run_times_per_1M'].append(time_per_1M)
        
        # Extract time without initialization (from Event line)
        event_time_match = re.search(r'Event\s+\d+\s+\(\s*(\d+)\s*s\s+total\s*\)', content)
        if event_time_match:
            time_no_init = int(event_time_match.group(1))
            yaml_stats[yaml_path]['time_no_init'] += time_no_init
            yaml_stats[yaml_path]['events_no_init'] += events
            time_no_init_per_1M = (time_no_init / events) * 1e6 / 3600.0
            yaml_stats[yaml_path]['run_times_no_init_per_1M'].append(time_no_init_per_1M)
        yaml_stats[yaml_path]['events'] += events
        yaml_stats[yaml_path]['runs'] += 1

    warning_msg = ""
    print('\r' + ' ' * 50 + '\r', end='', flush=True)
    
    print(f"{'GROUP':40} {'With init [h]/1M':>18} {'Min':>10} {'Max':>10} {'No init [h]/1M':>16} {'Total events':>15} {'Runs':>5}")
    print('-'*122)
    for yaml, stats in yaml_stats.items():
        if stats['events'] == 0:
            continue
        
        if stats['time'] > 0 and stats['run_times_per_1M'] and stats['events_with_init'] > 0:
            avg_time_per_1M = (stats['time'] / stats['events_with_init']) * 1e6 / 3600.0
            min_time_per_1M = min(stats['run_times_per_1M'])
            max_time_per_1M = max(stats['run_times_per_1M'])
            time_str = f"{avg_time_per_1M:18.2f}"
            min_str = f"{min_time_per_1M:10.2f}"
            max_str = f"{max_time_per_1M:10.2f}"
        else:
            time_str = f"{'---':>18}"
            min_str = f"{'---':>10}"
            max_str = f"{'---':>10}"
        
        if stats['time_no_init'] > 0 and stats['run_times_no_init_per_1M'] and stats['events_no_init'] > 0:
            avg_time_no_init_per_1M = (stats['time_no_init'] / stats['events_no_init']) * 1e6 / 3600.0
            time_no_init_str = f"{avg_time_no_init_per_1M:16.2f}"
        else:
            time_no_init_str = f"{'---':>16}"
        
        yaml_dir = os.path.dirname(yaml)
        
        if len(yaml_dir.split(base_path)) > 2:
            if len(warning_msg) == 0:
                warning_msg += "Warning: YAML path contains base path multiple times, uses first occurrence for output path splitting.\n"
            warning_msg += "YAML path: " + yaml_dir + ", base path: " + base_path + "\n"          
        short_dir = yaml_dir.split(base_path, 1)[1].strip('/')
        
        print(f"{short_dir:40} {time_str} {min_str} {max_str} {time_no_init_str} {stats['events']:15d} {stats['runs']:5d}")
    print('-'*122)
    if len(warning_msg) > 0:
        print("\n" + warning_msg)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_runtime.py <folder> OR python3 timing.py <file1> [<file2> ...]")
        sys.exit(1)
    main(sys.argv[1:])
