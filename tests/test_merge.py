import copy
from datetime import datetime

from collector.store.merge import apply_retention, attach_awards, merge_notices
from tests.helpers import TODAY, make_award, make_notice

NOW = datetime(2026, 11, 2, 9, 0)


def test_merge_new_notice_counts_as_new():
    merged, new, updated = merge_notices({}, [make_notice()], TODAY)
    assert len(merged) == 1 and new == 1 and updated == 0
    assert merged["public:R26BK00000001"].first_seen == TODAY


def test_merge_reissue_keeps_first_seen_and_history():
    old = make_notice(notice_ord="000", close_at="2026-11-10T00:00", first_seen="2026-10-25",
                      last_seen="2026-10-25")
    new = make_notice(notice_ord="001", close_at="2026-11-17T00:00", kind="변경공고",
                      first_seen=TODAY, last_seen=TODAY)
    merged, n_new, n_upd = merge_notices({old.key: old}, [new], TODAY)
    got = merged[old.key]
    assert (n_new, n_upd) == (0, 1)
    assert got.notice_ord == "001" and got.close_at == "2026-11-17T00:00"
    assert got.first_seen == "2026-10-25" and got.last_seen == TODAY
    assert got.history[0]["close_at"] == "2026-11-10T00:00"
    assert got.history[0]["notice_ord"] == "000"


def test_merge_unchanged_not_counted():
    old = make_notice(first_seen="2026-10-25", last_seen="2026-10-25")
    merged, n_new, n_upd = merge_notices({old.key: old}, [make_notice()], TODAY)
    assert (n_new, n_upd) == (0, 0)
    assert merged[old.key].last_seen == TODAY and merged[old.key].history == ()


def test_merge_keeps_interest_true_and_result_note():
    old = make_notice(interest=True, interest_reason="본사 소재", result_note="유찰")
    incoming = make_notice(interest=False, interest_reason=None, result_note=None)
    merged, _, _ = merge_notices({old.key: old}, [incoming], TODAY)
    assert merged[old.key].interest is True
    assert merged[old.key].interest_reason == "본사 소재"
    assert merged[old.key].result_note == "유찰"


def test_merge_cancel_kind_sets_cancelled():
    old = make_notice()
    cancelled = make_notice(notice_ord="001", kind="취소공고")
    merged, _, _ = merge_notices({old.key: old}, [cancelled], TODAY)
    merged = attach_awards(merged, {}, NOW)
    assert merged[old.key].status == "cancelled"


def test_attach_awards_marks_awarded_and_keeps_others():
    done = make_notice(key="public:A", notice_no="A", close_at="2026-10-30T14:00",
                       open_at="2026-11-01T15:00")
    still_open = make_notice(key="public:B", notice_no="B")
    notices = {done.key: done, still_open.key: still_open}
    result = attach_awards(notices, {done.key: make_award(done)}, NOW)
    assert result["public:A"].status == "awarded"
    assert result["public:B"].status == "open"


def test_apply_retention_removes_old_keeps_recent():
    old = make_notice(key="public:OLD", notice_no="OLD", posted_at="2024-01-01T09:00")
    recent = make_notice(key="public:NEW", notice_no="NEW", posted_at="2026-11-01T09:00")
    nodate = make_notice(key="public:ND", notice_no="ND", posted_at=None)
    kept = apply_retention({old.key: old, recent.key: recent, nodate.key: nodate}, NOW, 730)
    assert set(kept) == {"public:NEW", "public:ND"}


def test_merge_does_not_mutate_inputs():
    old = make_notice(first_seen="2026-10-25")
    existing = {old.key: old}
    incoming = [make_notice(notice_ord="001")]
    snapshot = copy.deepcopy(existing)
    merged, _, _ = merge_notices(existing, incoming, TODAY)
    assert existing == snapshot and merged is not existing


def test_merge_reissue_resets_result_note():
    old = make_notice(notice_ord="000", result_note="유찰", close_at="2026-10-20T14:00", open_at="2026-10-21T15:00")
    reissued = make_notice(notice_ord="001", kind="재공고", close_at="2026-11-20T14:00", open_at="2026-11-21T15:00")
    merged, _, _ = merge_notices({old.key: old}, [reissued], TODAY)
    merged = attach_awards(merged, {}, NOW)
    assert merged[old.key].result_note is None and merged[old.key].status == "open"
    assert merged[old.key].history[0]["result_note"] == "유찰"


def test_merge_plans_complete_snapshot_replaces_and_keeps_first_seen():
    from collector.store.merge import merge_plans
    from tests.helpers import make_plan
    old = make_plan(first_seen="2026-11-01")
    gone = make_plan(key="plan:GONE", plan_no="GONE")
    fresh = make_plan(title="2027회계연도 외부회계감사 용역(변경)", first_seen="2026-11-06")
    added = make_plan(key="plan:NEW", plan_no="NEW", first_seen="2026-11-06")
    merged, new_count = merge_plans({old.key: old, gone.key: gone}, [fresh, added], complete=True)
    assert set(merged) == {old.key, "plan:NEW"} and new_count == 1  # 원본에서 사라진 계획은 지운다
    assert merged[old.key].title.endswith("(변경)") and merged[old.key].first_seen == "2026-11-01"
    assert merged["plan:NEW"].first_seen == "2026-11-06"


def test_merge_plans_partial_keeps_existing_when_a_call_failed():
    from collector.store.merge import merge_plans
    from tests.helpers import make_plan
    kept = make_plan(key="plan:KEPT", plan_no="KEPT")
    added = make_plan(key="plan:NEW", plan_no="NEW")
    merged, new_count = merge_plans({kept.key: kept}, [added], complete=False)
    assert set(merged) == {"plan:KEPT", "plan:NEW"} and new_count == 1


def test_prune_plans_drops_order_months_before_window():
    from collector.store.merge import prune_plans
    from tests.helpers import make_plan
    plans = {p.key: p for p in (make_plan(key="plan:A", order_ym="2026-07"), make_plan(key="plan:B", order_ym="2026-08"),
                                make_plan(key="plan:C", order_ym=None))}
    assert set(prune_plans(plans, "2026-08")) == {"plan:B", "plan:C"}
