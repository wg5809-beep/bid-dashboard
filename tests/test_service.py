"""업무 분류: 공고명 → (구분 target/other, 업무명). 설정의 service_lines 순서가 우선순위."""
from pathlib import Path

import dataclasses
import pytest

from collector.config import ServiceLine, load_config
from collector.rules.service import classify_service, classify_all
from tests.helpers import make_notice

CFG = load_config(Path("collector/config.yaml"))


@pytest.mark.parametrize("title, expected", [
    ("나주시 2026년 결산 외부회계감사 용역", ("target", "회계감사")),
    ("[전남광주] 2026년 외부회계감사 용역 사업자 선정", ("target", "회계감사")),
    ("2026년 법인세 세무조정 및 세무자문 용역", ("target", "세무조정")),
    ("세무진단 용역", ("target", "세무진단")),
    ("세무조사 대응 자문 용역", ("target", "세무조사대응")),
    ("세무조사 적법절차 분석 위탁교육", ("other", None)),
    ("지능형 과학실 사업 설계 용역", ("other", None)),
    ("언어모델 기반 기술가치평가 체크리스트 개발", ("other", None)),
    ("2026회계연도 재무결산 위탁용역", ("target", "PA")),
    ("소공인 특화지원사업 회계정산 용역", ("target", "사업비정산")),
    ("세무컨설팅 용역", ("target", "세무컨설팅")),
    ("출자회사 재무실사 용역", ("target", "기업실사")),
    ("비상장주식 공정가치 평가 용역", ("target", "공정가치평가")),
    ("2026년 국고보조사업 사업비 정산 검증 용역", ("target", "사업비정산")),
    ("2026년 결산 회계자문 용역", ("target", "PA")),
    ("2026년 경영평가 지표 개선 연구용역", ("other", None)),
    ("타당성 조사 용역", ("other", None)),
    ("2027년 중소기업경기전망조사 실사 용역", ("other", None)),  # 설문 실사 ≠ 재무실사
    ("", ("other", None)),
    (None, ("other", None)),
])
def test_classify_service(title, expected):
    assert classify_service(title, CFG) == expected


def test_first_matching_line_in_config_order_wins():
    cfg = dataclasses.replace(CFG, service_lines=(ServiceLine("세무조정", ("세무조정",)), ServiceLine("회계감사", ("회계감사",))))
    assert classify_service("회계감사 및 세무조정", cfg) == ("target", "세무조정")


def test_classify_all_rewrites_every_notice_without_mutating_input():
    notices = {"a": make_notice(key="a", title="세무조정 용역"), "b": make_notice(key="b", title="타당성 조사")}
    out = classify_all(notices, CFG)
    assert out is not notices
    assert (out["a"].category, out["a"].service) == ("target", "세무조정")
    assert (out["b"].category, out["b"].service) == ("other", None)
    assert notices["a"].category == "other"  # 기본값, 입력은 그대로


def test_default_config_has_nine_target_lines():
    assert [line.name for line in CFG.service_lines] == [
        "회계감사", "세무조정", "세무조사대응", "세무진단", "세무컨설팅", "기업실사", "공정가치평가", "사업비정산", "PA",
    ]
