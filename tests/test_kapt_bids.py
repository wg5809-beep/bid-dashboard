import dataclasses
import json
from datetime import date, datetime
from pathlib import Path

from collector.config import load_config
from collector.sources import kapt_bids
from collector.sources.kapt_bids import collect_apt, fetch_kapt_notices, to_notice
from tests.fakes import FakeClient

CFG = load_config(Path("collector/config.yaml"))
HONAM = dataclasses.replace(CFG, apt_regions=("전남광주", "전북"))
ROWS = json.loads(Path("tests/fixtures/kapt_bid_item.json").read_text(encoding="utf-8"))
TODAY = "2026-11-02"
WINDOW = [(datetime(2026, 10, 30), datetime(2026, 11, 2, 23, 59))]


def test_to_notice_apt_fields_and_url():
    n = to_notice(ROWS[0], CFG, TODAY)
    assert n.key == "apt:2026110200123" and n.track == "apt" and n.notice_ord == "0"
    assert n.title.startswith("[전남광주]") and n.agency == "빛가람 ○○아파트"
    assert n.complex_name == "빛가람 ○○아파트"
    assert n.posted_at == "2026-11-02T00:00" and n.close_at == "2026-11-16T17:00" and n.open_at is None
    assert n.kind == "신규공고" and n.contract_method == "일반경쟁" and n.award_method == "적격심사"
    assert n.source_system == "K-APT"
    assert n.url == "https://www.k-apt.go.kr/bid/bidDetail.do?bidNum=2026110200123"
    assert n.region == "전남광주" and n.limit_regions == ()
    assert (n.interest, n.interest_reason) == (True, "본사 소재")
    assert n.budget is None and n.estimate is None


def test_to_notice_unknown_codes_fall_back_to_raw():
    n = to_notice({**ROWS[0], "bidState": "7", "codeKind": "zz"}, CFG, TODAY)
    assert n.kind == "7" and n.contract_method == "zz"


def test_collect_apt_filters_region_and_keyword():
    client = FakeClient({(kapt_bids.SERVICE, "getPblAncDeSearchV3"): ROWS})
    notices = collect_apt(client, HONAM, WINDOW, TODAY)
    assert [n.notice_no for n in notices] == ["2026110200123"]


def test_collect_apt_default_config_is_nationwide():
    client = FakeClient({(kapt_bids.SERVICE, "getPblAncDeSearchV3"): ROWS})
    notices = collect_apt(client, CFG, WINDOW, TODAY)
    assert [n.notice_no for n in notices] == ["2026110200123", "2026110200124"]  # 경기 포함, 청소용역 제외


def test_fetch_uses_yyyymmdd_and__type_json():
    client = FakeClient({(kapt_bids.SERVICE, "getPblAncDeSearchV3"): ROWS})
    rows = fetch_kapt_notices(client, date(2026, 10, 30), date(2026, 11, 2))
    assert len(rows) == 3
    _, _, params = client.requests[0]
    assert params == {"startDate": "20261030", "endDate": "20261102"}


def test_fetch_accepts_datetime_windows():
    client = FakeClient({(kapt_bids.SERVICE, "getPblAncDeSearchV3"): []})
    fetch_kapt_notices(client, WINDOW[0][0], WINDOW[0][1])
    assert client.requests[0][2]["endDate"] == "20261102"
