#! /usr/bin/env python3
"""perf_awt.py - Performance testing script for awt.py"""

import argparse
import cProfile
import datetime
import os
import pstats
from pstats import SortKey
import re
import requests
import signal
import string
import subprocess
import time
from urllib.parse import quote


# Set AWT_DIR
AWT_DIR = os.path.dirname(os.path.abspath(__file__))


# Use abiflib.util.get_abiftool_dir to determine abiftool root
from abiflib.util import get_abiftool_dir



# --- b1060time support (minimal, just timestamp generation) ---
_B1060_ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase + '-_'
def get_base60_digit(x):
    if x < 0 or x >= 60:
        raise ValueError(f"{x} is out of range to represent as single base60 digit")
    return _B1060_ALPHABET[x % 60]

def get_b1060_timestamp_from_datetime(dt):
    ttup = dt.timetuple()
    datepart = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}-"
    timepart = get_base60_digit(dt.hour) + get_base60_digit(dt.minute) + get_base60_digit(dt.second)
    return datepart + timepart


# Start awt.py in a subprocess and detect the port


def start_awt_server(log_path, profile_output_path=None):
    env = os.environ.copy()
    env['AWT_DIR'] = AWT_DIR
    abiftool_dir = get_abiftool_dir()
    env['ABIFTOOL_DIR'] = abiftool_dir
    env['PYTHONUNBUFFERED'] = '1'
    # Do NOT set AWT_PROFILE; instead, use --profile-output option

    print(f"[perf] Logging awt.py output to {log_path}")

    cmd = ['python3', os.path.join(AWT_DIR, 'awt.py')]
    if profile_output_path:
        cmd.append(f'--profile-output={profile_output_path}')

    proc = subprocess.Popen(
        cmd,
        stdout=open(log_path, 'w'),
        stderr=subprocess.STDOUT,
        env=env,
        preexec_fn=os.setsid
    )

    port = None
    try:
        for _ in range(30):  # Try for 6 seconds
            time.sleep(0.2)
            with open(log_path) as f:
                output = f.read()
            # More flexible regex: allow whitespace, any host, and extra output
            match = re.search(r'Running on\s+http://[\w\.-]+:(\d+)', output)
            if match:
                port = int(match.group(1))
                break
        if not port:
            print("[perf] Could not detect Flask port. Log output:")
            with open(log_path) as f:
                print(f.read())
            raise RuntimeError("Could not detect Flask port.")
        return proc, port
    except Exception as e:
        proc.terminate()
        raise e

def analyze_profile(cprof_file):
    import io
    s = io.StringIO()
    s.write(f"Analyzing profile: {cprof_file}\n\n")
    p = pstats.Stats(cprof_file, stream=s)
    p.strip_dirs().sort_stats(SortKey.CUMULATIVE).print_stats(30)
    return s.getvalue()

def get_git_rev(awt_dir):
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=awt_dir).decode().strip()
    except Exception:
        return 'unknown'

def build_cprof_path(awt_dir, b1060time, git_rev, id_value=None):
    # If id_value is provided, include it in the filename
    id_part = f"-{id_value}" if id_value else ""
    return os.path.join(awt_dir, 'timing', f"awt-perf-{b1060time}{id_part}-{git_rev}.cprof")

def run_perf_test(proc, port, path, cprof_path):
    url = f"http://127.0.0.1:{port}{path}"
    print(f"Performance testing {url}\nProfiling to: {cprof_path}")
    start = time.time()
    try:
        response = requests.get(url, timeout=60)
    except requests.Timeout:
        print(f"Request to {url} did not complete within 60 seconds.")
        return None
    elapsed = time.time() - start
    print(f"Request completed in {elapsed:.3f} seconds. Profile saved to {cprof_path}")
    print(f"Status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {url} returned {response.status_code}")
    elif "<html" not in response.text.lower():
        print(f"Error: {url} did not return HTML")
    elif elapsed >= 60:
        print(f"Warning: Performance test took too long: {elapsed:.3f} seconds")
    return cprof_path


def list_ids():
    """Print all ids and their .abif filenames from abif_list.yml, one per line."""
    try:
        import yaml
    except ImportError:
        print("PyYAML is required to list ids.")
        return
    abif_list_path = os.path.join(AWT_DIR, 'abif_list.yml')
    try:
        with open(abif_list_path, 'r') as f:
            abif_list = yaml.safe_load(f)
    except Exception as e:
        print(f"Could not read abif_list.yml: {e}")
        return
    # abif_list is expected to be a list of dicts with 'id' and 'filename' keys
    for entry in abif_list:
        id_ = entry.get('id')
        filename = entry.get('filename')
        if id_ and filename:
            print(f"{id_}: {filename}")

def main():
    parser = argparse.ArgumentParser(description='Profile or analyze AWT performance.')
    parser.add_argument('cprof_file', nargs='?', help='Analyze an existing .cprof file instead of running a new test.')
    parser.add_argument('--path', help='Endpoint path to test (e.g. /id/sf2024-mayor)')
    parser.add_argument('--id', help='ID to test (sets --path to /id/<id> unless --path is given)')
    parser.add_argument('--list-ids', action='store_true', help='List all ids and their .abif filenames')
    args = parser.parse_args()

    if args.list_ids:
        list_ids()
        return

    if args.cprof_file:
        summary = analyze_profile(args.cprof_file)
        print(summary)
        return

    # Determine endpoint path
    if args.path:
        path = args.path
    elif args.id:
        path = f"/id/{args.id}"
    else:
        path = "/id/sf2024-mayor"

    git_rev = get_git_rev(AWT_DIR)
    now = datetime.datetime.now(datetime.UTC)
    b1060time = get_b1060_timestamp_from_datetime(now)
    log_path = os.path.join(AWT_DIR, 'timing', f"out-{b1060time}-{git_rev}.out")

    # Build .cprof path for server-side profile
    git_rev = get_git_rev(AWT_DIR)
    now = datetime.datetime.now(datetime.UTC)
    b1060time = get_b1060_timestamp_from_datetime(now)
    # Use id in filename if available and simple
    id_for_filename = None
    if args.id:
        # Only use safe characters for filenames
        id_for_filename = re.sub(r'[^A-Za-z0-9_.-]', '_', args.id)
    cprof_path = build_cprof_path(AWT_DIR, b1060time, git_rev, id_for_filename)

    proc, port = start_awt_server(log_path, profile_output_path=cprof_path)

    def cleanup(*_):
        print("[perf] Cleaning up server subprocess...")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        exit(1)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        cprof_path_result = run_perf_test(proc, port, path, cprof_path)
        if cprof_path_result and os.path.exists(cprof_path_result):
            summary = analyze_profile(cprof_path_result)
            print(summary)
        else:
            print(f"[perf] WARNING: Expected profile file {cprof_path} not found.")
    finally:
        print("[perf] Terminating awt.py server...")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


if __name__ == "__main__":
    main()
