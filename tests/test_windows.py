from datetime import datetime

from collector.windows import month_windows


def test_month_windows_single_short_range():
    begin, end = datetime(2026, 10, 30), datetime(2026, 11, 2, 23, 59)
    assert month_windows(begin, end) == [(begin, end)]


def test_month_windows_splits_90_days_into_contiguous_windows():
    begin, end = datetime(2026, 8, 4), datetime(2026, 11, 2, 23, 59)
    windows = month_windows(begin, end)
    assert 3 <= len(windows) <= 4
    assert windows[0][0] == begin and windows[-1][1] == end
    for (b1, e1), (b2, e2) in zip(windows, windows[1:]):
        assert b2 > e1 and (b2 - e1).total_seconds() <= 60
        assert (e1 - b1).days <= 30
    assert all((e - b).days <= 30 for b, e in windows)


def test_month_windows_rejects_inverted_range():
    import pytest
    with pytest.raises(ValueError):
        month_windows(datetime(2026, 11, 2), datetime(2026, 11, 1))
