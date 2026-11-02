"""시도 지역 정규화·추출과 금액 파싱.

2026년 기준 광주·전남은 전남광주통합특별시로 통합되어 하나의 지역 "전남광주"로 다룬다.
"""
from __future__ import annotations

import re

REGIONS: tuple[str, ...] = (
    "서울", "부산", "대구", "인천", "대전", "울산", "세종", "경기",
    "강원", "충북", "충남", "전북", "전남광주", "경북", "경남", "제주",
)
UNCLASSIFIED = "미분류"

# 시도 명칭·약칭·구명칭 → 지역. 긴 키부터 부분일치.
_SIDO_ALIASES: dict[str, str] = {
    "서울특별시": "서울", "서울시": "서울", "서울": "서울",
    "부산광역시": "부산", "부산시": "부산", "부산": "부산",
    "대구광역시": "대구", "대구시": "대구", "대구": "대구",
    "인천광역시": "인천", "인천시": "인천", "인천": "인천",
    "대전광역시": "대전", "대전시": "대전", "대전": "대전",
    "울산광역시": "울산", "울산시": "울산", "울산": "울산",
    "세종특별자치시": "세종", "세종시": "세종", "세종": "세종",
    "경기도": "경기", "경기": "경기",
    "강원특별자치도": "강원", "강원도": "강원", "강원": "강원",
    "충청북도": "충북", "충북": "충북",
    "충청남도": "충남", "충남": "충남",
    "전북특별자치도": "전북", "전라북도": "전북", "전북": "전북",
    "전남광주통합특별시": "전남광주", "전남광주": "전남광주",
    "광주광역시": "전남광주", "전라남도": "전남광주", "전남": "전남광주", "광주": "전남광주",
    "경상북도": "경북", "경북": "경북",
    "경상남도": "경남", "경남": "경남",
    "제주특별자치도": "제주", "제주도": "제주", "제주": "제주",
}

# 기관명에서 지역을 뽑기 위한 시·군 힌트. 두 시도에 같은 이름이 있는 곳(고성 등)은 넣지 않는다.
_CITY_HINTS: dict[str, tuple[str, ...]] = {
    "경기": ("수원", "성남", "고양", "용인", "부천", "안산", "안양", "남양주", "화성", "평택", "의정부",
           "시흥", "파주", "김포", "광명", "광주시", "군포", "하남", "오산", "이천", "안성", "구리",
           "의왕", "포천", "양주", "동두천", "과천", "여주", "양평", "가평", "연천"),
    "강원": ("춘천", "원주", "강릉", "동해", "태백", "속초", "삼척", "홍천", "횡성", "영월", "평창",
           "정선", "철원", "화천", "양구", "인제", "양양"),
    "충북": ("청주", "충주", "제천", "보은", "옥천", "영동", "증평", "진천", "괴산", "음성", "단양"),
    "충남": ("천안", "공주", "보령", "아산", "서산", "논산", "계룡", "당진", "금산", "부여", "서천",
           "청양", "홍성", "예산", "태안"),
    "전북": ("전주", "군산", "익산", "정읍", "남원", "김제", "완주", "진안", "무주", "장수", "임실",
           "순창", "고창", "부안"),
    "전남광주": ("목포", "여수", "순천", "나주", "광양", "담양", "곡성", "구례", "고흥", "보성", "화순",
             "장흥", "강진", "해남", "영암", "무안", "함평", "영광", "장성", "완도", "진도", "신안",
             "광산구"),
    "경북": ("포항", "경주", "김천", "안동", "구미", "영주", "영천", "상주", "문경", "경산", "군위",
           "의성", "청송", "영양", "영덕", "청도", "고령", "성주", "칠곡", "예천", "봉화", "울진", "울릉"),
    "경남": ("창원", "진주", "통영", "사천", "김해", "밀양", "거제", "양산", "의령", "함안", "창녕",
           "남해", "하동", "산청", "함양", "거창", "합천"),
    "제주": ("서귀포",),
}

INSTITUTION_HINTS: dict[str, str] = {
    **_SIDO_ALIASES,
    **{city: region for region, cities in _CITY_HINTS.items() for city in cities},
}
_HINTS_LONGEST_FIRST = sorted(INSTITUTION_HINTS, key=len, reverse=True)
_ALIASES_LONGEST_FIRST = sorted(_SIDO_ALIASES, key=len, reverse=True)

SIDO_CODE: dict[str, str] = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "전남광주", "30": "대전",
    "31": "울산", "36": "세종", "41": "경기", "42": "강원", "51": "강원", "43": "충북",
    "44": "충남", "45": "전북", "52": "전북", "46": "전남광주", "47": "경북", "48": "경남",
    "50": "제주",
}

_PREFIX_RE = re.compile(r"^\s*\[([^\]]{1,12})\]")


def _compact(text) -> str:
    return "".join(str(text or "").split())


def _first_hit(body: str, keys: list[str], table: dict[str, str]) -> str | None:
    for key in keys:
        if key in body:
            return table[key]
    return None


def normalize_region(name: str | None) -> str | None:
    """시도 명칭(정식·약칭·구명칭)을 16개 지역 중 하나로. 알 수 없으면 None."""
    body = _compact(name)
    if not body:
        return None
    if body in _SIDO_ALIASES:
        return _SIDO_ALIASES[body]
    return _first_hit(body, _ALIASES_LONGEST_FIRST, _SIDO_ALIASES)


def region_from_institution(name: str | None) -> str | None:
    """기관명 안의 시도·시군 이름으로 지역 추출. 긴 이름부터 매칭한다."""
    body = _compact(name)
    if not body:
        return None
    return _first_hit(body, _HINTS_LONGEST_FIRST, INSTITUTION_HINTS)


def region_from_kapt(title: str | None, bid_area) -> str | None:
    """K-apt 공고명 접두어 `[경기]` 우선, 없으면 법정동 시도코드 앞 2자리."""
    match = _PREFIX_RE.match(str(title or ""))
    if match:
        region = normalize_region(match.group(1))
        if region:
            return region
    code = str(bid_area or "").strip()[:2]
    return SIDO_CODE.get(code) if len(code) == 2 else None


def parse_amount(value) -> int | None:
    """'1,200,000' 같은 금액 문자열을 int로. 빈값·숫자 아님·0 이하는 None."""
    if value is None:
        return None
    text = re.sub(r"[^0-9.\-]", "", str(value))
    if not text or text in {".", "-"}:
        return None
    try:
        amount = int(float(text))
    except ValueError:
        return None
    return amount if amount > 0 else None
