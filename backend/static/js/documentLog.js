/**
 * The history of one document: an invoice, a quote, or a repair order.
 *
 * All three already recorded their history - payments landed in
 * invoice.payments_history, everything else in the application log - but none
 * of it was reachable from the document. Payments only appeared if they
 * happened to carry a proof file, so a plain cash payment left no visible
 * trace, and the audit log was admin-only and application-wide.
 *
 * One module for all three because the shape is the same: what happened, when,
 * and who did it. Only invoices add money to that, and only they show it.
 *
 * Include this and a container, then call DocumentLog.open(kind, id).
 */
(function () {
  "use strict";

  const MODAL_ID = "document-log-modal";
  let current = null;

  const money = (v) =>
    Number(v || 0).toLocaleString("en-PK", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const esc = (v) =>
    String(v == null ? "" : v).replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  const TITLES = {
    invoice: "Invoice",
    quote: "Quote",
    "repair-order": "Repair order",
  };

  /**
   * Every movement of money, oldest first, with a running balance.
   *
   * The advance is money the customer handed over, but it is taken when the
   * invoice is written and never enters payments_history - so it is added as
   * the opening line. Without it the running balance would not reconcile with
   * what the invoice says is still owed.
   */
  function paymentRows(data) {
    const rows = [];

    if (data.advance > 0) {
      rows.push({
        when: data.created_at || "",
        what: "Advance taken with the invoice",
        amount: data.advance,
        who: data.created_by || "—",
        proof: null,
      });
    }

    (data.payments || []).forEach((p) => {
      rows.push({
        when: p.timestamp || "",
        what: "Payment received",
        amount: Number(p.amount) || 0,
        who: p.person || "—",
        proof: p.proof_path || null,
      });
    });

    rows.sort((a, b) => String(a.when).localeCompare(String(b.when)));

    let paid = 0;
    rows.forEach((r) => {
      paid += r.amount;
      r.paidToDate = Math.round(paid * 100) / 100;
      r.owedAfter = Math.round((data.amount_due - paid) * 100) / 100;
    });
    return rows;
  }

  function ensureModal() {
    let modal = document.getElementById(MODAL_ID);
    if (modal) return modal;

    modal = document.createElement("div");
    modal.id = MODAL_ID;
    modal.className = "modal";
    modal.style.cssText =
      "display:none;position:fixed;z-index:1200;left:0;top:0;width:100%;height:100%;" +
      "overflow:auto;background:rgba(0,0,0,.45);padding-top:50px;";
    modal.innerHTML = `
      <div style="background:#fff;margin:3% auto;padding:24px;width:94%;max-width:820px;
                  border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.18);">
        <div style="display:flex;justify-content:space-between;align-items:center;
                    border-bottom:1px solid #e2e8f0;padding-bottom:12px;margin-bottom:18px;">
          <h2 id="dlog-title" style="margin:0;font-size:1.12rem;">History</h2>
          <span id="dlog-close" style="cursor:pointer;font-size:26px;line-height:1;color:#718096;">&times;</span>
        </div>
        <div id="dlog-body"></div>
        <div style="display:flex;justify-content:flex-end;gap:8px;border-top:1px solid #edf2f7;
                    padding-top:14px;margin-top:16px;">
          <button id="dlog-close-btn" class="wide-btn-delete">Close</button>
          <button id="dlog-export" class="wide-btn-submit">Export Excel</button>
        </div>
      </div>`;
    document.body.appendChild(modal);

    const close = () => {
      modal.style.display = "none";
      current = null;
    };
    modal.querySelector("#dlog-close").addEventListener("click", close);
    modal.querySelector("#dlog-close-btn").addEventListener("click", close);
    modal.querySelector("#dlog-export").addEventListener("click", exportLog);
    modal.addEventListener("click", (e) => {
      if (e.target === modal) close();
    });
    return modal;
  }

  const TH =
    "padding:7px 10px 7px 0;border-bottom:1px solid #e2e8f0;text-align:left;" +
    "font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#718096;";
  const TD = "padding:8px 10px 8px 0;border-bottom:1px solid #f1f5f9;vertical-align:top;";
  const NUM = TD + "text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;";

  function moneySection(data) {
    const rows = paymentRows(data);
    const paid = rows.length ? rows[rows.length - 1].paidToDate : 0;

    const cards = [
      ["Invoice total", money(data.amount_due), "#2d3748"],
      ["Received", money(paid), "#2f855a"],
      ["Still owed", money(data.amount_remaining), "#8b1538"],
    ]
      .map(
        ([label, value, colour]) => `
        <div style="border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;min-width:0;">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#718096;">${label}</div>
          <div style="font-weight:700;color:${colour};">PKR ${value}</div>
        </div>`
      )
      .join("");

    const body = rows.length
      ? rows
          .map(
            (r) => `<tr>
              <td style="${TD}white-space:nowrap;">${esc(r.when)}</td>
              <td style="${TD}">${esc(r.what)}</td>
              <td style="${TD}color:#718096;">${esc(r.who)}</td>
              <td style="${NUM}color:#2f855a;">${money(r.amount)}</td>
              <td style="${NUM}">${money(r.owedAfter)}</td>
              <td style="${TD}">${
                r.proof
                  ? `<a href="/static/${esc(r.proof)}" target="_blank" style="color:#2b6cb0;">View</a>`
                  : '<span style="color:#a0aec0;">—</span>'
              }</td>
            </tr>`
          )
          .join("")
      : `<tr><td colspan="6" style="padding:24px 0;text-align:center;color:#718096;">
           Nothing received against this invoice yet.</td></tr>`;

    return `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:18px;">
        ${cards}
      </div>
      <h3 style="margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#718096;">Payments</h3>
      <div style="overflow-x:auto;margin-bottom:22px;">
        <table style="width:100%;border-collapse:collapse;font-size:13.5px;min-width:560px;">
          <thead><tr>
            <th style="${TH}">When</th><th style="${TH}">What</th><th style="${TH}">Recorded by</th>
            <th style="${TH}text-align:right;">Amount</th><th style="${TH}text-align:right;">Owed after</th>
            <th style="${TH}">Proof</th>
          </tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>`;
  }

  function activitySection(data) {
    const body = data.entries.length
      ? data.entries
          .map(
            (e) => `<tr>
              <td style="${TD}white-space:nowrap;">${esc(e.when)}</td>
              <td style="${TD}white-space:nowrap;font-weight:600;">${esc(e.action)}</td>
              <td style="${TD}color:#718096;">${esc(e.user)}</td>
              <td style="${TD}">${esc(e.details)}</td>
            </tr>`
          )
          .join("")
      : `<tr><td colspan="4" style="padding:24px 0;text-align:center;color:#718096;">
           Nothing recorded. Actions taken from now on will appear here.</td></tr>`;

    return `
      <h3 style="margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#718096;">Activity</h3>
      <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;font-size:13.5px;min-width:540px;">
          <thead><tr>
            <th style="${TH}">When</th><th style="${TH}">Action</th>
            <th style="${TH}">By</th><th style="${TH}">Details</th>
          </tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>`;
  }

  function render(data) {
    const modal = ensureModal();
    const label = TITLES[data.kind] || "Document";

    modal.querySelector("#dlog-title").textContent =
      `${label} ${data.reference} — ${data.customer_name || "—"}`;

    // A quote carries no payments, so it gets no money section rather than an
    // empty one implying something is owed.
    const showMoney = data.kind === "invoice" && data.amount_due !== undefined;
    modal.querySelector("#dlog-body").innerHTML =
      (showMoney ? moneySection(data) : "") + activitySection(data);

    modal.style.display = "block";
  }

  function exportLog() {
    if (!current) return;
    const data = current;
    const label = TITLES[data.kind] || "Document";

    const sheet = [
      [label, data.reference],
      ["Customer", data.customer_name || ""],
      ["Created", data.created_at || ""],
      ["Created by", data.created_by || ""],
    ];

    if (data.kind === "invoice") {
      const rows = paymentRows(data);
      const paid = rows.length ? rows[rows.length - 1].paidToDate : 0;
      sheet.push(
        [],
        ["Invoice total (PKR)", data.amount_due],
        ["Received (PKR)", paid],
        ["Still owed (PKR)", data.amount_remaining],
        [],
        ["PAYMENTS"],
        ["When", "What", "Recorded by", "Amount (PKR)", "Received to date (PKR)", "Owed after (PKR)", "Proof"],
        ...rows.map((r) => [
          r.when, r.what, r.who, r.amount, r.paidToDate, r.owedAfter,
          r.proof ? `${window.location.origin}/static/${r.proof}` : "",
        ])
      );
    }

    sheet.push(
      [],
      ["ACTIVITY"],
      ["When", "Action", "By", "Details", "IP"],
      ...data.entries.map((e) => [e.when, e.action, e.user, e.details, e.ip_address])
    );

    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(sheet), "History");
    XLSX.writeFile(wb, `${data.kind}_${data.document_id}_history.xlsx`);
  }

  const URLS = {
    invoice: (id) => `/api/invoice/${id}/log`,
    quote: (id) => `/api/invoice/${id}/log`,
    "repair-order": (id) => `/api/repair-orders/${id}/log`,
  };

  async function open(kind, id) {
    const url = URLS[kind];
    if (!url) return;
    try {
      const data = await APIHelper.get(url(id));
      if (!data) return;
      current = data;
      render(data);
    } catch (error) {
      console.error("Error loading document log:", error);
      const message = error?.message || "Could not load the history for this document.";
      if (typeof showError === "function") showError(message);
      else alert(message);
    }
  }

  window.DocumentLog = { open };
})();
