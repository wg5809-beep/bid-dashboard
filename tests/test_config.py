import dataclasses
from pathlib import Path

import pytest

from collector.config import load_config

CFG_PATH = Path("collector/config.yaml")


def test_load_default_config():
    cfg = load_config(CFG_PATH)
    assert "회계" in cfg.public_keywords
    assert "환경영향평가" in cfg.public_exclude
    assert cfg.apt_regions == ("전남광주", "전북")
    assert cfg.interest_home_regions == ("전남광주",)
    assert "호남" in cfg.interest_limit_regions
    assert "한전KDN" in cfg.interest_institutions
    assert cfg.retention_days == 730 and cfg.backfill_days == 90
    assert cfg.max_calls_per_service == 100


def test_config_is_immutable():
    cfg = load_config(CFG_PATH)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.retention_days = 1
