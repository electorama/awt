import os
import subprocess
import tempfile
import time
import re
import requests
from urllib.parse import quote
import cProfile
import datetime

# Adjust these paths as needed
AWT_DIR = os.path.dirname(os.path.abspath(__file__))
ABIFTOOL_DIR = '/home/robla/src/abiftool'

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


def main():
    proc, port = start_awt_server()
    try:
        id_ = 'sf2024-mayor'
        encoded_id = quote(id_, safe='')
        path = f"/id/{encoded_id}"
        url = f"http://127.0.0.1:{port}{path}"
        # Get git revision
        try:
            git_rev = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=AWT_DIR).decode().strip()
        except Exception:
            git_rev = 'unknown'
        b1060time = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        cprof_path = os.path.join(AWT_DIR, 'timing', f"awt-perf-{b1060time}-{git_rev}.cprof")
        print(f"Performance testing {url} (original id: {id_})\nProfiling to: {cprof_path}")
        pr = cProfile.Profile()
        pr.enable()
        start = time.time()
        try:
            response = requests.get(url, timeout=60)
        except requests.Timeout:
            print(f"Request to {url} did not complete within 60 seconds.")
            return
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
    finally:
        print("[perf] Terminating awt.py server...")
        import signal
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait()

if __name__ == "__main__":
    main()
