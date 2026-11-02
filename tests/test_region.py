import pytest

from collector.rules.region import (
    REGIONS,
    UNCLASSIFIED,
    normalize_region,
    parse_amount,
    region_from_institution,
    region_from_kapt,
)


def test_regions_has_16():
    assert len(REGIONS) == 16
    assert "전남광주" in REGIONS and "광주" not in REGIONS and "전남" not in REGIONS
    assert UNCLASSIFIED == "미분류"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("광주광역시", "전남광주"),
        ("전라남도", "전남광주"),
        ("전남광주통합특별시", "전남광주"),
        ("전남", "전남광주"),
        ("전라북도", "전북"),
        ("전북특별자치도", "전북"),
        ("강원특별자치도", "강원"),
        ("서울특별시", "서울"),
        ("경기도", "경기"),
        ("세종특별자치시", "세종"),
        ("제주특별자치도", "제주"),
        ("호남", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_region(name, expected):
    assert normalize_region(name) == expected


@pytest.mark.parametrize(
    "inst,expected",
    [
        ("광주광역시 북구", "전남광주"),
        ("나주시", "전남광주"),
        ("전주시청", "전북"),
        ("경기도 광주시", "경기"),
        ("한국전력공사", None),
        ("강원특별자치도교육청", "강원"),
        ("부산광역시 해운대구청", "부산"),
        (None, None),
    ],
)
def test_region_from_institution(inst, expected):
    assert region_from_institution(inst) == expected


@pytest.mark.parametrize(
    "title,area,expected",
    [
        ("[경기] 청소용역", None, "경기"),
        ("[전남광주] 외부회계감사", None, "전남광주"),
        ("[전남] 외부회계감사", None, "전남광주"),
        ("회계감사 용역", "2900000000", "전남광주"),
        ("회계감사 용역", 4600000000, "전남광주"),
        ("회계감사 용역", "5200000000", "전북"),
        ("회계감사 용역", None, None),
        ("회계감사 용역", "99", None),
    ],
)
def test_region_from_kapt(title, area, expected):
    assert region_from_kapt(title, area) == expected


@pytest.mark.parametrize(
    "v,expected",
    [
        ("1,200,000", 1200000),
        ("", None),
        ("0", None),
        (None, None),
        ("abc", None),
        (350000, 350000),
        ("12000000.00", 12000000),
        (" 5,000 원", 5000),
    ],
)
def test_parse_amount_variants(v, expected):
    assert parse_amount(v) == expected
