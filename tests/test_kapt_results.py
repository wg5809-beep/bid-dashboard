import json
from datetime import date
from pathlib import Path

from collector.sources import kapt_results
from collector.sources.kapt_results import (
    fetch_participants,
    fetch_results_by_posted,
    match_results,
    result_note_from_state,
    to_award,
)
from tests.fakes import FakeClient
from tests.helpers import make_notice

RESULTS = json.loads(Path("tests/fixtures/kapt_result_item.json").read_text(encoding="utf-8"))
ENTRPS = json.loads(Path("tests/fixtures/kapt_entrps_item.json").read_text(encoding="utf-8"))


def apt_notice(bid_num, status="closed"):
    return make_notice(key=f"apt:{bid_num}", notice_no=bid_num, notice_ord="0", track="apt",
                       status=status, close_at="2026-11-16T17:00", open_at=None,
                       agency="빛가람 ○○아파트", complex_name="빛가람 ○○아파트")


def test_to_award_picks_winner_from_participants():
    n = apt_notice("2026110200123")
    award = to_award(RESULTS[0], n, ENTRPS)
    assert award.key == n.key and award.track == "apt"
    assert award.winner == "○○회계법인" and award.amount == 3300000
    assert award.participants == 3 and award.awarded_at == "2026-11-18T00:00"
    assert award.opened_at == n.close_at and award.title == n.title and award.region == n.region


def test_to_award_without_winner_keeps_amount_and_none_winner():
    n = apt_notice("2026110200123")
    award = to_award(RESULTS[0], n, [])
    assert award.winner is None and award.amount == 3300000 and award.participants is None


def test_match_results_only_pending_known_notices():
    notices = {
        "apt:2026110200123": apt_notice("2026110200123", "closed"),
        "apt:2026110200555": apt_notice("2026110200555", "open"),
    }
    matched = match_results(RESULTS, notices)
    assert set(matched) == {"apt:2026110200123"}
    assert matched["apt:2026110200123"]["bidState"] == "5"


def test_result_note_from_state():
    assert result_note_from_state({"bidState": "4"}) == "유찰"
    assert result_note_from_state({"bidState": "6"}) == "취소"
    assert result_note_from_state({"bidState": "9"}) == "낙찰무효"
    assert result_note_from_state({"bidState": "10"}) == "낙찰무효"
    assert result_note_from_state({"bidState": "5"}) is None
    assert result_note_from_state({}) is None


def test_fetch_results_by_posted_params():
    client = FakeClient({(kapt_results.SERVICE, "getPblAncDeSearchV3"): RESULTS})
    rows = fetch_results_by_posted(client, date(2026, 11, 1), date(2026, 11, 18))
    assert len(rows) == 3
    service, _, params = client.requests[0]
    assert service == "kapt_results" and params == {"startDate": "20261101", "endDate": "20261118"}


def test_fetch_participants_by_bid_num():
    client = FakeClient({(kapt_results.SERVICE, "getBidEntrpsInfoSearchV3"): ENTRPS})
    rows = fetch_participants(client, "2026110200123")
    assert len(rows) == 3 and client.requests[0][2] == {"bidNum": "2026110200123"}
