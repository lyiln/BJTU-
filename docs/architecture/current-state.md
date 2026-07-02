# BJTU Room Finder Current State

## Scope
- 本次分析范围：当前代码库的功能边界、前后端入口、搜索/同步数据流、数据库读写、外部依赖、最近修复过的状态渲染问题。
- 明确不包含：未读取运行时私有数据文件 `data/**` 的内容；未重新执行线上教务系统同步；未审查第三方服务当前可用性；未修改源码、测试、配置或依赖。

## Files Read
| File | Why Read | Key Evidence |
|---|---|---|
| `AGENTS.md` | 确认后续 AI 对话的任务前/任务后同步 hook | 任务前读取本文档；任务后如改变代码、测试、行为、API、数据流、数据库逻辑、依赖、命令或运维假设，需要更新本文档。 |
| `README.md` | 理解项目目标、启动方式、同步说明 | 项目是本地 BJTU 空教室查询工具；默认访问 `http://127.0.0.1:8000`；开发命令包含 `uv run pytest` 和 `uv run uvicorn bjtu_rooms.app:create_app --factory --reload`。 |
| `pyproject.toml` | 确认技术栈、入口脚本、测试配置 | 依赖 FastAPI、Playwright、BeautifulSoup、keyring、uvicorn；脚本 `bjtu-rooms = "bjtu_rooms.cli:main"`；pytest 读取 `tests`。 |
| `bjtu_rooms/cli.py` | 确认命令行启动路径 | `main()` 使用 `uvicorn.run("bjtu_rooms.app:app", reload=False)` 启动，默认会打开浏览器。 |
| `bjtu_rooms/app.py` | 确认 HTTP API、静态文件、应用生命周期 | 定义 `/api/status`、`/api/buildings`、`/api/search`、`/api/preferences`、`/api/credentials`、`/api/sync`；启动时可能异步同步。 |
| `bjtu_rooms/models.py` | 确认核心数据类型 | 定义 `Room`、`Occupancy`、`Preference`、`PeriodStatus`、`SearchResult`、`SyncState`；`MAX_PERIOD = 7`。 |
| `bjtu_rooms/core.py` | 确认搜索、排序、节次状态逻辑 | `search_empty_rooms()` 过滤已占用教室并生成 `period_statuses`；按偏好分、连续空闲、楼栋和自然教室号排序。 |
| `bjtu_rooms/storage.py` | 确认 SQLite schema 和读写路径 | 数据库为 `data/rooms.sqlite3`；表包括 `rooms`、`occupancies`、`preferences`、`sync_state`。 |
| `bjtu_rooms/sync.py` | 确认同步和 Playwright 抓取流程 | `sync_today()` 调用 `fetch_classroom_data()`，解析后写入数据库并保存同步状态。 |
| `bjtu_rooms/parser.py` | 确认 HTML 解析策略 | 支持 JSON-like payload、BJTU 周视图表格、通用表格、文本兜底；白色背景视为空闲。 |
| `bjtu_rooms/credentials.py` | 确认账号密码存储 | 用户名写入 settings；密码通过 `keyring` 存取，service name 为 `bjtu-room-finder`。 |
| `static/index.html` | 确认页面结构和结果表列 | 结果表当前列为教室、楼栋、今日状态、连续空闲、偏好；没有“可空到”列。 |
| `static/app.js` | 确认前端状态、fetch、渲染逻辑 | 初始化读取状态/楼栋/偏好；搜索调用 `/api/search`；`renderPeriodStatuses()` 渲染 1-7 节状态点，缺字段时显示“暂无状态”。 |
| `tests/test_core.py` | 确认核心行为测试 | 覆盖搜索排序、占用排除、`period_statuses` 生成和 `asdict()` 序列化结构。 |

