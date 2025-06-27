import os
import abiflib
import subprocess
import tempfile
import time
import re
import requests
import pytest
import signal
import yaml
from urllib.parse import quote

# Adjust these paths as needed
# AWT_DIR = '/home/robla/src/awt'
AWT_DIR = os.path.dirname(os.path.abspath(__file__))
ABIFTOOL_DIR = '/home/robla/src/abiftool'
# ABIFTOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(abiflib.__file__)))
print(f"{ABIFTOOL_DIR=}")

ABIF_LIST_PATH = os.path.join(AWT_DIR, 'abif_list.yml')

@pytest.fixture(scope="session")
def awt_server():
    """Start awt.py in a subprocess and yield the detected port."""
    env = os.environ.copy()
    env['AWT_DIR'] = AWT_DIR
    env['ABIFTOOL_DIR'] = ABIFTOOL_DIR
    env['PYTHONUNBUFFERED'] = '1'

    log_file = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    log_path = log_file.name
    print(f"\n[pytest] Logging awt.py output to {log_path}")

    proc = subprocess.Popen(
        ['python3', os.path.join(AWT_DIR, 'awt.py')],
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
            match = re.search(r'Running on http://127\.0\.0\.1:(\d+)', output)
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

def load_ids_from_yaml(yaml_path):
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    return [item['id'] for item in data if 'id' in item]

@pytest.mark.parametrize("id_", load_ids_from_yaml(ABIF_LIST_PATH))
def test_awt_url_returns_html(awt_server, id_):
    """Test that each /id/<id> URL returns 200 and includes HTML content."""
    # URL-encode the id to handle special characters like |
    encoded_id = quote(id_, safe='')
    path = f"/id/{encoded_id}"
    url = f"http://127.0.0.1:{awt_server}{path}"
    print(f"Testing {url} (original id: {id_})")
    response = requests.get(url)
    assert response.status_code == 200, f"{url} returned {response.status_code}"
    assert "<html" in response.text.lower(), f"{url} did not return HTML"
