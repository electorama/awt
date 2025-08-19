"""
Pytest configuration and hooks for AWT tests.
"""
import os
import pytest
import subprocess
import tempfile
import time
import re
import signal
import abiflib

ABIFTOOL_DIR = abiflib.get_abiftool_dir()

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Called at the end of the test session to display additional information.
    This is where we can show tips about the AWT_PYTEST_CACHING environment variable.
    """

    caching_backend = os.environ.get('AWT_PYTEST_CACHING', 'none')
    if caching_backend == 'none':
        terminalreporter.write_line("")
        terminalreporter.write_line("TIP: Set AWT_PYTEST_CACHING=filesystem to run tests faster with persistent caching", yellow=True)
        terminalreporter.write_line("     Example: AWT_PYTEST_CACHING=filesystem pytest test_awt_routes.py", yellow=True)
    else:
        terminalreporter.write_line("")
        terminalreporter.write_line(f"AWT_PYTEST_CACHING: {caching_backend}", yellow=True)

@pytest.fixture(scope="session")
def awt_dir():
    """Return the absolute path to the awt project root."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

@pytest.fixture(scope="function")
def awt_server(request, awt_dir):
    """Start awt.py in a subprocess and yield the detected port."""
    cli_args = request.param if hasattr(request, 'param') else []
    env = os.environ.copy()
    env['AWT_DIR'] = awt_dir
    env['ABIFTOOL_DIR'] = ABIFTOOL_DIR
    env['PYTHONUNBUFFERED'] = '1'

    log_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    log_path = log_file.name
    print(f"\n[pytest] Logging awt.py output to {log_path}")

    cmd = ['python3', os.path.join(awt_dir, 'awt.py')] + cli_args
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