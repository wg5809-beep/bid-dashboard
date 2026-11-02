# 회계법인 용역 공공입찰 대시보드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 나라장터·K-apt 입찰공고를 매일 07:00 KST에 수집해 공고·낙찰을 JSON으로 누적하고, GitHub Pages 정적 사이트(대시보드·캘린더·지도·낙찰) 로 PC·모바일에서 보여준다.

**Architecture:** Python 수집기(`collector/`)가 공공데이터포털 API 4종을 호출해 `data/*.json`을 불변 병합으로 갱신한다. GitHub Actions가 매일 수집기를 실행해 `data/`를 커밋하고 `web/`+`data/`를 Pages로 배포한다. 프론트엔드는 프레임워크 없는 ES 모듈로 JSON만 읽어 4개 뷰를 그린다.

**Tech Stack:** Python 3.12 (Actions) / 3.14 (로컬), `requests`, `pyyaml`, `pytest`; 프론트 Vanilla JS(ES2022 모듈) + CSS, 테스트는 `node --test`; GitHub Actions, GitHub Pages(deploy-pages).

**Spec:** `docs/superpowers/specs/2026-11-02-bid-dashboard-design.md`

## Global Constraints

- 인증키는 환경변수 `DATA_GO_KR_SERVICE_KEY`로만 읽는다. 코드·테스트·fixture·로그에 키 문자열을 넣지 않는다. 미설정이면 즉시 `RuntimeError("DATA_GO_KR_SERVICE_KEY not configured")`.
- 브라우저는 API를 호출하지 않는다. `web/`는 `../data/*.json`만 fetch 한다.
- 하루 호출 상한: 서비스별 100건. 클라이언트가 호출 횟수를 세고 `meta.json`에 기록한다.
- 조달청 API 날짜 범위는 1회 호출당 1개월 이내. `inqryBgnDt/inqryEndDt` 형식 `YYYYMMDDHHMM`. 국토교통부 공동주택 API는 `startDate/endDate` 형식 `YYYYMMDD`.
- 모든 저장은 새 객체 생성 후 임시파일 → `os.replace`. 기존 dict/list를 제자리에서 수정하지 않는다.
- 파일 800줄·함수 50줄 이하. 서비스 1개 = 소스 파일 1개.
- 지역 명칭 정규화: 광주광역시·전라남도·전남광주통합특별시 → `전남광주`; 전라북도·전북특별자치도 → `전북`; 강원도·강원특별자치도 → `강원`. 지역 목록(16): 서울, 부산, 대구, 인천, 대전, 울산, 세종, 경기, 강원, 충북, 충남, 전북, 전남광주, 경북, 경남, 제주. 그 외는 `미분류`.
- 날짜·시각 문자열은 저장 시 ISO `YYYY-MM-DDTHH:MM` (KST, 타임존 표기 없음). 날짜만 있으면 `T00:00`.
- 테스트는 실제 네트워크를 쓰지 않는다. HTTP는 모두 가짜 세션으로 대체.
- 커밋 메시지는 `<type>: <description>` + 끝에 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` 과 `Claude-Session: https://claude.ai/code/session_01TnuMWLncKRAS3VmzcC8c3J`.

## Review Focus

1. **API 응답이 `items`를 dict 1개(단건)나 빈 문자열로 돌려주는 경우** — 조달청 API는 결과 1건이면 `items`가 리스트가 아닐 수 있고, 0건이면 `""`다. 클라이언트는 항상 `list[dict]`를 돌려줘야 한다. → Task 6 테스트 `test_get_items_single_dict_and_empty_string`.
2. **같은 공고번호의 변경·취소 공고가 등록된 경우** — 차수(`bidNtceOrd`)가 올라가며 다시 들어온다. 기존 낙찰 정보·최초수집일은 유지하고 마감일·공고명은 새 값으로 바뀌어야 하며, 공고종류에 "취소"가 있으면 상태 `cancelled`. → Task 5 테스트 `test_merge_reissue_keeps_first_seen_and_history`, `test_merge_cancel_kind_sets_cancelled`.
3. **마감일·개찰일이 비어 있는 공고** — 캘린더·D-n·상태 전이는 `None`을 깨지지 않고 건너뛰어야 한다. → Task 5 `test_derive_status_without_dates_is_open`, Task 13 `test_build_month_grid_skips_events_without_date`.
4. **금액 필드가 `"1,200,000"`·`""`·`"0"`으로 오는 경우** — 정수 변환 실패 시 `None`, 0은 `None`으로 취급해 화면에 "-"로 표시. → Task 7 `test_parse_amount_variants`.
5. **수집이 중간에 실패한 날** — 일부 서비스만 실패해도 성공한 서비스 결과는 저장하고, `meta.json`에 서비스별 오류를 남기고, 화면 상단 배지가 빨간색으로 바뀌어야 한다. → Task 11 `test_run_records_partial_failure`, Task 12 `test_status_badge_class_for_failed_meta`.

---

## 파일 구조

```
bid-dashboard/
├─ collector/
│  ├─ __init__.py
│  ├─ config.py            Config 로딩(frozen dataclass)
│  ├─ config.yaml          키워드·제외어·관심지역·기관목록·보존기간·백필
│  ├─ model.py             Notice / Award / Meta dataclass + to_dict/from_dict
│  ├─ windows.py           날짜 범위를 월 단위 창으로 분할
│  ├─ main.py              오케스트레이션 + CLI
│  ├─ rules/
│  │  ├─ __init__.py
│  │  ├─ keywords.py       matches_keywords
│  │  ├─ region.py         normalize_region / region_from_institution / region_from_kapt / parse_amount
│  │  ├─ interest.py       judge_interest
│  │  └─ status.py         derive_status
│  ├─ store/
│  │  ├─ __init__.py
│  │  ├─ json_store.py     load_json / save_json(원자적) / load_notices / load_awards
│  │  └─ merge.py          merge_notices / attach_awards / apply_retention
│  └─ sources/
│     ├─ __init__.py
│     ├─ client.py         DataGoClient (페이지네이션·에러코드·호출수)
│     ├─ nara_bids.py      나라장터 용역 공고 + 참가가능지역
│     ├─ nara_awards.py    나라장터 용역 낙찰·개찰결과
│     ├─ kapt_bids.py      공동주택 입찰공고
│     └─ kapt_results.py   공동주택 입찰결과·참여업체
├─ tests/                  pytest, fixtures/*.json
├─ web/
│  ├─ index.html
│  ├─ css/style.css
│  ├─ assets/korea-sido.svg
│  └─ js/
│     ├─ app.js            탭 라우팅·공통 필터 상태·상태 배지
│     ├─ data.js           JSON 로드
│     ├─ lib/format.js     금액·날짜·D-day·상태 라벨 (순수 함수, 테스트)
│     ├─ lib/filter.js     트랙/관심지역/검색 필터 (순수 함수, 테스트)
│     ├─ lib/calendar.js   월 그리드 생성 (순수 함수, 테스트)
│     ├─ lib/csv.js        CSV 직렬화 (순수 함수, 테스트)
│     ├─ lib/stats.js      KPI·지역 집계·낙찰 요약 (순수 함수, 테스트)
│     └─ views/            dashboard.js calendar.js map.js awards.js detail.js
├─ tools/build_map.py      TopoJSON → korea-sido.svg 변환(1회성)
├─ data/                   notices.json awards.json meta.json
├─ .github/workflows/daily.yml
├─ requirements.txt  pyproject.toml(pytest 설정)  package.json(node --test)  .gitignore  README.md
└─ docs/superpowers/{specs,plans}/
```

