/**
 * App shell: one persistent sidebar + a command palette, injected into every
 * page from a single destination registry.
 *
 * Why: every page used to carry nothing but a "Back" button, so moving between
 * modules meant walking back up to home first (Invoices -> Inventory was four
 * clicks). Every destination here is one click, or one keystroke via Cmd/Ctrl+K.
 *
 * Include after auth_jwt.js:
 *   <link rel="stylesheet" href="../static/css/app-shell.css" />
 *   <script src="../static/js/app-shell.js"></script>
 */
(function () {
  "use strict";

  const icon = (paths) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;

  const ICONS = {
    home: icon('<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>'),
    invoice: icon('<path d="M6 2h9l4 4v16H6z"/><path d="M15 2v4h4"/><path d="M9 12h7M9 16h7"/>'),
    quote: icon('<path d="M6 2h9l4 4v16H6z"/><path d="M15 2v4h4"/><path d="M9 13l2 2 4-4"/>'),
    wrench: icon('<path d="M14.7 6.3a4 4 0 0 0 5 5l-9.6 9.6a2.1 2.1 0 0 1-3-3z"/><path d="M14.7 6.3 17.5 3.5"/>'),
    box: icon('<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/>'),
    truck: icon('<path d="M2 7h11v9H2z"/><path d="M13 10h4l4 3v3h-8z"/><circle cx="7" cy="18" r="1.6"/><circle cx="17" cy="18" r="1.6"/>'),
    car: icon('<path d="M4 13h16l-1.6-4.4A2 2 0 0 0 16.5 7h-9a2 2 0 0 0-1.9 1.6z"/><path d="M4 13v4h16v-4"/><circle cx="7.5" cy="17" r="1.4"/><circle cx="16.5" cy="17" r="1.4"/>'),
    cash: icon('<path d="M3 6h18v12H3z"/><circle cx="12" cy="12" r="2.5"/>'),
    chart: icon('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'),
    people: icon('<circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 11a3 3 0 0 0 0-6"/><path d="M17.5 20a6 6 0 0 0-2-4.4"/>'),
    clock: icon('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
    wallet: icon('<path d="M3 7h15a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 7V6a2 2 0 0 1 2-2h11"/><circle cx="16.5" cy="13" r="1.2"/>'),
    shield: icon('<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/>'),
    chat: icon('<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z"/>'),
    gear: icon('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 7.5 19.4l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3 15.1H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 8.5l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 10 4.6V4a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 2.6 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>'),
    plus: icon('<path d="M12 5v14M5 12h14"/>'),
    search: icon('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>'),
    logout: icon('<path d="M15 17l5-5-5-5"/><path d="M20 12H9"/><path d="M12 20H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h6"/>'),
    theme: icon('<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/>'),
    collapse: icon('<path d="M4 5h16M4 12h16M4 19h16"/>'),
  };

  /**
   * Every destination in the app, grouped the way the business actually works
   * rather than by which hub page happened to link to it. `permission` matches
   * the server's role_permissions values.
   */
  const NAV = [
    {
      group: null,
      items: [{ label: "Dashboard", href: "/home.html", permission: "home", icon: "home" }],
    },
    {
      group: "Create",
      items: [
        { label: "New invoice or quote", href: "/invoice.html", permission: "invoice", icon: "plus" },
        { label: "New repair order", href: "/repair-order.html", permission: "repair-order", icon: "plus" },
      ],
    },
    {
      group: "Sales",
      items: [
        { label: "Invoices", href: "/invoice-management.html", permission: "invoice", icon: "invoice" },
        { label: "Quotes", href: "/pending-quotes.html", permission: "invoice", icon: "quote" },
        { label: "Repair orders", href: "/repair-orders-management.html", permission: "repair-order", icon: "wrench" },
      ],
    },
    {
      group: "Operations",
      items: [
        { label: "Inventory", href: "/inventory.html", permission: "inventory", icon: "box" },
        { label: "Vendors", href: "/vendors", permission: "vendors", icon: "truck" },
        { label: "Cars & customers", href: "/car.html", permission: "car", icon: "car" },
      ],
    },
    {
      group: "Finance",
      items: [
        { label: "Daily expenses", href: "/daily-expenses.html", permission: "daily-expenses", icon: "cash" },
        { label: "Major expenses", href: "/major-expenses.html", permission: "major-expenses", icon: "wallet" },
        { label: "Monthly ledger", href: "/monthly-ledger.html", permission: "daily-expenses", icon: "chart" },
        { label: "Reports", href: "/reports.html", permission: "reports", icon: "chart" },
      ],
    },
    {
      group: "People",
      items: [
        { label: "Employees", href: "/employees.html", permission: "hr", icon: "people" },
        { label: "Attendance", href: "/attendance.html", permission: "hr", icon: "clock" },
        { label: "Salaries", href: "/salaries-management.html", permission: "hr", icon: "wallet" },
      ],
    },
    {
      group: "Admin",
      items: [
        { label: "Users & roles", href: "/admin.html", permission: "admin", icon: "shield" },
        { label: "WhatsApp", href: "/whatsapp-notifications.html", permission: "admin", icon: "chat" },
        { label: "Settings", href: "/settings.html", permission: "settings", icon: "gear" },
      ],
    },
  ];

  /**
   * Creates that open a modal rather than having a page of their own, so they
   * are reachable from the palette. The two create *pages* live in NAV above.
   */
  const ACTIONS = [
    { label: "New vendor", href: "/vendors?new=1", permission: "vendors", icon: "plus" },
    { label: "Record daily expense", href: "/daily-expenses.html?new=1", permission: "daily-expenses", icon: "plus" },
    { label: "Add inventory item", href: "/inventory.html?new=1", permission: "inventory", icon: "plus" },
  ];

  // ----- permissions -------------------------------------------------------

  function allowed(permission) {
    const user = window.auth && auth.user;
    if (!user) return false;
    if (user.role === "admin" || permission === "home") return true;

    const perms = window.auth && auth.getCachedPermissions && auth.getCachedPermissions();
    // Permissions still in flight: show the item, the page guard and the server
    // both still enforce. Hiding it would make the nav flicker on every load.
    return perms ? perms.includes(permission) : true;
  }

  const visibleGroups = () =>
    NAV.map((g) => ({ ...g, items: g.items.filter((i) => allowed(i.permission)) })).filter(
      (g) => g.items.length
    );

  const visibleActions = () => ACTIONS.filter((a) => allowed(a.permission));

  // ----- current page ------------------------------------------------------

  function isCurrent(href) {
    const here = window.location.pathname.replace(/\/$/, "") || "/";
    const target = href.split("?")[0].replace(/\/$/, "") || "/";
    if (here === target) return true;
    // Detail pages should light up their list: /vendors/7 -> Vendors.
    return target !== "/" && here.startsWith(target + "/");
  }

  // ----- sidebar -----------------------------------------------------------

  function buildSidebar() {
    const user = (window.auth && auth.user) || {};
    const name = user.username || "Signed in";
    const initial = String(name).charAt(0).toUpperCase();

    const groups = visibleGroups()
      .map(
        (g) =>
          (g.group ? `<p class="app-shell__group-label">${g.group}</p>` : "") +
          g.items
            .map(
              (i) =>
                `<a class="app-shell__link${isCurrent(i.href) ? " is-current" : ""}" href="${i.href}"${
                  isCurrent(i.href) ? ' aria-current="page"' : ""
                } title="${i.label}">${ICONS[i.icon]}<span>${i.label}</span></a>`
            )
            .join("")
      )
      .join("");

    const nav = document.createElement("nav");
    nav.className = "app-shell";
    nav.setAttribute("aria-label", "Main");
    nav.innerHTML = `
      <a class="app-shell__brand" href="/home.html">
        <img src="/static/images/logo-without-background.png" alt="" />
        <span class="app-shell__brand-text">GermanATO</span>
      </a>
      <button type="button" class="app-shell__search" data-shell-search>
        ${ICONS.search}<span>Search or jump to</span><kbd>${
      navigator.platform.includes("Mac") ? "⌘K" : "Ctrl K"
    }</kbd>
      </button>
      <div class="app-shell__nav">${groups}</div>
      <div class="app-shell__footer">
        <div class="app-shell__user">
          <span class="app-shell__avatar">${initial}</span>
          <span class="app-shell__user-meta">
            <span class="app-shell__user-name">${name}</span><br />
            <span class="app-shell__user-role">${(user.role || "").replace("_", " ")}</span>
          </span>
        </div>
        <div class="app-shell__footer-actions">
          <button type="button" class="app-shell__icon-btn" data-shell-collapse title="Collapse sidebar" aria-label="Collapse sidebar">${ICONS.collapse}</button>
          <button type="button" class="app-shell__icon-btn" data-shell-theme title="Switch theme" aria-label="Switch theme">${ICONS.theme}</button>
          <button type="button" class="app-shell__icon-btn" data-shell-logout title="Sign out" aria-label="Sign out">${ICONS.logout}</button>
        </div>
      </div>`;

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "app-shell__toggle";
    toggle.setAttribute("aria-label", "Open navigation");
    toggle.innerHTML = ICONS.collapse;

    const scrim = document.createElement("button");
    scrim.type = "button";
    scrim.className = "app-shell__scrim";
    scrim.setAttribute("aria-label", "Close navigation");
    scrim.tabIndex = -1;

    document.body.prepend(nav, toggle, scrim);
    document.body.classList.add("has-app-shell");
    if (localStorage.getItem("shellCollapsed") === "1") {
      document.body.classList.add("shell-collapsed");
    }

    toggle.addEventListener("click", () => document.body.classList.toggle("shell-open"));
    scrim.addEventListener("click", () => document.body.classList.remove("shell-open"));

    nav.querySelector("[data-shell-collapse]").addEventListener("click", () => {
      // On mobile the sidebar is a drawer, so the same button closes it.
      if (window.matchMedia("(max-width: 900px)").matches) {
        document.body.classList.remove("shell-open");
        return;
      }
      const collapsed = document.body.classList.toggle("shell-collapsed");
      localStorage.setItem("shellCollapsed", collapsed ? "1" : "0");
    });

    nav.querySelector("[data-shell-theme]").addEventListener("click", () => {
      const next = localStorage.getItem("theme") === "dark" ? "light" : "dark";
      localStorage.setItem("theme", next);
      if (window.applyTheme) window.applyTheme(next);
      else window.location.reload();
    });

    nav.querySelector("[data-shell-logout]").addEventListener("click", async () => {
      if (window.auth) await auth.logout();
      window.location.href = "/login.html";
    });

    nav.querySelector("[data-shell-search]").addEventListener("click", openPalette);
  }

  // ----- command palette ---------------------------------------------------

  let palette = null;
  let results = [];
  let cursor = 0;

  function allEntries() {
    return [
      ...visibleActions().map((a) => ({ ...a, group: "Actions" })),
      ...visibleGroups().flatMap((g) =>
        g.items.map((i) => ({ ...i, group: g.group || "Go to" }))
      ),
    ];
  }

  function buildPalette() {
    palette = document.createElement("div");
    palette.className = "cmdk";
    palette.setAttribute("role", "dialog");
    palette.setAttribute("aria-modal", "true");
    palette.setAttribute("aria-label", "Search or jump to");
    palette.innerHTML = `
      <div class="cmdk__panel">
        <input class="cmdk__input" type="text" placeholder="Search or jump to..." aria-label="Search or jump to" autocomplete="off" spellcheck="false" />
        <div class="cmdk__list" role="listbox"></div>
        <div class="cmdk__footer"><span>↑↓ Navigate</span><span>↵ Open</span><span>esc Close</span></div>
      </div>`;
    document.body.appendChild(palette);

    const input = palette.querySelector(".cmdk__input");
    input.addEventListener("input", () => render(input.value));
    palette.addEventListener("mousedown", (e) => {
      if (e.target === palette) closePalette();
    });
    palette.addEventListener("keydown", onPaletteKey);
  }

  function render(query) {
    const q = query.trim().toLowerCase();
    results = q
      ? allEntries().filter((e) => e.label.toLowerCase().includes(q))
      : allEntries();
    cursor = 0;

    const list = palette.querySelector(".cmdk__list");
    if (!results.length) {
      list.innerHTML = `<p class="cmdk__empty">Nothing matches "${query}"</p>`;
      return;
    }

    let lastGroup = null;
    list.innerHTML = results
      .map((e, idx) => {
        const header = e.group !== lastGroup ? `<p class="cmdk__group">${e.group}</p>` : "";
        lastGroup = e.group;
        return (
          header +
          `<button type="button" class="cmdk__item" role="option" data-idx="${idx}" aria-selected="${
            idx === 0
          }">${ICONS[e.icon]}<span>${e.label}</span>${
            isCurrent(e.href) ? '<span class="cmdk__item-hint">current</span>' : ""
          }</button>`
        );
      })
      .join("");

    list.querySelectorAll(".cmdk__item").forEach((el) => {
      el.addEventListener("click", () => go(Number(el.dataset.idx)));
      el.addEventListener("mousemove", () => move(Number(el.dataset.idx)));
    });
  }

  function move(idx) {
    const items = palette.querySelectorAll(".cmdk__item");
    if (!items.length) return;
    cursor = (idx + items.length) % items.length;
    items.forEach((el, i) => el.setAttribute("aria-selected", String(i === cursor)));
    items[cursor].scrollIntoView({ block: "nearest" });
  }

  function go(idx) {
    const entry = results[idx];
    if (entry) window.location.href = entry.href;
  }

  function onPaletteKey(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      closePalette();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      move(cursor + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      move(cursor - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(cursor);
    }
  }

  function openPalette() {
    if (!palette) buildPalette();
    render("");
    palette.classList.add("is-open");
    const input = palette.querySelector(".cmdk__input");
    input.value = "";
    input.focus();
  }

  function closePalette() {
    if (palette) palette.classList.remove("is-open");
  }

  // ----- boot --------------------------------------------------------------

  /**
   * "New ..." actions deep-link with ?new=1. Open the destination page's own
   * create form so the action really is one click, not one click plus a hunt
   * for the button. Runs on load so the page's own init has already finished.
   */
  function handleNewParam() {
    if (new URLSearchParams(window.location.search).get("new") !== "1") return;

    const opener = ["openAddVendorModal", "openAddModal"].find(
      (fn) => typeof window[fn] === "function"
    );
    if (opener) {
      window[opener]();
      return;
    }

    // Pages whose create form is always on screen: put the cursor in it.
    const field = document.querySelector(
      "form input:not([type=hidden]):not([disabled]), form select, form textarea"
    );
    if (field) {
      field.scrollIntoView({ block: "center", behavior: "smooth" });
      field.focus({ preventScroll: true });
    }
  }

  /**
   * The sidebar now carries the brand, the navigation and sign-out, so the page
   * header only needs to say which page you are on. Strip the duplicated
   * chrome and keep anything genuinely page-specific (Reports' Refresh, say).
   */
  function slimHeader() {
    const header = document.querySelector(".top-header");
    if (!header) return;

    // Tag only - the redundant controls are hidden in CSS, never removed.
    // Several pages set backBtn.href unguarded on load, so deleting the node
    // threw and aborted their whole init.
    const title = header.querySelector(".brand-text h1, h1");
    const onlyBrand =
      title && title.textContent.trim().toLowerCase() === "germanato";

    // On the dashboard the header only repeated the app name, and the
    // dashboard writes its own greeting, so the whole bar is redundant there.
    header.classList.add(onlyBrand ? "page-header--redundant" : "page-header");
  }

  /**
   * Unsaved-changes guard. Reaching any module is now one click, which also
   * makes abandoning a half-filled form one click. Typing marks the page dirty;
   * a successful write (api:saved) or a form submit clears it.
   */
  function guardUnsavedChanges() {
    let dirty = false;

    document.addEventListener("input", (e) => {
      const field = e.target;
      if (!field.closest("form")) return;
      // Filters and search boxes are not work worth protecting.
      if (field.type === "search" || /search|filter/i.test(field.id + field.name)) return;
      dirty = true;
    });

    const clean = () => {
      dirty = false;
    };
    document.addEventListener("submit", clean, true);
    document.addEventListener("reset", clean, true);
    window.addEventListener("api:saved", clean);

    window.addEventListener("beforeunload", (e) => {
      if (!dirty) return;
      e.preventDefault();
      e.returnValue = "";
    });
  }

  function boot() {
    // The login page is the one screen with no shell.
    if (/login\.html$/.test(window.location.pathname) || window.location.pathname === "/") return;
    if (!window.auth || !auth.isAuthenticated) return;
    if (document.querySelector(".app-shell")) return;

    buildSidebar();
    slimHeader();
    guardUnsavedChanges();
    window.addEventListener("load", handleNewParam);

    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        palette && palette.classList.contains("is-open") ? closePalette() : openPalette();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.AppShell = { open: openPalette };
})();
