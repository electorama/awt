
"""Server utilities for AWT.

This module houses helpers that are part of the server/runtime surface area
but are not Flask route handlers or presentation logic.

Currently includes:
- b1060time formatting helpers (UTC, fixed width) per the spec below.
- RouteProfiler, which records per-request timings and mirrors them to
  both the console logger and the optional ABIF log.

Spec and rationale for b1060time:
https://github.com/robla/base10x60timestamp
"""

from __future__ import annotations

import datetime as _dt
import logging
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, Optional

try:
    from abiflib.devtools import abiflib_test_log
except Exception:  # pragma: no cover - dev helper may be absent in tests
    abiflib_test_log = None

ABIFLIB_LOGGER = abiflib_test_log if callable(abiflib_test_log) else None

__all__ = [
    'RouteProfiler',
    'b1060time_from_datetime',
    'b1060time_from_epoch',
]

# Alphabet for base-60 time digits (HH, MM, SS)
_B1060_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_'  # noqa: E501


def _b60(n: int) -> str:
    if n < 0 or n >= 60:
        raise ValueError(f"{n} is out of range to represent as single base60 digit")
    return _B1060_ALPHABET[n]


def b1060time_from_datetime(dt: _dt.datetime) -> str:
    """Return b1060time string (YYYYMMDD-HHMMSS in base60) for a datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    else:
        dt = dt.astimezone(_dt.timezone.utc)
    datepart = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}-"
    timepart = _b60(dt.hour) + _b60(dt.minute) + _b60(dt.second)
    return datepart + timepart


def b1060time_from_epoch(epoch: Optional[int]) -> str:
    """Return b1060time string for a Unix epoch seconds value (UTC)."""
    if epoch is None:
        return ''
    dt = _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc)
    return b1060time_from_datetime(dt)


def _now_b1060() -> str:
    return b1060time_from_datetime(_dt.datetime.now(_dt.timezone.utc))


class RouteProfiler:
    """Track per-request timings and structured logs for slow /id routes."""

    def __init__(self, identifier: str, resulttype: Optional[str], *,
                 request_path: Optional[str] = None,
                 query_string: Optional[str] = None) -> None:
        self._logger = logging.getLogger('awt.routes.id')
        self.identifier = identifier
        self.resulttype = resulttype or 'all'
        self.req_id = uuid.uuid4().hex[:8]
        self.started = time.perf_counter()
        self.spans: Dict[str, list[float]] = defaultdict(list)
        self.debug_lines: list[str] = []
        self.path = request_path or ''
        self.query_string = query_string or ''

    @staticmethod
    def _format_fields(fields: Dict[str, Any]) -> str:
        return ' '.join(f"{key}={value}" for key, value in fields.items() if value is not None)

    def _log_to_abiflib(self, message: str, **fields: Any) -> None:
        if not ABIFLIB_LOGGER:
            return
        try:
            payload = dict(fields or {})
            route = payload.pop('route', self.path) or ''
            query = payload.pop('query', self.query_string) or ''
            if route and query:
                route = f"{route}?{query}"
            b1060 = _now_b1060()
            total_val = payload.pop('total', None)
            steps_val = payload.pop('steps', None)
            other_val = payload.pop('other', None)
            extras = self._format_fields(payload)
            parts = [f"[{self.req_id}]", b1060, route, message]
            if total_val is not None:
                parts.append(f"total={total_val}")
            if steps_val:
                parts.append(f"steps={steps_val}")
            if other_val:
                parts.append(f"other:{other_val}")
            if extras:
                parts.append(extras)
            line = ' '.join(part for part in parts if part).strip()
            ABIFLIB_LOGGER(line, showframeinfo=False)
        except Exception:  # pragma: no cover - logging should not raise
            pass

    def log_request_start(self, *, path: str, cache_type: str, args_count: int) -> None:
        self.path = path
        fields = {'path': path, 'cache_type': cache_type, 'args': args_count}
        self.log('request start', **fields)
        self._log_to_abiflib('request start', **fields)

    def log(self, message: str, **fields: Any) -> None:
        prefix = f"[req={self.req_id} id={self.identifier} result={self.resulttype}]"
        extras = self._format_fields(dict(fields or {}))
        if extras:
            self._logger.info("%s %s %s", prefix, message, extras)
        else:
            self._logger.info("%s %s", prefix, message)

    def debug_checkpoint(self, code: str, message: str, **fields: Any) -> None:
        payload = dict(fields or {})
        self.log(f"checkpoint {code}", detail=message, **payload)
        stamp = _dt.datetime.now().strftime('%d/%b/%Y %H:%M:%S')
        self.debug_lines.append(f" {code} ---->  [{stamp}] {message}")
        payload.setdefault('checkpoint', code)
        self._log_to_abiflib(f"checkpoint {code}", detail=message, **payload)

    def time_block(self, name: str, func, *, log_fields: Optional[Dict[str, Any]] = None):
        start = time.perf_counter()
        try:
            result = func()
        except Exception as exc:
            elapsed = time.perf_counter() - start
            self.spans[name].append(elapsed)
            fields = dict(log_fields or {})
            fields['step'] = name
            fields['elapsed_s'] = f"{elapsed:.3f}"
            fields['error'] = type(exc).__name__
            self.log(f"{name} failed", **fields)
            self._log_to_abiflib(f"{name} failed", **fields)
            raise
        else:
            elapsed = time.perf_counter() - start
            self.spans[name].append(elapsed)
            fields = dict(log_fields or {})
            fields['step'] = name
            fields['elapsed_s'] = f"{elapsed:.3f}"
            self.log(f"{name} completed", **fields)
            self._log_to_abiflib(f"{name} completed", **fields)
            return result, elapsed

    def log_skip(self, name: str, **fields: Any) -> None:
        payload = dict(fields or {})
        payload['step'] = name
        self.log(f"{name} skipped", **payload)
        self._log_to_abiflib(f"{name} skipped", **payload)

    def render_debug_output(self, intro: str = '') -> str:
        body = '\n'.join(self.debug_lines)
        if intro and body:
            separator = '' if intro.endswith('\n') else '\n'
            return f"{intro}{separator}{body}"
        return intro or body

    def finalize(self) -> float:
        total = time.perf_counter() - self.started
        summary_parts = []
        for name, values in sorted(self.spans.items()):
            span_total = sum(values)
            count = len(values)
            part = f"{name}:{span_total:.3f}s"
            if count > 1:
                part += f"/{count}x"
            summary_parts.append(part)
        summary = ', '.join(summary_parts)
        measured = sum(sum(values) for values in self.spans.values())
        other = max(total - measured, 0.0)
        fields = {
            "total": f"{total:.3f}",
            "steps": summary or "none",
            "other": f"{other:.3f}s",
        }
        self.log('request complete', **fields)
        self._log_to_abiflib('request complete', **fields)
        return total
