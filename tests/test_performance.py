import os
import pytest
import requests
from urllib.parse import quote
import time

# Test case definitions
PERFORMANCE_CASES = [
    # This test runs slow on the first run, then fast on subsequent
    # runs (because of the filesystem cache)
    # TODO: Get awt processing the sf2024-mayor's race in under 40 seconds
    {"id": "performance_001_filesystem", "cli_args": [], "cache_mode": "filesystem", "run": False, "election_id": "sf2024-mayor", "timeout": 45},
    # performance_002 and _003 are slow because they always miss the cache
    # TODO: Get awt processing the sf2024-mayor's race in under 40 seconds
    {"id": "performance_002_nocache", "cli_args": ["--caching=none"], "cache_mode": "none", "run": False, "election_id": "sf2024-mayor", "timeout": 40},
    # TODO: Get awt processing the sf2024-mayor's race in under 40 seconds
    {"id": "performance_003_simple", "cli_args": ["--caching=simple"], "cache_mode": "simple", "run": False, "election_id": "sf2024-mayor", "timeout": 40},
]

@pytest.mark.parametrize("perf_case, awt_server", [
    (case, case["cli_args"]) for case in PERFORMANCE_CASES
], indirect=["awt_server"], ids=[c["id"] for c in PERFORMANCE_CASES])
def test_performance(awt_server, awt_dir, perf_case):
    """Performance test for a single /id/<id> URL with various caching modes."""
    if not perf_case["run"]:
        pytest.xfail(f"Test case {perf_case['id']} is disabled (run=False).")

    id_ = perf_case["election_id"]
    encoded_id = quote(id_, safe='')
    path = f"/id/{encoded_id}"
    url = f"http://127.0.0.1:{awt_server}{path}"

    print(f"Performance testing {url} (cache: {perf_case['cache_mode']})")

    timeout = perf_case.get("timeout", int(os.getenv("AWT_PERF_TIMEOUT", "45")))
    start_time = time.time()

    try:
        response = requests.get(url, timeout=timeout)
    except requests.Timeout:
        pytest.fail(f"Request to {url} did not complete within {timeout} seconds.")

    elapsed = time.time() - start_time

    print(f"Request completed in {elapsed:.3f} seconds.")

    assert response.status_code == 200, f"{url} returned {response.status_code}"
    assert "<html" in response.text.lower(), f"{url} did not return HTML"
    assert elapsed < timeout, f"Performance test took too long: {elapsed:.3f} seconds"
