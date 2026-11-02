"""공고명 키워드 포함/제외 매칭. 공백을 제거한 뒤 부분일치로 비교한다."""
from __future__ import annotations

from collections.abc import Sequence


def _compact(text: str | None) -> str:
    return "".join(str(text or "").split())


def matches_keywords(title: str | None, include: Sequence[str], exclude: Sequence[str]) -> bool:
    body = _compact(title)
    if not body:
        return False
    if any(_compact(word) and _compact(word) in body for word in exclude):
        return False
    return any(_compact(word) and _compact(word) in body for word in include)
