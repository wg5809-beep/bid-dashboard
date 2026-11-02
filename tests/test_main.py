import dataclasses
import json
from datetime import datetime
from pathlib import Path

import pytest

from collector import main as main_mod
from collector.config import load_config
from collector.main import run
from collector.sources import kapt_bids, kapt_results, nara_awards, nara_bids
from collector.sources.client import DataGoError
from collector.store.json_store import load_awards, load_notices
from tests.fakes import FakeClient

CFG_PATH = Path("collector/config.yaml").resolve()
CFG = load_config(CFG_PATH)
FX = Path("tests/fixtures")
BIDS = json.loads((FX / "nara_bid_item.json").read_text(encoding="utf-8"))
REGIONS = json.loads((FX / "nara_region_item.json").read_text(encoding="utf-8"))
AWARDS = json.loads((FX / "nara_award_item.json").read_text(encoding="utf-8"))
OPENG = json.loads((FX / "nara_openg_item.json").read_text(encoding="utf-8"))
KBIDS = json.loads((FX / "kapt_bid_item.json").read_text(encoding="utf-8"))
KRES = json.loads((FX / "kapt_result_item.json").read_text(encoding="utf-8"))
KENT = json.loads((FX / "kapt_entrps_item.json").read_text(encoding="utf-8"))

DAY1 = datetime(2026, 11, 2, 7, 0)   # 월요일
DAY2 = datetime(2026, 11, 18, 7, 0)  # 수요일, 개찰 이후
SUNDAY = datetime(2026, 11, 22, 7, 0)


def full_table(over=None):
    table = {
        (nara_bids.SERVICE, nara_bids.OP_LIST): BIDS,
        (nara_bids.SERVICE, nara_bids.OP_REGION): REGIONS,
        (nara_awards.SERVICE, nara_awards.OP_AWARDS): AWARDS,
        (nara_awards.SERVICE, nara_awards.OP_OPENG): OPENG,
        (kapt_bids.SERVICE, kapt_bids.OP_BY_POSTED): KBIDS,
        (kapt_results.SERVICE, kapt_results.OP_BY_TITLE): KRES,
        (kapt_results.SERVICE, kapt_results.OP_PARTICIPANTS): KENT,
    }
    table.update(over or {})
    return table


def test_run_first_time_writes_three_files_and_counts(tmp_path):
    meta = run(CFG, FakeClient(full_table()), tmp_path, DAY1)
    assert (tmp_path / "notices.json").exists() and (tmp_path / "awards.json").exists()
    assert (tmp_path / "meta.json").exists()
    assert meta.ok is True and meta.errors == ()
    # 나라장터 1 + 아파트 공고 2(전남광주 123, 경기 124) + 아파트 결과에서 생성 3(777 낙찰, 555 유찰, 서울 999 낙찰)
    assert meta.new_notices == 6 and meta.notice_count == 6
    assert meta.new_awards == 2 and meta.run_at == "2026-11-02T07:00"
    assert meta.calls["nara_bids"] > 0 and meta.calls["kapt_bids"] == 1
    assert meta.calls["kapt_results"] == len(CFG.apt_keywords) + 2  # 키워드별 1회 + 낙찰 2건 참여업체
    notices = load_notices(tmp_path / "notices.json")
    assert notices["public:R26BK00000001"].status == "open" and notices["apt:2026110200123"].status == "open"
    assert notices["apt:2026110200777"].status == "awarded" and notices["apt:2026110200555"].status == "failed"
    assert notices["apt:2026110200999"].status == "awarded" and notices["apt:2026110200999"].region == "서울"


def test_run_apt_regions_setting_excludes_other_regions(tmp_path):
    honam = dataclasses.replace(CFG, apt_regions=("전남광주", "전북"))
    meta = run(honam, FakeClient(full_table()), tmp_path, DAY1)
    assert meta.notice_count == 4 and meta.new_awards == 1
    assert "apt:2026110200999" not in load_notices(tmp_path / "notices.json")


