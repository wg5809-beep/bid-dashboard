"""공동주택(K-apt) 입찰공고 소스 (국토교통부_공동주택 입찰공고 정보제공 서비스).

공고일 범위로 전국 공고를 받아 지역(호남)과 공고명 키워드로 로컬 필터한다.
"""
from __future__ import annotations

from datetime import datetime

from collector.config import Config
from collector.model import Notice
from collector.rules.interest import judge_interest
from collector.rules.keywords import matches_keywords
from collector.rules.region import UNCLASSIFIED, region_from_kapt
from collector.sources.common import fmt_ymd, text, to_iso

BASE = "https://apis.data.go.kr/1613000/ApHusBidPblAncInfoOfferServiceV3"
SERVICE = "kapt_bids"
OP_BY_POSTED = "getPblAncDeSearchV3"
JSON_PARAM = "_type"
DETAIL_URL = "https://www.k-apt.go.kr/bid/bidDetail.do?bidNum={bidNum}"

BID_STATE = {"1": "신규공고", "2": "수정공고", "3": "재공고"}
CODE_AUTH = {"01": "K-APT", "02": "조달청", "03": "아파트비드포유", "04": "KG2B전자입찰",
             "05": "나이스아파트", "06": "이 아파트", "99": "기타민간업체"}
CODE_KIND = {"01": "일반경쟁", "02": "제한경쟁", "03": "지명경쟁"}
CODE_SUC_WAY = {"01": "최저(고) 낙찰", "02": "적격심사", "03": "최저 낙찰", "04": "최고 낙찰",
                "05": "적격심사(최저)", "06": "적격심사(최고)"}


def _code(table: dict[str, str], raw: dict, key: str) -> str | None:
    value = text(raw, key)
    return table.get(value, value) if value else None


def fetch_kapt_notices(client, begin, end) -> list[dict]:
    params = {"startDate": fmt_ymd(begin), "endDate": fmt_ymd(end)}
    return client.get_items(SERVICE, BASE, OP_BY_POSTED, params, json_param=JSON_PARAM)


def to_notice(raw: dict, cfg: Config, today: str) -> Notice:
    bid_num = text(raw, "bidNum") or ""
    title = text(raw, "bidTitle") or ""
    complex_name = text(raw, "bidKaptname")
    region = region_from_kapt(title, raw.get("bidArea")) or UNCLASSIFIED
    interest, reason = judge_interest(complex_name, None, region, (), cfg)
    return Notice(
        key=f"apt:{bid_num}",
        track="apt",
        notice_no=bid_num,
        notice_ord="0",
        title=title,
        agency=complex_name,
        demand_agency=None,
        agency_code=text(raw, "aptCode"),
        posted_at=to_iso(raw.get("bidRegDate")),
        close_at=to_iso(raw.get("bidDeadline")),
        open_at=None,
        budget=None,
        estimate=None,
        contract_method=_code(CODE_KIND, raw, "codeKind"),
        award_method=_code(CODE_SUC_WAY, raw, "codeSucWay"),
        kind=_code(BID_STATE, raw, "bidState"),
        limit_regions=(),
        region=region,
        interest=interest,
        interest_reason=reason,
        url=DETAIL_URL.format(bidNum=bid_num),
        status="open",
        first_seen=today,
        last_seen=today,
        complex_name=complex_name,
        source_system=_code(CODE_AUTH, raw, "codeAuth"),
    )


def collect_apt(client, cfg: Config, windows: list[tuple[datetime, datetime]], today: str) -> list[Notice]:
    notices: list[Notice] = []
    for begin, end in windows:
        for raw in fetch_kapt_notices(client, begin, end):
            if not matches_keywords(text(raw, "bidTitle"), cfg.apt_keywords, ()):
                continue
            notice = to_notice(raw, cfg, today)
            if notice.region in cfg.apt_regions:
                notices.append(notice)
    return notices
