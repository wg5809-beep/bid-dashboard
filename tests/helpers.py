"""테스트 공용 팩토리."""
from __future__ import annotations

import dataclasses

from collector.model import Award, Notice

TODAY = "2026-11-02"


def make_notice(**over) -> Notice:
    base = dict(
        key="public:R26BK00000001",
        track="public",
        notice_no="R26BK00000001",
        notice_ord="000",
        title="나주시 2026년 결산 외부회계감사 용역",
        agency="나주시",
        demand_agency="나주시",
        agency_code="4680000",
        posted_at="2026-11-02T09:00",
        close_at="2026-11-16T14:00",
        open_at="2026-11-16T15:00",
        budget=12000000,
        estimate=11000000,
        contract_method="제한경쟁",
        award_method="적격심사",
        kind="일반공고",
        limit_regions=("전남광주통합특별시",),
        region="전남광주",
        interest=True,
        interest_reason="본사 소재",
        url="https://www.g2b.go.kr/x",
        status="open",
        first_seen=TODAY,
        last_seen=TODAY,
    )
    base.update(over)
    return Notice(**base)


def make_award(notice: Notice | None = None, **over) -> Award:
    notice = notice or make_notice()
    base = dict(
        key=notice.key,
        notice_no=notice.notice_no,
        notice_ord=notice.notice_ord,
        track=notice.track,
        winner="○○회계법인",
        winner_bizno="1234567890",
        winner_ceo="김대표",
        amount=10500000,
        planned_price=11800000,
        rate=88.98,
        participants=5,
        opened_at="2026-11-16T15:00",
        awarded_at="2026-11-17T00:00",
        title=notice.title,
        agency=notice.agency,
        region=notice.region,
        interest=notice.interest,
    )
    base.update(over)
    return Award(**base)


def replace(obj, **changes):
    return dataclasses.replace(obj, **changes)


def make_plan(**over):
    from collector.model import Plan
    base = dict(
        key="plan:R26DD00000001",
        plan_no="R26DD00000001",
        title="2027회계연도 외부회계감사 용역",
        agency="나주시",
        parent_agency="전남광주통합특별시",
        agency_type="지방자치단체",
        order_ym="2026-12",
        amount=30000000,
        contract_method="제한경쟁",
        procurement="자체조달",
        dept="회계과",
        tel="061-000-0000",
        posted_at="2026-11-05T10:00",
        changed_at=None,
        notice_nos=(),
        region="전남광주",
        interest=True,
        interest_reason="본사 소재",
        url="https://www.g2b.go.kr/link/PRPA015_01/single/?oderPlanNo=R26DD00000001",
        first_seen=TODAY,
    )
    base.update(over)
    return Plan(**base)
