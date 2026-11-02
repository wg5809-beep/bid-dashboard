"""수집 오케스트레이션: 공고 수집 → 병합 → 낙찰 반영 → 보존 정리 → 저장 → meta 기록.

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

import requests

from collector.config import Config, load_config
from collector.model import Award, Meta, Notice
from collector.rules.status import parse_iso
from collector.sources import kapt_bids, kapt_results, nara_awards, nara_bids
from collector.sources.client import DataGoClient, DataGoError
from collector.store.json_store import load_awards, load_notices, save_awards, save_json, save_notices
from collector.store.merge import apply_retention, attach_awards, merge_notices
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
    days = cfg.backfill_days if backfill else cfg.lookback_days
    windows = month_windows(*_day_range(now, days))
    today = now.strftime("%Y-%m-%d")
    public = _guard(errors, nara_bids.SERVICE, nara_bids.collect_public, client, cfg, windows, today) or []
    apt = _guard(errors, kapt_bids.SERVICE, kapt_bids.collect_apt, client, cfg, windows, today) or []
    return [*public, *apt]


def _public_awards(cfg: Config, client, notices: Mapping[str, Notice], now: datetime, backfill: bool):
    days = cfg.award_weekly_lookback_days if (backfill or now.weekday() == 6) else cfg.award_lookback_days
    pending = {k: notices[k] for k in nara_awards.pending_award_keys(notices)}
    awards: dict[str, Award] = {}
    notes: dict[str, str] = {}
    for begin, end in month_windows(*_day_range(now, days)):
        awards.update(nara_awards.match_awards(nara_awards.fetch_awards(client, begin, end), pending))
        notes.update(nara_awards.result_notes(nara_awards.fetch_openg_results(client, begin, end), pending))
    return awards, notes


def _apt_awards(client, notices: Mapping[str, Notice]):
    pending = {k: n for k, n in notices.items()
               if n.track == "apt" and n.status in kapt_results.PENDING_STATUSES}
    posted = [parse_iso(n.posted_at) for n in pending.values() if parse_iso(n.posted_at)]
    awards: dict[str, Award] = {}
    notes: dict[str, str] = {}
    if not posted:
        return awards, notes
    for begin, end in month_windows(min(posted), max(posted).replace(hour=23, minute=59)):
        matched = kapt_results.match_results(kapt_results.fetch_results_by_posted(client, begin, end), pending)
        for key, raw in matched.items():
            note = kapt_results.result_note_from_state(raw)
            if note:
                notes[key] = note
                continue
            participants = kapt_results.fetch_participants(client, pending[key].notice_no)
            awards[key] = kapt_results.to_award(raw, pending[key], participants)
    return awards, notes


def _apply_notes(notices: dict[str, Notice], notes: Mapping[str, str]) -> dict[str, Notice]:
    return {k: (dataclasses.replace(n, result_note=notes[k]) if k in notes else n) for k, n in notices.items()}


def _collect_awards(cfg, client, notices, existing: Mapping[str, Award], now, backfill, errors):
    found = _guard(errors, nara_awards.SERVICE, _public_awards, cfg, client, notices, now, backfill)
    found_apt = _guard(errors, kapt_results.SERVICE, _apt_awards, client, notices)
    new_awards: dict[str, Award] = {}
    notes: dict[str, str] = {}
    for result in (found, found_apt):
        if result:
            new_awards.update({k: a for k, a in result[0].items() if k not in existing})
            notes.update(result[1])
    return {**existing, **new_awards}, notes, len(new_awards)


def run(cfg: Config, client, data_dir: Path, now: datetime, backfill: bool = False) -> Meta:
    errors: list[str] = []
    counts = {"new": 0, "updated": 0, "awards": 0, "notices": 0, "award_total": 0}
    try:
        notices = load_notices(data_dir / "notices.json")
        awards = load_awards(data_dir / "awards.json")
        incoming = _collect_notices(cfg, client, now, backfill, errors)
        notices, counts["new"], counts["updated"] = merge_notices(notices, incoming, now.strftime("%Y-%m-%d"))
        notices = attach_awards(notices, awards, now)
        awards, notes, counts["awards"] = _collect_awards(cfg, client, notices, awards, now, backfill, errors)
        notices = apply_retention(attach_awards(_apply_notes(notices, notes), awards, now), now, cfg.retention_days)
        counts["notices"], counts["award_total"] = len(notices), len(awards)
        save_notices(data_dir / "notices.json", notices)
        save_awards(data_dir / "awards.json", awards)
    except Exception as exc:  # 어디서 실패해도 meta는 남긴다
        errors.append(f"fatal: {exc}")
        raise
    finally:
        meta = Meta(run_at=now.strftime("%Y-%m-%dT%H:%M"), ok=not errors, calls=dict(getattr(client, "calls", {})),
                    new_notices=counts["new"], updated_notices=counts["updated"], new_awards=counts["awards"],
                    errors=tuple(errors), notice_count=counts["notices"], award_count=counts["award_total"])
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
    meta = run(cfg, build_client(cfg), Path(args.data_dir), datetime.now(), backfill=args.backfill)
    print(f"run_at={meta.run_at} ok={meta.ok} notices={meta.notice_count} (+{meta.new_notices}/~{meta.updated_notices}) "
          f"awards={meta.award_count} (+{meta.new_awards}) calls={meta.calls}")
    for err in meta.errors:
        print(f"ERROR {err}", file=sys.stderr)
    return 0 if meta.ok else 1


if __name__ == "__main__":
    sys.exit(cli())