---

### Task 1: 저장소 골격 + 설정 로더

**Files:**
- Create: `collector/__init__.py`, `collector/config.py`, `collector/config.yaml`, `requirements.txt`, `pyproject.toml`, `.gitignore`, `README.md`(제목·한 줄 설명만)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` frozen dataclass: `public_keywords: tuple[str,...]`, `public_exclude: tuple[str,...]`, `apt_keywords: tuple[str,...]`, `apt_regions: tuple[str,...]`, `interest_home_regions: tuple[str,...]`, `interest_limit_regions: tuple[str,...]`, `interest_institutions: tuple[str,...]`, `retention_days: int`, `backfill_days: int`, `lookback_days: int`, `award_lookback_days: int`, `award_weekly_lookback_days: int`, `max_calls_per_service: int`. `load_config(path: Path) -> Config`.
- config.yaml 값(스펙 5.1·5.2·5.3): public_keywords = [회계, 세무, 재무, 실사, 평가, 감사, 결산, 원가, 자산재평가, 타당성, 사업성]; public_exclude = [안전평가, 안전점검, 환경영향평가, 교통영향평가, 성능평가, 내진성능, 정밀안전, 구조안전, 건축물 평가, 소방, 시설물]; apt_keywords = [회계감사, 외부회계감사, 회계, 세무, 결산, 장기수선충당금 검토]; apt_regions = [전남광주, 전북]; interest_home_regions = [전남광주]; interest_limit_regions = [전남광주, 광주, 전남, 전북, 호남]; interest_institutions = 스펙 5.3의 25개 기관명; retention_days 730; backfill_days 90; lookback_days 3; award_lookback_days 7; award_weekly_lookback_days 60; max_calls_per_service 100.

- [ ] **Step 1: 로컬 git 초기화 및 기본 파일**

```bash
cd "C:\Users\정상현.AzureAD\Desktop\RPA\공공입찰"
git init -b main
```
`.gitignore`: `.env`, `__pycache__/`, `.pytest_cache/`, `node_modules/`, `*.pyc`, `.venv/`.
`requirements.txt`: `requests>=2.32`, `pyyaml>=6.0`, `pytest>=8`.
`pyproject.toml`: `[tool.pytest.ini_options] testpaths=["tests"] pythonpath=["."]`.

- [ ] **Step 2: 실패하는 테스트 작성** `tests/test_config.py`

```python
from pathlib import Path
from collector.config import load_config

def test_load_default_config():
    cfg = load_config(Path("collector/config.yaml"))
    assert "회계" in cfg.public_keywords
    assert "환경영향평가" in cfg.public_exclude
    assert cfg.apt_regions == ("전남광주", "전북")
    assert cfg.interest_home_regions == ("전남광주",)
    assert "호남" in cfg.interest_limit_regions
    assert "한전KDN" in cfg.interest_institutions
    assert cfg.retention_days == 730 and cfg.backfill_days == 90
    assert cfg.max_calls_per_service == 100

def test_config_is_immutable():
    cfg = load_config(Path("collector/config.yaml"))
    import dataclasses, pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.retention_days = 1
```

- [ ] **Step 3: 실패 확인** — `python -m pytest tests/test_config.py -v` → ModuleNotFoundError
- [ ] **Step 4: `collector/config.yaml`과 `load_config` 구현** (yaml.safe_load → 리스트는 tuple로 변환해 frozen dataclass 생성)
- [ ] **Step 5: 통과 확인** — `python -m pytest tests/test_config.py -v` → 2 passed
- [ ] **Step 6: GitHub 저장소 생성(사용자 승인됨) 및 첫 커밋**

```bash
git add -A && git commit -m "chore: scaffold collector config and project files"
gh repo create wg5809-beep/bid-dashboard --public --source=. --push --description "회계법인 용역 공공입찰 대시보드 (나라장터·K-apt 일일 수집)"
```

---

### Task 2: 키워드 매칭 규칙

**Files:**
- Create: `collector/rules/__init__.py`, `collector/rules/keywords.py`
- Test: `tests/test_keywords.py`

**Interfaces:**
- Produces: `matches_keywords(title: str, include: Sequence[str], exclude: Sequence[str]) -> bool`. 공백 제거 후 부분일치. include 중 하나라도 포함 AND exclude 중 아무것도 포함하지 않으면 True. 제외어 "건축물 평가"처럼 공백 포함 제외어는 공백 제거 후 비교.

- [ ] **Step 1: 실패하는 테스트**

```python
import pytest
from collector.rules.keywords import matches_keywords
INC = ["회계", "평가", "감사"]; EXC = ["환경영향평가", "건축물 평가"]

@pytest.mark.parametrize("title,expected", [
    ("2026년 외부회계감사 용역", True),
    ("○○댐 환경영향평가 용역", False),
    ("노후 건축물 평가 용역", False),
    ("청소 용역 사업자 선정", False),
    ("자산 재 평가 용역", True),  # 공백 무시
    ("", False),
])
def test_matches_keywords(title, expected):
    assert matches_keywords(title, INC, EXC) is expected
```

- [ ] **Step 2: 실패 확인** `python -m pytest tests/test_keywords.py -v`
- [ ] **Step 3: 구현**
- [ ] **Step 4: 통과 확인** → 6 passed
- [ ] **Step 5: Commit** `feat: keyword include/exclude matching`

---

### Task 3: 지역 정규화·추출 + 금액 파싱

**Files:**
- Create: `collector/rules/region.py`
- Test: `tests/test_region.py`

**Interfaces:**
- Produces:
  - `REGIONS: tuple[str,...]` 16개(Global Constraints 순서), `UNCLASSIFIED = "미분류"`.
  - `normalize_region(name: str | None) -> str | None` — 정식명·약칭·구명칭을 16개 중 하나로. 매칭 없으면 None. "호남"은 None(지역이 아니라 묶음) — 관심지역 판정에서 별도 처리.
  - `region_from_institution(name: str | None) -> str | None` — 기관명 안의 시도명/광역시명/시군명 사전으로 추출. 사전은 모듈 상수 `INSTITUTION_HINTS: dict[str, str]`(예: "광주"→전남광주, "나주"→전남광주, "전주"→전북, "익산"→전북, "춘천"→강원, "수원"→경기 …). 최소 17개 시도 명칭 + 각 시도 주요 시·군 명칭 포함. 주의: "광주"는 경기 광주시와 충돌하므로 "광주시"가 포함되고 "광주광역시"가 아니면 경기로 판정.
  - `region_from_kapt(title: str | None, bid_area: str | int | None) -> str | None` — 공고명 접두어 `[경기]` 우선, 없으면 `bid_area` 앞 2자리 코드 사전 `SIDO_CODE = {11:서울,26:부산,27:대구,28:인천,29:전남광주,30:대전,31:울산,36:세종,41:경기,42:강원,51:강원,43:충북,44:충남,45:전북,52:전북,46:전남광주,47:경북,48:경남,50:제주}`.
  - `parse_amount(value) -> int | None` — 쉼표·공백 제거, 숫자 아님/빈값/0 → None.

- [ ] **Step 1: 실패하는 테스트**

```python
import pytest
from collector.rules.region import (normalize_region, region_from_institution,
    region_from_kapt, parse_amount, REGIONS)

def test_regions_has_16():
    assert len(REGIONS) == 16 and "전남광주" in REGIONS and "광주" not in REGIONS

