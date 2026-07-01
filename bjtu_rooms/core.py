from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date

from .models import MAX_PERIOD, Occupancy, Preference, Room, SearchResult

BUILDING_LABELS = {
    "sy": "思源楼",
    "sx": "思源西楼",
    "sd": "思源东楼",
    "yf": "逸夫教学楼",
    "jx": "机械楼",
    "dy": "第一教学楼",
    "de": "第二教学楼",
    "dw": "第五教学楼",
    "dq": "第七教学楼",
    "db": "第八教学楼",
    "dj": "第九教学楼",
    "ty": "天佑会堂",
    "zy": "致远楼",
    "zx": "知行楼",
    "xx": "信息楼",
}


def ranges_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    validate_period_range(start_a, end_a)
    validate_period_range(start_b, end_b)
    return start_a <= end_b and start_b <= end_a


def validate_period_range(start_period: int, end_period: int) -> None:
    if start_period < 1 or end_period < 1:
        raise ValueError("periods must be positive")
    if start_period > end_period:
        raise ValueError("start_period cannot be after end_period")
    if end_period > MAX_PERIOD:
        raise ValueError(f"end_period cannot exceed {MAX_PERIOD}")


def split_room_name(raw_name: str) -> tuple[str, str]:
    normalized = re.sub(r"\s+", "", raw_name).lower()
    match = re.match(r"([a-zA-Z\u4e00-\u9fff]+)[-_\s]*([0-9a-zA-Z\-]+)$", normalized)
    if not match:
        return normalized, ""
    return match.group(1), match.group(2)


def normalize_room(raw_name: str, campus: str = "") -> Room:
    building, room = split_room_name(raw_name)
    return Room(raw_name=raw_name.strip(), building=building, room=room, campus=campus.strip())


def is_room_free(
    occupancies: Iterable[Occupancy],
    day: date,
    start_period: int,
    end_period: int,
) -> bool:
    validate_period_range(start_period, end_period)
    return not any(
        occupancy.day == day
        and ranges_overlap(start_period, end_period, occupancy.start_period, occupancy.end_period)
        for occupancy in occupancies
    )


def free_until_period(
    occupancies: Iterable[Occupancy],
    day: date,
    after_period: int,
) -> int:
    if after_period < 1 or after_period > MAX_PERIOD:
        raise ValueError(f"after_period must be between 1 and {MAX_PERIOD}")
    blockers = sorted(
        occupancy.start_period
        for occupancy in occupancies
        if occupancy.day == day and occupancy.start_period > after_period
    )
    if not blockers:
        return MAX_PERIOD
    return blockers[0] - 1


def preference_score(room: Room, preference: Preference) -> int:
    score = 0
    building = room.building.lower()
    room_no = room.room.lower()
    preferred_buildings = {item.lower() for item in preference.preferred_buildings}
    preferred_prefixes = tuple(item.lower() for item in preference.preferred_room_prefixes)
    if building in preferred_buildings:
        score += 100
    if preferred_prefixes and room_no.startswith(preferred_prefixes):
        score += 30
    return score


def search_empty_rooms(
    rooms: Iterable[Room],
    occupancy_by_room: dict[str, list[Occupancy]],
    day: date,
    start_period: int,
    end_period: int,
    preference: Preference,
    building_filter: str | None = None,
) -> list[SearchResult]:
    validate_period_range(start_period, end_period)
    building_filter_normalized = building_filter.strip().lower() if building_filter else ""
    results: list[SearchResult] = []

    for room in rooms:
        if building_filter_normalized and not building_matches(room, building_filter_normalized):
            continue

        occupancies = occupancy_by_room.get(room.raw_name, [])
        if not is_room_free(occupancies, day, start_period, end_period):
            continue

        free_until = free_until_period(occupancies, day, end_period)
        score = preference_score(room, preference)
        results.append(
            SearchResult(
                building=room.building,
                building_label=building_label(room.building),
                room=room.room,
                campus=room.campus,
                raw_name=room.raw_name,
                free_until_period=free_until,
                continuous_free_periods=free_until - start_period + 1,
                preference_matched=score > 0,
                preference_score=score,
            )
        )

    return sorted(
        results,
        key=lambda item: (
            -item.preference_score,
            -item.continuous_free_periods,
            item.building,
            natural_room_key(item.room),
        ),
    )


def natural_room_key(value: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", value.lower())
    return tuple(int(part) if part.isdigit() else part for part in parts)


def building_label(building: str) -> str:
    return BUILDING_LABELS.get(building.lower(), building)


def building_matches(room: Room, building_filter: str) -> bool:
    filter_value = building_filter.strip().lower()
    if not filter_value:
        return True
    building = room.building.lower()
    label = building_label(building).lower()
    raw_name = room.raw_name.lower()
    return (
        filter_value == building
        or filter_value in label
        or filter_value in raw_name
    )
