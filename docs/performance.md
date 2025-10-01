# Performance Logging Playbook

This guide walks through producing a reproducible log bundle for slow routes such as `/id/sf2024-mayor`. Follow the steps in order whenever we want a fresh trace that both of us can inspect.

## 1. One-time setup

Run these commands from the project root to create shared log directories:

```bash
mkdir -p local/logs local/db local/cache
```

## 2. Start a logging-friendly shell

Export these environment variables in the shell session where you will run `awt.py`:

```bash
export ABIFLIB_LOG="$(pwd)/local/logs/abiflib.log"
export AWT_STATUS=debug
export AWT_CACHE_TYPE=none          # disable cache so we see full compute cost
export AWT_REQUEST_LOG_DB="$(pwd)/local/db/awt-requests.sqlite"
export AWT_CACHE_DIR="$(pwd)/local/cache"
export PYTHONUNBUFFERED=1
```

- `ABIFLIB_LOG` routes all abiflib instrumentation (via `abiflib_test_log`) into `local/logs/abiflib.log`.
- `AWT_STATUS=debug` keeps the on-page diagnostics, and also enables the detailed `awt.routes.id` log lines described below.
- `AWT_CACHE_TYPE=none` forces every request to recompute, which is required to observe the slow path. Re-enable caching later by switching to `filesystem` if desired.
- `PYTHONUNBUFFERED=1` ensures stdout is flushed immediately into our log file.

## 3. Launch `awt.py` with file-backed logging

Use `tee` so both the terminal and a shared log capture the same stream. Substitute a unique suffix if you want to keep multiple runs.

```bash
runstamp="$(date +%Y%m%d-%H%M%S)"
python3 awt.py --debug --caching=${AWT_CACHE_TYPE:-none} 2>&1 \
  | tee -a "local/logs/awt-server-${runstamp}.log"
```

- The server prints a line like `Running on http://127.0.0.1:51827`. Note the port for the next step.
- To reuse the same file on subsequent runs, drop the `runstamp` variable and point `tee` at a fixed filename (e.g., `local/logs/awt-server.log`). The file is appended, not truncated.

## 4. Exercise the slow route

In another shell (or a browser), send one or more requests to the target endpoint using the observed port. Example curl invocation:

```bash
PORT=51827   # replace with the actual port printed by awt
curl -s -o /tmp/sf2024.html "http://127.0.0.1:${PORT}/id/sf2024-mayor"
```

Optional variants:

- Add `?transform_ballots=0` or other query params while you gather comparison runs.
- Repeat with `AWT_CACHE_TYPE=filesystem` after restarting the server if you want to confirm caching behavior. When caching is enabled, the request log database (`local/db/awt-requests.sqlite`) records GET activity.

## 5. Inspect the captured data

Key artifacts live under `local/logs/`:

- `awt-server-*.log` — combined Flask output. Look for `awt.routes.id` lines, which include a `[req=XYZ123]` token so you can follow each request: checkpoints (`checkpoint 00006 detail=...`) mark the milestones that also populate the on-page debug pane, and the final `request complete` summary lists total time plus per-step counts (useful to spot repeated abiflib invocations versus single slow steps).
- `abiflib.log` — the same `[req=XYZ123]` tokens appear, now with `route=/id/...`, `step=<name>`, and `function=<module.call>` so you can see which top-level call (e.g., `conduits.ResultConduit.update_IRV_result`) spent the time. The trailing `other=` value on `request complete` records how much wall-clock time is not explained by the profiled steps (template rendering, Flask overhead, etc.).

Useful quick checks:

```bash
tail -n 40 local/logs/awt-server-*.log
grep 'awt.routes.id' local/logs/awt-server-*.log | tail
tail -n 40 local/logs/abiflib.log
sqlite3 local/db/awt-requests.sqlite 'SELECT url, count, last_seen FROM urls ORDER BY last_seen DESC LIMIT 10;'
```

Share those files (or their relevant excerpts) when reporting on performance experiments.

## 6. Resetting between runs (optional)

If you want a clean slate:

```bash
rm -f local/logs/abiflib.log local/logs/awt-server-*.log
rm -f local/db/awt-requests.sqlite
rm -rf local/cache/*
```

Now restart from step 2 to capture the next trial.

## 7. Troubleshooting hints

- If `awt.py` exits immediately, verify that the virtual environment (or system Python) can import `abiflib` and that the abiftool repo is discoverable (see `src/bifhub.py` expectations).
- If the server prints no port, look at the most recent `awt-server-*.log` — startup errors will appear before the `Running on` line.
- Missing log lines in `abiflib.log` usually mean `ABIFLIB_LOG` wasn’t set or the directory didn’t exist; re-run step 1 and try again.
- If you only see `awt.routes.id` start lines with no `request complete`, the request likely crashed; grab the traceback earlier in the same log.

Following these steps ensures both of us can review identical log files when diagnosing performance issues.