## Confirmed Facts
| Fact | Evidence | Source Type | Confidence |
|---|---|---|---|
| 项目是本地 BJTU 空教室查询工具。 | `README.md` 标题和说明。 | Project Docs | Confirmed |
| 项目级 AI hook 已在 `AGENTS.md` 中定义。 | `AGENTS.md` 要求任务前读取 `docs/architecture/current-state.md`，任务后按影响范围更新该文档。 | Project Docs | Confirmed |
| Web 服务由 FastAPI 提供，静态页面在 `static/`。 | `bjtu_rooms/app.py:create_app()` 挂载 `StaticFiles(directory=STATIC_DIR)` 并返回 `static/index.html`。 | Source Code | Confirmed |
| 默认 CLI 运行不会热重载 Python 代码。 | `bjtu_rooms/cli.py:main()` 调用 `uvicorn.run(..., reload=False)`。 | Source Code | Confirmed |
| 搜索接口是 `GET /api/search`，参数包括 `date`、`start_period`、`end_period`、可选 `building`。 | `bjtu_rooms/app.py:search()`。 | Source Code | Confirmed |
| 搜索结果后端包含 `period_statuses` 字段。 | `bjtu_rooms/models.py:SearchResult.period_statuses`；`bjtu_rooms/core.py:search_empty_rooms()` 填充该字段。 | Source Code | Confirmed |
| 前端当前不展示“可空到”列。 | `static/index.html` 的表头只有教室、楼栋、今日状态、连续空闲、偏好；`static/app.js:renderResults()` 不渲染 `free_until_period`。 | Source Code | Confirmed |
| 前端遇到缺失 `period_statuses` 会显示“暂无状态”，不会再直接 `.map` 崩溃。 | `static/app.js:renderPeriodStatuses()` 先检查 `Array.isArray(statuses)`。 | Source Code | Confirmed |
| SQLite 数据库路径是 `data/rooms.sqlite3`。 | `bjtu_rooms/storage.py:DB_PATH = DATA_DIR / "rooms.sqlite3"`。 | Source Code | Confirmed |
| 同步状态保存在 `sync_state` 表，偏好保存在 `preferences` 表。 | `bjtu_rooms/storage.py:init_db()` 建表 SQL。 | Database Schema | Confirmed |
| 账号用户名存入 settings，密码存入系统 keyring。 | `bjtu_rooms/credentials.py:get_username()`、`save_username()`、`save_password()`。 | Source Code | Confirmed |
| 教务同步依赖 Playwright 打开 BJTU 教务系统并解析课堂占用 HTML。 | `bjtu_rooms/sync.py:fetch_classroom_data()` 使用 `async_playwright()`；`parse_classroom_html()` 处理 HTML。 | Source Code | Confirmed |
| 最近提交为 `a19457b Fix room status rendering`。 | `git log --oneline -n 5` 输出。 | Config | Confirmed |

## Entry Points
| Entry | File | Function / Component | Evidence |
|---|---|---|---|
| AI 任务同步 hook | `AGENTS.md` | Pre-Task Hook / Post-Task Hook | 任务前读取 `docs/architecture/current-state.md`；任务后按变更影响更新本文档。 |
| CLI 启动 | `bjtu_rooms/cli.py` | `main()` | 解析 `--host`、`--port`、`--no-browser` 后调用 uvicorn。 |
| FastAPI 应用 | `bjtu_rooms/app.py` | `create_app()` / module-level `app` | 创建 FastAPI、挂载静态文件、注册 API。 |
| 首页 | `bjtu_rooms/app.py` + `static/index.html` | `GET /` / static HTML | `index()` 返回 `static/index.html`。 |
| 状态 API | `bjtu_rooms/app.py` | `GET /api/status` | 返回 `sync`、`rooms_count`、`has_username`。 |
| 搜索 API | `bjtu_rooms/app.py` | `GET /api/search` | 读取数据库后调用 `search_empty_rooms()`。 |
| 同步 API | `bjtu_rooms/app.py` | `POST /api/sync` | 调用 `sync_today()`。 |
| 前端初始化 | `static/app.js` | `init()` | 设置今天日期、填充节次、加载状态/楼栋/偏好。 |

## Call Chain
```text
[confirmed] user opens CLI
  -> [confirmed] bjtu_rooms.cli:main()
  -> [confirmed] uvicorn runs bjtu_rooms.app:app
  -> [confirmed] bjtu_rooms.app:create_app()
  -> [confirmed] static/index.html + static/app.js served

[confirmed] user searches rooms in browser
  -> [confirmed] static/app.js:runSearch()
  -> [confirmed] GET /api/search
  -> [confirmed] bjtu_rooms.app:search()
  -> [confirmed] storage.load_rooms()
  -> [confirmed] storage.load_occupancy_by_room()
  -> [confirmed] storage.get_preference()
  -> [confirmed] core.search_empty_rooms()
  -> [confirmed] dataclasses.asdict() response payload
  -> [confirmed] static.app.js:renderResults()
  -> [confirmed] static.app.js:renderPeriodStatuses()

[confirmed] user triggers sync
  -> [confirmed] static/app.js sync button click handler
  -> [confirmed] POST /api/sync
  -> [confirmed] bjtu_rooms.app:sync()
  -> [confirmed] bjtu_rooms.sync:sync_today()
  -> [confirmed] bjtu_rooms.sync:fetch_classroom_data()
  -> [confirmed] bjtu_rooms.parser:parse_classroom_html()
  -> [confirmed] storage.upsert_rooms_and_occupancies()
  -> [confirmed] storage.save_sync_state()
```

