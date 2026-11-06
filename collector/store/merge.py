"""공고 병합·낙찰 반영·보존기간 정리. 입력은 수정하지 않고 새 dict를 돌려준다."""
from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta

from collector.model import Award, Notice, Plan
from collector.rules.status import derive_status, parse_iso

_HISTORY_FIELDS = ("notice_ord", "title", "close_at", "open_at", "kind", "result_note")
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
    reissued = old.notice_ord != new.notice_ord  # 차수가 바뀌면(재공고·변경) 이전 유찰/재입찰 결과는 무효
    merged = dataclasses.replace(
        new,
        first_seen=old.first_seen,
        last_seen=today,
        interest=old.interest or new.interest,
        interest_reason=old.interest_reason if old.interest else new.interest_reason,
        result_note=new.result_note if reissued else (old.result_note or new.result_note),
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


def merge_plans(
    existing: Mapping[str, Plan], incoming: Iterable[Plan], complete: bool
) -> tuple[dict[str, Plan], int]:
    """발주계획 병합 → (결과, 신규 수). 처음 본 날짜(first_seen)는 유지한다.

    complete=True(모든 호출 성공)면 이번에 받은 목록이 곧 현재 상태이므로 원본에서 사라진 계획은 지운다.
    일부 호출이 실패했으면 못 받은 계획을 지우지 않도록 기존 것을 남긴다.
    """
    merged: dict[str, Plan] = {} if complete else dict(existing)
    new_count = 0
    for plan in incoming:
        old = existing.get(plan.key)
        new_count += int(old is None and plan.key not in merged)
        merged[plan.key] = dataclasses.replace(plan, first_seen=old.first_seen) if old else plan
    return merged, new_count


def prune_plans(plans: Mapping[str, Plan], min_order_ym: str) -> dict[str, Plan]:
    """발주 예정월이 수집 범위보다 앞선 계획을 버린다(예정월 없는 계획은 남긴다)."""
    return {k: p for k, p in plans.items() if p.order_ym is None or p.order_ym >= min_order_ym}
