// ZKTeco Device Management page (pull method)
let devices = [];

document.addEventListener("DOMContentLoaded", function () {
  if (typeof auth === "undefined" || !auth.requirePageAccess) {
    setTimeout(function () {
      if (typeof auth !== "undefined" && auth.requirePageAccess) init();
      else window.location.href = "/login.html";
    }, 100);
    return;
  }
  init();
});

function init() {
  if (!auth.requirePageAccess("hr")) return;
  loadDevices();
  setupBackButton();
  setupModals();
}

function setupBackButton() {
  const backBtn = document.getElementById("back-btn");
  if (backBtn) {
    backBtn.addEventListener("click", function (e) {
      e.preventDefault();
      window.location.href = "/hr";
    });
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : text;
  return div.innerHTML;
}

async function loadDevices() {
  const el = document.getElementById("deviceList");
  if (!el) return;
  try {
    const data = await APIHelper.get("/api/zkteco/devices");
    devices = (data && data.devices) ? data.devices : [];
    renderDevices();
  } catch (err) {
    console.error("Error loading devices:", err);
    el.innerHTML = '<div class="empty-cell">Failed to load devices.</div>';
  }
}

function renderDevices() {
  const el = document.getElementById("deviceList");
  if (!el) return;
  if (devices.length === 0) {
    el.innerHTML = '<div class="empty-cell">No devices. Click "Add device" to add a ZKTeco device (IP + port).</div>';
    return;
  }
  el.innerHTML = devices
    .map(function (d) {
      const addr = d.ip_address != null && d.port != null ? escapeHtml(d.ip_address) + ":" + d.port : "—";
      return (
        '<div class="device-card" data-id="' +
        d.id +
        '">' +
        '<div class="device-info">' +
        "<strong>" +
        escapeHtml(d.name || "Device") +
        "</strong>" +
        '<span class="device-addr">' +
        addr +
        "</span>" +
        (d.last_sync ? '<span class="device-last-sync">Last sync: ' + escapeHtml(d.last_sync) + "</span>" : "") +
        (d.last_sync_status ? '<span class="device-status">' + escapeHtml(d.last_sync_status) + "</span>" : "") +
        "</div>" +
        '<div class="device-actions">' +
        '<button type="button" class="btn-device btn-test" data-id="' +
        d.id +
        '">Test</button>' +
        '<button type="button" class="btn-device btn-sync" data-id="' +
        d.id +
        '">Sync</button>' +
        "</div>" +
        "</div>"
      );
    })
    .join("");

  el.querySelectorAll(".btn-test").forEach(function (btn) {
    btn.addEventListener("click", function () {
      testDevice(Number(this.getAttribute("data-id")));
    });
  });
  el.querySelectorAll(".btn-sync").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const id = Number(this.getAttribute("data-id"));
      const dev = devices.find(function (d) {
        return d.id === id;
      });
      openSyncModal(id, dev ? dev.name : "Device");
    });
  });
}

async function testDevice(deviceId) {
  const btn = document.querySelector(".btn-test[data-id='" + deviceId + "']");
  if (btn) btn.disabled = true;
  try {
    const res = await APIHelper.request("/api/zkteco/devices/" + deviceId + "/test", { method: "POST" });
    const ok = res && res.success;
    const msg = (res && res.message) || "Unknown response";
    if (typeof showNotification === "function") showNotification(msg, ok ? "success" : "error");
  } catch (err) {
    if (typeof showNotification === "function") showNotification(err.message || "Test failed", "error");
  }
  if (btn) btn.disabled = false;
}

function openDeviceModal() {
  document.getElementById("deviceForm").reset();
  document.getElementById("devicePort").value = "4370";
  document.getElementById("deviceTimeout").value = "30";
  document.getElementById("deviceModal").classList.add("active");
}

function closeDeviceModal() {
  document.getElementById("deviceModal").classList.remove("active");
}

