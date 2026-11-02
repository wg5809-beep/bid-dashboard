"""네트워크 없이 클라이언트를 시험하는 가짜 객체."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeResponse:
    payload: Any
    status_code: int = 200

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


@dataclass
class FakeSession:
    """get() 호출마다 responses 순서대로 돌려주고 (url, params)를 기록한다."""

    responses: list
    calls: list = field(default_factory=list)

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if not self.responses:
            raise AssertionError("no more fake responses")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, FakeResponse):
            return item
        return FakeResponse(item)


def envelope(items, total=None, code="00", msg="NORMAL SERVICE"):
    """조달청/국토부 공통 응답 봉투."""
    count = total if total is not None else (len(items) if isinstance(items, list) else 1)
    return {
        "response": {
            "header": {"resultCode": code, "resultMsg": msg},
            "body": {"items": items, "numOfRows": "500", "pageNo": "1", "totalCount": str(count)},
        }
    }


class FakeClient:
    """DataGoClient와 같은 get_items 시그니처. (service, op) → 응답 또는 예외."""

    def __init__(self, table: dict[tuple[str, str], Any] | None = None):
        self.table = dict(table or {})
        self.calls: dict[str, int] = {}
        self.requests: list[tuple[str, str, dict]] = []

    def get_items(self, service, base_url, op, params, page_size=500, json_param="type"):
        self.calls[service] = self.calls.get(service, 0) + 1
        self.requests.append((service, op, dict(params)))
        result = self.table.get((service, op), [])
        if isinstance(result, Exception):
            raise result
        if callable(result):
            return result(params)
        return list(result)
