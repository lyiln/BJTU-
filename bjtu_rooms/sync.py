from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .credentials import get_password, get_username
from .models import Occupancy
from .parser import parse_classroom_html
from .storage import (
    get_connection,
    init_db,
    load_settings,
    prune_occupancies_outside_retention_window,
    save_sync_state,
    upsert_rooms_and_occupancies,
)

LOGIN_URL = "https://aa.bjtu.edu.cn/client/login/"
ROOM_VIEW_URL = "https://aa.bjtu.edu.cn/classroom/timeholdresult/room_view/"


class SyncError(RuntimeError):
    pass


async def sync_today(target_day: date | None = None, headed: bool = False) -> str:
    day = target_day or date.today()
    conn = get_connection()
    init_db(conn)
    try:
        rooms, occupancies = await fetch_classroom_data(day, headed=headed)
        if not rooms:
            raise SyncError("教室查询页没有解析到教室数据，可能页面结构需要校准。")
        _validate_occupancy_week(occupancies, day)
        upsert_rooms_and_occupancies(conn, rooms, occupancies, day)
        prune_occupancies_outside_retention_window(conn, day)
        message = f"同步完成：{len(rooms)} 间教室，{len(occupancies)} 条占用记录。"
        save_sync_state(conn, synced_day=day, status="ok", message=message)
        return message
    except Exception as exc:
        message = str(exc)
        save_sync_state(conn, synced_day=None, status="error", message=message)
        raise
    finally:
        conn.close()


async def fetch_classroom_data(target_day: date, headed: bool = False):
    try:
        from playwright.async_api import async_playwright
    except Exception as exc:  # pragma: no cover - dependency availability
        raise SyncError("Playwright 未安装；请先运行 `uv sync`。") from exc

    username = get_username()
    password = get_password(username) if username else None
    if not username or not password:
        raise SyncError("请先在页面中保存教务系统账号和密码。")

    settings = load_settings()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=not headed)
        page = await browser.new_page()
        try:
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
            await _login(page, username, password)
            server_week_number = None
            if not _configured_week_number(settings, target_day):
                await page.goto(ROOM_VIEW_URL, wait_until="networkidle", timeout=30_000)
                server_week_number = _week_number_from_url(page.url)
            await page.goto(
                _room_view_url(settings, target_day, server_week_number),
                wait_until="networkidle",
                timeout=30_000,
            )
            html = await page.content()
            if _looks_like_login_page(html):
                if headed:
                    raise SyncError("登录未成功，请确认账号密码或验证码。")
                await browser.close()
                return await fetch_classroom_data(target_day, headed=True)
            return parse_classroom_html(html, target_day)
        finally:
            if not page.is_closed():
                await browser.close()


async def _login(page, username: str, password: str) -> None:
    if await _is_logged_in_home(page):
        return

    username_selector = await _first_existing_selector(
        page,
        [
            "input[name='username']",
            "input[name='userName']",
            "input[name='loginname']",
            "input[id*='user']",
            "input[type='text']",
        ],
    )
    password_selector = await _first_existing_selector(
        page,
        [
            "input[name='password']",
            "input[name='passwd']",
            "input[id*='pass']",
            "input[type='password']",
        ],
    )
    if not username_selector or not password_selector:
        if await _is_logged_in_home(page):
            return
        raise SyncError("没有在登录页找到账号或密码输入框，可能需要更新登录选择器。")

    await page.fill(username_selector, username)
    await page.fill(password_selector, password)
    submit_selector = await _first_existing_selector(
        page,
        [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('登录')",
            "a:has-text('登录')",
        ],
    )
    if submit_selector:
        await page.click(submit_selector)
    else:
        await page.keyboard.press("Enter")
    await page.wait_for_load_state("domcontentloaded", timeout=30_000)


async def _is_logged_in_home(page) -> bool:
    try:
        return await page.locator("a[href*='/classroom/timeholdresult/room_view/']").count() > 0
    except Exception:
        return False


async def _first_existing_selector(page, selectors: list[str]) -> str | None:
    for selector in selectors:
        try:
            if await page.locator(selector).count() > 0:
                return selector
        except Exception:
            continue
    return None


def _looks_like_login_page(html: str) -> bool:
    lowered = html.lower()
    return "password" in lowered and ("login" in lowered or "登录" in html)


def _week_number_from_semester_start(semester_start: str | None, target_day: date) -> int | None:
    if not semester_start:
        return None
    start = datetime.fromisoformat(semester_start).date()
    delta = (target_day - start).days
    if delta < 0:
        return None
    return delta // 7 + 1


def _configured_week_number(settings: Mapping[str, Any], target_day: date) -> int | None:
    configured = settings.get("week_number")
    if isinstance(configured, int) and configured > 0:
        return configured
    if isinstance(configured, str) and configured.isdigit() and int(configured) > 0:
        return int(configured)
    semester_start = settings.get("semester_start")
    if not isinstance(semester_start, str):
        return None
    return _week_number_from_semester_start(semester_start, target_day)


def _room_view_url(
    settings: Mapping[str, Any],
    target_day: date,
    server_week_number: int | None = None,
) -> str:
    week_number = _configured_week_number(settings, target_day) or server_week_number
    if not week_number:
        raise SyncError("教务系统没有返回当前教学周，无法读取完整教室列表。")
    return f"{ROOM_VIEW_URL}?zc={week_number}&perpage=500"


def _week_number_from_url(url: str) -> int | None:
    values = parse_qs(urlparse(url).query).get("zc", [])
    if not values or not values[0].isdigit():
        return None
    return int(values[0])


def _validate_occupancy_week(
    occupancies: Sequence[Occupancy],
    target_day: date,
) -> None:
    if not occupancies:
        return
    week_start = target_day - timedelta(days=target_day.isoweekday() - 1)
    week_end = week_start + timedelta(days=6)
    if all(week_start <= occupancy.day <= week_end for occupancy in occupancies):
        return
    first_day = min(occupancy.day for occupancy in occupancies)
    last_day = max(occupancy.day for occupancy in occupancies)
    raise SyncError(
        "教务系统返回的占用日期与查询日期不在同一周："
        f"查询 {target_day.isoformat()}，返回 {first_day.isoformat()} 至 {last_day.isoformat()}。"
    )


async def sync_from_html_file(path: Path, target_day: date) -> str:
    conn = get_connection()
    init_db(conn)
    html = path.read_text(encoding="utf-8")
    rooms, occupancies = parse_classroom_html(html, target_day)
    _validate_occupancy_week(occupancies, target_day)
    upsert_rooms_and_occupancies(conn, rooms, occupancies, target_day)
    prune_occupancies_outside_retention_window(conn, target_day)
    message = f"从 HTML 样本导入完成：{len(rooms)} 间教室，{len(occupancies)} 条占用记录。"
    save_sync_state(conn, synced_day=target_day, status="ok", message=message)
    conn.close()
    return message
