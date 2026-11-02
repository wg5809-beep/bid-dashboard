import json
from datetime import datetime
from pathlib import Path

from collector.config import load_config
from collector.sources import nara_bids
from collector.sources.nara_bids import (
    collect_public,
    fetch_region_limits_for,
    fetch_service_notices,
    is_region_limited,
    limit_regions_of,
    to_notice,
)
from tests.fakes import FakeClient

CFG = load_config(Path("collector/config.yaml"))
BIDS = json.loads(Path("tests/fixtures/nara_bid_item.json").read_text(encoding="utf-8"))
REGIONS = json.loads(Path("tests/fixtures/nara_region_item.json").read_text(encoding="utf-8"))
TODAY = "2026-11-02"
WINDOW = [(datetime(2026, 10, 30, 0, 0), datetime(2026, 11, 2, 23, 59))]


def test_to_notice_maps_fields_and_dates():
    n = to_notice(BIDS[0], CFG, TODAY)
    assert n.key == "public:R26BK00000001" and n.track == "public"
    assert n.notice_no == "R26BK00000001" and n.notice_ord == "000"
    assert n.posted_at == "2026-11-02T09:30" and n.close_at == "2026-11-16T14:00"
    assert n.open_at == "2026-11-16T15:00"
    assert n.budget == 12000000 and n.estimate == 10909091
    assert n.agency == "조달청" and n.agency_code == "1230000"
    assert n.contract_method == "제한경쟁" and n.award_method == "적격심사"
    assert n.kind == "일반공고" and n.url == "https://www.g2b.go.kr/link/R26BK00000001"
    assert n.status == "open" and n.first_seen == TODAY and n.last_seen == TODAY


def test_limit_regions_of_ignores_judgement_basis_and_reads_joint_duty_regions():
    assert limit_regions_of(BIDS[0]) == ()  # 판단기준 텍스트는 지역이 아니다
    assert limit_regions_of({**BIDS[0], "jntcontrctDutyRgnNm1": "전라남도", "jntcontrctDutyRgnNm2": "전라남도"}) == ("전라남도",)
    assert is_region_limited(BIDS[0]) is True and is_region_limited(BIDS[1]) is False


def test_fetch_region_limits_for_uses_hour_window_and_filters_by_notice_no():
    client = FakeClient({(nara_bids.SERVICE, "getBidPblancListInfoPrtcptPsblRgn"): REGIONS})
    limited = [BIDS[0], {**BIDS[0], "bidNtceNo": "R26BK00000003", "bidNtceDt": "2026-11-02 09:50:00"}]
    limits = fetch_region_limits_for(client, limited)
    assert limits == {"R26BK00000001": ("전남광주통합특별시", "전북특별자치도")}
    assert client.calls[nara_bids.SERVICE] == 1  # 같은 시간 버킷은 1회 호출
    params = client.requests[0][2]
    assert params["inqryDiv"] == "1" and params["inqryBgnDt"] == "202611020900" and params["inqryEndDt"] == "202611020959"


def test_to_notice_region_from_limit_first():
    n = to_notice(BIDS[0], CFG, TODAY, ("전남광주통합특별시", "전북특별자치도"))
    assert n.region == "전남광주"
    assert n.limit_regions == ("전남광주통합특별시", "전북특별자치도")
    assert n.interest is True and n.interest_reason == "지역제한"


def test_to_notice_region_from_institution_when_no_limit():
    raw = {**BIDS[1], "bidNtceNm": "전주시 회계 용역", "ntceInsttNm": "전주시", "dminsttNm": "전주시"}
    n = to_notice(raw, CFG, TODAY)
    assert n.region == "전북" and n.interest is False and n.limit_regions == ()


def test_to_notice_unclassified_and_fallback_url():
    n = to_notice(BIDS[1], CFG, TODAY)
    assert n.region == "미분류" and n.url == "https://www.g2b.go.kr"
    assert n.budget is None and n.estimate is None


def test_fetch_service_notices_dedupes_by_notice_no_keeping_higher_ord():
    dup = {**BIDS[0], "bidNtceOrd": "001", "bidNtceNm": "2026년 결산 외부회계감사 용역(변경)"}
    client = FakeClient({(nara_bids.SERVICE, "getBidPblancListInfoServcPPSSrch"): [BIDS[0], dup]})
    rows = fetch_service_notices(client, WINDOW[0][0], WINDOW[0][1], ["회계", "감사"])
    assert len(rows) == 1 and rows[0]["bidNtceOrd"] == "001"
    assert client.calls[nara_bids.SERVICE] == 2
    params = client.requests[0][2]
    assert params["inqryDiv"] == "1" and params["bidNtceNm"] == "회계"
    assert params["inqryBgnDt"] == "202610300000" and params["inqryEndDt"] == "202611022359"


def test_collect_public_filters_exclude_words():
    client = FakeClient({
        (nara_bids.SERVICE, "getBidPblancListInfoServcPPSSrch"): BIDS,
        (nara_bids.SERVICE, "getBidPblancListInfoPrtcptPsblRgn"): REGIONS,
    })
    notices = collect_public(client, CFG, WINDOW, TODAY)
    assert [n.notice_no for n in notices] == ["R26BK00000001"]
    assert notices[0].region == "전남광주" and notices[0].interest_reason == "지역제한"
    assert notices[0].limit_regions == ("전남광주통합특별시", "전북특별자치도")
    region_calls = [1 for _, op, _ in client.requests if op == "getBidPblancListInfoPrtcptPsblRgn"]
    assert len(region_calls) == 1  # 지역제한 공고(키워드 통과분)에 대해서만


def test_to_notice_institution_list_match_sets_home_region():
    raw = {**BIDS[1], "bidNtceNm": "한국전력공사 결산 회계 용역", "ntceInsttNm": "한국전력공사", "dminsttNm": "한국전력공사"}
    n = to_notice(raw, CFG, TODAY)
    assert (n.interest, n.interest_reason) == (True, "본사 소재")
    assert n.region == "전남광주"
