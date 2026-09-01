/**
 * Monthly Financial Ledger.
 *
 * The full picture, deliberately: unlike the Daily Expenses till this counts
 * parts, payroll, capital spending and invoice settlements too. Nothing here
 * asks for scope=till.
 *
 * Lives apart from dailyExpenses.js because that module is 1,000 lines of
 * expense and cash forms this page does not have.
 */

let ledgerData = null;

const PKR = (n) =>
  "PKR " + Number(n || 0).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const el = (id) => document.getElementById(id);
const iso = (d) => d.toISOString().split("T")[0];
const esc = (v) =>
  String(v == null ? "" : v).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

// ----- loading ------------------------------------------------------------

async function loadLedger(params) {
  const utils = window.PerformanceUtils || null;
  try {
    if (utils) utils.showLoading("ledger-details-tbody", "Loading ledger...");
    const data = await APIHelper.get(`/api/expenses/monthly-ledger?${params.toString()}`);
    if (!data) return;
    ledgerData = data;
    renderAll();
  } catch (error) {
    console.error("Error loading ledger:", error);
    APIHelper.renderError("ledger-details-tbody", error, () => loadLedger(params));
  } finally {
    if (utils) utils.hideLoading("ledger-details-tbody");
  }
}

function loadMonth(month) {
  const p = new URLSearchParams();
  p.append("month", month);
  el("ledger-start-date").value = "";
  el("ledger-end-date").value = "";
  loadLedger(p);
}

function loadRange(start, end) {
  const p = new URLSearchParams();
  p.append("start_date", start);
  p.append("end_date", end);
  loadLedger(p);
}

// ----- rendering ----------------------------------------------------------

function renderAll() {
  const d = ledgerData;
  el("ledger-scope").textContent =
    `${d.start_date} to ${d.end_date} · ${d.days} day${d.days === 1 ? "" : "s"} · ` +
    `${d.entry_count} transaction${d.entry_count === 1 ? "" : "s"}` +
    (d.invoice_settlements.count
      ? ` · includes ${d.invoice_settlements.count} invoice settlement${
          d.invoice_settlements.count === 1 ? "" : "s"
        } worth ${PKR(d.invoice_settlements.total)}`
      : "");

  el("ledger-opening-balance").textContent = PKR(d.initial_balance);
  el("ledger-total-in").textContent = PKR(d.total_in);
  el("ledger-total-out").textContent = PKR(d.total_out);
  el("ledger-net-change").textContent = (d.net_change >= 0 ? "+" : "") + PKR(d.net_change);
  el("ledger-closing-balance").textContent = PKR(d.closing_balance);

  renderBreakdown("expense-breakdown", d.expense_breakdown, d.total_out);
  renderBreakdown("income-breakdown", d.income_breakdown, d.total_in);
  populateBucketFilter();
  renderDetails();
  renderDaily();
}

function renderBreakdown(targetId, rows, total) {
  const box = el(targetId);
  if (!box) return;
  if (!rows || !rows.length) {
    box.innerHTML = `<p class="muted">Nothing in this period.</p>`;
    return;
  }
  box.innerHTML = rows
    .map((r) => {
      const pct = total > 0 ? (r.total / total) * 100 : 0;
      return `<div class="bd-row">
          <div class="bd-row__head">
            <span class="bd-row__name">${esc(r.bucket)}</span>
            <span class="bd-row__val">${PKR(r.total)}<em>${pct.toFixed(1)}% · ${r.count}</em></span>
          </div>
          <div class="bd-row__bar"><span style="width:${Math.max(pct, 0.6).toFixed(2)}%"></span></div>
        </div>`;
    })
    .join("");
}

function populateBucketFilter() {
  const sel = el("ledger-bucket-filter");
  const chosen = sel.value;
  const buckets = [...new Set(ledgerData.details.map((d) => d.bucket))].sort();
  sel.innerHTML =
    `<option value="">All categories</option>` +
    buckets.map((b) => `<option value="${esc(b)}">${esc(b)}</option>`).join("");
  if (buckets.includes(chosen)) sel.value = chosen;
}

function visibleDetails() {
  const term = (el("ledger-search").value || "").trim().toLowerCase();
  const type = el("ledger-type-filter").value;
  const bucket = el("ledger-bucket-filter").value;
  return ledgerData.details.filter((d) => {
    if (type && d.type !== type) return false;
    if (bucket && d.bucket !== bucket) return false;
    if (!term) return true;
    return (
      (d.description || "").toLowerCase().includes(term) ||
      (d.bucket || "").toLowerCase().includes(term) ||
      (d.notes || "").toLowerCase().includes(term)
    );
  });
}

function renderDetails() {
  const rows = visibleDetails();
  const tbody = el("ledger-details-tbody");

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-row">No transactions match this filter.</td></tr>`;
  } else {
    tbody.innerHTML = rows
      .map((d) => {
        const settled = d.invoice_id
          ? ` <span class="pill pill--invoice">Invoice #${d.invoice_id}</span>`
          : "";
        return `<tr>
            <td class="nowrap">${esc(d.date)}</td>
            <td><span class="pill pill--${d.type}">${d.type === "in" ? "In" : "Out"}</span></td>
            <td>${esc(d.description)}${settled}</td>
            <td>${esc(d.bucket)}</td>
            <td class="muted">${esc(d.notes) || "&mdash;"}</td>
            <td class="num ${d.type === "in" ? "amt-in" : "amt-out"}">
              ${d.type === "in" ? "+" : "−"}${PKR(d.amount)}</td>
            <td class="num">${PKR(d.balance)}</td>
          </tr>`;
      })
      .join("");
  }

  const shown = rows.length;
  const all = ledgerData.details.length;
  const sum = rows.reduce((t, d) => t + (d.type === "in" ? d.amount : -d.amount), 0);
  el("ledger-details-count").textContent =
    shown === all
      ? `${all} transaction${all === 1 ? "" : "s"}`
      : `${shown} of ${all} transactions · net ${(sum >= 0 ? "+" : "") + PKR(sum)}`;
}