async function saveDevice() {
  const name = document.getElementById("deviceName").value.trim();
  const ip = document.getElementById("deviceIp").value.trim();
  const port = parseInt(document.getElementById("devicePort").value, 10) || 4370;
  const timeout = parseInt(document.getElementById("deviceTimeout").value, 10) || 30;
  const serialNumber = document.getElementById("deviceSn").value.trim();
  if (!name || !ip) {
    if (typeof showNotification === "function") showNotification("Name and IP address are required.", "error");
    return;
  }
  try {
    const body = { name, ip_address: ip, port, timeout };
    if (serialNumber) body.serial_number = serialNumber;
    const res = await APIHelper.request("/api/zkteco/devices", {
      method: "POST",
      body: JSON.stringify(body)
    });
    if (res && res.device && !res.error) {
      if (typeof showNotification === "function") showNotification("Device added successfully.", "success");
      closeDeviceModal();
      loadDevices();
    } else throw new Error((res && res.error) || "Failed to add device");
  } catch (err) {
    if (typeof showNotification === "function") showNotification(err.message || "Failed to add device.", "error");
  }
}

let syncDeviceId = null;

function openSyncModal(deviceId, deviceName) {
  syncDeviceId = deviceId;
  document.getElementById("syncDeviceName").textContent = "Sync from: " + (deviceName || "Device");
  document.getElementById("syncStartDate").value = "";
  document.getElementById("syncEndDate").value = "";
  document.getElementById("syncModal").classList.add("active");
}

function closeSyncModal() {
  syncDeviceId = null;
  document.getElementById("syncModal").classList.remove("active");
}

async function confirmSync() {
  if (!syncDeviceId) return;
  const start = document.getElementById("syncStartDate").value.trim();
  const end = document.getElementById("syncEndDate").value.trim();
  const body = {};
  if (start) body.start_date = start;
  if (end) body.end_date = end;
  const confirmBtn = document.getElementById("confirmSyncBtn");
  if (confirmBtn) confirmBtn.disabled = true;
  try {
    const res = await APIHelper.request("/api/zkteco/devices/" + syncDeviceId + "/sync", {
      method: "POST",
      body: JSON.stringify(body)
    });
    if (res && !res.error) {
      const msg =
        "Synced: " +
        (res.created || 0) +
        " created, " +
        (res.updated || 0) +
        " updated." +
        (res.skipped_unknown_user ? " " + res.skipped_unknown_user + " unknown user(s) skipped." : "");
      if (typeof showNotification === "function") showNotification(msg, "success");
      closeSyncModal();
      loadDevices();
    } else throw new Error((res && res.error) || "Sync failed");
  } catch (err) {
    if (typeof showNotification === "function") showNotification(err.message || "Sync failed.", "error");
  }
  if (confirmBtn) confirmBtn.disabled = false;
}

function setupModals() {
  const addBtn = document.getElementById("addDeviceBtn");
  if (addBtn) addBtn.addEventListener("click", openDeviceModal);
  const refreshBtn = document.getElementById("refreshDevicesBtn");
  if (refreshBtn) refreshBtn.addEventListener("click", function () {
    refreshBtn.disabled = true;
    loadDevices().finally(function () {
      refreshBtn.disabled = false;
    });
  });
  const closeDeviceBtn = document.getElementById("closeDeviceModal");
  const cancelDeviceBtn = document.getElementById("cancelDeviceBtn");
  const saveDeviceBtn = document.getElementById("saveDeviceBtn");
  if (closeDeviceBtn) closeDeviceBtn.addEventListener("click", closeDeviceModal);
  if (cancelDeviceBtn) cancelDeviceBtn.addEventListener("click", closeDeviceModal);
  if (saveDeviceBtn) saveDeviceBtn.addEventListener("click", saveDevice);
  const deviceModal = document.getElementById("deviceModal");
  if (deviceModal) deviceModal.addEventListener("click", function (e) { if (e.target === deviceModal) closeDeviceModal(); });
  const closeSyncBtn = document.getElementById("closeSyncModal");
  const cancelSyncBtn = document.getElementById("cancelSyncBtn");
  const confirmSyncBtn = document.getElementById("confirmSyncBtn");
  if (closeSyncBtn) closeSyncBtn.addEventListener("click", closeSyncModal);
  if (cancelSyncBtn) cancelSyncBtn.addEventListener("click", closeSyncModal);
  if (confirmSyncBtn) confirmSyncBtn.addEventListener("click", confirmSync);
  const syncModal = document.getElementById("syncModal");
  if (syncModal) syncModal.addEventListener("click", function (e) { if (e.target === syncModal) closeSyncModal(); });
}
