"""공동주택(K-apt) 입찰결과 소스 (국토교통부_공동주택 입찰결과공지 정보제공 서비스).

실호출 확인: 공고일·마감일 범위 조회는 0건을 돌려주고, 공고명 조회(getBidPblAncNmSearchV3, bidTitle+searchYear)가
해당 연도의 결과(낙찰 5·유찰 4·취소 6 …)를 돌려준다. 공고 서비스는 진행중 공고만 보여주므로
결과 서비스 행으로 과거 공고와 낙찰 이력을 함께 축적한다.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from collector.config import Config
from collector.model import Award, Notice
from collector.rules.region import parse_amount
from collector.sources import kapt_bids
from collector.sources.common import text, to_iso

BASE = "https://apis.data.go.kr/1613000/ApHusBidResultNoticeInfoOfferServiceV3"
SERVICE = "kapt_results"
OP_BY_TITLE = "getBidPblAncNmSearchV3"
OP_PARTICIPANTS = "getBidEntrpsInfoSearchV3"
JSON_PARAM = "_type"
PENDING_STATUSES = ("closed", "opened", "unknown")
STATE_NOTES = {"4": "유찰", "6": "취소", "9": "낙찰무효", "10": "낙찰무효"}
STATE_LABELS = {"1": "신규공고", "2": "수정공고", "3": "재공고", "4": "유찰", "5": "낙찰(계약완료)", "6": "취소",
                "9": "낙찰무효", "10": "계약취소", "99": "낙찰취소후신규공고"}
AWARDED_STATE = "5"


def fetch_results_by_title(client, keyword: str, year: int) -> list[dict]:
    params = {"bidTitle": keyword, "searchYear": str(year)}
    return client.get_items(SERVICE, BASE, OP_BY_TITLE, params, json_param=JSON_PARAM)


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


def notice_from_result(raw: dict, cfg: Config, today: str) -> Notice:
    """결과 행으로 공고 레코드를 만든다(공고 서비스에서 이미 사라진 과거 공고용)."""
    base = kapt_bids.to_notice(raw, cfg, today)
    state = text(raw, "bidState") or ""
    return dataclasses.replace(
        base,
        kind=STATE_LABELS.get(state, base.kind),
        result_note=STATE_NOTES.get(state),
        status="closed",
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


def is_awarded(raw: dict) -> bool:
    return (text(raw, "bidState") or "") == AWARDED_STATE