@pytest.mark.parametrize("name,expected", [
    ("광주광역시", "전남광주"), ("전라남도", "전남광주"), ("전남광주통합특별시", "전남광주"),
    ("전라북도", "전북"), ("전북특별자치도", "전북"), ("강원특별자치도", "강원"),
    ("서울특별시", "서울"), ("경기도", "경기"), ("호남", None), ("", None), (None, None)])
def test_normalize_region(name, expected):
    assert normalize_region(name) == expected

@pytest.mark.parametrize("inst,expected", [
    ("광주광역시 북구", "전남광주"), ("나주시", "전남광주"), ("전주시청", "전북"),
    ("경기도 광주시", "경기"), ("한국전력공사", None), ("강원특별자치도교육청", "강원")])
def test_region_from_institution(inst, expected):
    assert region_from_institution(inst) == expected

@pytest.mark.parametrize("title,area,expected", [
    ("[경기] 청소용역", None, "경기"), ("[전남광주] 외부회계감사", None, "전남광주"),
    ("회계감사 용역", "2900000000", "전남광주"), ("회계감사 용역", 4600000000, "전남광주"),
    ("회계감사 용역", "5200000000", "전북"), ("회계감사 용역", None, None)])
def test_region_from_kapt(title, area, expected):
    assert region_from_kapt(title, area) == expected

@pytest.mark.parametrize("v,expected", [("1,200,000", 1200000), ("", None), ("0", None),
    (None, None), ("abc", None), (350000, 350000), ("12000000.00", 12000000)])
def test_parse_amount_variants(v, expected):
    assert parse_amount(v) == expected
```

- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 구현** — `INSTITUTION_HINTS`는 긴 키부터 매칭(정렬: 길이 내림차순)해 "광주광역시"가 "광주"보다 먼저 잡히게 한다.
- [ ] **Step 4: 통과 확인**
- [ ] **Step 5: Commit** `feat: region normalization and amount parsing`

---

### Task 4: 관심지역 판정

**Files:**
- Create: `collector/rules/interest.py`
- Test: `tests/test_interest.py`

**Interfaces:**
- Consumes: `Config`(Task 1), `normalize_region`, `region_from_institution`(Task 3).
- Produces: `judge_interest(agency: str|None, demand_agency: str|None, region: str|None, limit_regions: Sequence[str], cfg: Config) -> tuple[bool, str|None]`. 반환 reason 값은 정확히 `"본사 소재"` 또는 `"지역제한"` 또는 None. 판정 순서: ① `region`(이미 판정된 공고 지역) 또는 기관명에서 뽑은 지역이 `cfg.interest_home_regions`에 있거나, 기관명/수요기관명이 `cfg.interest_institutions` 중 하나를 포함 → (True, "본사 소재"); ② `limit_regions` 각 항목을 normalize 하거나 원문 그대로 비교해 `cfg.interest_limit_regions`(전남광주·광주·전남·전북·호남)와 겹치면 → (True, "지역제한"); ③ (False, None).

- [ ] **Step 1: 실패하는 테스트**

```python
from pathlib import Path
from collector.config import load_config
from collector.rules.interest import judge_interest
CFG = load_config(Path("collector/config.yaml"))

def test_home_region_by_region():
    assert judge_interest("나주시", None, "전남광주", [], CFG) == (True, "본사 소재")

def test_home_region_by_institution_list():
    assert judge_interest("한국전력공사", None, None, [], CFG) == (True, "본사 소재")

def test_limit_region_honam():
    assert judge_interest("환경부", "환경부", None, ["호남권"], CFG) == (True, "지역제한")

def test_limit_region_jeonbuk_name():
    assert judge_interest("조달청", "전주시", None, ["전라북도"], CFG) == (True, "지역제한")

def test_jeonbuk_home_without_limit_is_not_interest():
    assert judge_interest("전주시", "전주시", "전북", [], CFG) == (False, None)

def test_other_region():
    assert judge_interest("서울특별시", None, "서울", ["서울특별시"], CFG) == (False, None)
```

- [ ] **Step 2: 실패 확인** / **Step 3: 구현** / **Step 4: 통과 확인**
- [ ] **Step 5: Commit** `feat: interest region judgment (home vs limit)`

---

### Task 5: 데이터 모델 + JSON 저장소 + 병합·상태 전이

**Files:**
- Create: `collector/model.py`, `collector/store/__init__.py`, `collector/store/json_store.py`, `collector/store/merge.py`, `collector/rules/status.py`
- Test: `tests/test_model_store.py`, `tests/test_merge.py`, `tests/test_status.py`

**Interfaces:**
- Produces (`model.py`, 모두 `@dataclass(frozen=True)`):
  - `Notice(key: str, track: str, notice_no: str, notice_ord: str, title: str, agency: str|None, demand_agency: str|None, agency_code: str|None, posted_at: str|None, close_at: str|None, open_at: str|None, budget: int|None, estimate: int|None, contract_method: str|None, award_method: str|None, kind: str|None, limit_regions: tuple[str,...], region: str, interest: bool, interest_reason: str|None, url: str|None, status: str, first_seen: str, last_seen: str, history: tuple[dict,...] = (), complex_name: str|None = None, source_system: str|None = None, result_note: str|None = None)`. `track`은 `"public"` | `"apt"`. key 규칙: public → `f"public:{notice_no}"` (차수는 필드로 보존, 같은 공고번호는 한 레코드), apt → `f"apt:{bidNum}"`.
  - `Award(key: str, notice_no: str, notice_ord: str, track: str, winner: str|None, winner_bizno: str|None, winner_ceo: str|None, amount: int|None, planned_price: int|None, rate: float|None, participants: int|None, opened_at: str|None, awarded_at: str|None, title: str, agency: str|None, region: str, interest: bool)`.
  - `Meta(run_at: str, ok: bool, calls: dict[str,int], new_notices: int, updated_notices: int, new_awards: int, errors: tuple[str,...], notice_count: int, award_count: int)`.
  - 각 클래스에 `to_dict() -> dict`, `@classmethod from_dict(d) -> Self`; `dataclasses.replace`로 갱신.
  - 상태 문자열 상수 `STATUS = ("open","closed","opened","awarded","failed","rebid","cancelled","unknown")`.
- Produces (`json_store.py`): `load_json(path: Path, default)`, `save_json(path: Path, obj) -> None`(tmp + os.replace, `ensure_ascii=False, indent=1, sort_keys=True`), `load_notices(path) -> dict[str, Notice]`, `save_notices(path, notices: Mapping[str, Notice])`, 동일하게 `load_awards/save_awards(dict[str, Award])`. notices.json 형태: `{"items": [notice dict...]}`.
- Produces (`status.py`): `derive_status(notice: Notice, award: Award|None, now: datetime, result_note: str|None) -> str`. 규칙: kind에 "취소" → cancelled; award 있음 → awarded; result_note "유찰" → failed, "재입찰" → rebid; open_at 있고 now > open_at + 60일 → unknown; open_at 있고 now > open_at → opened; close_at 있고 now > close_at → closed; 그 외 open.
- Produces (`merge.py`):
  - `merge_notices(existing: Mapping[str,Notice], incoming: Iterable[Notice], today: str) -> tuple[dict[str,Notice], int, int]` → (병합결과, 신규수, 갱신수). 같은 key가 있으면 incoming의 공고 필드로 교체하되 `first_seen`·`interest`(둘 중 True)·`history`(이전 title/close_at/open_at/kind/notice_ord를 dict로 append)·`result_note`는 기존 유지, `last_seen=today`. 차수가 같고 바뀐 필드가 없으면 갱신으로 세지 않는다.
  - `attach_awards(notices, awards: Mapping[str,Award], now) -> dict[str,Notice]` → 모든 notice의 status를 `derive_status`로 재계산.
  - `apply_retention(notices, now, days) -> dict[str,Notice]` → posted_at이 days 이전인 것 제거. awards는 건드리지 않는다.

- [ ] **Step 1: 실패하는 테스트** `tests/test_model_store.py`

```python
def test_notice_roundtrip(tmp_path):  # to_dict/from_dict/save/load 왕복, limit_regions tuple 유지
def test_save_json_is_atomic_and_utf8(tmp_path):  # 한글이 \u 이스케이프 없이 저장, tmp 파일 잔존 없음
```
`tests/test_status.py`

```python
# now = 2026-11-02T09:00
def test_derive_status_open_before_close()
def test_derive_status_closed_after_close_before_open()
def test_derive_status_opened_after_open()
def test_derive_status_unknown_after_60_days()
def test_derive_status_awarded_when_award_present()
def test_derive_status_cancelled_by_kind()   # kind="취소공고"
def test_derive_status_failed_and_rebid_by_result_note()
def test_derive_status_without_dates_is_open()
```
`tests/test_merge.py`

```python
def test_merge_new_notice_counts_as_new()
def test_merge_reissue_keeps_first_seen_and_history():
    # 기존 ord "000", close 2026-11-10 → incoming ord "001", close 2026-11-17
    # 결과: notice_ord "001", close_at 새 값, first_seen 유지, history[0]["close_at"]=="2026-11-10T00:00", 갱신수 1
