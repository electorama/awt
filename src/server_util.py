"""Server utilities for AWT.

This module houses helpers that are part of the server/runtime surface area
but are not Flask route handlers or presentation logic.

Currently includes:
- b1060time formatting helpers (UTC, fixed width) per the spec below.

Spec and rationale for b1060time:
https://github.com/robla/base10x60timestamp
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional


# Alphabet for base-60 time digits (HH, MM, SS)
_B1060_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_'  # noqa: E501


def _b60(n: int) -> str:
    if n < 0 or n >= 60:
        raise ValueError(f"{n} is out of range to represent as single base60 digit")
    return _B1060_ALPHABET[n]


def b1060time_from_datetime(dt: _dt.datetime) -> str:
    """Return b1060time string (YYYYMMDD-HHMMSS in base60) for a datetime.

    - Always renders in UTC.
    - Uses timezone-aware arithmetic to avoid deprecation warnings.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    else:
        dt = dt.astimezone(_dt.timezone.utc)
    datepart = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}-"
    timepart = _b60(dt.hour) + _b60(dt.minute) + _b60(dt.second)
    return datepart + timepart


def b1060time_from_epoch(epoch: Optional[int]) -> str:
    """Return b1060time string for a Unix epoch seconds value (UTC)."""
    if not epoch and epoch != 0:
        return ''
    dt = _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc)
    return b1060time_from_datetime(dt)

