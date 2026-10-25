// ZKTeco Device Management page (PUSH: device sends attendance to this server)
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
    devices = data && data.devices ? data.devices : [];
    renderDevices();
  } catch (err) {
    console.error("Error loading devices:", err);
    APIHelper.renderError(el, err, loadDevices);
  }
}

function renderDevices() {
  const el = document.getElementById("deviceList");
  if (!el) return;
  if (devices.length === 0) {
    el.innerHTML =
      '<div class="empty-cell">No devices. Click "Add device" and enter the device serial number (SN). Set Cloud Server on the device to this server.</div>';
    return;
  }
  el.innerHTML = devices
    .map(function (d) {
      const addr =
        d.ip_address != null && d.port != null
          ? escapeHtml(d.ip_address) + ":" + d.port
          : "—";
      const lastSeen = d.last_seen_at
        ? '<span class="device-last-sync">Last push: ' + escapeHtml(d.last_seen_at) + "</span>"
        : "";
      return (
        '<div class="device-card" data-id="' +
        d.id +
        '">' +
        '<div class="device-info">' +
        "<strong>" +
        escapeHtml(d.name || "Device") +
        "</strong>" +
        '<span class="device-addr">SN: ' +
        escapeHtml(d.serial_number || "—") +
        (addr !== "—" ? " · " + addr : "") +
        "</span>" +
        lastSeen +
        "</div>" +
        '<div class="device-actions">' +
        '<button type="button" class="btn-device btn-remove" data-id="' +
        d.id +
        '" title="Remove device">Remove</button>' +
        "</div>" +
        "</div>"
      );
    })
    .join("");

  el.querySelectorAll(".btn-remove").forEach(function (btn) {
    btn.addEventListener("click", function () {
      removeDevice(Number(this.getAttribute("data-id")));
    });
  });
}

async function removeDevice(deviceId) {
  const dev = devices.find(function (d) {
    return d.id === deviceId;
  });
  const name = dev ? dev.name || "Device" : "this device";
  if (
    !confirm(
      "Remove " + name + " from device list? You can add it again later.",
    )
  )
    return;
  const btn = document.querySelector(".btn-remove[data-id='" + deviceId + "']");
  if (btn) btn.disabled = true;
  try {
    const res = await APIHelper.request("/api/zkteco/devices/" + deviceId, {
      method: "DELETE",
    });
    if (res && !res.error) {
      if (typeof showNotification === "function")
        showNotification("Device removed.", "success");
      loadDevices();
    } else throw new Error((res && res.error) || "Failed to remove device");
  } catch (err) {
    if (typeof showNotification === "function")
      showNotification(err.message || "Failed to remove device.", "error");
  }
  if (btn) btn.disabled = false;
}

function openDeviceModal() {
  document.getElementById("deviceForm").reset();
  const portEl = document.getElementById("devicePort");
  const timeoutEl = document.getElementById("deviceTimeout");
  if (portEl) portEl.value = "";
  if (timeoutEl) timeoutEl.value = "30";
  document.getElementById("deviceModal").classList.add("show");
}

function closeDeviceModal() {
  document.getElementById("deviceModal").classList.remove("show");
}

async function saveDevice() {
  const name = document.getElementById("deviceName").value.trim();
  const serialNumber = document.getElementById("deviceSn").value.trim();
  const ip = document.getElementById("deviceIp").value.trim();
  const portVal = document.getElementById("devicePort").value.trim();
  const timeoutVal = document.getElementById("deviceTimeout").value.trim();
  if (!serialNumber) {
    if (typeof showNotification === "function")
      showNotification("Serial number (SN) is required.", "error");
    return;
  }
  if (!name) {
    if (typeof showNotification === "function")
      showNotification("Name is required.", "error");
    return;
  }
  const body = { name, serial_number: serialNumber };
  if (ip) body.ip_address = ip;
  if (portVal) {
    const p = parseInt(portVal, 10);
    if (!isNaN(p)) body.port = p;
  }
  if (timeoutVal) {
    const t = parseInt(timeoutVal, 10);
    if (!isNaN(t)) body.timeout = t;
  }
  try {
    const res = await APIHelper.request("/api/zkteco/devices", {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (res && res.device && !res.error) {
      if (typeof showNotification === "function")
        showNotification("Device added successfully.", "success");
      closeDeviceModal();
      loadDevices();
    } else throw new Error((res && res.error) || "Failed to add device");
  } catch (err) {
    if (typeof showNotification === "function")
      showNotification(err.message || "Failed to add device.", "error");
  }
}

function setupModals() {
  const addBtn = document.getElementById("addDeviceBtn");
  if (addBtn) addBtn.addEventListener("click", openDeviceModal);
  const refreshBtn = document.getElementById("refreshDevicesBtn");
  if (refreshBtn)
    refreshBtn.addEventListener("click", function () {
      refreshBtn.disabled = true;
      loadDevices().finally(function () {
        refreshBtn.disabled = false;
      });
    });
  const closeDeviceBtn = document.getElementById("closeDeviceModal");
  const cancelDeviceBtn = document.getElementById("cancelDeviceBtn");
  const saveDeviceBtn = document.getElementById("saveDeviceBtn");
  if (closeDeviceBtn)
    closeDeviceBtn.addEventListener("click", closeDeviceModal);
  if (cancelDeviceBtn)
    cancelDeviceBtn.addEventListener("click", closeDeviceModal);
  if (saveDeviceBtn) saveDeviceBtn.addEventListener("click", saveDevice);
  const deviceModal = document.getElementById("deviceModal");
  if (deviceModal)
    deviceModal.addEventListener("click", function (e) {
      if (e.target === deviceModal) closeDeviceModal();
    });
}