def test_merge_unchanged_not_counted()
def test_merge_cancel_kind_sets_cancelled()  # attach_awards 후 status == "cancelled"
def test_attach_awards_marks_awarded_and_keeps_others()
def test_apply_retention_removes_old_keeps_recent()
def test_merge_does_not_mutate_inputs()  # 입력 dict id/내용 불변
```

- [ ] **Step 2: 실패 확인** `python -m pytest tests/test_model_store.py tests/test_status.py tests/test_merge.py -v`
- [ ] **Step 3: 구현** (`model.py` → `json_store.py` → `status.py` → `merge.py` 순)
- [ ] **Step 4: 통과 확인** → 전부 passed
- [ ] **Step 5: Commit** `feat: notice/award model, atomic json store, merge and status rules`

---

### Task 6: 공공데이터포털 HTTP 클라이언트

**Files:**
- Create: `collector/sources/__init__.py`, `collector/sources/client.py`
- Test: `tests/test_client.py`, `tests/fakes.py`(FakeSession)

**Interfaces:**
- Produces:
  - `class DataGoError(Exception)`: 속성 `code: str`, `service: str`.
  - `class DataGoClient`: `__init__(self, service_key: str, session=None, max_calls_per_service: int = 100, sleep: Callable[[float],None] = time.sleep)`. `service_key`가 빈 문자열이면 `RuntimeError("DATA_GO_KR_SERVICE_KEY not configured")`.
  - `get_items(self, service: str, base_url: str, op: str, params: dict, page_size: int = 500, json_param: str = "type") -> list[dict]` — `pageNo`를 1부터 올리며 `totalCount`까지 수집. `json_param`은 조달청 `type=json`, 국토교통부 `_type=json`. 응답 파싱: `resp.json()["response"]["header"]["resultCode"]`가 `"00"`이 아니고 `"03"`도 아니면 `DataGoError`. `body.items`가 dict이면 `[dict]`, `""`/None이면 `[]`, `{"item": [...]}` 형태면 그 안의 리스트. 서비스별 호출 수 `self.calls: dict[str,int]`; 한도 초과 시 `DataGoError(code="LOCAL_LIMIT")`. 429/5xx와 resultCode 05는 최대 3회 지수 백오프(0.6s 기준) 재시도.
  - `tests/fakes.py`: `FakeSession(responses: list[dict|Exception])` — `get(url, params, timeout)` 호출마다 순서대로 응답 객체(`.status_code`, `.json()`) 반환하고 `calls`에 (url, params) 기록.

- [ ] **Step 1: 실패하는 테스트**

```python
def test_requires_key(): RuntimeError
def test_get_items_paginates_until_total():  # totalCount 3, page_size 2 → 2회 호출, 3건
def test_get_items_single_dict_and_empty_string():  # items=dict → 1건, items="" → 0건
def test_result_code_03_is_empty()
def test_result_code_22_raises_with_code()
def test_local_call_limit():  # max_calls_per_service=1, 두 번째 호출에서 DataGoError code LOCAL_LIMIT
def test_retry_on_500_then_success():  # sleep은 가짜로 기록만
def test_service_key_not_in_logged_params():  # FakeSession.calls의 params에 serviceKey가 들어가되, repr/str(client)에 키 미노출
```

- [ ] **Step 2: 실패 확인** / **Step 3: 구현** (`requests.Session.get(url, params=..., timeout=30)`; serviceKey는 params에 원본 그대로 넣어 requests가 1회 인코딩) / **Step 4: 통과 확인**
- [ ] **Step 5: Commit** `feat: data.go.kr client with pagination, error codes, call budget`

---

### Task 7: 나라장터 용역 공고 소스

**Files:**
- Create: `collector/sources/nara_bids.py`, `tests/fixtures/nara_bid_item.json`, `tests/fixtures/nara_region_item.json`
- Test: `tests/test_nara_bids.py`

**Interfaces:**
- Consumes: `DataGoClient.get_items`, `matches_keywords`, `region_from_institution`, `normalize_region`, `parse_amount`, `judge_interest`, `Notice`.
- Produces:
  - 상수 `BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"`, `SERVICE = "nara_bids"`.
  - `fetch_service_notices(client, begin: datetime, end: datetime, keywords: Sequence[str]) -> list[dict]` — 키워드마다 `getBidPblancListInfoServcPPSSrch`에 `inqryDiv="1"`, `inqryBgnDt/inqryEndDt`(`%Y%m%d%H%M`), `bidNtceNm=keyword` 로 호출, `bidNtceNo` 기준 중복 제거(차수 큰 것 유지).
  - `fetch_region_limits(client, begin, end) -> dict[str, tuple[str,...]]` — `getBidPblancListInfoPrtcptPsblRgn`(`inqryDiv="1"`, 같은 범위) 결과를 `bidNtceNo` → 참가가능지역명 튜플(`prtcptPsblRgnNm`)로. 응답 필드명이 다르면 첫 실행 로그로 확인해 상수 `REGION_FIELD`만 바꾼다.
  - `to_notice(raw: dict, limit_regions: tuple[str,...], cfg: Config, today: str) -> Notice`. 필드 매핑: `bidNtceNo→notice_no`, `bidNtceOrd→notice_ord`, `bidNtceNm→title`, `ntceInsttNm→agency`, `dminsttNm→demand_agency`, `ntceInsttCd→agency_code`, `bidNtceDt→posted_at`, `bidClseDt→close_at`, `opengDt→open_at`, `asignBdgtAmt→budget`, `presmptPrce→estimate`, `cntrctCnclsMthdNm→contract_method`, `sucsfbidMthdNm→award_method`, `ntceKindNm→kind`, `bidNtceDtlUrl→url`(없으면 `https://www.g2b.go.kr` 로 대체). 날짜 문자열 `"2026-11-02 14:00:00"` → `"2026-11-02T14:00"`. region: limit_regions 첫 항목 normalize → 없으면 `region_from_institution(demand_agency) or region_from_institution(agency)` → 없으면 `"미분류"`. interest는 `judge_interest(agency, demand_agency, region, limit_regions, cfg)`. status 초기값 `"open"`, first_seen=last_seen=today.
  - `collect_public(client, cfg, windows: list[tuple[datetime,datetime]], today) -> list[Notice]` — 창마다 fetch 2종 → 키워드 필터(`matches_keywords(title, cfg.public_keywords, cfg.public_exclude)`) → to_notice.

