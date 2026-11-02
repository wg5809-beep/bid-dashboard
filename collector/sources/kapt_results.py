"""공동주택(K-apt) 입찰결과 소스 (국토교통부_공동주택 입찰결과공지 정보제공 서비스).

보유 공고의 공고일 범위로 결과 목록을 받아 입찰번호로 조인하고, 참여업체 조회로 낙찰자를 붙인다.
"""
from __future__ import annotations

from collections.abc import Mapping

from collector.model import Award, Notice
from collector.rules.region import parse_amount
from collector.sources.common import fmt_ymd, text, to_iso

BASE = "https://apis.data.go.kr/1613000/ApHusBidResultNoticeInfoOfferServiceV3"
SERVICE = "kapt_results"
OP_BY_POSTED = "getPblAncDeSearchV3"
OP_PARTICIPANTS = "getBidEntrpsInfoSearchV3"
JSON_PARAM = "_type"
PENDING_STATUSES = ("closed", "opened", "unknown")
STATE_NOTES = {"4": "유찰", "6": "취소", "9": "낙찰무효", "10": "낙찰무효"}


def fetch_results_by_posted(client, begin, end) -> list[dict]:
    params = {"startDate": fmt_ymd(begin), "endDate": fmt_ymd(end)}
    return client.get_items(SERVICE, BASE, OP_BY_POSTED, params, json_param=JSON_PARAM)


def fetch_participants(client, bid_num: str) -> list[dict]:
    return client.get_items(SERVICE, BASE, OP_PARTICIPANTS, {"bidNum": bid_num}, json_param=JSON_PARAM)


def _winner(participants: list[dict]) -> str | None:
    for row in participants:
        flag = (text(row, "bidSuccessfulYn") or "").upper()
        if flag.startswith("Y") or flag.startswith("낙찰"):
            return text(row, "companyName")
    return None


def to_award(raw: dict, notice: Notice, participants: list[dict]) -> Award:
    return Award(
        key=notice.key,
        notice_no=notice.notice_no,
        notice_ord=notice.notice_ord,
        track=notice.track,
        winner=_winner(participants),
        winner_bizno=None,
        winner_ceo=None,
        amount=parse_amount(raw.get("amount")),
        planned_price=None,
        rate=None,
        participants=len(participants) or None,
        opened_at=notice.close_at,
        awarded_at=to_iso(raw.get("bidRegdate") or raw.get("bidRegDate")),
        title=notice.title,
        agency=notice.agency,
        region=notice.region,
        interest=notice.interest,
    )


def match_results(raws: list[dict], notices: Mapping[str, Notice]) -> dict[str, dict]:
    matched: dict[str, dict] = {}
    for raw in raws:
        key = f"apt:{text(raw, 'bidNum') or ''}"
        notice = notices.get(key)
        if notice is not None and notice.status in PENDING_STATUSES:
            matched[key] = raw
    return matched


def result_note_from_state(raw: dict) -> str | None:
    return STATE_NOTES.get(text(raw, "bidState") or "")
