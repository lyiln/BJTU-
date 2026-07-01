from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any

from bs4 import BeautifulSoup

from .core import normalize_room
from .models import MAX_PERIOD, Occupancy, Room

PERIOD_RE = re.compile(r"(?:第)?\s*(\d{1,2})\s*(?:[-~至到]\s*(\d{1,2}))?\s*节")
ROOM_RE = re.compile(r"([a-zA-Z\u4e00-\u9fff]+[-_\s]*[0-9][0-9a-zA-Z\-]*)")
DATE_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")
CHINESE_MONTH_DAY_RE = re.compile(r"(\d{1,2})月(\d{1,2})日")
WEEKDAY_PERIOD_RE = re.compile(r"星期\s*(\d)\s+第\s*(\d{1,2})\s*节")


def parse_classroom_html(html: str, fallback_day: date) -> tuple[list[Room], list[Occupancy]]:
    soup = BeautifulSoup(html, "html.parser")
    rooms: dict[str, Room] = {}
    occupancies: list[Occupancy] = []

    for room, occupancy_items in _parse_json_like_payloads(soup, fallback_day):
        rooms[room.raw_name] = room
        occupancies.extend(occupancy_items)

    for room, occupancy_items in _parse_bjtu_week_tables(soup, fallback_day):
        rooms[room.raw_name] = room
        occupancies.extend(occupancy_items)

    for room, occupancy_items in _parse_tables(soup, fallback_day):
        rooms[room.raw_name] = room
        occupancies.extend(occupancy_items)

    if not rooms:
        for room in _parse_rooms_from_text(soup.get_text("\n")):
            rooms[room.raw_name] = room

    return sorted(rooms.values(), key=lambda item: (item.building, item.room)), _dedupe_occupancies(
        occupancies
    )


def _parse_bjtu_week_tables(
    soup: BeautifulSoup,
    fallback_day: date,
) -> list[tuple[Room, list[Occupancy]]]:
    parsed: list[tuple[Room, list[Occupancy]]] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue
        if "教室/节次" not in table.get_text(" ", strip=True):
            continue

        weekday_dates = _bjtu_weekday_dates(rows[0], fallback_day)
        for tr in rows[2:]:
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            room_label = _extract_room_label(_cell_text(cells[0]))
            if not room_label:
                continue
            room = normalize_room(room_label)
            occupancies: list[Occupancy] = []
            for cell in cells[1:]:
                title = cell.get("title", "")
                match = WEEKDAY_PERIOD_RE.search(title)
                if not match:
                    continue
                weekday = int(match.group(1))
                period = int(match.group(2))
                if period < 1 or period > MAX_PERIOD:
                    continue
                if _bjtu_cell_is_available(cell):
                    continue
                day = weekday_dates.get(weekday) or _date_for_weekday(fallback_day, weekday)
                occupancies.append(
                    Occupancy(
                        raw_room_name=room.raw_name,
                        day=day,
                        start_period=period,
                        end_period=period,
                        source=title,
                    )
                )
            parsed.append((room, occupancies))
    return parsed


def _bjtu_weekday_dates(header_row: Any, fallback_day: date) -> dict[int, date]:
    dates: dict[int, date] = {}
    weekday = 1
    for cell in header_row.find_all(["td", "th"]):
        text = _cell_text(cell)
        match = CHINESE_MONTH_DAY_RE.search(text)
        if not match:
            continue
        month = int(match.group(1))
        day = int(match.group(2))
        year = _infer_year_for_month_day(month, fallback_day)
        dates[weekday] = date(year, month, day)
        weekday += 1
    return dates


def _infer_year_for_month_day(month: int, fallback_day: date) -> int:
    if fallback_day.month == 1 and month == 12:
        return fallback_day.year - 1
    if fallback_day.month == 12 and month == 1:
        return fallback_day.year + 1
    return fallback_day.year


def _date_for_weekday(fallback_day: date, weekday: int) -> date:
    return fallback_day + timedelta(days=weekday - fallback_day.isoweekday())


def _extract_room_label(value: str) -> str | None:
    without_capacity = re.sub(r"\s*\([^)]*\)\s*$", "", value).strip()
    match = ROOM_RE.fullmatch(without_capacity.replace(" ", ""))
    if not match:
        return None
    return match.group(1)


def _bjtu_cell_is_available(cell: Any) -> bool:
    style = str(cell.get("style", "")).replace(" ", "").lower()
    text = _cell_text(cell)
    if "background-color:#fff" in style or "background:#fff" in style:
        return True
    if "background-color:" in style or "background:" in style:
        return False
    return _cell_is_available(text)


def _parse_json_like_payloads(
    soup: BeautifulSoup,
    fallback_day: date,
) -> list[tuple[Room, list[Occupancy]]]:
    parsed: list[tuple[Room, list[Occupancy]]] = []
    for script in soup.find_all("script"):
        text = script.string or script.get_text()
        if not text or "room" not in text.lower():
            continue
        for json_text in _extract_json_candidates(text):
            try:
                payload = json.loads(json_text)
            except json.JSONDecodeError:
                continue
            parsed.extend(_walk_json_payload(payload, fallback_day))
    return parsed


