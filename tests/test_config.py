import dataclasses
from pathlib import Path

import pytest

from collector.config import load_config

CFG_PATH = Path("collector/config.yaml")


def test_load_default_config():
    cfg = load_config(CFG_PATH)
    assert "회계" in cfg.public_keywords
    assert "환경영향평가" in cfg.public_exclude
    assert cfg.apt_regions == ()  # 빈 목록 = 전국
    assert cfg.interest_home_regions == ("전남광주",)
    assert "호남" in cfg.interest_limit_regions
    assert "한전KDN" in cfg.interest_institutions
    assert cfg.retention_days == 730 and cfg.backfill_days == 90
    assert cfg.max_calls_per_service == 300
    assert "평가" not in cfg.public_keywords and "경영평가" in cfg.public_keywords
    assert "사업수행능력" in cfg.public_exclude


def test_config_is_immutable():
    cfg = load_config(CFG_PATH)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.retention_days = 1


def test_empty_apt_regions_collects_every_region():
    cfg = load_config(CFG_PATH)
    assert cfg.collects_apt_region("제주") and cfg.collects_apt_region("충남")


def test_apt_regions_list_restricts_collection():
    cfg = dataclasses.replace(load_config(CFG_PATH), apt_regions=("전남광주", "전북"))
    assert cfg.collects_apt_region("전북") and not cfg.collects_apt_region("제주")


def test_service_lines_loaded_in_order_with_keywords():
    cfg = load_config(CFG_PATH)
    assert cfg.service_lines[0].name == "회계감사" and "회계감사" in cfg.service_lines[0].keywords
    by_name = {line.name: line for line in cfg.service_lines}
    assert by_name["세무조사대응"].keywords == ("세무조사",) and "교육" in by_name["세무조사대응"].exclude
    assert by_name["회계감사"].exclude == ()


def test_service_lines_bad_shape_raises(tmp_path):
    head = CFG_PATH.read_text(encoding="utf-8").split("service_lines:")[0]
    bad = tmp_path / "c.yaml"
    bad.write_text(head + "service_lines:" + chr(10) + "  - 회계감사" + chr(10), encoding="utf-8")
    with pytest.raises(RuntimeError, match="service_lines"):
        load_config(bad)


def test_plan_settings_loaded_with_defaults_when_missing(tmp_path):
    cfg = load_config(CFG_PATH)
    assert cfg.plan_past_months == 3 and cfg.plan_posted_lookback_days == 730
    lines = [ln for ln in CFG_PATH.read_text(encoding="utf-8").splitlines() if not ln.startswith("plan_")]
    old = tmp_path / "old.yaml"
    old.write_text(chr(10).join(lines), encoding="utf-8")
    assert load_config(old).plan_past_months == 3  # 예전 설정 파일도 그대로 읽힌다
