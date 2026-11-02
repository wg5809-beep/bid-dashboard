from datetime import datetime

from collector.rules.status import derive_status
from tests.helpers import make_award, make_notice

NOW = datetime(2026, 11, 2, 9, 0)


def test_derive_status_open_before_close():
    assert derive_status(make_notice(), None, NOW, None) == "open"


def test_derive_status_closed_after_close_before_open():
    n = make_notice(close_at="2026-11-01T14:00", open_at="2026-11-03T15:00")
    assert derive_status(n, None, NOW, None) == "closed"


def test_derive_status_opened_after_open():
    n = make_notice(close_at="2026-10-30T14:00", open_at="2026-11-01T15:00")
    assert derive_status(n, None, NOW, None) == "opened"


def test_derive_status_unknown_after_60_days():
    n = make_notice(close_at="2026-08-01T14:00", open_at="2026-08-02T15:00")
    assert derive_status(n, None, NOW, None) == "unknown"


def test_derive_status_awarded_when_award_present():
    n = make_notice(close_at="2026-10-30T14:00", open_at="2026-11-01T15:00")
    assert derive_status(n, make_award(n), NOW, None) == "awarded"


def test_derive_status_cancelled_by_kind():
    assert derive_status(make_notice(kind="취소공고"), None, NOW, None) == "cancelled"


def test_derive_status_failed_and_rebid_by_result_note():
    n = make_notice(close_at="2026-10-30T14:00", open_at="2026-11-01T15:00")
    assert derive_status(n, None, NOW, "유찰") == "failed"
    assert derive_status(n, None, NOW, "재입찰") == "rebid"


def test_derive_status_without_dates_is_open():
    assert derive_status(make_notice(close_at=None, open_at=None), None, NOW, None) == "open"


def test_derive_status_closed_without_open_date():
    n = make_notice(close_at="2026-11-01T14:00", open_at=None)
    assert derive_status(n, None, NOW, None) == "closed"


def test_derive_status_unknown_after_60_days_without_open_at():
    n = make_notice(close_at="2026-08-01T17:00", open_at=None)
    assert derive_status(n, None, NOW, None) == "unknown"