def _extract_json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for match in re.finditer(r"(\[[\s\S]*?\]|\{[\s\S]*?\})", text):
        candidate = match.group(1).strip()
        if "room" in candidate.lower() or "教室" in candidate:
            candidates.append(candidate)
    return candidates


def _walk_json_payload(payload: Any, fallback_day: date) -> list[tuple[Room, list[Occupancy]]]:
    items: list[tuple[Room, list[Occupancy]]] = []
    if isinstance(payload, dict):
        room_name = _first_string(payload, ("room", "room_name", "classroom", "jsmc", "教室"))
        if room_name:
            room = normalize_room(room_name)
            occupancies = _occupancies_from_mapping(room.raw_name, payload, fallback_day)
            items.append((room, occupancies))
        for value in payload.values():
            items.extend(_walk_json_payload(value, fallback_day))
    elif isinstance(payload, list):
        for value in payload:
            items.extend(_walk_json_payload(value, fallback_day))
    return items


def _first_string(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    lowered = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _occupancies_from_mapping(
    raw_room_name: str,
    payload: dict[str, Any],
    fallback_day: date,
) -> list[Occupancy]:
    text = " ".join(str(value) for value in payload.values() if value is not None)
    day = _parse_date(text) or fallback_day
    return [
        Occupancy(raw_room_name=raw_room_name, day=day, start_period=start, end_period=end, source=text)
        for start, end in _parse_period_ranges(text)
    ]


def _parse_tables(soup: BeautifulSoup, fallback_day: date) -> list[tuple[Room, list[Occupancy]]]:
    parsed: list[tuple[Room, list[Occupancy]]] = []
    for table in soup.find_all("table"):
        header_periods = _header_periods(table)
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            raw_room = _extract_room_label(_cell_text(cells[0]))
            if not raw_room:
                continue
            room = normalize_room(raw_room)
            occupancies: list[Occupancy] = []
            period_cursor = 1
            for index, cell in enumerate(cells[1:], start=1):
                text = _cell_text(cell)
                colspan = int(cell.get("colspan", "1")) if str(cell.get("colspan", "1")).isdigit() else 1
                start, end = _cell_period_range(cell, text, index, period_cursor, header_periods, colspan)
                period_cursor = end + 1
                if _cell_is_available(text):
                    continue
                day = _parse_date(text) or fallback_day
                occupancies.append(
                    Occupancy(
                        raw_room_name=room.raw_name,
                        day=day,
                        start_period=start,
                        end_period=end,
                        source=text,
                    )
                )
            parsed.append((room, occupancies))
    return parsed


def _header_periods(table: Any) -> dict[int, tuple[int, int]]:
    periods: dict[int, tuple[int, int]] = {}
    first_row = table.find("tr")
    if not first_row:
        return periods
    for index, cell in enumerate(first_row.find_all(["td", "th"])[1:], start=1):
        ranges = _parse_period_ranges(_cell_text(cell))
        if ranges:
            periods[index] = ranges[0]
    return periods


def _cell_period_range(
    cell: Any,
    text: str,
    index: int,
    period_cursor: int,
    header_periods: dict[int, tuple[int, int]],
    colspan: int,
) -> tuple[int, int]:
    for attr_start, attr_end in (
        ("data-start-period", "data-end-period"),
        ("data-start", "data-end"),
        ("start", "end"),
    ):
        start_value = cell.get(attr_start)
        end_value = cell.get(attr_end)
        if str(start_value).isdigit() and str(end_value).isdigit():
            return int(start_value), int(end_value)

    ranges = _parse_period_ranges(text)
    if ranges:
        return ranges[0]
    if index in header_periods:
        return header_periods[index]
    return period_cursor, min(MAX_PERIOD, period_cursor + colspan - 1)


def _parse_rooms_from_text(text: str) -> list[Room]:
    return [normalize_room(match.group(1)) for match in ROOM_RE.finditer(text)]


def _parse_period_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in PERIOD_RE.finditer(text):
        start = int(match.group(1))
        end = int(match.group(2) or match.group(1))
        if 1 <= start <= end <= MAX_PERIOD:
            ranges.append((start, end))
    return ranges


def _parse_date(text: str) -> date | None:
    match = DATE_RE.search(text)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    return date(year, month, day)


def _cell_text(cell: Any) -> str:
    return re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip()


def _looks_like_room(value: str) -> bool:
    return bool(ROOM_RE.fullmatch(value.replace(" ", "")))


def _cell_is_available(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {"", "空", "available", "free", "-", "--", "无", "none"}


def _dedupe_occupancies(occupancies: list[Occupancy]) -> list[Occupancy]:
    seen: set[tuple[str, date, int, int]] = set()
    deduped: list[Occupancy] = []
    for occupancy in occupancies:
        key = (
            occupancy.raw_room_name,
            occupancy.day,
            occupancy.start_period,
            occupancy.end_period,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(occupancy)
    return deduped