def test_run_second_time_attaches_award_and_sets_awarded(tmp_path):
    run(CFG, FakeClient(full_table()), tmp_path, DAY1)
    meta = run(CFG, FakeClient(full_table()), tmp_path, DAY2)
    notices = load_notices(tmp_path / "notices.json")
    awards = load_awards(tmp_path / "awards.json")
    assert meta.new_awards == 2 and meta.award_count == 4  # 1차 777·999 + 2차 나라장터·123
    assert notices["public:R26BK00000001"].status == "awarded"
    assert awards["public:R26BK00000001"].winner == "○○회계법인"
    assert notices["apt:2026110200123"].status == "awarded"
    assert awards["apt:2026110200123"].winner == "○○회계법인"
    assert meta.new_notices == 0


def test_run_does_not_overwrite_existing_award(tmp_path):
    run(CFG, FakeClient(full_table()), tmp_path, DAY1)
    run(CFG, FakeClient(full_table()), tmp_path, DAY2)
    changed = [{**AWARDS[0], "bidwinnrNm": "다른회계법인"}, AWARDS[1]]
    run(CFG, FakeClient(full_table({(nara_awards.SERVICE, nara_awards.OP_AWARDS): changed})), tmp_path, DAY2)
    assert load_awards(tmp_path / "awards.json")["public:R26BK00000001"].winner == "○○회계법인"


def test_run_records_partial_failure(tmp_path):
    run(CFG, FakeClient(full_table()), tmp_path, DAY1)
    table = full_table({(nara_awards.SERVICE, nara_awards.OP_AWARDS): DataGoError("nara_awards", "22", "limit")})
    meta = run(CFG, FakeClient(table), tmp_path, DAY2)
    assert meta.ok is False and len(meta.errors) == 1 and "22" in meta.errors[0]  # 같은 오류는 1줄로 합침
    assert load_notices(tmp_path / "notices.json")
    saved = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert saved["ok"] is False


def test_run_sunday_uses_weekly_award_window(tmp_path):
    client = FakeClient(full_table())
    run(CFG, client, tmp_path, SUNDAY)
    award_calls = [p for s, op, p in client.requests if op == nara_awards.OP_AWARDS]
    assert award_calls and award_calls[0]["inqryBgnDt"] == "202609230000"


def test_run_weekday_uses_daily_windows(tmp_path):
    run(CFG, FakeClient(full_table()), tmp_path, DAY1)
    client = FakeClient(full_table())
    run(CFG, client, tmp_path, DAY2)  # 수요일, pending 있음
    bid_calls = [p for s, op, p in client.requests if op == nara_bids.OP_LIST]
    award_calls = [p for s, op, p in client.requests if op == nara_awards.OP_AWARDS]
    assert bid_calls[0]["inqryBgnDt"] == "202611150000"
    assert award_calls[0]["inqryBgnDt"] == "202611110000"
    assert award_calls[0]["bidNtceNm"] == CFG.public_keywords[0]
    assert len({p["bidNtceNm"] for p in award_calls}) == len(CFG.public_keywords)


def test_run_backfill_uses_90_days_in_month_windows(tmp_path):
    client = FakeClient(full_table())
    run(CFG, client, tmp_path, DAY1, backfill=True)
    bid_calls = [p for s, op, p in client.requests if op == nara_bids.OP_LIST]
    assert bid_calls[0]["inqryBgnDt"] == "202608040000"
    assert len({p["inqryBgnDt"] for p in bid_calls}) >= 3


def test_run_backfill_award_window_covers_backfill_days(tmp_path):
    run(CFG, FakeClient(full_table()), tmp_path, DAY1)
    client = FakeClient(full_table())
    run(CFG, client, tmp_path, DAY2, backfill=True)
    award_calls = [p for s, op, p in client.requests if op == nara_awards.OP_AWARDS]
    assert award_calls and min(p["inqryBgnDt"] for p in award_calls) == "202608200000"


def test_run_writes_meta_even_if_store_raises(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(main_mod, "save_notices", boom)
    with pytest.raises(RuntimeError):
        run(CFG, FakeClient(full_table()), tmp_path, DAY1)
    saved = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert saved["ok"] is False and "disk full" in saved["errors"][0]


def test_cli_exit_code_1_on_errors(tmp_path, monkeypatch):
    table = full_table({(kapt_bids.SERVICE, kapt_bids.OP_BY_POSTED): DataGoError("kapt_bids", "20", "denied")})
    monkeypatch.setattr(main_mod, "build_client", lambda cfg: FakeClient(table))
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "dummy")
    code = main_mod.cli(["--data-dir", str(tmp_path), "--config", "collector/config.yaml"])
    assert code == 1
    assert (tmp_path / "meta.json").exists()


