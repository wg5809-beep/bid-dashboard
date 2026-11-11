"""조회 기간을 API 제한에 맞춰 연속·비중첩 창으로 나눈다.

나라장터 입찰공고·낙찰 서비스는 2026-11-11부터 조회 범위가 7일(00:00~7일째 23:59)을 넘으면
07 "입력범위값 초과 에러"를 돌려준다(그전까지는 1개월).
"""
from __future__ import annotations

from datetime import datetime, timedelta

MAX_WINDOW_DAYS = 7


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
