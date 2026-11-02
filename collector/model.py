"""공고(Notice)·낙찰(Award)·실행기록(Meta) 불변 모델."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

STATUS: tuple[str, ...] = (
    "open", "closed", "opened", "awarded", "failed", "rebid", "cancelled", "unknown",
)
TRACKS: tuple[str, ...] = ("public", "apt")


def _tuple_fields(cls) -> set[str]:
    return {f.name for f in fields(cls) if str(f.type).startswith("tuple")}


def _from_dict(cls, data: dict[str, Any]):
    names = {f.name for f in fields(cls)}
    tuples = _tuple_fields(cls)
    kwargs = {}
    for name in names:
        if name not in data:
            continue
        value = data[name]
        kwargs[name] = tuple(value) if name in tuples and value is not None else value
    return cls(**kwargs)


@dataclass(frozen=True)
class Notice:
    key: str
    track: str
    notice_no: str
    notice_ord: str
    title: str
    agency: str | None
    demand_agency: str | None
    agency_code: str | None
    posted_at: str | None
    close_at: str | None
    open_at: str | None
    budget: int | None
    estimate: int | None
    contract_method: str | None
    award_method: str | None
    kind: str | None
    limit_regions: tuple[str, ...]
    region: str
    interest: bool
    interest_reason: str | None
    url: str | None
    status: str
    first_seen: str
    last_seen: str
    history: tuple[dict, ...] = ()
    complex_name: str | None = None
    source_system: str | None = None
    result_note: str | None = None
    category: str = "other"  # target(주타겟 업무) / other(기타)
    service: str | None = None  # 주타겟 업무명 (회계감사, 세무조정 …)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Notice":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class Award:
    key: str
    notice_no: str
    notice_ord: str
    track: str
    winner: str | None
    winner_bizno: str | None
    winner_ceo: str | None
    amount: int | None
    planned_price: int | None
    rate: float | None
    participants: int | None
    opened_at: str | None
    awarded_at: str | None
    title: str
    agency: str | None
    region: str
    interest: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Award":
        return _from_dict(cls, data)


@dataclass(frozen=True)
class Meta:
    run_at: str
    ok: bool
    calls: dict[str, int]
    new_notices: int
    updated_notices: int
    new_awards: int
    errors: tuple[str, ...]
    notice_count: int
    award_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Meta":
        return _from_dict(cls, data)
