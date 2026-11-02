"""관심지역 판정.

① 본사 소재: 공고 지역 또는 기관명에서 뽑은 지역이 소재지 목록에 있거나, 기관명이 소재기관 목록에 포함.
② 지역제한: 참가제한지역에 지역제한 목록(전남광주·광주·전남·전북·호남)이 포함.
"""
from __future__ import annotations

from collections.abc import Sequence

from collector.config import Config
from collector.rules.region import normalize_region, region_from_institution

HOME = "본사 소재"
LIMIT = "지역제한"


def _compact(text) -> str:
    return "".join(str(text or "").split())


def _is_home(agency, demand_agency, region, cfg: Config) -> bool:
    regions = {region, region_from_institution(agency), region_from_institution(demand_agency)}
    if regions & set(cfg.interest_home_regions):
        return True
    names = [_compact(agency), _compact(demand_agency)]
    return any(_compact(inst) in name for inst in cfg.interest_institutions for name in names if name)


def _is_limited(limit_regions: Sequence[str], cfg: Config) -> bool:
    wanted = {_compact(w) for w in cfg.interest_limit_regions}
    for raw in limit_regions:
        text = _compact(raw)
        if not text:
            continue
        if normalize_region(text) in wanted or any(w in text for w in wanted):
            return True
    return False


def judge_interest(
    agency: str | None,
    demand_agency: str | None,
    region: str | None,
    limit_regions: Sequence[str],
    cfg: Config,
) -> tuple[bool, str | None]:
    if _is_home(agency, demand_agency, region, cfg):
        return True, HOME
    if _is_limited(limit_regions, cfg):
        return True, LIMIT
    return False, None
