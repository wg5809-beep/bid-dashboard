"""공공데이터포털(data.go.kr) 공통 클라이언트.

페이지네이션, resultCode 판정, 일시 오류 재시도, 서비스별 호출 예산을 담당한다.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from urllib.parse import quote, quote_plus

import requests

RETRY_BACKOFF = 0.6
MAX_RETRIES = 3
TIMEOUT = 30
EMPTY_CODES = {"00", "03"}
TRANSIENT_CODES = {"01", "05"}


_KEY_QUERY_RE = re.compile(r"(serviceKey=)[^&\s]+")


def redact(text: str, key: str | None) -> str:
    """오류 메시지에서 인증키를 가린다: serviceKey=... 쿼리와 원본/URL인코딩 형태 모두."""
    masked = _KEY_QUERY_RE.sub(r"\1***", str(text))
    if key:
        for form in {key, quote(key, safe=""), quote_plus(key)}:
            masked = masked.replace(form, "***")
    return masked


class DataGoError(Exception):
    def __init__(self, service: str, code: str, message: str, key: str | None = None):
        message = redact(message, key)
        super().__init__(f"{service}: {code} {message}")
        self.service = service
        self.code = code
        self.message = message


def _to_list(items) -> list[dict]:
    if isinstance(items, dict) and "item" in items:
        items = items["item"]
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return [i for i in items if isinstance(i, dict)]
    return []


class DataGoClient:
    def __init__(
        self,
        service_key: str,
        session=None,
        max_calls_per_service: int = 100,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not service_key:
            raise RuntimeError("DATA_GO_KR_SERVICE_KEY not configured")
        self._key = service_key
        self._session = session or requests.Session()
        self._sleep = sleep
        self.max_calls_per_service = max_calls_per_service
        self.calls: dict[str, int] = {}

    def __repr__(self) -> str:
        return f"DataGoClient(calls={self.calls})"

    def _budget(self, service: str) -> None:
        used = self.calls.get(service, 0)
        if used >= self.max_calls_per_service:
            raise DataGoError(service, "LOCAL_LIMIT", f"daily call budget {self.max_calls_per_service} reached")
        self.calls[service] = used + 1

    def _request(self, service: str, url: str, params: dict) -> dict:
        last_error: DataGoError | None = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt:
                self._sleep(RETRY_BACKOFF * (2 ** (attempt - 1)))
            try:
                resp = self._session.get(url, params=params, timeout=TIMEOUT)
            except requests.RequestException as exc:
                last_error = DataGoError(service, "NETWORK", f"{type(exc).__name__}: {exc}", self._key)
                continue
            if resp.status_code >= 500 or resp.status_code == 429:
                last_error = DataGoError(service, f"HTTP_{resp.status_code}", "transient http error")
                continue
            if resp.status_code >= 400:
                raise DataGoError(service, f"HTTP_{resp.status_code}", "client error")
            try:
                body = resp.json()
            except ValueError as exc:
                raise DataGoError(service, "BAD_JSON", str(exc), self._key) from exc
            code, msg = _header(body)
            if not code:  # 헤더 없는 응답(게이트웨이 오류 페이지 등)은 일시 오류로 보고 재시도
                snippet = str(body)[:160]
                last_error = DataGoError(service, "BAD_RESPONSE", f"no result header: {snippet}", self._key)
                continue
            if code in TRANSIENT_CODES:
                last_error = DataGoError(service, code, msg)
                continue
            if code not in EMPTY_CODES:
                raise DataGoError(service, code, msg)
            return body
        assert last_error is not None
        raise last_error

    def get_items(
        self,
        service: str,
        base_url: str,
        op: str,
        params: dict,
        page_size: int = 500,
        json_param: str = "type",
    ) -> list[dict]:
        url = f"{base_url.rstrip('/')}/{op}"
        collected: list[dict] = []
        page = 1
        while True:
            self._budget(service)
            query = {**params, "serviceKey": self._key, "pageNo": str(page),
                     "numOfRows": str(page_size), json_param: "json"}
            body = self._request(service, url, query)
            items, total = _body(body)
            collected.extend(items)
            if not items or len(collected) >= total or len(items) < page_size:
                return collected
            page += 1


def _header(body: dict) -> tuple[str, str]:
    header = (body.get("response") or {}).get("header") or {}
    return str(header.get("resultCode", "")), str(header.get("resultMsg", ""))


def _body(body: dict) -> tuple[list[dict], int]:
    section = (body.get("response") or {}).get("body") or {}
    items = _to_list(section.get("items"))
    try:
        total = int(section.get("totalCount") or 0)
    except (TypeError, ValueError):
        total = len(items)
    return items, total
