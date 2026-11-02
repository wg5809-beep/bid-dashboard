"""조회 기간을 API 제한(1개월 이내)에 맞춰 연속·비중첩 창으로 나눈다."""
from __future__ import annotations

from datetime import datetime, timedelta

MAX_WINDOW_DAYS = 30


def month_windows(begin: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    if end < begin:
        raise ValueError(f"end({end}) must not precede begin({begin})")
    windows: list[tuple[datetime, datetime]] = []
    cursor = begin
    while True:
        window_end = cursor + timedelta(days=MAX_WINDOW_DAYS) - timedelta(minutes=1)
        if window_end >= end:
            windows.append((cursor, end))
            return windows
        windows.append((cursor, window_end))
        cursor = window_end + timedelta(minutes=1)
