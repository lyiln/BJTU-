from datetime import date

import pytest

from bjtu_rooms.models import Occupancy
from bjtu_rooms.sync import (
    SyncError,
    _room_view_url,
    _validate_occupancy_week,
    _week_number_from_url,
)


def test_room_view_url_uses_server_resolved_week_without_semester_configuration() -> None:
    url = _room_view_url({}, date(2026, 9, 8), server_week_number=1)

    assert url.endswith("?zc=1&perpage=500")


def test_room_view_url_uses_week_derived_from_semester_start() -> None:
    url = _room_view_url(
        {"semester_start": "2026-08-31"},
        date(2026, 9, 8),
        server_week_number=1,
    )

    assert url.endswith("?zc=2&perpage=500")


def test_week_number_from_redirected_room_view_url() -> None:
    assert _week_number_from_url("https://aa.bjtu.edu.cn/room_view/?zc=1") == 1
    assert _week_number_from_url("https://aa.bjtu.edu.cn/room_view/") is None


def test_validate_occupancy_week_rejects_records_from_another_week() -> None:
    occupancies = [
        Occupancy("YF401", date(2026, 7, 2), 1, 1),
        Occupancy("SY101", date(2026, 7, 3), 2, 2),
    ]

    with pytest.raises(SyncError, match="与查询日期不在同一周"):
        _validate_occupancy_week(occupancies, date(2026, 9, 8))


def test_validate_occupancy_week_rejects_mixed_week_records() -> None:
    occupancies = [
        Occupancy("YF401", date(2026, 9, 8), 1, 1),
        Occupancy("SY101", date(2026, 7, 3), 2, 2),
    ]

    with pytest.raises(SyncError, match="与查询日期不在同一周"):
        _validate_occupancy_week(occupancies, date(2026, 9, 8))


def test_validate_occupancy_week_accepts_records_from_target_week() -> None:
    occupancies = [Occupancy("YF401", date(2026, 9, 8), 1, 1)]

    _validate_occupancy_week(occupancies, date(2026, 9, 8))
