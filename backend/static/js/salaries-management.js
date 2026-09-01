// Salaries Management
// Future: fetch slip from GET /api/salary/record?worker_id=&month=&year= when backend is ready

let workers = [];
let departments = [];

document.addEventListener("DOMContentLoaded", function () {
  if (typeof auth === "undefined" || !auth.requirePageAccess) {
    setTimeout(() => {
      if (typeof auth !== "undefined" && auth.requirePageAccess) {
        initSalaries();
      } else {
        window.location.href = "login.html";
      }
    }, 100);
    return;
  }
  initSalaries();
});

function initSalaries() {
  if (!auth.requirePageAccess("hr")) return;
  loadDepartments();
  loadWorkers();
  setupFilters();
  setupSlipModal();
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

async function loadDepartments() {
  try {
    const data = await APIHelper.get("/api/settings/departments");
    if (data && data.departments) {
      departments = data.departments;
      const sel = document.getElementById("departmentFilter");
      if (sel) {
        departments.forEach((d) => {
          const opt = document.createElement("option");
          opt.value = d.name || d;
          opt.textContent = d.name || d;
          sel.appendChild(opt);
        });
      }
    }
  } catch (err) {
    console.error("Error loading departments:", err);
  }
}

async function loadWorkers() {
  try {
    const data = await APIHelper.get("/api/workers");
    if (!data || !data.workers) return;
    workers = data.workers;
    applyFiltersAndRender();
  } catch (err) {
    console.error("Error loading workers:", err);
    APIHelper.renderError("salariesTableBody", err, loadWorkers);
  }
}

function getFilteredWorkers() {
  const dept = document.getElementById("departmentFilter").value.trim();
  const status = document.getElementById("statusFilter").value.trim();
  return workers.filter((w) => {
    if (dept && w.department !== dept) return false;
    if (status && w.status !== status) return false;
    return true;
  });
}

function applyFiltersAndRender() {
  const filtered = getFilteredWorkers();
  renderTable(filtered);
}

function renderTable(list) {
  const tbody = document.getElementById("salariesTableBody");
  if (!tbody) return;

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-cell">No workers to display</td></tr>';
    return;
  }

  const formatSalary = (s) => {
    if (s == null || s === "") return "—";
    const n = Number(s);
    if (isNaN(n)) return "—";
    return "PKR " + n.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  tbody.innerHTML = list
    .map(
      (w) => `
    <tr>
      <td>${escapeHtml(w.employee_id || "—")}</td>
      <td>${escapeHtml([w.first_name, w.last_name].filter(Boolean).join(" ") || "—")}</td>
      <td>${escapeHtml(w.position || "—")}</td>
      <td>${escapeHtml(w.department || "—")}</td>
      <td>${formatSalary(w.salary)}</td>
      <td>
        <button type="button" class="btn-slip" data-worker-id="${w.id}">Print slip</button>
        <button type="button" class="btn-advance" data-worker-id="${w.id}"
                data-worker-name="${escapeHtml([w.first_name, w.last_name].filter(Boolean).join(" "))}"
                data-worker-salary="${w.salary || 0}">Advance</button>
      </td>
    </tr>
  `
    )
    .join("");

  tbody.querySelectorAll(".btn-slip").forEach((btn) => {
    btn.addEventListener("click", function () {
      openSlipModal(Number(this.getAttribute("data-worker-id")));
    });
  });

  tbody.querySelectorAll(".btn-advance").forEach((btn) => {
    btn.addEventListener("click", function () {
      openAdvanceModal({
        id: Number(this.getAttribute("data-worker-id")),
        name: this.getAttribute("data-worker-name"),
        salary: Number(this.getAttribute("data-worker-salary")) || 0,
      });
    });
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function setupFilters() {
  const dept = document.getElementById("departmentFilter");
  const status = document.getElementById("statusFilter");
  const clearBtn = document.getElementById("clearFiltersBtn");
  if (dept) dept.addEventListener("change", applyFiltersAndRender);
  if (status) status.addEventListener("change", applyFiltersAndRender);
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      if (dept) dept.value = "";
      if (status) status.value = "";
      applyFiltersAndRender();
    });
  }
}

// Build slip payload from attendance-based salary API; fallback to worker salary if API fails.
async function getSlipPayload(workerId, month, year) {
  const worker = workers.find((w) => w.id === workerId);
  if (!worker) return null;
  const fallback = {
    worker_id: worker.id,
    employee_id: worker.employee_id,
    first_name: worker.first_name,
    last_name: worker.last_name,
    position: worker.position,
    department: worker.department,
    base_salary: worker.salary != null ? Number(worker.salary) : 0,
    deductions: 0,
    bonuses: 0,
    net_salary: worker.salary != null ? Number(worker.salary) : 0,
    days_worked: null,
    total_hours: null,
    incomplete_records_count: 0,
    incomplete_dates: [],
    requires_manual_review: false,
    review_notes: null,
    month: Number(month),
    year: Number(year)
  };
  try {
    const res = await APIHelper.get(
      "/api/salary/calculate?worker_id=" + workerId + "&month=" + month + "&year=" + year
    );
    if (res && res.net_salary !== undefined) {
      return {
        worker_id: res.worker_id,
        employee_id: res.employee_id,
        first_name: res.first_name,
        last_name: res.last_name,
        position: res.position,
        department: res.department,
        base_salary: res.base_salary,
        deductions: res.deductions || 0,
        bonuses: res.bonuses || 0,
        net_salary: res.net_salary,
        days_worked: res.days_worked,
        total_hours: res.total_hours,
        incomplete_records_count: res.incomplete_records_count || 0,
        incomplete_dates: Array.isArray(res.incomplete_dates) ? res.incomplete_dates : [],
        requires_manual_review: Boolean(res.requires_manual_review),
        review_notes: res.review_notes || null,
        month: res.month,
        year: res.year
      };
    }
  } catch (e) {
    console.warn("Salary calculate API failed, using fallback:", e);
  }
  return fallback;
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

let slipWorkerId = null;

function openSlipModal(workerId) {
  slipWorkerId = workerId;
  const modal = document.getElementById("slipModal");
  const yearInput = document.getElementById("slipYear");
  const now = new Date();
  if (yearInput) yearInput.value = now.getFullYear();
  const monthSelect = document.getElementById("slipMonth");
  if (monthSelect) monthSelect.value = String(now.getMonth() + 1);
  if (modal) modal.classList.add("active");
  updateSlipPreview();
}

async function updateSlipPreview() {
  const monthSelect = document.getElementById("slipMonth");
  const yearInput = document.getElementById("slipYear");
  if (!slipWorkerId || !monthSelect || !yearInput) return;
  const payload = await getSlipPayload(slipWorkerId, monthSelect.value, yearInput.value);
  if (!payload) return;
  const preview = document.getElementById("slipPreview");
  if (!preview) return;
  preview.innerHTML = renderSlipHtml(payload);
}

function renderSlipHtml(payload) {
  const monthName = MONTH_NAMES[payload.month - 1] || "";
  const net = Number(payload.net_salary);
  const formatted = "PKR " + (isNaN(net) ? "0.00" : net.toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  const name = [payload.first_name, payload.last_name].filter(Boolean).join(" ") || "—";
  const daysRow =
    payload.days_worked != null
      ? `<tr><td>Days worked</td><td>${payload.days_worked}</td></tr>`
      : "";
  const hoursRow =
    payload.total_hours != null
      ? `<tr><td>Total hours</td><td>${payload.total_hours} h</td></tr>`
      : "";
  const reviewWarning = payload.requires_manual_review
    ? `<p class="slip-review-warning">
        ${escapeHtml(payload.review_notes || "Manual review required: incomplete attendance found for selected period.")}
      </p>`
    : "";
  const incompleteRow = payload.requires_manual_review
    ? `<tr><td>Incomplete attendance</td><td>${payload.incomplete_records_count || 0} record(s)</td></tr>`
    : "";

  // A slip that showed only the net would leave a worker who drew an advance
  // wondering where the rest went, so show the arithmetic.
  const money = (v) =>
    "PKR " + Number(v || 0).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const advancesTotal = Number(payload.advances_total || 0);
  const advanceRows = advancesTotal
    ? `<tr><td>Earned this month</td><td>${money(payload.earned_salary)}</td></tr>
       <tr><td>Less advances taken</td><td>&minus;${money(advancesTotal)}</td></tr>` +
      (payload.advances || [])
        .map(
          (a) =>
            `<tr class="slip-subrow"><td>&nbsp;&nbsp;${escapeHtml(a.date)}${
              a.notes ? " &middot; " + escapeHtml(a.notes) : ""
            }</td><td>&minus;${money(a.amount)}</td></tr>`
        )
        .join("")
    : "";
  const overdrawnWarning = payload.overdrawn
    ? `<p class="slip-review-warning">${escapeHtml(payload.advance_notes || "")}</p>`
    : "";
  return `
    <div class="slip-content">
      <h3>GermanATO</h3>
      <p class="slip-title">Salary Slip (based on attendance)</p>
      ${reviewWarning}
      ${overdrawnWarning}
      <table class="slip-table">
        <tr><td>Employee ID</td><td>${escapeHtml(String(payload.employee_id || "—"))}</td></tr>
        <tr><td>Name</td><td>${escapeHtml(name)}</td></tr>
        <tr><td>Position</td><td>${escapeHtml(payload.position || "—")}</td></tr>
        <tr><td>Department</td><td>${escapeHtml(payload.department || "—")}</td></tr>
        <tr><td>Period</td><td>${monthName} ${payload.year}</td></tr>
        ${daysRow}
        ${hoursRow}
        ${incompleteRow}
        ${advanceRows}
        <tr><td>${payload.overdrawn ? "To recover" : "Net Salary"}</td><td><strong>${formatted}</strong></td></tr>
      </table>
    </div>
  `;
}

function setupSlipModal() {
  const modal = document.getElementById("slipModal");
  const closeBtn = document.getElementById("closeSlipModal");
  const cancelBtn = document.getElementById("cancelSlipBtn");
  const printBtn = document.getElementById("printSlipBtn");
  const monthSelect = document.getElementById("slipMonth");
  const yearInput = document.getElementById("slipYear");

  function closeModal() {
    if (modal) modal.classList.remove("active");
    slipWorkerId = null;
  }

  if (closeBtn) closeBtn.addEventListener("click", closeModal);
  if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
  if (modal) {
    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeModal();
    });
  }
  if (monthSelect) monthSelect.addEventListener("change", updateSlipPreview);
  if (yearInput) yearInput.addEventListener("input", updateSlipPreview);

  if (printBtn) {
    printBtn.addEventListener("click", async function () {
      const monthSelect = document.getElementById("slipMonth");
      const yearInput = document.getElementById("slipYear");
      if (!slipWorkerId || !monthSelect || !yearInput) return;
      const payload = await getSlipPayload(slipWorkerId, monthSelect.value, yearInput.value);
      if (!payload) return;
      const printArea = document.getElementById("slipPrintArea");
      if (printArea) {
        printArea.innerHTML = renderSlipHtml(payload);
        printArea.classList.add("visible");
      }
      window.print();
      if (printArea) printArea.classList.remove("visible");
    });
  }
}

function showError(msg) {
  if (typeof showNotification === "function") showNotification(msg, "error");
  else console.error(msg);
}

// ===== SALARY ADVANCES =====
// Partial salary drawn mid-month. Recorded against the worker only - the
// expense is the full month's salary at payroll, and calculate_salary() nets
// these off, so the same rupee is never handed over twice.

let advanceWorker = null;

const advanceMoney = (v) =>
  "PKR " +
  Number(v || 0).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function openAdvanceModal(worker) {
  advanceWorker = worker;
  const modal = document.getElementById("advanceModal");
  if (!modal) return;

  const today = new Date().toISOString().split("T")[0];
  document.getElementById("advanceDate").value = today;
  document.getElementById("advanceAmount").value = "";
  document.getElementById("advanceNotes").value = "";
  document.getElementById("advanceWorkerLine").textContent =
    `${worker.name} · monthly salary ${advanceMoney(worker.salary)}`;

  modal.classList.add("active");
  loadAdvanceHistory();
}

function closeAdvanceModal() {
  const modal = document.getElementById("advanceModal");
  if (modal) modal.classList.remove("active");
  advanceWorker = null;
}

async function loadAdvanceHistory() {
  if (!advanceWorker) return;
  const box = document.getElementById("advanceHistory");
  const remaining = document.getElementById("advanceRemaining");
  const when = new Date(document.getElementById("advanceDate").value || Date.now());

  try {
    const data = await APIHelper.get(
      `/api/salary/advances?worker_id=${advanceWorker.id}` +
        `&year=${when.getFullYear()}&month=${when.getMonth() + 1}`
    );
    if (!data) return;

    const left = Math.max(advanceWorker.salary - data.total, 0);
    remaining.textContent = advanceWorker.salary
      ? `Drawn this month: ${advanceMoney(data.total)} · still available: ${advanceMoney(left)}`
      : "This worker has no monthly salary set, so nothing can be advanced.";

    box.innerHTML = data.advances.length
      ? data.advances
          .map(
            (a) => `<div class="advance-row">
              <span class="advance-row__date">${escapeHtml(a.date)}</span>
              <span class="advance-row__amt">${advanceMoney(a.amount)}</span>
              <span class="advance-row__note">${escapeHtml(a.notes || a.payment_method || "")}</span>
              <button type="button" class="advance-row__del" data-advance-id="${a.id}"
                      title="Remove this advance">&times;</button>
            </div>`
          )
          .join("")
      : `<p class="advance-empty">Nothing drawn this month.</p>`;

    box.querySelectorAll(".advance-row__del").forEach((b) =>
      b.addEventListener("click", () => deleteAdvance(Number(b.dataset.advanceId)))
    );
  } catch (error) {
    console.error("Error loading advances:", error);
    box.innerHTML = `<p class="advance-empty">Could not load this month's advances.</p>`;
  }
}

async function submitAdvance(event) {
  event.preventDefault();
  if (!advanceWorker) return;

  const btn = document.getElementById("saveAdvanceBtn");
  const amount = Number(document.getElementById("advanceAmount").value);
  if (!(amount > 0)) return showError("Enter an amount above zero");

  btn.disabled = true;
  try {
    const res = await APIHelper.post("/api/salary/advances", {
      worker_id: advanceWorker.id,
      date: document.getElementById("advanceDate").value,
      amount: amount,
      payment_method: document.getElementById("advanceMethod").value,
      notes: document.getElementById("advanceNotes").value,
    });
    if (res) {
      showSuccess("Advance recorded");
      document.getElementById("advanceAmount").value = "";
      document.getElementById("advanceNotes").value = "";
      loadAdvanceHistory();
    }
  } catch (error) {
    // The server rejects an advance that would exceed the month's salary, and
    // its message names the amount still available - worth showing verbatim.
    showError(error?.message || "Could not record the advance");
  } finally {
    btn.disabled = false;
  }
}

async function deleteAdvance(id) {
  if (!confirm("Remove this advance? The salary calculation will go back up by that amount.")) return;
  try {
    const res = await APIHelper.delete(`/api/salary/advances/${id}`);
    if (res) {
      showSuccess("Advance removed");
      loadAdvanceHistory();
    }
  } catch (error) {
    showError(error?.message || "Could not remove the advance");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("advanceModal");
  if (!modal) return;

  document.getElementById("closeAdvanceModal").addEventListener("click", closeAdvanceModal);
  document.getElementById("cancelAdvanceBtn").addEventListener("click", closeAdvanceModal);
  document.getElementById("advanceForm").addEventListener("submit", submitAdvance);
  // A different date can mean a different month, so the remaining figure moves.
  document.getElementById("advanceDate").addEventListener("change", loadAdvanceHistory);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeAdvanceModal();
  });
});
