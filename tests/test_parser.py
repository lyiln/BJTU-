from __future__ import annotations

from datetime import date

from bjtu_rooms.parser import parse_classroom_html


def test_parse_classroom_table() -> None:
    html = """
    <table>
      <tr>
        <th>教室</th>
        <th>第1节</th>
        <th>第2节</th>
        <th>第3节</th>
      </tr>
      <tr>
        <td>YF401</td>
        <td>空</td>
        <td>高数</td>
        <td>空</td>
      </tr>
      <tr>
        <td>SY101</td>
        <td colspan="2">第1-2节 物理</td>
        <td>-</td>
      </tr>
    </table>
    """

    rooms, occupancies = parse_classroom_html(html, date(2026, 7, 2))

    assert [room.raw_name for room in rooms] == ["SY101", "YF401"]
    assert {(item.raw_room_name, item.start_period, item.end_period) for item in occupancies} == {
        ("YF401", 2, 2),
        ("SY101", 1, 2),
    }


def test_parse_rooms_from_text_when_no_table_is_present() -> None:
    rooms, occupancies = parse_classroom_html("可查询教室：YF401、SY101", date(2026, 7, 2))

    assert {room.raw_name for room in rooms} == {"YF401", "SY101"}
    assert occupancies == []


def test_parse_bjtu_week_table() -> None:
    html = """
    <table class="table table-bordered">
      <tr>
        <th width="105">星期</th>
        <th colspan="7">星期一 <span>06月29日</span></th>
        <th colspan="7">星期二 <span>06月30日</span></th>
      </tr>
      <tr>
        <th>教室/节次</th>
        <td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td>
        <td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td>
      </tr>
      <tr>
        <td>SY101 <span class="text-muted">(90)</span></td>
        <td title="星期1 第1节" style="background-color: #d8cc56"></td>
        <td title="星期1 第2节" style="background-color: #fff"></td>
        <td title="星期1 第3节" style="background-color: #fff"></td>
        <td title="星期1 第4节" style="background-color: #fff"></td>
        <td title="星期1 第5节" style="background-color: #fff"></td>
        <td title="星期1 第6节" style="background-color: #fff"></td>
        <td title="星期1 第7节" style="background-color: #fff"></td>
        <td title="星期2 第1节" style="background-color: #fff"></td>
        <td title="星期2 第2节" style="background-color: #394ed6"></td>
        <td title="星期2 第3节" style="background-color: #fff"></td>
        <td title="星期2 第4节" style="background-color: #fff"></td>
        <td title="星期2 第5节" style="background-color: #fff"></td>
        <td title="星期2 第6节" style="background-color: #fff"></td>
        <td title="星期2 第7节" style="background-color: #fff"></td>
      </tr>
    </table>
    """

    rooms, occupancies = parse_classroom_html(html, date(2026, 7, 2))

    assert [room.raw_name for room in rooms] == ["SY101"]
    assert {(item.day.isoformat(), item.start_period) for item in occupancies} == {
        ("2026-06-29", 1),
        ("2026-06-30", 2),
    }
