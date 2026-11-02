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