## Data Flow
| Data | From | To | Evidence |
|---|---|---|---|
| Search parameters | `static/app.js:runSearch()` | `/api/search` query string | Uses `URLSearchParams` with date/start/end/building. |
| Rooms | SQLite `rooms` table | `load_rooms()` -> `search_empty_rooms()` | `storage.load_rooms()` returns `list[Room]`. |
| Occupancies | SQLite `occupancies` table | `load_occupancy_by_room()` -> `search_empty_rooms()` | `storage.load_occupancy_by_room()` groups records by raw room name. |
| Preferences | SQLite `preferences` table | `get_preference()` -> `preference_score()` | `storage.get_preference()` returns `Preference`; `core.preference_score()` scores building/prefix. |
| Period statuses | `core.period_statuses()` | API `items[].period_statuses` -> UI status dots | `SearchResult.period_statuses`; frontend `renderPeriodStatuses()`. |
| Sync state | `sync_today()` | SQLite `sync_state` -> `/api/status` -> topbar text | `save_sync_state()` and `app.status()`. |
| Credentials | Account modal | `/api/credentials` -> settings/keyring | `static/app.js` posts username/password; `credentials.save_credentials()` persists them. |

## State Transitions
| From | Event | To | Evidence |
|---|---|---|---|
| `sync_state.status = never` | `init_db()` creates first row | `never` with message `No sync has run yet.` | `storage.init_db()` insert-or-ignore SQL. |
| Any sync state | `sync_today()` succeeds | `ok` with synced date and message | `sync.py:sync_today()` calls `save_sync_state(..., status="ok")`. |
| Any sync state | `sync_today()` raises | `error` with exception message | `sync.py:sync_today()` catches exception and calls `save_sync_state(..., status="error")`. |
| Frontend `hasSearched = false` | Search succeeds | `hasSearched = true` | `static/app.js:runSearch()` sets it after rendering. |
| Account modal hidden | Account button click | Modal visible | `static/app.js` sets `accountModal.hidden = false`. |
| Account modal visible | Close/cancel/backdrop/save success | Modal hidden | `closeAccountModal()` sets `hidden = true`. |

## Database Operations
| Table / Entity | Operation | File | Evidence |
|---|---|---|---|
| `rooms` | Create table | `bjtu_rooms/storage.py` | `init_db()` SQL. |
| `rooms` | Insert/update room metadata | `bjtu_rooms/storage.py` | `upsert_rooms_and_occupancies()` uses `insert ... on conflict(raw_name) do update`. |
| `rooms` | Read all rooms | `bjtu_rooms/storage.py` | `load_rooms()` selects raw_name/building/room/campus. |
| `occupancies` | Create table and day/room index | `bjtu_rooms/storage.py` | `init_db()` SQL includes `idx_occupancies_day_room`. |
| `occupancies` | Replace affected days then insert occupancies | `bjtu_rooms/storage.py` | `upsert_rooms_and_occupancies()` deletes by day then inserts records. |
| `occupancies` | Read occupancies for selected day | `bjtu_rooms/storage.py` | `load_occupancy_by_room()` joins rooms and occupancies by room_id. |
| `preferences` | Create table and default row | `bjtu_rooms/storage.py` | Defaults are `["yf"]` and `["4", "5", "6"]`. |
| `preferences` | Read/write preference | `bjtu_rooms/storage.py` | `get_preference()` / `save_preference()`. |
| `sync_state` | Create table and default row | `bjtu_rooms/storage.py` | Default status `never`. |
| `sync_state` | Save sync result | `bjtu_rooms/storage.py` | `save_sync_state()`. |

## External Dependencies
| Dependency | Usage | Evidence | Risk |
|---|---|---|---|
| FastAPI | HTTP API and app factory | `pyproject.toml`; `bjtu_rooms/app.py` imports `FastAPI`, `HTTPException`, `Query` | API shape changes need frontend compatibility. |
| Uvicorn | Local server | `pyproject.toml`; `bjtu_rooms/cli.py` | CLI uses `reload=False`; code changes require service restart. |
| Playwright | BJTU login and classroom page fetch | `pyproject.toml`; `sync.py:fetch_classroom_data()` | Browser install, login structure, CAPTCHA, or network issues can break sync. |
| BeautifulSoup | HTML parsing | `pyproject.toml`; `parser.py:parse_classroom_html()` | BJTU page structure changes may require parser updates. |
| keyring | Password storage | `pyproject.toml`; `credentials.py` | Platform keychain availability affects saving/loading password. |
| SQLite stdlib | Local persistent store | `storage.py` imports `sqlite3` | Local `data/rooms.sqlite3` carries app state; not tracked by source. |

