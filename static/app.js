const statusText = document.querySelector("#statusText");
const syncButton = document.querySelector("#syncButton");
const searchForm = document.querySelector("#searchForm");
const preferenceForm = document.querySelector("#preferenceForm");
const credentialForm = document.querySelector("#credentialForm");
const dateInput = document.querySelector("#dateInput");
const startPeriod = document.querySelector("#startPeriod");
const endPeriod = document.querySelector("#endPeriod");
const buildingInput = document.querySelector("#buildingInput");
const buildingPrefs = document.querySelector("#buildingPrefs");
const roomPrefs = document.querySelector("#roomPrefs");
const usernameInput = document.querySelector("#usernameInput");
const passwordInput = document.querySelector("#passwordInput");
const resultCount = document.querySelector("#resultCount");
const resultsBody = document.querySelector("#resultsBody");
const toast = document.querySelector("#toast");

init();

function init() {
  const today = new Date();
  dateInput.value = formatLocalDate(today);
  fillPeriods();
  startPeriod.value = "1";
  endPeriod.value = "2";
  loadStatus();
  loadBuildings();
  loadPreferences();
}

function fillPeriods() {
  for (let period = 1; period <= 7; period += 1) {
    const startOption = document.createElement("option");
    startOption.value = String(period);
    startOption.textContent = `第 ${period} 节`;
    startPeriod.append(startOption);

    const endOption = document.createElement("option");
    endOption.value = String(period);
    endOption.textContent = `第 ${period} 节`;
    endPeriod.append(endOption);
  }
}

syncButton.addEventListener("click", async () => {
  syncButton.disabled = true;
  showToast("开始同步教务系统数据...");
  try {
    const payload = await requestJson("/api/sync", { method: "POST" });
    showToast(payload.message);
    await loadStatus();
    await loadBuildings();
  } catch (error) {
    showToast(error.message, true);
    await loadStatus();
  } finally {
    syncButton.disabled = false;
  }
});

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const params = new URLSearchParams({
    date: dateInput.value,
    start_period: startPeriod.value,
    end_period: endPeriod.value,
  });
  if (buildingInput.value.trim()) {
    params.set("building", buildingInput.value.trim());
  }
  try {
    const payload = await requestJson(`/api/search?${params.toString()}`);
    renderResults(payload.items);
  } catch (error) {
    showToast(error.message, true);
  }
});

preferenceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    preferred_buildings: splitCsv(buildingPrefs.value),
    preferred_room_prefixes: splitCsv(roomPrefs.value),
  };
  try {
    await requestJson("/api/preferences", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    showToast("偏好已保存。");
  } catch (error) {
    showToast(error.message, true);
  }
});

credentialForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await requestJson("/api/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: usernameInput.value,
        password: passwordInput.value,
      }),
    });
    passwordInput.value = "";
    showToast("账号已保存到本机。");
    await loadStatus();
  } catch (error) {
    showToast(error.message, true);
  }
});

async function loadStatus() {
  try {
    const payload = await requestJson("/api/status");
    const sync = payload.sync;
    const pieces = [];
    pieces.push(`本地教室数：${payload.rooms_count}`);
    if (sync.last_sync_date) {
      pieces.push(`最近同步：${sync.last_sync_date}`);
    } else {
      pieces.push("尚未同步");
    }
    if (!payload.has_username) {
      pieces.push("请先保存教务账号");
    }
    if (sync.status === "error") {
      pieces.push(`同步错误：${sync.message}`);
    }
    statusText.textContent = pieces.join(" · ");
  } catch (error) {
    statusText.textContent = `状态读取失败：${error.message}`;
  }
}

async function loadBuildings() {
  try {
    const payload = await requestJson("/api/buildings");
    const currentValue = buildingInput.value;
    buildingInput.textContent = "";

    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "全部教学楼";
    buildingInput.append(allOption);

    for (const item of payload.items) {
      const option = document.createElement("option");
      option.value = item.value;
      option.textContent = item.label;
      buildingInput.append(option);
    }
    buildingInput.value = currentValue;
  } catch (error) {
    showToast(error.message, true);
  }
}

async function loadPreferences() {
  try {
    const payload = await requestJson("/api/preferences");
    buildingPrefs.value = payload.preferred_buildings.join(", ");
    roomPrefs.value = payload.preferred_room_prefixes.join(", ");
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderResults(items) {
  resultCount.textContent = `${items.length} 间可用`;
  resultsBody.textContent = "";
  if (!items.length) {
    const row = document.createElement("tr");
    row.innerHTML = `<td colspan="5" class="empty">这个时间段没有查到空教室。</td>`;
    resultsBody.append(row);
    return;
  }

  for (const item of items) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(item.raw_name)}</td>
      <td>${escapeHtml(item.building_label || item.building || "-")}</td>
      <td>第 ${item.free_until_period} 节</td>
      <td>${item.continuous_free_periods} 节</td>
      <td>${item.preference_matched ? '<span class="badge">偏好</span>' : ""}</td>
    `;
    resultsBody.append(row);
  }
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "请求失败");
  }
  return payload;
}

function splitCsv(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.classList.remove("show");
  }, 3600);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatLocalDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
