"""업무 분류: 공고명을 회계법인 주타겟 업무(설정 service_lines)와 기타로 나눈다.

분류는 공고명만 보는 순수 함수이며, 설정이 바뀌면 매 수집 때 전체 공고를 다시 분류한다.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from collector.config import Config
from collector.model import Notice
from collector.rules.keywords import matches_keywords

TARGET = "target"
OTHER = "other"


def classify_service(title: str | None, cfg: Config) -> tuple[str, str | None]:
    """→ ("target", 업무명) 또는 ("other", None). service_lines 순서대로 처음 맞는 업무가 이긴다."""
    for line in cfg.service_lines:
        if matches_keywords(title, line.keywords, line.exclude):
            return TARGET, line.name
    return OTHER, None


def classify_all(notices: Mapping[str, Notice], cfg: Config) -> dict[str, Notice]:
    out = {}
    for key, notice in notices.items():
        category, service = classify_service(notice.title, cfg)
        out[key] = dataclasses.replace(notice, category=category, service=service)
    return out
