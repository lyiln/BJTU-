from __future__ import annotations

from dataclasses import asdict
from datetime import date

import pytest

from bjtu_rooms.core import period_statuses, ranges_overlap, search_empty_rooms
from bjtu_rooms.models import Occupancy, Preference, Room


def test_ranges_overlap() -> None:
    assert ranges_overlap(1, 2, 2, 3)
    assert ranges_overlap(3, 5, 1, 3)
    assert not ranges_overlap(1, 2, 3, 4)


def test_ranges_overlap_rejects_invalid_periods() -> None:
    with pytest.raises(ValueError):
        ranges_overlap(4, 3, 1, 2)


def test_search_empty_rooms_prefers_favorite_building_then_free_duration() -> None:
    day = date(2026, 7, 2)
    rooms = [
        Room(raw_name="SY101", building="sy", room="101"),
        Room(raw_name="YF401", building="yf", room="401"),
        Room(raw_name="YF201", building="yf", room="201"),
    ]
    occupancy_by_room = {
        "SY101": [Occupancy("SY101", day, 7, 7)],
        "YF401": [Occupancy("YF401", day, 7, 7)],
        "YF201": [Occupancy("YF201", day, 6, 6)],
    }

    results = search_empty_rooms(
        rooms,
        occupancy_by_room,
        day,
        start_period=3,
        end_period=4,
        preference=Preference(preferred_buildings=("yf",), preferred_room_prefixes=("4",)),
    )

    assert [item.raw_name for item in results] == ["YF401", "YF201", "SY101"]
    assert results[0].preference_matched is True
    assert results[0].free_until_period == 6
    assert [status.period for status in results[0].period_statuses] == [1, 2, 3, 4, 5, 6, 7]
    assert [status.period for status in results[0].period_statuses if status.selected] == [3, 4]
    payload = asdict(results[0])
    assert payload["period_statuses"][0] == {
        "period": 1,
        "available": True,
        "selected": False,
    }


def test_search_excludes_occupied_rooms() -> None:
    day = date(2026, 7, 2)
    rooms = [Room(raw_name="YF401", building="yf", room="401")]
    occupancy_by_room = {"YF401": [Occupancy("YF401", day, 3, 4)]}

    results = search_empty_rooms(
        rooms,
        occupancy_by_room,
        day,
        start_period=3,
        end_period=4,
        preference=Preference(),
    )

    assert results == []


def test_period_statuses_marks_availability_and_selected_periods() -> None:
    day = date(2026, 7, 2)
    statuses = period_statuses(
        [
            Occupancy("YF401", day, 2, 2),
            Occupancy("YF401", day, 5, 6),
        ],
        day,
        selected_start_period=3,
        selected_end_period=5,
    )

    assert [(status.period, status.available, status.selected) for status in statuses] == [
        (1, True, False),
        (2, False, False),
        (3, True, True),
        (4, True, True),
        (5, False, True),
        (6, False, False),
        (7, True, False),
    ]
