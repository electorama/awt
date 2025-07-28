import os
import sys

# Add awt project root to sys.path
AWT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if AWT_DIR not in sys.path:
    sys.path.insert(0, AWT_DIR)

# Add abiftool (sibling) to sys.path if needed
ABIFTOOL_DIR = os.path.abspath(os.path.join(AWT_DIR, '..', 'abiftool'))
if os.path.isdir(ABIFTOOL_DIR) and ABIFTOOL_DIR not in sys.path:
    sys.path.insert(0, ABIFTOOL_DIR)

import abiflib
import subprocess
import tempfile
import time
import re
import requests
from pathlib import Path
import pytest
import signal
from urllib.parse import quote



# Adjust these paths as needed
AWT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ABIFTOOL_DIR = abiflib.get_abiftool_dir()

@pytest.fixture(scope="session")
def awt_server(request):
    """Start awt.py in a subprocess and yield the detected port. Accepts extra CLI args via request.param."""
    env = os.environ.copy()
    env['AWT_DIR'] = AWT_DIR
    env['ABIFTOOL_DIR'] = ABIFTOOL_DIR
    env['PYTHONUNBUFFERED'] = '1'

    log_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    log_path = log_file.name
    print(f"\n[pytest] Logging awt.py output to {log_path}")

    cli_args = request.param if hasattr(request, 'param') else []
    cmd = ['python3', os.path.join(AWT_DIR, 'awt.py')] + cli_args
    proc = subprocess.Popen(
        cmd,
        stdout=open(log_path, 'w'),
        stderr=subprocess.STDOUT,
        env=env,
        preexec_fn=os.setsid
    )

    try:
        port = None
        for _ in range(30):  # Try for 6 seconds
            time.sleep(0.2)
            with open(log_path) as f:
                output = f.read()
            match = re.search(r'http://127\.0\.0\.1:(\d+)', output)
            if match:
                port = int(match.group(1))
                break

        if not port:
            raise RuntimeError("Could not detect Flask port.")

        yield port

    finally:
        print("\n[pytest] Terminating awt.py server...")
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait()

@pytest.mark.parametrize("awt_server", [[]], indirect=True)
def test_awt_url_returns_html_performance(awt_server):
    """Performance test for a single /id/<id> URL with default caching (filesystem)."""
    _run_performance_test(awt_server, cache_mode="filesystem")


@pytest.mark.parametrize("awt_server", [["--caching=none"]], indirect=True)
def test_awt_url_returns_html_performance_nocache(awt_server):
    """Performance test for a single /id/<id> URL with caching disabled."""
    _run_performance_test(awt_server, cache_mode="none")


@pytest.mark.parametrize("awt_server", [["--caching=simple"]], indirect=True)
def test_awt_url_returns_html_performance_simplecache(awt_server):
    """Performance test for a single /id/<id> URL with simple (in-memory) caching."""
    _run_performance_test(awt_server, cache_mode="simple")


def _run_performance_test(port, cache_mode):
    id_ = 'sf2024-mayor'
    encoded_id = quote(id_, safe='')
    path = f"/id/{encoded_id}"
    url = f"http://127.0.0.1:{port}{path}"
    import cProfile
    import pstats
    import io
    import subprocess
    # Get git revision
    try:
        git_rev = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=AWT_DIR).decode().strip()
    except Exception:
        git_rev = 'unknown'
    # Use timestamp as b1060time-style identifier
    import datetime
    b1060time = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    timing_dir = Path(AWT_DIR) / 'timing'
    timing_dir.mkdir(exist_ok=True)
    cprof_path = timing_dir / f"awt-perf-{b1060time}-{git_rev}-{cache_mode}.cprof"
    print(f"Performance testing {url} (original id: {id_}, cache: {cache_mode})\nProfiling to: {cprof_path}")
    pr = cProfile.Profile()
    pr.enable()
    start = time.time()
    timeout = 40
    try:
        response = requests.get(url, timeout=timeout)
    except requests.Timeout:
        pytest.fail(f"Request to {url} did not complete within 25 seconds.")
    elapsed = time.time() - start
    pr.disable()
    pr.dump_stats(cprof_path)
    print(f"Request completed in {elapsed:.3f} seconds. Profile saved to {cprof_path}")
    assert response.status_code == 200, f"{url} returned {response.status_code}"
    assert "<html" in response.text.lower(), f"{url} did not return HTML"
    assert elapsed < timeout, f"Performance test took too long: {elapsed:.3f} seconds"
