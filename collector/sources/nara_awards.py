"""나라장터 용역 낙찰·개찰결과 소스 (조달청_나라장터 낙찰정보서비스).

개찰일시 범위로 낙찰 목록을 받아 보유 공고에 공고번호로 조인한다. 공고별 개별 호출은 하지 않는다.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from collector.model import Award, Notice
from collector.rules.region import parse_amount
from collector.sources.common import fmt_pps, text, to_iso

BASE = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"
SERVICE = "nara_awards"
OP_AWARDS = "getScsbidListSttusServcPPSSrch"
OP_OPENG = "getOpengResultListInfoServcPPSSrch"
AWARD_INQRY_DIV = "3"  # 개찰일시. resultCode 10이 나오면 "2"(공고일시)로 바꾼다.
OPENG_PAGE_SIZE = 50   # 개찰결과 응답은 느려 작은 페이지로
PENDING_STATUSES = ("closed", "opened", "unknown")


def _window_params(begin: datetime, end: datetime) -> dict:
    return {"inqryDiv": AWARD_INQRY_DIV, "inqryBgnDt": fmt_pps(begin), "inqryEndDt": fmt_pps(end)}


def fetch_awards(client, begin: datetime, end: datetime) -> list[dict]:
    return client.get_items(SERVICE, BASE, OP_AWARDS, _window_params(begin, end))


def fetch_openg_results(client, begin: datetime, end: datetime) -> list[dict]:
    return client.get_items(SERVICE, BASE, OP_OPENG, _window_params(begin, end), page_size=OPENG_PAGE_SIZE)


def _to_float(value) -> float | None:
    try:
        return float(str(value).replace(",", "")) if value not in (None, "") else None
    except ValueError:
        return None


def _to_int(value) -> int | None:
    try:
        return int(float(str(value).replace(",", ""))) if value not in (None, "") else None
    except ValueError:
        return None


def to_award(raw: dict, notice: Notice) -> Award:
    return Award(
        key=notice.key,
        notice_no=notice.notice_no,
        notice_ord=text(raw, "bidNtceOrd") or notice.notice_ord,
        track=notice.track,
        winner=text(raw, "bidwinnrNm"),
        winner_bizno=text(raw, "bidwinnrBizno"),
        winner_ceo=text(raw, "bidwinnrCeoNm"),
        amount=parse_amount(raw.get("sucsfbidAmt")),
        planned_price=parse_amount(raw.get("presmptPrce")),
        rate=_to_float(raw.get("sucsfbidRate")),
        participants=_to_int(raw.get("prtcptCnum")),
        opened_at=to_iso(raw.get("rlOpengDt")),
        awarded_at=to_iso(raw.get("fnlSucsfDate")),
        title=notice.title,
        agency=notice.agency,
        region=notice.region,
        interest=notice.interest,
    )


def match_awards(raws: list[dict], notices: Mapping[str, Notice]) -> dict[str, Award]:
    matched: dict[str, Award] = {}
    for raw in raws:
        key = f"public:{text(raw, 'bidNtceNo') or ''}"
        notice = notices.get(key)
        if notice is not None:
            matched[key] = to_award(raw, notice)
    return matched


def result_notes(openg_raws: list[dict], notices: Mapping[str, Notice]) -> dict[str, str]:
    notes: dict[str, str] = {}
    for raw in openg_raws:
        key = f"public:{text(raw, 'bidNtceNo') or ''}"
        status = text(raw, "progrsDivCdNm") or ""
        if key in notices and ("유찰" in status or "재입찰" in status):
            notes[key] = "유찰" if "유찰" in status else "재입찰"
    return notes


def pending_award_keys(notices: Mapping[str, Notice]) -> list[str]:
    return [
        key for key, n in notices.items()
        if n.track == "public" and n.status in PENDING_STATUSES
    ]
