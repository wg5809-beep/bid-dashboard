import json
from pathlib import Path

from collector.model import STATUS, Award, Meta, Notice
from collector.store.json_store import (
    load_awards,
    load_json,
    load_notices,
    save_awards,
    save_json,
    save_notices,
)
from tests.helpers import make_award, make_notice


def test_status_constants():
    assert STATUS == ("open", "closed", "opened", "awarded", "failed", "rebid", "cancelled", "unknown")


def test_notice_roundtrip(tmp_path: Path):
    notice = make_notice(history=({"notice_ord": "000", "close_at": "2026-11-10T00:00"},))
    path = tmp_path / "notices.json"
    save_notices(path, {notice.key: notice})
    loaded = load_notices(path)
    assert loaded == {notice.key: notice}
    assert isinstance(loaded[notice.key].limit_regions, tuple)
    assert isinstance(loaded[notice.key].history, tuple)
    assert Notice.from_dict(notice.to_dict()) == notice


def test_award_roundtrip(tmp_path: Path):
    award = make_award()
    path = tmp_path / "awards.json"
    save_awards(path, {award.key: award})
    assert load_awards(path) == {award.key: award}
    assert Award.from_dict(award.to_dict()) == award


def test_meta_roundtrip():
    meta = Meta(run_at="2026-11-02T07:00", ok=False, calls={"nara_bids": 12}, new_notices=3,
                updated_notices=1, new_awards=0, errors=("nara_awards: 22 limit",),
                notice_count=10, award_count=2)
    assert Meta.from_dict(meta.to_dict()) == meta


def test_load_missing_file_returns_default(tmp_path: Path):
    assert load_json(tmp_path / "nope.json", {"items": []}) == {"items": []}
    assert load_notices(tmp_path / "nope.json") == {}


def test_save_json_is_atomic_and_utf8(tmp_path: Path):
    path = tmp_path / "x.json"
    save_json(path, {"items": [{"title": "회계감사"}]})
    raw = path.read_text(encoding="utf-8")
    assert "회계감사" in raw and "\\u" not in raw
    assert json.loads(raw)["items"][0]["title"] == "회계감사"
    assert [p.name for p in tmp_path.iterdir()] == ["x.json"]
