from __future__ import annotations

from datetime import date

from bjtu_rooms.models import Occupancy, Room
from bjtu_rooms.storage import (
    get_connection,
    init_db,
    load_occupancy_by_room,
    load_rooms,
    occupancy_retention_window,
    prune_occupancies_outside_retention_window,
    upsert_rooms_and_occupancies,
)


def test_upsert_rooms_and_occupancies(tmp_path) -> None:
    db_path = tmp_path / "rooms.sqlite3"
    conn = get_connection(db_path)
    init_db(conn)
    day = date(2026, 7, 2)

    upsert_rooms_and_occupancies(
        conn,
        [Room(raw_name="YF401", building="yf", room="401")],
        [Occupancy(raw_room_name="YF401", day=day, start_period=3, end_period=4)],
        day,
    )

    rooms = load_rooms(conn)
    occupancy_by_room = load_occupancy_by_room(conn, day)
    conn.close()

    assert rooms == [Room(raw_name="YF401", building="yf", room="401", campus="")]
    assert occupancy_by_room["YF401"][0].start_period == 3


def test_upsert_deduplicates_occupancies(tmp_path) -> None:
    db_path = tmp_path / "rooms.sqlite3"
    conn = get_connection(db_path)
    init_db(conn)
    day = date(2026, 7, 3)

    upsert_rooms_and_occupancies(
        conn,
        [Room(raw_name="YF401", building="yf", room="401")],
        [
            Occupancy(raw_room_name="YF401", day=day, start_period=3, end_period=4),
            Occupancy(raw_room_name="YF401", day=day, start_period=3, end_period=4),
        ],
        day,
    )

    count = conn.execute("select count(*) from occupancies").fetchone()[0]
    conn.close()

    assert count == 1


def test_prune_occupancies_keeps_current_and_next_week(tmp_path) -> None:
    db_path = tmp_path / "rooms.sqlite3"
    conn = get_connection(db_path)
    init_db(conn)
    reference_day = date(2026, 7, 3)
    old_day = date(2026, 6, 28)
    current_week_start = date(2026, 6, 29)
    next_week_end = date(2026, 7, 12)
    too_far_day = date(2026, 7, 13)

    upsert_rooms_and_occupancies(
        conn,
        [Room(raw_name="YF401", building="yf", room="401")],
        [
            Occupancy(raw_room_name="YF401", day=old_day, start_period=1, end_period=1),
            Occupancy(raw_room_name="YF401", day=current_week_start, start_period=1, end_period=1),
            Occupancy(raw_room_name="YF401", day=next_week_end, start_period=1, end_period=1),
            Occupancy(raw_room_name="YF401", day=too_far_day, start_period=1, end_period=1),
        ],
        reference_day,
    )

    deleted_count = prune_occupancies_outside_retention_window(conn, reference_day)
    remaining_days = [
        row["day"]
        for row in conn.execute("select day from occupancies order by day").fetchall()
    ]
    conn.close()

    assert occupancy_retention_window(reference_day) == (current_week_start, next_week_end)
    assert deleted_count == 2
    assert remaining_days == [current_week_start.isoformat(), next_week_end.isoformat()]
