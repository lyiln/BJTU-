from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

MAX_PERIOD = 7


@dataclass(frozen=True)
class Room:
    raw_name: str
    building: str
    room: str
    campus: str = ""


@dataclass(frozen=True)
class Occupancy:
    raw_room_name: str
    day: date
    start_period: int
    end_period: int
    source: str = ""


@dataclass(frozen=True)
class Preference:
    preferred_buildings: tuple[str, ...] = ("yf",)
    preferred_room_prefixes: tuple[str, ...] = ("4", "5", "6")


@dataclass(frozen=True)
class PeriodStatus:
    period: int
    available: bool
    selected: bool


@dataclass(frozen=True)
class SearchResult:
    building: str
    building_label: str
    room: str
    campus: str
    raw_name: str
    free_until_period: int
    continuous_free_periods: int
    preference_matched: bool
    preference_score: int
    period_statuses: tuple[PeriodStatus, ...]


@dataclass(frozen=True)
class SyncState:
    last_sync_date: date | None
    last_sync_at: datetime | None
    status: str
    message: str
