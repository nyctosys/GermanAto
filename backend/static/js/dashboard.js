/**
 * Home dashboard: the pending work the signed-in role can act on.
 *
 * Replaces the old grid of navigation cards, which only duplicated the sidebar.
 * Everything comes from one /api/dashboard call, already filtered by permission
 * server-side, so a role never sees a widget it cannot act on.
 */

const esc = (v) => APIHelper.escapeHtml(v == null ? "" : v);

const money = (n) =>
  "Rs " +
  Number(n || 0).toLocaleString("en-PK", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });

function daysAgo(iso) {
  if (!iso) return "";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (days <= 0) return "today";
  if (days === 1) return "1 day ago";
  return `${days} days ago`;
}

function statCard({ label, value, meta, href, alert }) {
  const tag = href ? "a" : "div";
  return `<${tag} class="stat${alert ? " stat--alert" : ""}"${href ? ` href="${href}"` : ""}>
    <p class="stat__label">${esc(label)}</p>
    <p class="stat__value">${esc(value)}</p>
    ${meta ? `<p class="stat__meta">${esc(meta)}</p>` : ""}
  </${tag}>`;
}

function panel({ title, href, linkText, rows, empty, extra }) {
  return `<section class="panel">
    <div class="panel__head">
      <h3 class="panel__title">${esc(title)}</h3>
      ${href ? `<a class="panel__link" href="${href}">${esc(linkText || "View all")}</a>` : ""}
    </div>
    ${extra || ""}
    ${
      rows && rows.length
        ? `<ul class="panel__list">${rows.join("")}</ul>`
        : `<p class="panel__empty">${esc(empty)}</p>`
    }
  </section>`;
}

function row({ href, primary, secondary, amount }) {
  const tag = href ? "a" : "div";
  return `<li><${tag} class="panel__row"${href ? ` href="${href}"` : ""}>
    <span class="panel__primary">${esc(primary)}
      ${secondary ? `<span class="panel__secondary">${esc(secondary)}</span>` : ""}
    </span>
    ${amount ? `<span class="panel__amount">${esc(amount)}</span>` : ""}
  </${tag}></li>`;
}

function buildStats(s) {
  const cards = [];

  if (s.insights) {
    cards.push(
      statCard({
        label: "Sales this month",
        value: money(s.insights.sales_month),
        href: "/reports.html",
      }),
      statCard({
        label: "Profit this month",
        value: money(s.insights.profit_month),
        meta: `${money(s.insights.expenses_month)} expenses`,
        href: "/reports.html",
      })
    );
  }

  if (s.invoices) {
    cards.push(
      statCard({
        label: "Unpaid invoices",
        value: s.invoices.unpaid_count,
        meta: `${money(s.invoices.unpaid_total)} outstanding`,
        href: "/invoice-management.html",
        alert: s.invoices.unpaid_count > 0,
      })
    );
  }

  if (s.quotes) {
    cards.push(
      statCard({
        label: "Pending quotes",
        value: s.quotes.pending_count,
        meta: `${money(s.quotes.pending_value)} potential`,
        href: "/pending-quotes.html",
      })
    );
  }

  if (s.repairs) {
    cards.push(
      statCard({
        label: "Open repair orders",
        value: s.repairs.open_count,
        meta: `${s.repairs.completed_today} completed today`,
        href: "/repair-orders-management.html",
      })
    );
  }

  if (s.expenses) {
    cards.push(
      statCard({
        label: "Expenses today",
        value: money(s.expenses.today_total),
        meta: `${money(s.expenses.month_total)} this month`,
        href: "/daily-expenses.html",
      })
    );
  }

  if (s.inventory) {
    cards.push(
      statCard({
        label: "Low stock items",
        value: s.inventory.low_stock_count,
        href: "/inventory.html",
        alert: s.inventory.low_stock_count > 0,
      })
    );
  }

  return cards.length ? `<div class="dash__stats">${cards.join("")}</div>` : "";
}

function buildPanels(s) {
  const panels = [];

  if (s.invoices) {
    panels.push(
      panel({
        title: "Invoices awaiting payment",
        href: "/invoice-management.html",
        rows: (s.invoices.oldest || []).map((i) =>
          row({
            href: `/invoice-management.html?id=${i.id}`,
            primary: i.customer_name,
            secondary: `Invoice #${i.id} · raised ${daysAgo(i.created_at)}`,
            amount: money(i.owed),
          })
        ),
        empty: "Every invoice is settled.",
      })
    );
  }

  if (s.quotes) {
    panels.push(
      panel({
        title: "Quotes awaiting a decision",
        href: "/pending-quotes.html",
        rows: (s.quotes.items || []).map((q) =>
          row({
            href: "/pending-quotes.html",
            primary: q.customer_name,
            secondary: `${q.quote_number} · sent ${daysAgo(q.created_at)}`,
            amount: money(q.total_amount),
          })
        ),
        empty: "No quotes are waiting.",
      })
    );
  }

  if (s.repairs) {
    const chips = Object.entries(s.repairs.by_status || {})
      .map(([st, n]) => `<span class="chip">${esc(st)} <strong>${n}</strong></span>`)
      .join("");

    panels.push(
      panel({
        title: "Repair orders in progress",
        href: "/repair-orders-management.html",
        extra: chips ? `<div class="chips">${chips}</div>` : "",
        rows: (s.repairs.items || []).map((r) =>
          row({
            href: "/repair-orders-management.html",
            primary: r.customer_name,
            secondary: `#${r.id} · ${r.status} · opened ${daysAgo(r.created_at)}`,
          })
        ),
        empty: "Nothing in the workshop right now.",
      })
    );
  }

  if (s.inventory) {
    panels.push(
      panel({
        title: "Stock to reorder",
        href: "/inventory.html",
        rows: (s.inventory.items || []).map((i) =>
          row({
            href: "/inventory.html",
            primary: i.item_name,
            secondary: `${i.category} · reorder at ${i.reorder_level}`,
            amount: `${i.quantity} left`,
          })
        ),
        empty: "Stock levels are healthy.",
      })
    );
  }

  return panels.length ? `<div class="dash__panels">${panels.join("")}</div>` : "";
}

function greet() {
  const user = auth.getCurrentUser() || {};
  const hour = new Date().getHours();
  const part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  return user.username ? `${part}, ${user.username}` : part;
}

async function loadDashboard() {
  const target = document.getElementById("dashContent");
  APIHelper.renderLoading(target, "Loading your dashboard...");

  try {
    const data = await APIHelper.get("/api/dashboard");
    const sections = (data && data.sections) || {};

    document.getElementById("dashGreeting").textContent = greet();
    document.getElementById("dashSubtitle").textContent = new Date().toLocaleDateString(
      "en-US",
      { weekday: "long", day: "numeric", month: "long", year: "numeric" }
    );

    const html = buildStats(sections) + buildPanels(sections);
    target.innerHTML =
      html ||
      `<p class="panel__empty">Nothing is assigned to your role yet. Use the sidebar to get started.</p>`;

    // Be explicit when a widget could not be built, rather than showing a
    // confident-looking dashboard with a section silently missing.
    if (data.unavailable && data.unavailable.length) {
      showError(`Could not load: ${data.unavailable.join(", ")}. Try refreshing.`);
    }
  } catch (error) {
    console.error("Error loading dashboard:", error);
    APIHelper.renderError(target, error, loadDashboard);
  }
}
