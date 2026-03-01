// Attendance page
let workers = [];
let attendance = [];

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
  setupFilters();
  setupModal();
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
