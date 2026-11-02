"""JSON 파일 저장소. 쓰기는 임시파일 → os.replace 로 원자적."""
from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from collector.model import Award, Notice


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"JSON 파일을 읽을 수 없습니다: {path} ({exc})") from exc


def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"JSON 파일을 저장할 수 없습니다: {path} ({exc})") from exc


def _load_items(path: Path, factory) -> dict:
    data = load_json(path, {"items": []})
    items = [factory(item) for item in data.get("items", [])]
    return {item.key: item for item in items}


def _save_items(path: Path, items: Mapping[str, Any]) -> None:
    ordered = sorted(items.values(), key=lambda item: item.key)
    save_json(path, {"items": [item.to_dict() for item in ordered]})


def load_notices(path: Path) -> dict[str, Notice]:
    return _load_items(path, Notice.from_dict)


def save_notices(path: Path, notices: Mapping[str, Notice]) -> None:
    _save_items(path, notices)


def load_awards(path: Path) -> dict[str, Award]:
    return _load_items(path, Award.from_dict)


def save_awards(path: Path, awards: Mapping[str, Award]) -> None:
    _save_items(path, awards)
