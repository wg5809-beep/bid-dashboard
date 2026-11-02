import pytest

from collector.rules.keywords import matches_keywords

INC = ["회계", "평가", "감사"]
EXC = ["환경영향평가", "건축물 평가"]


@pytest.mark.parametrize(
    "title,expected",
    [
        ("2026년 외부회계감사 용역", True),
        ("○○댐 환경영향평가 용역", False),
        ("노후 건축물 평가 용역", False),
        ("청소 용역 사업자 선정", False),
        ("자산 재 평가 용역", True),
        ("", False),
        (None, False),
    ],
)
def test_matches_keywords(title, expected):
    assert matches_keywords(title, INC, EXC) is expected
