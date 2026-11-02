"""소스 공통 유틸: 날짜 문자열 정규화."""
from __future__ import annotations

import re
from datetime import datetime

_DT_RE = re.compile(r"^(\d{4})[-./]?(\d{2})[-./]?(\d{2})(?:[ T]?(\d{2}):?(\d{2}))?")


def to_iso(value) -> str | None:
    """'2026-11-02 14:00:00' / '20261102' / '2026.11.02' → 'YYYY-MM-DDTHH:MM'."""
    text = str(value or "").strip()
    match = _DT_RE.match(text)
    if not match:
        return None
    year, month, day, hour, minute = match.groups()
    return f"{year}-{month}-{day}T{hour or '00'}:{minute or '00'}"


def fmt_pps(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M")


def fmt_ymd(dt) -> str:
    return dt.strftime("%Y%m%d")


def text(raw: dict, key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    value = str(value).strip()
    return value or None
