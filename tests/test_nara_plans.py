import dataclasses
import json
from datetime import datetime
from pathlib import Path

from collector.config import load_config
from collector.sources import nara_plans
from collector.sources.nara_plans import fetch_plans, in_order_range, plan_windows, to_plan
from tests.fakes import FakeClient

CFG = load_config(Path("collector/config.yaml"))
PLANS = json.loads(Path("tests/fixtures/nara_plan_item.json").read_text(encoding="utf-8"))
TODAY = "2026-11-06"
NOW = datetime(2026, 11, 6, 7, 0)


def test_to_plan_maps_fields():
    p = to_plan(PLANS[0], CFG, TODAY)
    assert p.key == "plan:R26DD20501968" and p.plan_no == "R26DD20501968"
    assert p.title == "2027~2029회계연도 회계감사 용역"
    assert p.agency == "한국문화예술위원회" and p.parent_agency == "한국문화예술위원회"
    assert p.agency_type == "기타공공기관" and p.order_ym == "2026-12"
    assert p.amount == 110000000 and p.contract_method == "제한경쟁" and p.procurement == "자체조달"
    assert p.dept == "감사실" and p.tel == "061-900-2117"
    assert p.posted_at == "2026-01-03T13:42" and p.changed_at is None
    assert p.notice_nos == () and p.first_seen == TODAY
    assert p.url == "https://www.g2b.go.kr/link/PRPA015_01/single/?oderPlanNo=R26DD20501968"
    assert (p.category, p.service) == ("target", "회계감사")


def test_to_plan_does_not_keep_officer_name():
    assert "홍길동" not in json.dumps(to_plan(PLANS[0], CFG, TODAY).to_dict(), ensure_ascii=False)


def test_to_plan_interest_from_institution_list():
    p = to_plan(PLANS[0], CFG, TODAY)  # 한국문화예술위원회 = 나주 소재 기관 목록
    assert (p.interest, p.interest_reason, p.region) == (True, "본사 소재", "전남광주")


def test_to_plan_region_from_agency_name_or_unclassified():
    assert to_plan({**PLANS[1], "orderInsttNm": "전북특별자치도 전주시"}, CFG, TODAY).region == "전북"
    p = to_plan(PLANS[1], CFG, TODAY)
    assert p.region == "미분류" and p.interest is False


def test_to_plan_splits_linked_notice_numbers_without_ord():
    p = to_plan(PLANS[1], CFG, TODAY)
    assert p.notice_nos == ("R26BK01805078", "R26BK01800258")
    assert p.changed_at == "2026-10-29T21:15" and p.order_ym == "2026-10"


def test_to_plan_bad_month_and_unsafe_url_fall_back():
    p = to_plan({**PLANS[0], "orderMnth": "", "orderPlanDtlUrl": "javascript:alert(1)", "sumOrderAmt": "0"}, CFG, TODAY)
    assert p.order_ym is None and p.url == "https://www.g2b.go.kr" and p.amount is None


def test_plan_windows_split_posted_range_into_28_day_windows_without_order_month():
    """실호출 확인(2026-11-20): 게시일 범위는 달력상 1개월까지(2/18~3/19, 30일은 07 오류) → 가장 짧은 달에 맞춰 28일."""
    windows = plan_windows(NOW, posted_lookback_days=455)
    assert len(windows) == 17
    assert windows[0] == {"inqryDiv": "1", "inqryBgnDt": "202508080000", "inqryEndDt": "202509042359"}
    assert windows[1]["inqryBgnDt"] == "202509050000" and windows[-1]["inqryEndDt"] == "202611062359"
    assert all("orderBgnYm" not in w and "orderEndYm" not in w for w in windows)


def test_in_order_range_keeps_past_months_to_next_year_end():
    def plan(order_ym):
        return dataclasses.replace(to_plan(PLANS[0], CFG, TODAY), order_ym=order_ym)
    assert [in_order_range(plan(ym), NOW, 3) for ym in ("2026-07", "2026-08", "2027-12", "2028-01", None)] == [
        False, True, True, False, False]
    assert in_order_range(plan("2026-11"), datetime(2027, 2, 10, 7, 0), 3) is True  # 연도 넘김


def test_fetch_plans_sends_contains_keyword_and_filters_by_title():
    """실호출 확인(2026-11-20): bizNm은 앞글자 일치라 '%'를 붙여야 포함 검색이 된다."""
    client = FakeClient({(nara_plans.SERVICE, nara_plans.OP_LIST): PLANS})
    window = plan_windows(NOW, 455)[-1]
    plans = fetch_plans(client, CFG, window, "회계", TODAY)
    assert [p.plan_no for p in plans] == ["R26DD20501968", "R26DD20912432"]  # 유지보수(제외어)는 빠짐
    service, op, params = client.requests[0]
    assert (service, op) == ("nara_plans", "getOrderPlanSttusListServcPPSSrch")
    assert params == {**window, "bizNm": "%회계"}


def test_fetch_plans_skips_rows_without_plan_no():
    client = FakeClient({(nara_plans.SERVICE, nara_plans.OP_LIST): [{**PLANS[0], "orderPlanUntyNo": ""}]})
    assert fetch_plans(client, CFG, plan_windows(NOW, 455)[-1], "회계", TODAY) == []
