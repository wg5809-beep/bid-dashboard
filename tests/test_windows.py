from datetime import datetime, timedelta

from collector.windows import month_windows


def test_month_windows_single_short_range():
    begin, end = datetime(2026, 10, 30), datetime(2026, 11, 2, 23, 59)
    assert month_windows(begin, end) == [(begin, end)]


def test_month_windows_splits_90_days_into_contiguous_windows():
    begin, end = datetime(2026, 8, 4), datetime(2026, 11, 2, 23, 59)
    windows = month_windows(begin, end)
    assert len(windows) == 13
    assert windows[0][0] == begin and windows[-1][1] == end
    for (b1, e1), (b2, e2) in zip(windows, windows[1:]):
        assert b2 > e1 and (b2 - e1).total_seconds() <= 60


def test_month_windows_stay_within_api_7_day_limit():
    """실호출 확인(2026-11-11): 00:00~7일째 23:59는 정상, 1분만 길어도 07 입력범위값 초과."""
    limit = timedelta(days=7) - timedelta(minutes=1)
    windows = month_windows(datetime(2026, 11, 4), datetime(2026, 11, 11, 23, 59))  # 일일 낙찰 조회 범위
    assert len(windows) == 2
    assert all(e - b <= limit for b, e in windows)
    assert windows[0] == (datetime(2026, 11, 4), datetime(2026, 11, 10, 23, 59))


def test_month_windows_rejects_inverted_range():
    import pytest
    with pytest.raises(ValueError):
        month_windows(datetime(2026, 11, 2), datetime(2026, 11, 1))
