# bid-dashboard

회계법인 용역 공공입찰 대시보드. 나라장터(공공기관)와 K-apt(아파트) 입찰공고를 매일 07:00(KST)에 수집해
GitHub Pages 정적 사이트로 보여준다. PC와 휴대폰에서 같은 URL로 본다.

- 설계: `docs/superpowers/specs/2026-11-02-bid-dashboard-design.md`
- 구현 계획: `docs/superpowers/plans/2026-11-02-bid-dashboard.md`

## 화면

| 탭 | 내용 |
|---|---|
| 대시보드 | KPI 4개, 관심지역(전남광주·호남) 공고 고정 섹션, 진행중 공고(마감 임박순) |
| 캘린더 | 월 그리드에 입찰마감·개찰 일정. 날짜 클릭 → 그날 목록 |
| 지도 | 시도별 진행중 건수(색 농도). 전남광주는 항상 강조. 지역 클릭 → 목록 |
| 낙찰 | 낙찰·유찰·재입찰·결과미확인 이력, 필터, 상위 낙찰자, CSV 다운로드 |

모든 화면 공통: 트랙(전체/공공기관/아파트) 토글, 관심지역만 보기, 검색, 수집 상태 배지(정상/지연/실패).

## 구조

```
collector/        Python 수집기 (config.yaml = 키워드·제외어·관심지역·기관목록·보존기간)
  sources/        data.go.kr 서비스별 클라이언트 4개
  rules/          키워드·지역·관심지역·상태 규칙
  store/          JSON 저장(원자적)·병합
web/              정적 사이트 (프레임워크 없음)
data/             notices.json / awards.json / meta.json  ← Actions가 매일 커밋
tools/build_map.py  TopoJSON → web/assets/korea-sido.svg
tests/            pytest (수집기)      web/js/lib/*.test.js  node --test (프론트 순수 함수)
.github/workflows/daily.yml  매일 수집 → data 커밋 → Pages 배포
```

## 데이터 출처 (공공데이터포털, 모두 활용신청 승인 필요)

| 용도 | 서비스 |
|---|---|
| 공공기관 공고 | 조달청_나라장터 입찰공고정보서비스 (`1230000/ad/BidPublicInfoService`) |
| 공공기관 낙찰 | 조달청_나라장터 낙찰정보서비스 (`1230000/as/ScsbidInfoService`) |
| 아파트 공고 | 국토교통부_공동주택 입찰공고 정보제공 서비스 (`1613000/ApHusBidPblAncInfoOfferServiceV3`) |
| 아파트 결과 | 국토교통부_공동주택 입찰결과공지 정보제공 서비스 (`1613000/ApHusBidResultNoticeInfoOfferServiceV3`) |

## 설정 바꾸기

`collector/config.yaml`만 수정해 커밋하면 다음 실행부터 반영된다.

- `public_keywords` / `public_exclude`: 나라장터 공고명 포함어·제외어
- `apt_keywords` / `apt_regions`: 아파트 공고 키워드·수집 지역(빈 목록 = 전국, 기본값. 호남만: `[전남광주, 전북]`)
- `interest_home_regions` / `interest_institutions`: "본사 소재" 판정용 지역·기관명 목록
- `interest_limit_regions`: "지역제한" 판정용 지역명
- `retention_days`(공고 보존), `backfill_days`, `lookback_days`, `award_lookback_days`, `max_calls_per_service`

## 운영

- 인증키: 저장소 Settings → Secrets → `DATA_GO_KR_SERVICE_KEY` (Decoding 원본 키). 코드·로그에 넣지 않는다.
- 수동 실행: Actions → daily-collect-and-deploy → Run workflow (`backfill` 체크 시 과거 90일 재수집).
- 로컬 실행: 프로젝트 루트에 `.env` 파일(`DATA_GO_KR_SERVICE_KEY=...`) 생성 후
  `python -m collector.main [--backfill]`. 결과는 `data/`에 저장.
- 로컬 미리보기: `site/` 폴더에 `web/*`와 `data/`를 복사하고 `python -m http.server 8765` 실행.
- 테스트: `python -m pytest -q`, `npm test`.

## 문제 해결

| 증상 | 확인 |
|---|---|
| 배지 "수집 실패" | `data/meta.json`의 `errors`. 코드 20=활용신청 미승인, 22=일일 한도 초과, 30=키 미등록 |
| 배지 "갱신 지연" | Actions 실행 실패/미실행. cron은 UTC 22:00 |
| 지역이 미분류 | 기관명에 지역이 없음. `interest_institutions` 또는 `collector/rules/region.py`의 시군 힌트에 추가 |
| 아파트 공고 없음 | `apt_regions`·`apt_keywords` 확인. 기본값은 전국(빈 목록) |
