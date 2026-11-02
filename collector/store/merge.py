"""공고 병합·낙찰 반영·보존기간 정리. 입력은 수정하지 않고 새 dict를 돌려준다."""
from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from collector.model import Award, Notice
from collector.rules.status import derive_status, parse_iso

_HISTORY_FIELDS = ("notice_ord", "title", "close_at", "open_at", "kind")
_COMPARE_FIELDS = (
    "notice_ord", "title", "agency", "demand_agency", "posted_at", "close_at", "open_at",
    "budget", "estimate", "contract_method", "award_method", "kind", "limit_regions", "url",
)


def _changed(old: Notice, new: Notice) -> bool:
    return any(getattr(old, f) != getattr(new, f) for f in _COMPARE_FIELDS)


def _merge_one(old: Notice, new: Notice, today: str) -> tuple[Notice, bool]:
    if not _changed(old, new):
        return dataclasses.replace(old, last_seen=today), False
    snapshot = {f: getattr(old, f) for f in _HISTORY_FIELDS}
    merged = dataclasses.replace(
        new,
        first_seen=old.first_seen,
        last_seen=today,
        interest=old.interest or new.interest,
        interest_reason=old.interest_reason if old.interest else new.interest_reason,
        result_note=old.result_note if old.result_note else new.result_note,
        history=old.history + (snapshot,),
        status=old.status,
    )
    return merged, True


def merge_notices(
    existing: Mapping[str, Notice], incoming: Iterable[Notice], today: str
) -> tuple[dict[str, Notice], int, int]:
    merged = dict(existing)
    new_count = updated_count = 0
    for notice in incoming:
        old = merged.get(notice.key)
        if old is None:
            merged[notice.key] = dataclasses.replace(notice, first_seen=today, last_seen=today)
            new_count += 1
            continue
        merged[notice.key], changed = _merge_one(old, notice, today)
        updated_count += int(changed)
    return merged, new_count, updated_count


def attach_awards(
    notices: Mapping[str, Notice], awards: Mapping[str, Award], now: datetime
) -> dict[str, Notice]:
    return {
        key: dataclasses.replace(
            notice, status=derive_status(notice, awards.get(key), now, notice.result_note)
        )
        for key, notice in notices.items()
    }


def apply_retention(notices: Mapping[str, Notice], now: datetime, days: int) -> dict[str, Notice]:
    cutoff = now - timedelta(days=days)
    kept = {}
    for key, notice in notices.items():
        posted = parse_iso(notice.posted_at)
        if posted is None or posted >= cutoff:
            kept[key] = notice
    return kept