- [ ] **Step 1: fixture 작성** — `nara_bid_item.json`에 위 필드명을 가진 항목 2개(하나는 "나주시 2026년 결산 외부회계감사 용역", 하나는 "○○ 환경영향평가 용역"), `nara_region_item.json`에 `{"bidNtceNo":"R26BK00000001","bidNtceOrd":"000","prtcptPsblRgnNm":"전남광주통합특별시"}`.
- [ ] **Step 2: 실패하는 테스트**

```python
def test_to_notice_maps_fields_and_dates()      # close_at == "2026-11-16T14:00", budget int, key "public:R26BK00000001"
def test_to_notice_region_from_limit_first()     # limit ("전남광주통합특별시",) → region 전남광주, interest True, reason "지역제한"? → 주의: 기관이 나주시면 "본사 소재"가 먼저. 테스트는 기관 "조달청"으로.
def test_to_notice_region_from_institution_when_no_limit()
def test_collect_public_filters_exclude_words()  # FakeSession으로 2건 응답 → 환경영향평가 제외 → 1건
def test_fetch_service_notices_dedupes_by_notice_no_keeping_higher_ord()
def test_parse_amount_variants_in_notice()       # asignBdgtAmt "0" → budget None
```

- [ ] **Step 3: 실패 확인** / **Step 4: 구현** / **Step 5: 통과 확인**
- [ ] **Step 6: Commit** `feat: nara service bid source with region-limit join`

---

### Task 8: 나라장터 낙찰·개찰결과 소스

**Files:**
- Create: `collector/sources/nara_awards.py`, `tests/fixtures/nara_award_item.json`, `tests/fixtures/nara_openg_item.json`
- Test: `tests/test_nara_awards.py`

**Interfaces:**
- Produces:
  - `BASE = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"`, `SERVICE = "nara_awards"`.
  - `fetch_awards(client, begin, end) -> list[dict]` — `getScsbidListSttusServcPPSSrch`, `inqryDiv="3"`(개찰일시) 범위. 첫 실행에서 resultCode 10이 나오면 `inqryDiv="2"`로 바꾼다(상수 `AWARD_INQRY_DIV`).
  - `fetch_openg_results(client, begin, end) -> list[dict]` — `getOpengResultListInfoServcPPSSrch`, 같은 범위, `numOfRows` 50 이하(응답 느림).
  - `to_award(raw: dict, notice: Notice) -> Award` — `bidwinnrNm→winner`, `bidwinnrBizno→winner_bizno`, `bidwinnrCeoNm→winner_ceo`, `sucsfbidAmt→amount`, `presmptPrce→planned_price`, `sucsfbidRate→rate(float)`, `prtcptCnum→participants(int)`, `rlOpengDt→opened_at`, `fnlSucsfDate→awarded_at`; title/agency/region/interest/track은 notice에서 복제.
  - `match_awards(raws: list[dict], notices: Mapping[str,Notice]) -> dict[str, Award]` — key `public:{bidNtceNo}`가 notices에 있는 것만.
  - `result_notes(openg_raws: list[dict], notices) -> dict[str, str]` — `progrsDivCdNm`이 "유찰"/"재입찰"을 포함하면 해당 key → 그 문자열.
  - `pending_award_keys(notices, now) -> list[str]` — status가 closed/opened/unknown이고 track public인 것.

- [ ] **Step 1: fixture** (낙찰 1건 `R26BK00000001`, 개찰결과 1건 유찰 `R26BK00000002`)
- [ ] **Step 2: 실패하는 테스트**

```python
def test_to_award_maps_and_copies_notice_fields()   # rate 88.123 float, participants 5
def test_match_awards_ignores_unknown_notice()
def test_result_notes_detects_failed_and_rebid()
def test_pending_award_keys_excludes_open_and_awarded()
def test_fetch_awards_uses_openg_date_div_and_window_format()  # FakeSession.calls[0].params["inqryDiv"]=="3", inqryBgnDt len 12
```

- [ ] **Step 3: 실패 확인** / **Step 4: 구현** / **Step 5: 통과 확인**
- [ ] **Step 6: Commit** `feat: nara award and opening-result source`

---

### Task 9: 공동주택(K-apt) 입찰공고 소스

**Files:**
- Create: `collector/sources/kapt_bids.py`, `tests/fixtures/kapt_bid_item.json`
- Test: `tests/test_kapt_bids.py`

**Interfaces:**
- Produces:
  - `BASE = "https://apis.data.go.kr/1613000/ApHusBidPblAncInfoOfferServiceV3"`, `SERVICE = "kapt_bids"`, `DETAIL_URL = "https://www.k-apt.go.kr/bid/bidDetail.do?bidNum={bidNum}"`.
  - 코드표 상수: `BID_STATE = {"1":"신규공고","2":"수정공고","3":"재공고"}`, `CODE_AUTH = {"01":"K-APT","02":"조달청","03":"아파트비드포유","04":"KG2B전자입찰","05":"나이스아파트","06":"이 아파트","99":"기타민간업체"}`, `CODE_KIND = {"01":"일반경쟁","02":"제한경쟁","03":"지명경쟁"}`, `CODE_SUC_WAY = {"01":"최저(고) 낙찰","02":"적격심사","03":"최저 낙찰","04":"최고 낙찰","05":"적격심사(최저)","06":"적격심사(최고)"}`.
  - `fetch_kapt_notices(client, begin: date, end: date) -> list[dict]` — `getPblAncDeSearchV3`에 `startDate/endDate`(`%Y%m%d`), `json_param="_type"`.
  - `to_notice(raw, cfg, today) -> Notice` — `bidNum→notice_no`(ord `"0"`), `bidTitle→title`, `bidKaptname→agency`와 `complex_name`, `bidRegDate→posted_at`, `bidDeadline→close_at`, `open_at=None`, `kind=BID_STATE[bidState]`, `contract_method=CODE_KIND[codeKind]`, `award_method=CODE_SUC_WAY[codeSucWay]`, `source_system=CODE_AUTH[codeAuth]`, `url=DETAIL_URL`, region=`region_from_kapt(bidTitle, bidArea) or "미분류"`, limit_regions=(), interest=`judge_interest(agency, None, region, (), cfg)` (아파트는 지역이 전남광주면 "본사 소재").
  - `collect_apt(client, cfg, windows: list[tuple[date,date]], today) -> list[Notice]` — 공고명 키워드 필터(`cfg.apt_keywords`, 제외어 없음) AND `region in cfg.apt_regions`.

- [ ] **Step 1: fixture** — 3건: `[전남광주] 2026년 외부회계감사 용역`(bidArea 2900000000), `[경기] 외부회계감사`(4100000000), `[전북] 청소용역`(5200000000).
- [ ] **Step 2: 실패하는 테스트**

```python
def test_to_notice_apt_fields_and_url()          # key "apt:<bidNum>", url에 bidNum, kind "신규공고", interest (True,"본사 소재")
def test_collect_apt_filters_region_and_keyword() # 3건 → 1건
def test_fetch_uses_yyyymmdd_and__type_json()      # params startDate len 8, "_type"=="json"
```

