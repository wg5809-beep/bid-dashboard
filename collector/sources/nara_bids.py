"""나라장터 용역 입찰공고 소스 (조달청_나라장터 입찰공고정보서비스).

목록 응답(PPSSrch)에 지역제한 필드(rgnLmtBidLocplcJdgmBssNm, jntcontrctDutyRgnNm1~3)가 포함되어 있어
참가가능지역 오퍼레이션은 호출하지 않는다(날짜 범위 조회 시 전 업무구분 수만 건이 내려와 예산을 소진함).
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from collector.config import Config
from collector.model import Notice
from collector.rules.interest import judge_interest
from collector.rules.keywords import matches_keywords
from collector.rules.region import UNCLASSIFIED, normalize_region, parse_amount, region_from_institution
from collector.sources.common import fmt_pps, text, to_iso

BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
SERVICE = "nara_bids"
OP_LIST = "getBidPblancListInfoServcPPSSrch"
OP_REGION = "getBidPblancListInfoPrtcptPsblRgn"
REGION_FIELD = "prtcptPsblRgnNm"
JUDGEMENT_FIELD = "rgnLmtBidLocplcJdgmBssNm"  # 값이 있으면 지역제한 공고(값 자체는 "본사또는참여지사소재지" 같은 판단기준)
JOINT_DUTY_FIELDS = ("jntcontrctDutyRgnNm1", "jntcontrctDutyRgnNm2", "jntcontrctDutyRgnNm3")
FALLBACK_URL = "https://www.g2b.go.kr"


def _window_params(begin: datetime, end: datetime) -> dict:
    return {"inqryDiv": "1", "inqryBgnDt": fmt_pps(begin), "inqryEndDt": fmt_pps(end)}


def fetch_service_notices(client, begin: datetime, end: datetime, keywords: Sequence[str]) -> list[dict]:
    best: dict[str, dict] = {}
    for keyword in keywords:
        rows = client.get_items(SERVICE, BASE, OP_LIST, {**_window_params(begin, end), "bidNtceNm": keyword})
        for row in rows:
            no = text(row, "bidNtceNo")
            if not no:
                continue
            current = best.get(no)
            if current is None or (text(row, "bidNtceOrd") or "") >= (text(current, "bidNtceOrd") or ""):
                best[no] = row
    return list(best.values())


def limit_regions_of(raw: dict) -> tuple[str, ...]:
    """목록 행에 직접 실린 지역명(공동도급 의무지역)만 모은다. 판단기준 텍스트는 지역이 아니므로 제외."""
    names = [text(raw, field) for field in JOINT_DUTY_FIELDS]
    return tuple(dict.fromkeys(name for name in names if name))


def is_region_limited(raw: dict) -> bool:
    return bool(text(raw, JUDGEMENT_FIELD))


def _hour_bucket(posted: datetime) -> tuple[datetime, datetime]:
    start = posted.replace(minute=0, second=0, microsecond=0)
    return start, start.replace(minute=59)


def fetch_region_limits_for(client, raws: list[dict]) -> dict[str, tuple[str, ...]]:
    """지역제한 공고의 참가가능지역을 공고 등록시각이 속한 1시간 창으로 조회해 공고번호로 걸러낸다.

    참가가능지역 오퍼레이션은 공고번호 지정 조회를 지원하지 않고(실호출: 필수값/범위 오류),
    날짜 범위 조회는 전 업무구분을 돌려주므로 1시간 창(수백 행, 1페이지)을 버킷별로 1회만 호출한다.
    """
    wanted = {text(raw, "bidNtceNo") for raw in raws if text(raw, "bidNtceNo")}
    buckets: dict[tuple[datetime, datetime], None] = {}
    for raw in raws:
        posted = to_iso(raw.get("bidNtceDt"))
        if posted:
            buckets.setdefault(_hour_bucket(datetime.fromisoformat(posted)), None)
    grouped: dict[str, list[str]] = {}
    for begin, end in buckets:
        rows = client.get_items(SERVICE, BASE, OP_REGION, _window_params(begin, end))
        for row in rows:
            no, name = text(row, "bidNtceNo"), text(row, REGION_FIELD)
            if no in wanted and name and name not in grouped.setdefault(no, []):
                grouped[no].append(name)
    return {no: tuple(names) for no, names in grouped.items()}


def _institution_region(raw: dict) -> str | None:
    return region_from_institution(text(raw, "dminsttNm")) or region_from_institution(text(raw, "ntceInsttNm"))


def _limit_region(limit_regions: tuple[str, ...]) -> str | None:
    for name in limit_regions:
        region = normalize_region(name)
        if region:
            return region
    return None


def to_notice(raw: dict, cfg: Config, today: str, fetched_limits: tuple[str, ...] = ()) -> Notice:
    agency, demand = text(raw, "ntceInsttNm"), text(raw, "dminsttNm")
    limit_regions = tuple(dict.fromkeys((*fetched_limits, *limit_regions_of(raw))))
    home_region = _institution_region(raw)
    region = _limit_region(limit_regions) or home_region or UNCLASSIFIED
    # 소재지 판정에는 기관에서 유도한 지역만 쓴다(지역제한에서 온 지역을 소재지로 오판하지 않도록).
    interest, reason = judge_interest(agency, demand, home_region, limit_regions, cfg)
    if reason == "본사 소재" and region == UNCLASSIFIED and cfg.interest_home_regions:
        region = cfg.interest_home_regions[0]  # 기관 목록으로 소재지가 확인된 경우 지도에도 반영
    notice_no = text(raw, "bidNtceNo") or ""
    return Notice(
        key=f"public:{notice_no}",
        track="public",
        notice_no=notice_no,
        notice_ord=text(raw, "bidNtceOrd") or "000",
        title=text(raw, "bidNtceNm") or "",
        agency=agency,
        demand_agency=demand,
        agency_code=text(raw, "ntceInsttCd"),
        posted_at=to_iso(raw.get("bidNtceDt")),
        close_at=to_iso(raw.get("bidClseDt")),
        open_at=to_iso(raw.get("opengDt")),
        budget=parse_amount(raw.get("asignBdgtAmt")),
        estimate=parse_amount(raw.get("presmptPrce")),
        contract_method=text(raw, "cntrctCnclsMthdNm"),
        award_method=text(raw, "sucsfbidMthdNm"),
        kind=text(raw, "ntceKindNm"),
        limit_regions=limit_regions,
        region=region,
        interest=interest,
        interest_reason=reason,
        url=text(raw, "bidNtceDtlUrl") or FALLBACK_URL,
        status="open",
        first_seen=today,
        last_seen=today,
    )


def collect_public(client, cfg: Config, windows: list[tuple[datetime, datetime]], today: str) -> list[Notice]:
    notices: list[Notice] = []
    for begin, end in windows:
        rows = [raw for raw in fetch_service_notices(client, begin, end, cfg.public_keywords)
                if matches_keywords(text(raw, "bidNtceNm"), cfg.public_keywords, cfg.public_exclude)]
        limits = fetch_region_limits_for(client, [raw for raw in rows if is_region_limited(raw)])
        notices += [to_notice(raw, cfg, today, limits.get(text(raw, "bidNtceNo") or "", ())) for raw in rows]
    return notices
