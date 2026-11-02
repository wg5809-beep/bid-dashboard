import json
from datetime import datetime
from pathlib import Path

from collector.sources import nara_awards
from collector.sources.nara_awards import (
    fetch_awards,
    fetch_openg_results,
    match_awards,
    pending_award_keys,
    result_notes,
    to_award,
)
from tests.fakes import FakeClient
from tests.helpers import make_notice

AWARDS = json.loads(Path("tests/fixtures/nara_award_item.json").read_text(encoding="utf-8"))
OPENG = json.loads(Path("tests/fixtures/nara_openg_item.json").read_text(encoding="utf-8"))
NOW = datetime(2026, 11, 18, 9, 0)
BEGIN, END = datetime(2026, 11, 11, 0, 0), datetime(2026, 11, 18, 23, 59)


def notices():
    a = make_notice(key="public:R26BK00000001", notice_no="R26BK00000001", status="opened")
    b = make_notice(key="public:R26BK00000002", notice_no="R26BK00000002", status="closed")
    c = make_notice(key="public:R26BK00000003", notice_no="R26BK00000003", status="opened")
    d = make_notice(key="public:R26BK00000004", notice_no="R26BK00000004", status="open")
    e = make_notice(key="public:R26BK00000005", notice_no="R26BK00000005", status="awarded")
    f = make_notice(key="apt:K1", notice_no="K1", track="apt", status="closed")
    return {n.key: n for n in (a, b, c, d, e, f)}


def test_to_award_maps_and_copies_notice_fields():
    n = notices()["public:R26BK00000001"]
    award = to_award(AWARDS[0], n)
    assert award.key == n.key and award.track == "public"
    assert award.winner == "○○회계법인" and award.winner_bizno == "1234567890"
    assert award.winner_ceo == "김대표"
    assert award.amount == 10500000 and award.planned_price == 11800000
    assert award.rate == 88.123 and award.participants == 5
    assert award.opened_at == "2026-11-16T15:02" and award.awarded_at == "2026-11-17T00:00"
    assert award.title == n.title and award.agency == n.agency
    assert award.region == n.region and award.interest == n.interest


def test_match_awards_ignores_unknown_notice():
    matched = match_awards(AWARDS, notices())
    assert set(matched) == {"public:R26BK00000001"}


def test_result_notes_detects_failed_and_rebid():
    notes = result_notes(OPENG, notices())
    assert notes == {"public:R26BK00000002": "유찰", "public:R26BK00000003": "재입찰"}


def test_pending_award_keys_excludes_open_awarded_and_apt():
    assert sorted(pending_award_keys(notices())) == [
        "public:R26BK00000001", "public:R26BK00000002", "public:R26BK00000003",
    ]


def test_fetch_awards_uses_openg_date_div_and_window_format():
    client = FakeClient({(nara_awards.SERVICE, "getScsbidListSttusServcPPSSrch"): AWARDS})
    rows = fetch_awards(client, BEGIN, END)
    assert len(rows) == 2
    service, op, params = client.requests[0]
    assert service == "nara_awards" and params["inqryDiv"] == "3"
    assert params["inqryBgnDt"] == "202611110000" and params["inqryEndDt"] == "202611182359"


def test_fetch_openg_results_uses_small_pages():
    client = FakeClient({(nara_awards.SERVICE, "getOpengResultListInfoServcPPSSrch"): OPENG})
    rows = fetch_openg_results(client, BEGIN, END)
    assert len(rows) == 3