- [ ] **Step 3: 실패 확인** / **Step 4: 구현** / **Step 5: 통과 확인**
- [ ] **Step 6: Commit** `feat: k-apt bid source filtered to Honam and accounting keywords`

---

### Task 10: 공동주택 입찰결과 소스

**Files:**
- Create: `collector/sources/kapt_results.py`, `tests/fixtures/kapt_result_item.json`, `tests/fixtures/kapt_entrps_item.json`
- Test: `tests/test_kapt_results.py`

**Interfaces:**
- Produces:
  - `BASE = "https://apis.data.go.kr/1613000/ApHusBidResultNoticeInfoOfferServiceV3"`, `SERVICE = "kapt_results"`.
  - `fetch_results_by_posted(client, begin: date, end: date) -> list[dict]` — `getPblAncDeSearchV3`(`startDate/endDate`, `_type=json`).
  - `fetch_participants(client, bid_num: str) -> list[dict]` — `getBidEntrpsInfoSearchV3(bidNum=...)`. 하루 최대 `cfg.max_calls_per_service` 안에서 pending 수만큼.
  - `to_award(raw: dict, notice: Notice, participants: list[dict]) -> Award` — `amount→amount`, winner = participants 중 `bidSuccessfulYn`이 `Y`(또는 "낙찰"로 시작)인 항목의 `companyName`, participants 수 → `participants`, `bidRegdate/bidRegDate→awarded_at`, opened_at=`notice.close_at`.
  - `match_results(raws, notices) -> dict[str, dict]` — key `apt:{bidNum}`이 notices에 있고 상태가 closed/opened/unknown인 것만.
  - `result_note_from_state(raw) -> str|None` — `bidState` `"4"`→"유찰", `"6"`→"취소", `"9"/"10"`→"낙찰무효"; 그 외 None.

- [ ] **Step 1: fixture** / **Step 2: 실패하는 테스트**

```python
def test_to_award_picks_winner_from_participants()
def test_to_award_without_winner_keeps_amount_and_none_winner()
def test_match_results_only_pending_known_notices()
def test_result_note_from_state()
```

- [ ] **Step 3: 실패 확인** / **Step 4: 구현** / **Step 5: 통과 확인**
- [ ] **Step 6: Commit** `feat: k-apt result and participant source`

---

### Task 11: 날짜 창 분할 + 오케스트레이터 + CLI

**Files:**
- Create: `collector/windows.py`, `collector/main.py`
- Test: `tests/test_windows.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: Task 1~10 전부.
- Produces:
  - `month_windows(begin: datetime, end: datetime) -> list[tuple[datetime,datetime]]` — 각 창 길이 ≤ 30일, 연속·비중첩, 마지막 창 end == end.
  - `run(cfg: Config, client: DataGoClient, data_dir: Path, now: datetime, backfill: bool = False) -> Meta`:
    1. `today = now.strftime("%Y-%m-%d")`; 기존 notices/awards 로드.
    2. 공고 범위: backfill이면 `now - backfill_days`, 아니면 `now - lookback_days` ~ now. public은 `collect_public`, apt는 `collect_apt`. 각 소스를 `try/except DataGoError, requests.RequestException`으로 감싸 실패 시 `errors`에 `"{service}: {code} {msg}"` 추가하고 계속.
    3. `merge_notices` → 낙찰 범위: 일요일(`now.weekday()==6`)이거나 backfill이면 `award_weekly_lookback_days`, 아니면 `award_lookback_days`. public: `fetch_awards`+`fetch_openg_results` → `match_awards`/`result_notes`; apt: pending apt 공고의 posted_at 최소~최대를 월 창으로 → `fetch_results_by_posted` → `match_results` → 각 건 `fetch_participants`(호출 예산 내).
    4. awards는 기존 dict에 새 키만 추가(기존 낙찰 레코드는 덮어쓰지 않음). result_note는 notice에 `dataclasses.replace`.
    5. `attach_awards` → `apply_retention` → 저장 3종(notices, awards, meta). `Meta.ok = not errors`.
    6. 예외가 어디서 나도 `meta.json`은 기록된다(최상위 try/finally).
  - CLI: `python -m collector.main [--backfill] [--data-dir data] [--config collector/config.yaml]`. 키는 `os.environ["DATA_GO_KR_SERVICE_KEY"]`; `.env` 파일이 있으면 `KEY=VALUE` 줄을 읽어 환경에 없는 것만 채운다(외부 라이브러리 없이). 종료코드: errors 있으면 1.

- [ ] **Step 1: 실패하는 테스트** `tests/test_windows.py`

```python
def test_month_windows_single_short_range()
def test_month_windows_splits_90_days_into_3_or_4_contiguous()
```
`tests/test_main.py` — `tests/fakes.py`에 `FakeClient(get_items=lambda service, base_url, op, params, **kw: ...)` 추가. 서비스/op별로 fixture 리스트를 돌려주거나 `DataGoError`를 던지게 설정.

```python
def test_run_first_time_writes_three_files_and_counts()
def test_run_second_time_attaches_award_and_sets_awarded()
def test_run_records_partial_failure():   # nara_awards가 DataGoError(22) → meta.ok False, errors 1건, notices는 저장됨
def test_run_sunday_uses_weekly_award_window()  # FakeClient가 받은 inqryBgnDt가 60일 전
def test_run_writes_meta_even_if_store_raises(monkeypatch)
def test_cli_exit_code_1_on_errors(monkeypatch, tmp_path)
```

- [ ] **Step 2: 실패 확인** / **Step 3: 구현** (`main.py`가 50줄 함수 제한을 넘기면 `_collect_notices`, `_collect_awards_public`, `_collect_awards_apt`, `_persist`로 분리) / **Step 4: 통과 확인** — `python -m pytest -v` 전체 통과, `python -m pytest --cov=collector --cov-report=term-missing`(pytest-cov 추가) 80% 이상
- [ ] **Step 5: 통합 실행(키 필요)** — 프로젝트 폴더에 사용자가 만든 `.env`가 있을 때만: `python -m collector.main --backfill` → `data/meta.json`의 `ok`, `calls`, `notice_count` 확인하고 각 서비스 응답의 실제 필드명이 fixture와 다르면 소스 상수와 fixture를 고친 뒤 테스트 재실행. `.env`가 없으면 이 단계는 Task 17의 Actions 첫 실행으로 대체하고 그 사실을 보고한다.
- [ ] **Step 6: Commit** `feat: collector orchestration, windows, CLI`

---

### Task 12: 웹 앱 골격 + 공통 라이브러리 + 대시보드

**Files:**
- Create: `package.json`(`"scripts": {"test": "node --test web/js/lib/"}`, `"type": "module"`), `web/index.html`, `web/css/style.css`, `web/js/app.js`, `web/js/data.js`, `web/js/lib/format.js`, `web/js/lib/filter.js`, `web/js/lib/stats.js`, `web/js/views/dashboard.js`, `web/js/views/detail.js`
- Test: `web/js/lib/format.test.js`, `web/js/lib/filter.test.js`, `web/js/lib/stats.test.js`

**Interfaces:**
- `data.js`: `loadAll(base = "../data/") -> Promise<{notices: Notice[], awards: Award[], meta: Meta}>` — `fetch(base + "notices.json?v=" + Date.now())` 등 3개 병렬. 실패 시 `meta = {ok:false, errors:["데이터 로드 실패"]}`.
- `lib/format.js`: `formatAmount(n) -> string`("-" | "1,200만원" 단위 만원 반올림, 1억 이상 "1.2억원"), `formatDate(iso) -> "11/16(월)"`, `formatDateTime(iso) -> "11/16 14:00"`, `dday(iso, now) -> number|null`(일수, 과거는 음수), `ddayLabel(iso, now) -> "D-3"|"오늘"|"마감"|"-"`, `statusLabel(status) -> 한글`(open 공고중, closed 마감, opened 개찰완료, awarded 낙찰, failed 유찰, rebid 재입찰, cancelled 취소, unknown 결과미확인), `trackLabel(track)`(public 공공기관, apt 아파트), `regionLabel(region)`.
- `lib/filter.js`: `applyFilters(notices, {track: "all"|"public"|"apt", interestOnly: boolean, query: string, statuses?: string[]}) -> Notice[]` — query는 title/agency/demand_agency/complex_name 부분일치(공백 무시), 결과는 새 배열. `sortByClose(notices) -> Notice[]`(close_at 오름차순, null 마지막).
- `lib/stats.js`: `kpis(notices, awards, now) -> {newToday, closingIn7, interestOpen, openingThisWeek}`; `countByRegion(notices) -> Record<region, number>`(진행중 open/closed만); `awardSummary(awards) -> {count, avgRate, topWinners: [{name, count}]}`(상위 5).
- `app.js`: 해시 라우팅 `#dashboard|#calendar|#map|#awards`, 공통 필터 상태(트랙 토글·관심지역 토글·검색)를 모듈 상태 객체로 보관하고 변경 시 현재 뷰 `render(container, state)` 재호출. 상태 배지: `statusBadgeClass(meta, now) -> "ok"|"stale"|"fail"` (ok=meta.ok && run_at이 36시간 이내, stale=ok지만 36시간 초과, fail=!ok) — `lib/stats.js`에 두고 테스트.
- `views/dashboard.js`: `render(el, state)` — KPI 4개, 관심지역 섹션(고정, 진행중만), 진행중 목록 표(`<table>`; 768px 이하에서 CSS로 카드형: `display:block` 행 + `data-label` 속성). 행 클릭 → `views/detail.js`의 `openDetail(notice, award)` 모달.
- 관심지역 강조: 클래스 `.interest`에 주황(`#d9480f`) 좌측 4px 테두리 + 배지 텍스트 = `interest_reason` + (지역제한이면 limit_regions 첫 값). 전 뷰 공통.
- `index.html`: `<meta name="viewport" content="width=device-width, initial-scale=1">`, 상단 헤더(제목, 갱신시각, 상태 배지), 탭 4개, 필터 바, `<main id="view">`, `<script type="module" src="js/app.js">`. 폰트는 시스템 폰트.

