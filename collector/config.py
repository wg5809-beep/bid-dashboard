"""수집 설정 로딩. config.yaml → 불변 Config."""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ServiceLine:
    """주타겟 업무 하나: 이름, 포함 키워드, (선택) 제외 키워드."""
    name: str
    keywords: tuple[str, ...]
    exclude: tuple[str, ...] = ()


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
    service_lines: tuple[ServiceLine, ...] = ()  # 우선순위 순

    def collects_apt_region(self, region: str | None) -> bool:
        """아파트 트랙 수집 지역 판정. apt_regions가 비어 있으면 전국."""
        return not self.apt_regions or region in self.apt_regions


def _as_value(raw):
    if isinstance(raw, list):
        return tuple(str(item) for item in raw)
    return raw


def _service_lines(raw) -> tuple[ServiceLine, ...]:
    """[{name, keywords, exclude?}, ...] → ServiceLine 튜플. 형식이 틀리면 RuntimeError."""
    lines = []
    for item in raw or []:
        if not isinstance(item, dict) or not item.get("name") or not isinstance(item.get("keywords"), list):
            raise RuntimeError(f"service_lines 항목 형식 오류: {item!r} (name, keywords 필요)")
        lines.append(ServiceLine(str(item["name"]), _as_value(item["keywords"]), _as_value(item.get("exclude") or [])))
    return tuple(lines)


def load_config(path: Path) -> Config:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RuntimeError(f"설정 파일을 읽을 수 없습니다: {path} ({exc})") from exc
    names = {f.name for f in fields(Config)}
    missing = sorted(names - set(data) - {"service_lines"})
    if missing:
        raise RuntimeError(f"설정 누락: {', '.join(missing)}")
    values = {name: _as_value(data[name]) for name in names}
    values["service_lines"] = _service_lines(data.get("service_lines"))
    return Config(**values)
