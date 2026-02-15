// Attendance page
let workers = [];
let attendance = [];
let zktecoDevices = [];

document.addEventListener("DOMContentLoaded", function () {
  if (typeof auth === "undefined" || !auth.requirePageAccess) {
    setTimeout(() => {
      if (typeof auth !== "undefined" && auth.requirePageAccess) initAttendance();
      else window.location.href = "login.html";
    }, 100);
    return;
  }
  initAttendance();
});

function initAttendance() {
  if (!auth.requirePageAccess("hr")) return;
  loadWorkers();
  loadAttendance();
  loadZktecoDevices();
  setupFilters();
  setupModal();
  setupZktecoModals();
  setupBackButton();
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

async function loadWorkers() {
  try {
    const data = await APIHelper.get("/api/workers");
    if (!data || !data.workers) return;
    workers = data.workers;
    const sel = document.getElementById("workerFilter");
    const formSel = document.getElementById("attWorkerId");
    [sel, formSel].forEach((s) => {
      if (!s) return;
      while (s.options.length > 1) s.remove(1);
      workers.forEach((w) => {
        const opt = document.createElement("option");
        opt.value = w.id;
        opt.textContent = (w.first_name + " " + w.last_name).trim() + " (" + (w.employee_id || "") + ")";
        s.appendChild(opt);
      });
    });
  } catch (err) {
    console.error("Error loading workers:", err);
  }
}

function getFilterParams() {
  const workerId = document.getElementById("workerFilter").value;
  const start = document.getElementById("startDate").value;
  const end = document.getElementById("endDate").value;
  let url = "/api/attendance?";
  if (workerId) url += "worker_id=" + encodeURIComponent(workerId) + "&";
  if (start) url += "start_date=" + encodeURIComponent(start) + "&";
  if (end) url += "end_date=" + encodeURIComponent(end) + "&";
  return url.replace(/&$/, "");
}

async function loadAttendance() {
  const tbody = document.getElementById("attendanceTableBody");
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="8" class="loading-cell"><div class="loading-spinner"></div> Loading...</td></tr>';
  try {
    const url = getFilterParams();
    const data = await APIHelper.get(url || "/api/attendance");
    attendance = (data && data.attendance) ? data.attendance : [];
    renderTable();
  } catch (err) {
    console.error("Error loading attendance:", err);
    tbody.innerHTML = '<tr><td colspan="8" class="empty-cell">Failed to load attendance.</td></tr>';
  }
}

function renderTable() {
  const tbody = document.getElementById("attendanceTableBody");
  if (!tbody) return;
  if (attendance.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-cell">No attendance records.</td></tr>';
    return;
  }
  tbody.innerHTML = attendance
    .map(
      (a) => `
    <tr>
      <td>${escapeHtml(a.date || "—")}</td>
      <td>${escapeHtml(a.employee_id || "—")}</td>
      <td>${escapeHtml(a.worker_name || "—")}</td>
      <td>${escapeHtml(a.check_in_time || "—")}</td>
      <td>${escapeHtml(a.check_out_time || "—")}</td>
      <td>${a.work_hours != null ? a.work_hours + " h" : "—"}</td>
      <td>${escapeHtml(a.notes || "—")}</td>
      <td>
        <button type="button" class="btn-edit" data-id="${a.id}">Edit</button>
        <button type="button" class="btn-delete" data-id="${a.id}">Delete</button>
      </td>
    </tr>
  `
    )
    .join("");

  tbody.querySelectorAll(".btn-edit").forEach((btn) => {
    btn.addEventListener("click", function () {
      openModal(Number(this.getAttribute("data-id")));
    });
  });
  tbody.querySelectorAll(".btn-delete").forEach((btn) => {
    btn.addEventListener("click", function () {
      deleteRecord(Number(this.getAttribute("data-id")));
    });
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function setupFilters() {
  const apply = document.getElementById("applyFiltersBtn");
  const clear = document.getElementById("clearFiltersBtn");
  if (apply) apply.addEventListener("click", loadAttendance);
  if (clear) {
    clear.addEventListener("click", () => {
      document.getElementById("workerFilter").value = "";
      document.getElementById("startDate").value = "";
      document.getElementById("endDate").value = "";
      loadAttendance();
    });
  }
}

function openModal(recordId) {
  const modal = document.getElementById("attendanceModal");
  const title = document.getElementById("attendanceModalTitle");
  const form = document.getElementById("attendanceForm");
  const idInput = document.getElementById("attendanceRecordId");
  const workerSel = document.getElementById("attWorkerId");
  const dateInput = document.getElementById("attDate");
  const checkIn = document.getElementById("attCheckIn");
  const checkOut = document.getElementById("attCheckOut");
  const notes = document.getElementById("attNotes");

  form.reset();
  idInput.value = recordId || "";

  if (recordId) {
    const rec = attendance.find((a) => a.id === recordId);
    if (rec) {
      title.textContent = "Edit Attendance";
      workerSel.value = rec.worker_id;
      workerSel.disabled = true;
      dateInput.value = rec.date || "";
      checkIn.value = rec.check_in_time || "";
      checkOut.value = rec.check_out_time || "";
      notes.value = rec.notes || "";
    }
  } else {
    title.textContent = "Add Attendance";
    workerSel.disabled = false;
    const today = new Date().toISOString().slice(0, 10);
    dateInput.value = today;
  }
  if (modal) modal.classList.add("active");
}

function closeModal() {
  const modal = document.getElementById("attendanceModal");
  if (modal) modal.classList.remove("active");
}

async function saveAttendance() {
  const idInput = document.getElementById("attendanceRecordId");
  const workerId = document.getElementById("attWorkerId").value;
  const dateVal = document.getElementById("attDate").value;
  const checkIn = document.getElementById("attCheckIn").value.trim();
  const checkOut = document.getElementById("attCheckOut").value.trim();
  const notes = document.getElementById("attNotes").value.trim();

  if (!workerId || !dateVal) {
    if (typeof showNotification === "function") showNotification("Worker and date are required.", "error");
    return;
  }

  const recordId = idInput.value ? Number(idInput.value) : null;
  try {
    if (recordId) {
      const res = await APIHelper.request("/api/attendance/" + recordId, {
        method: "PUT",
        body: JSON.stringify({
          date: dateVal,
          check_in_time: checkIn || null,
          check_out_time: checkOut || null,
          notes: notes || null
        })
      });
      if (res && !res.error) {
        if (typeof showNotification === "function") showNotification("Attendance updated.", "success");
        closeModal();
        loadAttendance();
      } else throw new Error(res && res.error ? res.error : "Update failed");
    } else {
      const res = await APIHelper.request("/api/attendance", {
        method: "POST",
        body: JSON.stringify({
          worker_id: Number(workerId),
          date: dateVal,
          check_in_time: checkIn || null,
          check_out_time: checkOut || null,
          notes: notes || null
        })
      });
      if (res && !res.error) {
        if (typeof showNotification === "function") showNotification("Attendance record added.", "success");
        closeModal();
        loadAttendance();
      } else throw new Error(res && res.error ? res.error : "Create failed");
    }
  } catch (err) {
    if (typeof showNotification === "function") showNotification(err.message || "Failed to save.", "error");
    else console.error(err);
  }
}

async function deleteRecord(id) {
  if (!confirm("Delete this attendance record?")) return;
  try {
    const res = await APIHelper.request("/api/attendance/" + id, { method: "DELETE" });
    if (res && !res.error) {
      if (typeof showNotification === "function") showNotification("Record deleted.", "success");
      loadAttendance();
    } else throw new Error(res && res.error ? res.error : "Delete failed");
  } catch (err) {
    if (typeof showNotification === "function") showNotification(err.message || "Failed to delete.", "error");
  }
}

function setupModal() {
  const modal = document.getElementById("attendanceModal");
  const addBtn = document.getElementById("addAttendanceBtn");
  const closeBtn = document.getElementById("closeAttendanceModal");
  const cancelBtn = document.getElementById("cancelAttendanceBtn");
  const saveBtn = document.getElementById("saveAttendanceBtn");

  if (addBtn) addBtn.addEventListener("click", () => openModal(null));
  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
  if (saveBtn) saveBtn.addEventListener("click", saveAttendance);
  if (modal) modal.addEventListener("click", function (e) { if (e.target === modal) closeModal(); });
}

// ----- ZKTeco devices -----
async function loadZktecoDevices() {
  const el = document.getElementById("zktecoDevicesList");
  if (!el) return;
  try {
    const data = await APIHelper.get("/api/zkteco/devices");
    zktecoDevices = (data && data.devices) ? data.devices : [];
    renderZktecoDevices();
  } catch (err) {
    console.error("Error loading ZKTeco devices:", err);
    el.innerHTML = '<div class="empty-cell">Failed to load devices.</div>';
  }
}

function renderZktecoDevices() {
  const el = document.getElementById("zktecoDevicesList");
  if (!el) return;
  if (zktecoDevices.length === 0) {
    el.innerHTML = '<div class="empty-cell">No ZKTeco devices. Click "Add device" to register by name and serial number (SN).</div>';
    return;
  }
  el.innerHTML = zktecoDevices
    .map(
      (d) => {
        const statusBadge = getDeviceStatusBadge(d.last_seen_at);
        return `
    <div class="zkteco-device-card" data-id="${d.id}">
      <div class="zkteco-device-info">
        <strong>${escapeHtml(d.name || "Device")}</strong>
        ${statusBadge}
        <span class="zkteco-device-addr">SN: ${escapeHtml(d.serial_number || "—")}</span>
        ${d.last_seen_at ? `<span class="zkteco-last-seen">Last seen: ${escapeHtml(d.last_seen_at)}</span>` : ""}
        ${d.last_sync ? `<span class="zkteco-last-sync">Last push: ${escapeHtml(d.last_sync)}</span>` : ""}
        ${d.last_sync_status ? `<span class="zkteco-status">${escapeHtml(d.last_sync_status)}</span>` : ""}
      </div>
    </div>
  `;
      }
    )
    .join("");
}

function getDeviceStatusBadge(lastSeenAt) {
  if (!lastSeenAt) return '<span class="zkteco-badge zkteco-badge-unknown">Not seen</span>';
  const seen = new Date(lastSeenAt.replace(" ", "T"));
  const now = new Date();
  const minutesAgo = (now - seen) / (60 * 1000);
  if (minutesAgo <= 5) return '<span class="zkteco-badge zkteco-badge-online">Online</span>';
  if (minutesAgo <= 60) return '<span class="zkteco-badge zkteco-badge-recent">Seen recently</span>';
  return '<span class="zkteco-badge zkteco-badge-offline">Not seen recently</span>';
}

function openDeviceModal() {
  document.getElementById("deviceForm").reset();
  document.getElementById("deviceModal").classList.add("active");
}

function closeDeviceModal() {
  document.getElementById("deviceModal").classList.remove("active");
}

async function saveZktecoDevice() {
  const name = document.getElementById("deviceName").value.trim();
  const serialNumber = document.getElementById("deviceSn").value.trim();
  if (!name || !serialNumber) {
    if (typeof showNotification === "function") showNotification("Name and serial number are required.", "error");
    return;
  }
  try {
    const res = await APIHelper.request("/api/zkteco/devices", {
      method: "POST",
      body: JSON.stringify({ name, serial_number: serialNumber })
    });
    if (res && res.device && !res.error) {
      if (typeof showNotification === "function") showNotification("Device added successfully.", "success");
      closeDeviceModal();
      loadZktecoDevices();
    } else throw new Error((res && res.error) || "Failed to add device");
  } catch (err) {
    if (typeof showNotification === "function") showNotification(err.message || "Failed to add device.", "error");
  }
}

function setupZktecoModals() {
  const addDeviceBtn = document.getElementById("addDeviceBtn");
  if (addDeviceBtn) addDeviceBtn.addEventListener("click", openDeviceModal);
  const refreshDevicesBtn = document.getElementById("refreshDevicesBtn");
  if (refreshDevicesBtn) refreshDevicesBtn.addEventListener("click", function () {
    refreshDevicesBtn.disabled = true;
    loadZktecoDevices().finally(function () { refreshDevicesBtn.disabled = false; });
  });

  const closeDeviceModalBtn = document.getElementById("closeDeviceModal");
  const cancelDeviceBtn = document.getElementById("cancelDeviceBtn");
  const saveDeviceBtn = document.getElementById("saveDeviceBtn");
  if (closeDeviceModalBtn) closeDeviceModalBtn.addEventListener("click", closeDeviceModal);
  if (cancelDeviceBtn) cancelDeviceBtn.addEventListener("click", closeDeviceModal);
  if (saveDeviceBtn) saveDeviceBtn.addEventListener("click", saveZktecoDevice);

  const deviceModal = document.getElementById("deviceModal");
  if (deviceModal) deviceModal.addEventListener("click", function (e) { if (e.target === deviceModal) closeDeviceModal(); });
}
