from pathlib import Path

from collector.config import load_config
from collector.rules.interest import judge_interest

CFG = load_config(Path("collector/config.yaml"))


def test_home_region_by_region():
    assert judge_interest("나주시", None, "전남광주", [], CFG) == (True, "본사 소재")


def test_home_region_by_institution_name_without_region():
    assert judge_interest("한국전력거래소", None, None, [], CFG) == (True, "본사 소재")


def test_home_region_by_institution_list():
    assert judge_interest("한국전력공사", None, None, [], CFG) == (True, "본사 소재")


def test_home_region_by_demand_agency_in_list():
    assert judge_interest("조달청", "한전KDN", "미분류", [], CFG) == (True, "본사 소재")


def test_limit_region_honam():
    assert judge_interest("환경부", "환경부", None, ["호남권"], CFG) == (True, "지역제한")


def test_limit_region_jeonbuk_name():
    assert judge_interest("조달청", "전주시", None, ["전라북도"], CFG) == (True, "지역제한")


def test_home_takes_precedence_over_limit():
    assert judge_interest("나주시", None, "전남광주", ["전라남도"], CFG) == (True, "본사 소재")


def test_jeonbuk_home_without_limit_is_not_interest():
    assert judge_interest("전주시", "전주시", "전북", [], CFG) == (False, None)


def test_other_region():
    assert judge_interest("서울특별시", None, "서울", ["서울특별시"], CFG) == (False, None)


def test_result_is_tuple_of_bool_and_str_or_none():
    ok, reason = judge_interest(None, None, None, (), CFG)
    assert ok is False and reason is None
