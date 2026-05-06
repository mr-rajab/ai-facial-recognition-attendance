"""Shared SlowAPI limiter (disabled when RATE_LIMIT_ENABLED=0, e.g. pytest)."""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address

_enabled = os.environ.get("RATE_LIMIT_ENABLED", "1").lower() not in ("0", "false", "no")

limiter = Limiter(key_func=get_remote_address, enabled=_enabled)