## Async Jobs
- App startup uses `lifespan()` in `bjtu_rooms/app.py`; if `sync_state.last_sync_date != date.today()`, it schedules `_startup_sync()` with `asyncio.create_task()`.
- `_startup_sync()` catches all exceptions and suppresses them. Confirmed behavior: startup sync failures do not prevent the app from serving.
- Manual sync is `POST /api/sync`; it awaits `sync_today()` and returns either `{"ok": true, "message": ...}` or an HTTP 400 with error detail.

## Error Handling
- `/api/search` catches `ValueError` from `validate_period_range()` and returns HTTP 400 with the message.
- `/api/credentials` catches `CredentialError` and returns HTTP 400.
- `/api/sync` catches general exceptions and returns HTTP 400.
- `requestJson()` in `static/app.js` parses JSON, checks `response.ok`, and throws `payload.detail || "请求失败"`.
- Frontend data-shape safeguards currently exist for arrays from `payload.items`, `payload.preferred_buildings`, `payload.preferred_room_prefixes`, building list items, missing `payload.sync`, and missing `period_statuses`.

## Edge Cases
- `period_statuses` missing from an older running backend response shows “暂无状态” in the UI. This prevents a frontend crash but means the Python service likely needs restart to load current code.
- `bjtu_rooms.cli:main()` starts uvicorn without reload. Static files may reflect disk changes immediately, while Python route logic can stay stale until restart.
- `sync_today()` raises `SyncError` if no rooms are parsed.
- `fetch_classroom_data()` falls back to headed Playwright mode if the fetched page still looks like a login page and the initial run was headless.
- Parser supports several structures, but BJTU HTML changes remain a known parser maintenance risk.

## Risks
| Risk | Evidence | Impact | Suggested Next Step |
|---|---|---|---|
| Running service can be stale after code changes. | `cli.py` uses `reload=False`; previous issue manifested as frontend expecting `period_statuses` while old backend did not return it. | UI can show fallback “暂无状态” or mismatch current code. | Restart `uv run bjtu-rooms` after backend code changes; use reload command for development. |
| Startup sync errors are silent. | `_startup_sync()` catches `Exception` and `pass`es. | User may not know startup auto-sync failed unless checking `/api/status` after manual sync. | Consider surfacing startup sync failure through `sync_state` in a future task. |
| Parser depends on current BJTU page semantics. | `parser.py` uses table text, titles, background colors, and regexes. | Sync may parse zero rooms or wrong occupancies if upstream HTML changes. | Keep sample HTML-based parser tests updated when BJTU page changes. |
| Credential storage depends on keyring availability. | `credentials.py` raises/returns based on `keyring` import and keychain operations. | Sync cannot run without saved password. | Document platform setup or provide clearer UI error if keyring fails. |

## Possible Causes to Verify
| Possible Cause | Missing Evidence | Files to Check Next |
|---|---|---|
| If UI shows “暂无状态” after this commit, the running backend may still be stale. | Need live `/api/search` response from the currently running port. | Check `/api/search` response shape and restart CLI service if missing `period_statuses`. |
| If sync returns success but search results look wrong, parser may misclassify cells. | Need saved HTML sample and parsed output comparison. | `bjtu_rooms/parser.py`, `tests/test_parser.py`, optional `data/sample-room-view.html`. |
| If account save appears successful but sync says missing credentials, keyring lookup may fail. | Need platform keyring behavior and saved username state. | `bjtu_rooms/credentials.py`, `data/settings.json` runtime file. |

## Open Questions
- Should `free_until_period` remain in the API response even though the UI no longer displays “可空到”? Current code still keeps it in `SearchResult`.
- Should startup auto-sync failures be recorded in `sync_state` instead of silently ignored?
- Should there be an integration/API test for `/api/search` response shape? Current test verifies core dataclass serialization, not the FastAPI route.
- Should developer startup default to `--reload` or a separate dev script to avoid stale Python backends?

## Recommended Next Step
- `task-planning-flow`：如果要调整行为，例如记录启动同步失败、增加 API 集成测试、改变 dev 启动方式，先出小任务方案。
- `bugfix-flow`：如果再次出现搜索状态缺失、同步错误、解析结果异常，先按 bug 流程复现和定位。
- `execute-agent`：如果已有明确方案并批准实现，再修改源码和测试。
- `review-agent`：如果需要对最近提交 `a19457b Fix room status rendering` 做第二视角复核，可只读审查 diff。
- `sync-docs-flow`：后续如果继续修改 API、状态流转或数据库逻辑，应同步更新本文档或拆分到更细的模块文档。