function renderDaily() {
  const hideQuiet = el("hide-quiet-days").checked;
  const rows = ledgerData.daily_ledger.filter((r) => !hideQuiet || r.entry_count > 0);
  const tbody = el("daily-ledger-tbody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">No activity in this period.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows
    .map(
      (r) => `<tr class="${r.entry_count ? "" : "quiet-day"}">
        <td class="nowrap">${esc(r.date)}</td>
        <td class="num">${PKR(r.opening_balance)}</td>
        <td class="num amt-in">${r.inflow ? PKR(r.inflow) : "&mdash;"}</td>
        <td class="num amt-out">${r.outflow ? PKR(r.outflow) : "&mdash;"}</td>
        <td class="num">${r.entry_count || "&mdash;"}</td>
        <td class="num"><strong>${PKR(r.closing_balance)}</strong></td>
      </tr>`
    )
    .join("");
}

// ----- export -------------------------------------------------------------

function exportLedger() {
  if (!ledgerData) return;
  const wb = XLSX.utils.book_new();

  XLSX.utils.book_append_sheet(
    wb,
    XLSX.utils.json_to_sheet(
      ledgerData.details.map((d) => ({
        Date: d.date,
        Type: d.type === "in" ? "In" : "Out",
        Description: d.description,
        "Category / method": d.bucket,
        Invoice: d.invoice_id || "",
        Notes: d.notes,
        "Amount (PKR)": d.type === "in" ? d.amount : -d.amount,
        "Balance (PKR)": d.balance,
      }))
    ),
    "Transactions"
  );

  XLSX.utils.book_append_sheet(
    wb,
    XLSX.utils.json_to_sheet(
      ledgerData.daily_ledger.map((r) => ({
        Date: r.date,
        "Opening (PKR)": r.opening_balance,
        "In (PKR)": r.inflow,
        "Out (PKR)": r.outflow,
        Entries: r.entry_count,
        "Closing (PKR)": r.closing_balance,
      }))
    ),
    "Balances by day"
  );

  XLSX.utils.book_append_sheet(
    wb,
    XLSX.utils.json_to_sheet([
      ...ledgerData.expense_breakdown.map((r) => ({
        Direction: "Out", Bucket: r.bucket, "Total (PKR)": r.total, Entries: r.count,
      })),
      ...ledgerData.income_breakdown.map((r) => ({
        Direction: "In", Bucket: r.bucket, "Total (PKR)": r.total, Entries: r.count,
      })),
    ]),
    "Breakdown"
  );

  XLSX.writeFile(wb, `ledger_${ledgerData.start_date}_to_${ledgerData.end_date}.xlsx`);
}

// ----- presets ------------------------------------------------------------

function applyPreset(name) {
  const now = new Date();
  const monthOf = (d) => iso(d).substring(0, 7);

  if (name === "this-month") {
    el("ledger-month-select").value = monthOf(now);
    return loadMonth(monthOf(now));
  }
  if (name === "last-month") {
    const d = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    el("ledger-month-select").value = monthOf(d);
    return loadMonth(monthOf(d));
  }
  if (name === "last-3") {
    const from = new Date(now.getFullYear(), now.getMonth() - 2, 1);
    return setRange(iso(from), iso(now));
  }
  if (name === "this-year") {
    return setRange(iso(new Date(now.getFullYear(), 0, 1)), iso(now));
  }
}

function setRange(start, end) {
  el("ledger-start-date").value = start;
  el("ledger-end-date").value = end;
  loadRange(start, end);
}

function stepMonth(delta) {
  const input = el("ledger-month-select");
  const [y, m] = (input.value || iso(new Date()).substring(0, 7)).split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  input.value = iso(d).substring(0, 7);
  loadMonth(input.value);
}

// ----- wiring -------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  const month = el("ledger-month-select");
  if (!month) return;

  month.value = iso(new Date()).substring(0, 7);
  month.addEventListener("change", () => month.value && loadMonth(month.value));

  el("month-prev").addEventListener("click", () => stepMonth(-1));
  el("month-next").addEventListener("click", () => stepMonth(1));

  document.querySelectorAll(".chip[data-preset]").forEach((b) =>
    b.addEventListener("click", () => {
      document.querySelectorAll(".chip[data-preset]").forEach((o) => o.classList.remove("is-on"));
      b.classList.add("is-on");
      applyPreset(b.dataset.preset);
    })
  );

  el("btn-apply-range").addEventListener("click", () => {
    const s = el("ledger-start-date").value;
    const e = el("ledger-end-date").value;
    if (!s || !e) return alert("Choose both a from and a to date.");
    if (e < s) return alert("The end date is before the start date.");
    loadRange(s, e);
  });

  el("btn-export-ledger").addEventListener("click", exportLedger);

  // Re-filtering is local to data already loaded, so no refetch.
  ["ledger-search", "ledger-type-filter", "ledger-bucket-filter"].forEach((id) =>
    el(id).addEventListener("input", () => ledgerData && renderDetails())
  );
  el("hide-quiet-days").addEventListener("change", () => ledgerData && renderDaily());

  loadMonth(month.value);
});
