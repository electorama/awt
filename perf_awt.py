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
import tempfile
import time
from urllib.parse import quote

# Adjust these paths as needed
AWT_DIR = os.path.dirname(os.path.abspath(__file__))
ABIFTOOL_DIR = '/home/robla/src/abiftool'


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

def start_awt_server():
    env = os.environ.copy()
    env['AWT_DIR'] = AWT_DIR
    env['ABIFTOOL_DIR'] = ABIFTOOL_DIR
    env['PYTHONUNBUFFERED'] = '1'

    log_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    log_path = log_file.name
    print(f"[perf] Logging awt.py output to {log_path}")

    proc = subprocess.Popen(
        ['python3', os.path.join(AWT_DIR, 'awt.py')],
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

def build_cprof_path(awt_dir, b1060time, git_rev):
    return os.path.join(awt_dir, 'timing', f"awt-perf-{b1060time}-{git_rev}.cprof")

def run_perf_test(proc, port, path, awt_dir):
    id_ = path.split('/')[-1] if path.startswith('/id/') and len(path.split('/')) > 2 else path
    url = f"http://127.0.0.1:{port}{path}"
    git_rev = get_git_rev(awt_dir)
    now = datetime.datetime.now(datetime.UTC)
    b1060time = get_b1060_timestamp_from_datetime(now)
    cprof_path = build_cprof_path(awt_dir, b1060time, git_rev)
    print(f"Performance testing {url} (original id: {id_})\nProfiling to: {cprof_path}")
    pr = cProfile.Profile()
    pr.enable()
    start = time.time()
    try:
        response = requests.get(url, timeout=60)
    except requests.Timeout:
        print(f"Request to {url} did not complete within 60 seconds.")
        return None
    elapsed = time.time() - start
    pr.disable()
    pr.dump_stats(cprof_path)
    print(f"Request completed in {elapsed:.3f} seconds. Profile saved to {cprof_path}")
    print(f"Status code: {response.status_code}")
    if response.status_code != 200:
        print(f"Error: {url} returned {response.status_code}")
    elif "<html" not in response.text.lower():
        print(f"Error: {url} did not return HTML")
    elif elapsed >= 60:
        print(f"Warning: Performance test took too long: {elapsed:.3f} seconds")
    return cprof_path


def main():
    parser = argparse.ArgumentParser(description='Profile or analyze AWT performance.')
    parser.add_argument('cprof_file', nargs='?', help='Analyze an existing .cprof file instead of running a new test.')
    parser.add_argument('--path', default='/id/sf2024-mayor', help='Endpoint path to test (default: /id/sf2024-mayor)')
    args = parser.parse_args()

    if args.cprof_file:
        summary = analyze_profile(args.cprof_file)
        print(summary)
        return

    proc, port = start_awt_server()

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
        cprof_path = run_perf_test(proc, port, args.path, AWT_DIR)
        if cprof_path:
            summary = analyze_profile(cprof_path)
            print(summary)
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
