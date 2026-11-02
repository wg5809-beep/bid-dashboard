"""공고 상태 전이 규칙."""
from __future__ import annotations

from datetime import datetime, timedelta

from collector.model import Award, Notice

UNKNOWN_AFTER_DAYS = 60


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def derive_status(notice: Notice, award: Award | None, now: datetime, result_note: str | None) -> str:
    if notice.kind and "취소" in notice.kind:
        return "cancelled"
    if award is not None:
        return "awarded"
    if result_note:
        if "유찰" in result_note:
            return "failed"
        if "재입찰" in result_note:
            return "rebid"
    open_at = parse_iso(notice.open_at)
    close_at = parse_iso(notice.close_at)
    # 개찰일이 없는 공고(K-apt)는 마감일 기준으로 결과미확인 전이
    deadline = open_at or close_at
    if deadline and now > deadline + timedelta(days=UNKNOWN_AFTER_DAYS):
        return "unknown"
    if open_at and now > open_at:
        return "opened"
    if close_at and now > close_at:
        return "closed"
    return "open"
