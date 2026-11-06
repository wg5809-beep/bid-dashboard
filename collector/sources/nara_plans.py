"""나라장터 용역 발주계획 소스 (조달청_나라장터 발주계획현황서비스).

실호출 확인(2026-11-06):
- 용역 검색 오퍼레이션은 발주년월(orderBgnYm~orderEndYm)과 게시일시(inqryBgnDt~inqryEndDt)를 함께 줘야
  조건이 적용된다. 하나라도 빠지면 조건을 무시하고 최근 게시분만 돌려준다.
- 게시일시 범위는 1개월 제한이 없어(22개월 조회 성공) 창을 나누지 않는다.
- bidNtceNoList는 "공고번호 13자리 + 차수 3자리"를 쉼표로 이은 값이며, 비어 있으면 아직 공고 전이다.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from collector.config import Config
from collector.model import Plan
from collector.rules.interest import HOME, judge_interest
from collector.rules.keywords import matches_keywords
from collector.rules.region import UNCLASSIFIED, parse_amount, region_from_institution
from collector.rules.service import classify_service
from collector.sources.common import fmt_pps, text, to_iso

BASE = "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService"
SERVICE = "nara_plans"
OP_LIST = "getOrderPlanSttusListServcPPSSrch"
FALLBACK_URL = "https://www.g2b.go.kr"
NOTICE_NO_LENGTH = 13  # 연결 공고번호에서 차수(뒤 3자리)를 뗀 길이


def first_order_ym(now: datetime, past_months: int) -> tuple[int, int]:
    """수집 범위의 첫 발주 예정월 = 이번 달에서 past_months 개월 전."""
    index = now.year * 12 + (now.month - 1) - past_months
    return index // 12, index % 12 + 1


def plan_window(now: datetime, past_months: int, posted_lookback_days: int) -> dict:
    """조회 조건: 발주 예정월은 past_months 개월 전 ~ 내년 12월, 게시일은 posted_lookback_days 일 전 ~ 오늘."""
    year, month = first_order_ym(now, past_months)
    posted_from = (now - timedelta(days=posted_lookback_days)).replace(hour=0, minute=0, second=0, microsecond=0)
    posted_to = now.replace(hour=23, minute=59, second=0, microsecond=0)
    return {
        "orderBgnYm": f"{year}{month:02d}",
        "orderEndYm": f"{now.year + 1}12",
        "inqryDiv": "1",
        "inqryBgnDt": fmt_pps(posted_from),
        "inqryEndDt": fmt_pps(posted_to),
    }


def _order_ym(raw: dict) -> str | None:
    year, month = text(raw, "orderYear") or "", text(raw, "orderMnth") or ""
    if len(year) == 4 and year.isdigit() and month.isdigit() and 1 <= int(month) <= 12:
        return f"{year}-{int(month):02d}"
    return None


def _notice_nos(raw: dict) -> tuple[str, ...]:
    parts = [part.strip()[:NOTICE_NO_LENGTH] for part in (text(raw, "bidNtceNoList") or "").split(",")]
    return tuple(dict.fromkeys(part for part in parts if part))


def _safe_url(raw: dict) -> str:
    url = text(raw, "orderPlanDtlUrl") or ""
    return url if url.startswith("https://") else FALLBACK_URL


def to_plan(raw: dict, cfg: Config, today: str) -> Plan:
    agency, parent = text(raw, "orderInsttNm"), text(raw, "totlmngInsttNm")
    home_region = region_from_institution(agency) or region_from_institution(parent)
    interest, reason = judge_interest(agency, parent, home_region, (), cfg)
    region = home_region or UNCLASSIFIED
    if reason == HOME and region == UNCLASSIFIED and cfg.interest_home_regions:
        region = cfg.interest_home_regions[0]  # 기관 목록으로 소재지가 확인된 경우
    plan_no = text(raw, "orderPlanUntyNo") or ""
    title = text(raw, "bizNm") or ""
    category, service = classify_service(title, cfg)
    return Plan(
        key=f"plan:{plan_no}",
        plan_no=plan_no,
        title=title,
        agency=agency,
        parent_agency=parent,
        agency_type=text(raw, "jrsdctnDivNm"),
        order_ym=_order_ym(raw),
        amount=parse_amount(raw.get("sumOrderAmt")),
        contract_method=text(raw, "cntrctMthdNm"),
        procurement=text(raw, "prcrmntMethd"),
        dept=text(raw, "deptNm"),
        tel=text(raw, "telNo"),
        posted_at=to_iso(raw.get("nticeDt")),
        changed_at=to_iso(raw.get("chgDt")),
        notice_nos=_notice_nos(raw),
        region=region,
        interest=interest,
        interest_reason=reason,
        url=_safe_url(raw),
        first_seen=today,
        category=category,
        service=service,
    )


def fetch_plans(client, cfg: Config, window: dict, keyword: str, today: str) -> list[Plan]:
    """키워드 1개로 조회해, 사업명이 포함어·제외어 규칙을 통과한 계획만 돌려준다."""
    rows = client.get_items(SERVICE, BASE, OP_LIST, {**window, "bizNm": keyword})
    return [to_plan(raw, cfg, today) for raw in rows
            if text(raw, "orderPlanUntyNo")
            and matches_keywords(text(raw, "bizNm"), cfg.public_keywords, cfg.public_exclude)]
