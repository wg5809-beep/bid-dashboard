"""수집 오케스트레이션: 공고 수집 → 병합 → 낙찰 반영 → 보존 정리 → 저장 → 발주계획 → meta 기록.

CLI: python -m collector.main [--backfill] [--data-dir data] [--config collector/config.yaml]
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import sys
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from collector.config import Config, load_config
from collector.model import Award, Meta, Notice, Plan
from collector.rules.keywords import matches_keywords
from collector.rules.region import region_from_kapt
from collector.rules.service import classify_all
from collector.sources import kapt_bids, kapt_results, nara_awards, nara_bids, nara_plans
from collector.sources.client import DataGoClient, DataGoError, redact
from collector.store.json_store import (
    load_awards, load_notices, load_plans, save_awards, save_json, save_notices, save_plans,
)
from collector.store.merge import apply_retention, attach_awards, merge_notices, merge_plans, prune_plans
from collector.windows import month_windows

ENV_KEY = "DATA_GO_KR_SERVICE_KEY"
SOURCE_ERRORS = (DataGoError, requests.RequestException)


def _day_range(now: datetime, days: int) -> tuple[datetime, datetime]:
    begin = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=0, microsecond=0)
    return begin, end


def _guard(errors: list[str], label: str, fn, *args):
    """소스 호출을 감싸 실패해도 다른 소스는 계속 진행한다."""
    try:
        return fn(*args)
    except SOURCE_ERRORS as exc:
        errors.append(f"{label}: {exc}")
        return None


def _collect_notices(cfg: Config, client, now: datetime, backfill: bool, errors: list[str]) -> list[Notice]:
    """창 단위로 실패를 격리해, 한 창이 실패해도 다른 창의 결과는 유지한다."""
    days = cfg.backfill_days if backfill else cfg.lookback_days
    today = now.strftime("%Y-%m-%d")
    collected: list[Notice] = []
    for window in month_windows(*_day_range(now, days)):
        collected += _guard(errors, nara_bids.SERVICE, nara_bids.collect_public, client, cfg, [window], today) or []
        collected += _guard(errors, kapt_bids.SERVICE, kapt_bids.collect_apt, client, cfg, [window], today) or []
    return collected


def _public_awards(cfg: Config, client, notices: Mapping[str, Notice], now: datetime, backfill: bool, errors: list[str]):
    """키워드·창 단위로 실패를 격리해, 한 호출이 실패해도 받은 결과는 유지한다."""
    days = max(cfg.backfill_days, cfg.award_weekly_lookback_days) if backfill else cfg.award_lookback_days
    pending = {k: notices[k] for k in nara_awards.pending_award_keys(notices)}
    awards: dict[str, Award] = {}
    notes: dict[str, str] = {}
    if not pending:
        return awards, notes
    for begin, end in month_windows(*_day_range(now, days)):
        for keyword in cfg.public_keywords:
            rows = _guard(errors, nara_awards.SERVICE, nara_awards.fetch_awards, client, begin, end, [keyword]) or []
            awards.update(nara_awards.match_awards(rows, pending))
            rows = _guard(errors, nara_awards.SERVICE, nara_awards.fetch_openg_results, client, begin, end, [keyword]) or []
            notes.update(nara_awards.result_notes(rows, pending))
    return awards, notes


def _apt_result_rows(cfg: Config, client, now: datetime, errors: list[str]) -> list[dict]:
    """키워드×연도(올해 + 조회범위가 작년에 걸치면 작년)로 결과를 받아 지역·키워드로 거른다."""
    years = sorted({now.year, (now - timedelta(days=cfg.apt_result_lookback_days)).year})
    seen: dict[str, dict] = {}
    for year in years:
        for keyword in cfg.apt_keywords:
            rows = _guard(errors, kapt_results.SERVICE, kapt_results.fetch_results_by_title, client, keyword, year) or []
            for raw in rows:
                key = str(raw.get("bidNum") or "")
                if key and key not in seen and matches_keywords(raw.get("bidTitle"), cfg.apt_keywords, ()):
                    seen[key] = raw
    return [raw for raw in seen.values() if cfg.collects_apt_region(region_from_kapt(raw.get("bidTitle"), raw.get("bidArea")))]


def _apt_awards(cfg: Config, client, notices: Mapping[str, Notice], existing: Mapping[str, Award],
                now: datetime, errors: list[str]):
    """결과 행 → (낙찰, 결과메모, 새로 알게 된 공고). 공고 서비스에 없던 과거 공고도 결과 행으로 만든다."""
    today = now.strftime("%Y-%m-%d")
    awards: dict[str, Award] = {}
    notes: dict[str, str] = {}
    new_notices: list[Notice] = []
    for raw in _apt_result_rows(cfg, client, now, errors):
        key = f"apt:{raw.get('bidNum')}"
        notice = notices.get(key)
        if notice is None:
            notice = kapt_results.notice_from_result(raw, cfg, today)
            new_notices.append(notice)
        elif notice.status not in kapt_results.PENDING_STATUSES:
            continue
        note = kapt_results.result_note_from_state(raw)
        if note:
            notes[key] = note
        elif kapt_results.is_awarded(raw) and key not in existing:
            participants = _guard(errors, kapt_results.SERVICE, kapt_results.fetch_participants, client, notice.notice_no)
            awards[key] = kapt_results.to_award(raw, notice, participants or [])
    return awards, notes, new_notices


def _apply_notes(notices: dict[str, Notice], notes: Mapping[str, str]) -> dict[str, Notice]:
    return {k: (dataclasses.replace(n, result_note=notes[k]) if k in notes else n) for k, n in notices.items()}


def _collect_awards(cfg, client, notices, existing: Mapping[str, Award], now, backfill, errors):
    """→ (전체 낙찰, 결과메모, 신규 낙찰 수, 결과 서비스에서 새로 알게 된 아파트 공고)"""
    found = _guard(errors, nara_awards.SERVICE, _public_awards, cfg, client, notices, now, backfill, errors)
    found_apt = _guard(errors, kapt_results.SERVICE, _apt_awards, cfg, client, notices, existing, now, errors)
    new_awards: dict[str, Award] = {}
    notes: dict[str, str] = {}
    for result in (found, found_apt):
        if result:
            new_awards.update({k: a for k, a in result[0].items() if k not in existing})
            notes.update(result[1])
    new_notices = found_apt[2] if found_apt else []
    return {**existing, **new_awards}, notes, len(new_awards), new_notices


def _collect_plans(cfg: Config, client, existing: Mapping[str, Plan], now: datetime, errors: list[str]):
    """발주계획은 매번 전체를 다시 받는다 → (전체 계획, 신규 수). 키워드 단위로 실패를 격리한다."""
    window = nara_plans.plan_window(now, cfg.plan_past_months, cfg.plan_posted_lookback_days)
    today = now.strftime("%Y-%m-%d")
    before = len(errors)
    incoming: list[Plan] = []
    for keyword in cfg.public_keywords:
        incoming += _guard(errors, nara_plans.SERVICE, nara_plans.fetch_plans, client, cfg, window, keyword, today) or []
    merged, new_count = merge_plans(existing, incoming, complete=len(errors) == before)
    year, month = nara_plans.first_order_ym(now, cfg.plan_past_months)
    return classify_all(prune_plans(merged, f"{year}-{month:02d}"), cfg), new_count


def run(cfg: Config, client, data_dir: Path, now: datetime, backfill: bool = False) -> Meta:
    errors: list[str] = []
    counts = {"new": 0, "updated": 0, "awards": 0, "notices": 0, "award_total": 0, "plans": 0, "new_plans": 0}
    try:
        notices = load_notices(data_dir / "notices.json")
        awards = load_awards(data_dir / "awards.json")
        incoming = _collect_notices(cfg, client, now, backfill, errors)
        notices, counts["new"], counts["updated"] = merge_notices(notices, incoming, now.strftime("%Y-%m-%d"))
        notices = attach_awards(notices, awards, now)
        awards, notes, counts["awards"], late = _collect_awards(cfg, client, notices, awards, now, backfill, errors)
        notices, late_new, _ = merge_notices(notices, late, now.strftime("%Y-%m-%d"))
        counts["new"] += late_new
        notices = apply_retention(attach_awards(_apply_notes(notices, notes), awards, now), now, cfg.retention_days)
        notices = classify_all(notices, cfg)  # 설정 변경이 과거 공고에도 반영되도록 매번 전체 재분류
        counts["notices"], counts["award_total"] = len(notices), len(awards)
        save_notices(data_dir / "notices.json", notices)
        save_awards(data_dir / "awards.json", awards)
        plans, counts["new_plans"] = _collect_plans(cfg, client, load_plans(data_dir / "plans.json"), now, errors)
        counts["plans"] = len(plans)
        save_plans(data_dir / "plans.json", plans)
    except Exception as exc:  # 어디서 실패해도 meta는 남긴다 (키는 가린다)
        errors.append(f"fatal: {redact(str(exc), None)}")
        raise
    finally:
        meta = Meta(run_at=now.strftime("%Y-%m-%dT%H:%M"), ok=not errors, calls=dict(getattr(client, "calls", {})),
                    new_notices=counts["new"], updated_notices=counts["updated"], new_awards=counts["awards"],
                    errors=tuple(dict.fromkeys(errors)), notice_count=counts["notices"], award_count=counts["award_total"],
                    plan_count=counts["plans"], new_plans=counts["new_plans"])
        save_json(data_dir / "meta.json", meta.to_dict())
    return meta


def load_dotenv(path: Path, env: Mapping[str, str]) -> dict[str, str]:
    """`.env`의 KEY=VALUE 줄을 읽어, 주어진 환경에 없는 키만 채운 새 dict를 돌려준다."""
    merged = dict(env)
    if not path.exists():
        return merged
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        merged.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return merged


def now_kst() -> datetime:
    """KST 벽시계 시각(naive). Actions 러너가 UTC여도 공고 시각(KST)과 같은 기준을 쓴다."""
    return datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)


def build_client(cfg: Config) -> DataGoClient:
    env = load_dotenv(Path(".env"), os.environ)
    return DataGoClient(env.get(ENV_KEY, ""), max_calls_per_service=cfg.max_calls_per_service)


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="공공입찰 수집기")
    parser.add_argument("--backfill", action="store_true", help="첫 실행: 과거 backfill_days 범위 수집")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--config", default="collector/config.yaml")
    args = parser.parse_args(argv)
    cfg = load_config(Path(args.config))
    now = now_kst()
    try:
        client = build_client(cfg)
    except RuntimeError as exc:  # 키 미설정: 화면에 실패 배지가 뜨도록 meta만 남기고 종료
        meta = Meta(run_at=now.strftime("%Y-%m-%dT%H:%M"), ok=False, calls={}, new_notices=0, updated_notices=0,
                    new_awards=0, errors=(str(exc),), notice_count=0, award_count=0)
        save_json(Path(args.data_dir) / "meta.json", meta.to_dict())
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    meta = run(cfg, client, Path(args.data_dir), now, backfill=args.backfill)
    print(f"run_at={meta.run_at} ok={meta.ok} notices={meta.notice_count} (+{meta.new_notices}/~{meta.updated_notices}) "
          f"awards={meta.award_count} (+{meta.new_awards}) plans={meta.plan_count} (+{meta.new_plans}) calls={meta.calls}")
    for err in meta.errors:
        print(f"ERROR {err}", file=sys.stderr)
    return 0 if meta.ok else 1


if __name__ == "__main__":
    sys.exit(cli())
