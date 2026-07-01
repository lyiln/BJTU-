from __future__ import annotations

from datetime import date

from bjtu_rooms.models import Occupancy, Room
from bjtu_rooms.storage import (
    get_connection,
    init_db,
    load_occupancy_by_room,
    load_rooms,
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