- [ ] **Step 1: 실패하는 테스트**

```js
// format.test.js
test("formatAmount units", ...)        // 0/null → "-", 12000000 → "1,200만원", 350000000 → "3.5억원"
test("ddayLabel", ...)                 // now 2026-11-02 → "2026-11-05T14:00" → "D-3", 같은 날 → "오늘", 과거 → "마감"
test("statusLabel all statuses", ...)
// filter.test.js
test("applyFilters track and interest", ...)
test("applyFilters query ignores spaces", ...)   // "회계 감사" 가 "외부회계감사" 매칭
test("applyFilters returns new array and does not mutate", ...)
test("sortByClose puts null last", ...)
// stats.test.js
test("kpis counts", ...)               // fixture 5건으로 newToday 2, closingIn7 3, interestOpen 1, openingThisWeek 1
test("countByRegion only active", ...)
test("awardSummary top winners", ...)
test("statusBadgeClass for failed meta", ...)   // ok false → "fail"; run_at 2일 전 → "stale"
```

- [ ] **Step 2: 실패 확인** `npm test` → 모듈 없음 실패
- [ ] **Step 3: lib 3개 구현** / **Step 4: 통과 확인** `npm test` → all pass
- [ ] **Step 5: `index.html`·`style.css`·`app.js`·`data.js`·`views/dashboard.js`·`views/detail.js` 구현** — 테스트용 샘플 데이터는 `data/`에 Task 11 통합 실행 결과가 있으면 그것을, 없으면 `tests/fixtures/`를 조합해 `data/*.json`을 임시 생성(커밋하지 않음).
- [ ] **Step 6: 브라우저 검증** — `python -m http.server 8765` 루트에서 실행 후 chrome-devtools MCP로 `http://localhost:8765/web/#dashboard` 열어 1280px·375px 두 폭 스크린샷. 확인 항목: KPI 4개 표시, 관심지역 섹션이 최상단, 375px에서 표가 카드로 바뀌고 공고명·기관·D-day가 잘리지 않음, 상태 배지 색. 콘솔 에러 0건.
- [ ] **Step 7: Commit** `feat: web shell, shared libs, dashboard view`

---

### Task 13: 캘린더 뷰

**Files:**
- Create: `web/js/lib/calendar.js`, `web/js/views/calendar.js`
- Test: `web/js/lib/calendar.test.js`

**Interfaces:**
- `lib/calendar.js`: `toEvents(notices) -> Event[]` where `Event = {date: "YYYY-MM-DD", type: "close"|"open", notice}` (close_at/open_at 각각, 없는 것은 생략); `buildMonthGrid(year, month /*1-12*/, events) -> {weeks: Cell[][], label: "2026년 11월"}` with `Cell = {date: "YYYY-MM-DD"|null, inMonth: boolean, events: Event[]}`; 주는 일요일 시작, 6주 고정(42셀); `shiftMonth(year, month, delta) -> {year, month}`.
- `views/calendar.js`: `render(el, state)` — 월 이동 버튼, 그리드, 셀 클릭 시 선택일 이벤트 목록(모바일에서는 그리드 아래). 이벤트 칩 색: close 진함, open 연함; 트랙별 색상 변수 `--c-public`, `--c-apt`; 관심지역 칩은 `.interest` 테두리.

- [ ] **Step 1: 실패하는 테스트**

```js
test("buildMonthGrid 2026-11 has 42 cells starting Sunday", ...)   // 2026-11-01은 일요일 → weeks[0][0].date === "2026-11-01"
test("buildMonthGrid places events on correct cell", ...)
test("build_month_grid_skips_events_without_date", ...)             // close_at null 공고는 이벤트 없음
test("shiftMonth wraps year", ...)                                   // (2026,12,+1) → {2027,1}
```

- [ ] **Step 2: 실패 확인** / **Step 3: 구현** / **Step 4: 통과 확인**
- [ ] **Step 5: 브라우저 검증** — `#calendar` 1280px·375px 스크린샷, 월 이동, 셀 클릭 목록 표시 확인.
- [ ] **Step 6: Commit** `feat: calendar view`

---

### Task 14: 시도 지도 뷰

**Files:**
- Create: `tools/build_map.py`, `web/assets/korea-sido.svg`, `web/js/views/map.js`
- Test: `tests/test_build_map.py`

**Interfaces:**
- `tools/build_map.py`: 입력 `southkorea/southkorea-maps` 저장소의 `kostat/2018/json/skorea-provinces-2018-topo-simple.json`(실행 시 `tools/` 아래로 내려받아 사용, 저장소에는 결과 SVG만 커밋, SVG 주석에 출처 URL 명시). TopoJSON 디코딩(arcs·delta·transform)을 직접 구현(외부 의존성 없음). 함수 `topo_to_paths(topo: dict) -> list[tuple[str name, str d]]`, `merge_regions(paths, mapping: dict[str,str]) -> list[tuple[str,str]]`(광주광역시+전라남도 → 전남광주: 두 path d를 이어붙임), `write_svg(paths, out: Path, viewbox: str)`. 각 `<path>`에 `data-region="<16개 명칭 중 하나>"`, `id="r-<index>"`. 추가로 SVG 우측 하단에 `<rect data-region="미분류">`와 라벨.
- `views/map.js`: `render(el, state)` — SVG를 `fetch("assets/korea-sido.svg")`로 인라인 삽입, `countByRegion` 결과로 5단계 농도(0건 회색) 채움, 관심지역(`interest_home_regions` 전남광주)은 항상 주황 외곽선, 클릭/탭 → 우측(모바일: 아래) 목록. 지도 아래 범례 + 지역별 건수 표(내림차순).

