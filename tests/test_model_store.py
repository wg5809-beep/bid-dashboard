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


def test_notice_defaults_category_other_for_old_json():
    from tests.helpers import make_notice
    n = make_notice()
    assert n.category == "other" and n.service is None
    data = {k: v for k, v in n.to_dict().items() if k not in ("category", "service")}
    assert Notice.from_dict(data).category == "other"


def test_plan_roundtrip(tmp_path: Path):
    from collector.model import Plan
    from collector.store.json_store import load_plans, save_plans
    from tests.helpers import make_plan
    plan = make_plan(notice_nos=("R26BK00000001",))
    path = tmp_path / "plans.json"
    save_plans(path, {plan.key: plan})
    loaded = load_plans(path)
    assert loaded == {plan.key: plan} and isinstance(loaded[plan.key].notice_nos, tuple)
    assert Plan.from_dict(plan.to_dict()) == plan
    assert load_plans(tmp_path / "nope.json") == {}


def test_meta_from_old_json_defaults_plan_counts():
    meta = Meta.from_dict({"run_at": "2026-11-02T07:00", "ok": True, "calls": {}, "new_notices": 0, "updated_notices": 0,
                           "new_awards": 0, "errors": [], "notice_count": 1, "award_count": 0})
    assert meta.plan_count == 0 and meta.new_plans == 0
