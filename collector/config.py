"""수집 설정 로딩. config.yaml → 불변 Config."""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    public_keywords: tuple[str, ...]
    public_exclude: tuple[str, ...]
    apt_keywords: tuple[str, ...]
    apt_regions: tuple[str, ...]
    interest_home_regions: tuple[str, ...]
    interest_limit_regions: tuple[str, ...]
    interest_institutions: tuple[str, ...]
    retention_days: int
    backfill_days: int
    lookback_days: int
    award_lookback_days: int
    award_weekly_lookback_days: int
    apt_result_lookback_days: int
    max_calls_per_service: int


def _as_value(raw):
    if isinstance(raw, list):
        return tuple(str(item) for item in raw)
    return raw


def load_config(path: Path) -> Config:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"설정 파일을 읽을 수 없습니다: {path} ({exc})") from exc
    names = {f.name for f in fields(Config)}
    missing = sorted(names - set(data))
    if missing:
        raise RuntimeError(f"설정 누락: {', '.join(missing)}")
    return Config(**{name: _as_value(data[name]) for name in names})
