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
    if open_at and now > open_at + timedelta(days=UNKNOWN_AFTER_DAYS):
        return "unknown"
    if open_at and now > open_at:
        return "opened"
    close_at = parse_iso(notice.close_at)
    if close_at and now > close_at:
        return "closed"
    return "open"