- [ ] **Step 1: 실패하는 테스트** `tests/test_build_map.py`

```python
def test_topo_to_paths_decodes_small_synthetic_topology()   # 손으로 만든 2개 폴리곤 TopoJSON → 2 path, 좌표 변환 검증
def test_merge_regions_joins_gwangju_and_jeonnam()
def test_write_svg_has_16_regions_plus_unclassified(tmp_path)  # data-region 17종, 각 16개 명칭 1회
```

- [ ] **Step 2: 실패 확인** / **Step 3: 구현** / **Step 4: 통과 확인**
- [ ] **Step 5: 실제 SVG 생성** — `python tools/build_map.py --out web/assets/korea-sido.svg` 실행, 파일 크기 300KB 이하 확인(크면 topo-simple 사용 유지 + 좌표 소수 1자리 반올림).
- [ ] **Step 6: 브라우저 검증** — `#map` 스크린샷 1280px·375px, 전남광주 외곽선 강조, 클릭 시 목록.
- [ ] **Step 7: Commit** `feat: sido map view with merged Jeonnam-Gwangju`

---

### Task 15: 낙찰 축적 뷰 + CSV

**Files:**
- Create: `web/js/lib/csv.js`, `web/js/views/awards.js`
- Test: `web/js/lib/csv.test.js`

**Interfaces:**
- `lib/csv.js`: `toCsv(rows: object[], columns: {key, label}[]) -> string` — UTF-8 BOM(`\uFEFF`) 포함, 쉼표·줄바꿈·따옴표 이스케이프, CRLF. `downloadCsv(filename, text)`는 `views/awards.js`에 두고 테스트하지 않음.
- `views/awards.js`: `render(el, state)` — 대상 = status ∈ {awarded, failed, rebid, unknown, cancelled} 공고 + 매칭 award. 열: 개찰일, 공고명, 기관, 지역, 기초금액, 낙찰자, 낙찰금액, 낙찰률, 참가업체수, 상태. 필터: 기간(시작/종료 date input), 상태, 지역 select, 낙찰자 검색. 상단 요약 `awardSummary`. "CSV 다운로드" 버튼 → 현재 필터 결과.

- [ ] **Step 1: 실패하는 테스트**

```js
test("toCsv escapes comma quote newline and has BOM CRLF", ...)
test("toCsv uses labels as header in column order", ...)
```

- [ ] **Step 2: 실패 확인** / **Step 3: 구현** / **Step 4: 통과 확인**
- [ ] **Step 5: 브라우저 검증** — `#awards` 스크린샷, 필터 동작, CSV 버튼이 파일을 내려받고 Excel에서 한글이 깨지지 않음(BOM).
- [ ] **Step 6: Commit** `feat: awards view with CSV export`

---

### Task 16: GitHub Actions 일일 수집·배포 + Pages 설정 + 운영 문서

**Files:**
- Create: `.github/workflows/daily.yml`, `README.md`(갱신: 구조, 실행법, config 수정법, Secret, 문제해결)

**Interfaces:**
- `daily.yml`:
  - `on: schedule: - cron: '0 22 * * *'`, `workflow_dispatch: inputs: backfill (boolean, default false)`.
  - `permissions: contents: write, pages: write, id-token: write`. `concurrency: group: daily, cancel-in-progress: false`.
  - job `collect`: ubuntu-latest, `actions/checkout@v4`, `actions/setup-python@v5` (3.12), `pip install -r requirements.txt`, `python -m collector.main ${{ inputs.backfill && '--backfill' || '' }}` with `env: DATA_GO_KR_SERVICE_KEY: ${{ secrets.DATA_GO_KR_SERVICE_KEY }}`, `continue-on-error: true` + 결과를 `steps.collect.outcome`로 보관; 그 다음 `git config user.name "bid-bot"`, `git add data && git diff --cached --quiet || git commit -m "chore(data): daily update $(date -u +%F)" && git push`; `mkdir site && cp -r web/* site/ && cp -r data site/data`; `actions/upload-pages-artifact@v3` (path site).
  - job `deploy`: needs collect, `environment: github-pages`, `actions/deploy-pages@v4`.
  - 마지막 step: `if: steps.collect.outcome == 'failure'` → `exit 1` (배포는 끝난 뒤 워크플로를 실패로 표시).
  - `web/js/data.js`의 기본 base는 `"data/"`로 바꾼다(Pages에서는 `site/data/`가 같은 레벨). 로컬 서버 검증은 `site/`를 만들어 동일 구조로 한다(Task 12~15의 검증 명령도 이 구조로 재확인).
- Pages 설정: `gh api -X POST repos/wg5809-beep/bid-dashboard/pages -f build_type=workflow` (이미 있으면 PUT).

- [ ] **Step 1: 워크플로 작성 + data.js base 수정 + 테스트 재실행** (`npm test`, `python -m pytest -q`)
- [ ] **Step 2: Pages 활성화** — 위 gh api 호출, 응답 `html_url` 기록.
- [ ] **Step 3: Secret 등록 요청** — 사용자에게 `! gh secret set DATA_GO_KR_SERVICE_KEY -R wg5809-beep/bid-dashboard` 입력을 요청하고 `gh secret list -R wg5809-beep/bid-dashboard`로 존재 확인(값은 보지 않음).
- [ ] **Step 4: 커밋·푸시 후 첫 수동 실행** — `gh workflow run daily.yml -R wg5809-beep/bid-dashboard -f backfill=true`, `gh run watch` 로 완료 대기. 실패 시 로그(`gh run view --log-failed`)로 API 필드명·resultCode를 확인해 소스 상수·fixture 수정 → 테스트 → 재실행.
- [ ] **Step 5: 배포 검증** — Pages URL을 chrome-devtools로 열어 4개 탭 스크린샷(1280·375), `meta.json`의 `ok: true`, `calls` 각 100 이하, 콘솔 에러 0건. 결과를 사용자에게 보고(URL, 공고 수, 관심지역 건수, 호출 수).
- [ ] **Step 6: README 갱신 및 Commit** `ci: daily collection and pages deploy; docs: operations guide`

---

## 자체 점검 메모

- 스펙 5.1의 "변경이력 오퍼레이션"은 쓰지 않는다. 등록일시 기준 목록 조회가 변경·취소 공고를 차수 증가 + `ntceKindNm`으로 돌려주므로(Task 5·7) 같은 결과를 호출 1종으로 얻는다. 스펙 11장 첫 항목은 이 방식으로 충족된다.
- 스펙 6.1 KPI "이번 주 개찰 예정" = open_at이 오늘~+7일.
- 스펙 6.4 "기간 내 낙찰 건수·평균 낙찰률·상위 낙찰자 5곳" = `awardSummary`.
- 스펙 8의 커버리지 80%는 Task 11 Step 4에서 측정. 프론트 DOM 코드는 브라우저 검증 단계로 대체(스펙 8 통합 항목).