def test_cli_exit_code_0_on_success(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "build_client", lambda cfg: FakeClient(full_table()))
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "dummy")
    assert main_mod.cli(["--data-dir", str(tmp_path)]) == 0


def test_load_dotenv_fills_missing_only(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATA_GO_KR_SERVICE_KEY=from-file\nOTHER=x\n# comment\n", encoding="utf-8")
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    monkeypatch.setenv("OTHER", "keep")
    env = main_mod.load_dotenv(env_file, {"OTHER": "keep"})
    assert env["DATA_GO_KR_SERVICE_KEY"] == "from-file" and env["OTHER"] == "keep"


def test_cli_missing_key_writes_meta_and_returns_1(tmp_path, monkeypatch):
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # .env 없음
    code = main_mod.cli(["--data-dir", str(tmp_path / "data"), "--config", str(CFG_PATH)])
    assert code == 1
    saved = json.loads((tmp_path / "data" / "meta.json").read_text(encoding="utf-8"))
    assert saved["ok"] is False and "DATA_GO_KR_SERVICE_KEY" in saved["errors"][0]


def test_now_kst_is_naive_seoul_time():
    from datetime import timezone
    from zoneinfo import ZoneInfo
    got = main_mod.now_kst()
    expect = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
    assert got.tzinfo is None and abs((expect - got).total_seconds()) < 5


def test_run_fatal_error_is_redacted(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("failed GET /op?serviceKey=SECRETKEY&pageNo=1")
    monkeypatch.setattr(main_mod, "save_notices", boom)
    with pytest.raises(RuntimeError):
        run(CFG, FakeClient(full_table()), tmp_path, DAY1)
    saved = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert "SECRETKEY" not in saved["errors"][0] and "serviceKey=***" in saved["errors"][0]


def test_run_skips_public_awards_when_no_pending(tmp_path):
    client = FakeClient(full_table())
    run(CFG, client, tmp_path, DAY1)  # 모든 공고가 open → pending 없음
    assert not [1 for s, op, p in client.requests if s == nara_awards.SERVICE]


def test_run_keeps_partial_awards_when_one_keyword_fails(tmp_path):
    run(CFG, FakeClient(full_table()), tmp_path, DAY1)

    def flaky(params):
        if params.get("bidNtceNm") == "세무":
            raise DataGoError("nara_awards", "22", "limit")
        return AWARDS
    meta = run(CFG, FakeClient(full_table({(nara_awards.SERVICE, nara_awards.OP_AWARDS): flaky})), tmp_path, DAY2)
    assert meta.ok is False and any("22" in e for e in meta.errors)
    assert load_awards(tmp_path / "awards.json")["public:R26BK00000001"].winner == "○○회계법인"


def test_run_apt_results_query_years_cover_lookback(tmp_path):
    client = FakeClient(full_table())
    run(CFG, client, tmp_path, datetime(2027, 1, 10, 7, 0))  # 연초: 작년도 함께 조회
    years = {p["searchYear"] for s, op, p in client.requests if op == kapt_results.OP_BY_TITLE}
    assert years == {"2026", "2027"}
    client = FakeClient(full_table())
    run(CFG, client, tmp_path, datetime(2027, 6, 1, 7, 0))
    years = {p["searchYear"] for s, op, p in client.requests if op == kapt_results.OP_BY_TITLE}
    assert years == {"2027"}


def test_run_classifies_notices_into_target_and_other(tmp_path):
    run(CFG, FakeClient(full_table()), tmp_path, DAY1)
    notices = load_notices(tmp_path / "notices.json")
    assert (notices["apt:2026110200123"].category, notices["apt:2026110200123"].service) == ("target", "회계감사")
    categories = {n.category for n in notices.values()}
    assert categories <= {"target", "other"}
