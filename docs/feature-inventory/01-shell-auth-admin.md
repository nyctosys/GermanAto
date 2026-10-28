# Feature inventory: app shell, auth, shared utilities, dashboard, admin, settings, WhatsApp, hub pages

Paths are relative to `backend/`. Where this says "server", it means the Flask code.

---

## 0. Cross-cutting: the permission model (backend rules the UI relies on)

**Roles** (stored in `User.role`): `admin`, `accountant`, `inventory_manager`. These are the only valid values (`auth_routes_jwt.py:94,274`).

**Permission strings** (`jwt_auth.py:17-22`, `ADMIN_PERMISSIONS`): `home, invoice, search, inventory, car, reports, admin, daily-expenses, major-expenses, vendors, vendor-detail, hr, worker-detail, repair-order, repair-orders-management, settings, logs`.

**DEFAULT_ROLE_PERMISSIONS** (`jwt_auth.py:24-35`). These apply only while the `role_permissions` table is completely empty:
- accountant: `home, invoice, search, car, daily-expenses, vendors, vendor-detail, hr, worker-detail, repair-order, repair-orders-management, settings`
- inventory_manager: `home, inventory, repair-order, repair-orders-management, settings`
- admin: everything.

**PATH_PERMISSIONS** (`jwt_auth.py:37-61`). This is a prefix match; the first match wins:

| Path prefix | Permission |
|---|---|
| /api/admin/app-logs | logs |
| /api/reports | reports |
| /api/settings | settings |
| /api/inventory | inventory |
| /api/customers | car |
| /api/cars | car |
| /api/expenses/major | major-expenses |
| /api/expenses | daily-expenses |
| /api/cash-received | daily-expenses |
| /api/vendors | vendors |
| /api/ledger | vendors |
| /api/purchase-orders | vendors |
| /api/consignments | vendors |
| /api/workers | hr |
| /api/salaries | hr |
| /api/salary | hr |
| /api/attendance | hr |
| /api/zkteco | hr |
| /api/repair-orders | repair-order |
| /api/invoice | invoice |
| /api/quotes | invoice |
| /api/add | invoice |
| /api/search | invoice |

Not mapped: `/api/dashboard`, `/api/whatsapp/*` and `/api/auth/*`.

**Decorators**
- `jwt_auth.login_required`: needs a valid JWT and an active user. It does **not** check permissions.
- `jwt_auth.role_required(roles)` (`jwt_auth.py:140-173`) goes through `has_configured_permission` (`:88-111`):
  - admin always passes.
  - If the path has no mapped permission, the route's role list decides.
  - If the `role_permissions` table is empty, the route's role list decides.
  - **Otherwise only the `role_permissions` row decides, and the route's role list is ignored.**
  - On a DB error it falls back to the role list.
- `admin_required` is `role_required('admin')`. It goes through the same permission logic, so a non-admin who holds the mapped permission passes. For example, an accountant granted `logs` can call `/api/admin/app-logs`.
- `auth_routes_jwt.py` defines its **own** `role_required` (`:28-55`), which is a pure role check that ignores the permission table. Every `/api/auth/users*`, `/register` and `/roles-permissions` route is strictly admin-only.

**Effective permissions for a user** (`/api/auth/permissions/my`, `auth_routes_jwt.py:371-396`, mirrored in `reports_routes._user_permissions:629-641`):
- admin gets `ADMIN_PERMISSIONS`.
- Otherwise it is the rows for the role. If the role has no rows **and** the table is empty, it is the defaults.
- A role with zero rows while other roles have rows gets nothing.

**Token config** (`config.py:34-43`):
- Access token lasts 24 h; refresh token lasts 7 days; HS256.
- `JWT_TOKEN_LOCATION = headers + cookies`, but the frontend only ever sends headers and no cookie is ever set.
- Cookie CSRF protection is off.
- The refresh token is never rotated, so after 7 days the user must log in again.
- Logout is a server no-op with no blacklist (`auth_routes_jwt.py:220-225`).

---

## 0.1 app.py: page routes and cache headers

**General server settings**
- Flask on port 5001. `__main__` auto-opens a browser at `http://127.0.0.1:5001` after 1 s (`app.py:367-372`).
- `ProxyFix(x_proto=1, x_host=1)`.
- CORS on `/api/*`: origins `*`, credentials allowed, headers Content-Type/Authorization/X-Requested-With, methods GET/POST/PUT/DELETE/OPTIONS. PATCH is missing from the list even though `APIHelper.patch` exists.
- Flask-Compress is on.
- The session cookie is configured (`germanato_session`, 24 h, Lax, HttpOnly), but the JWT flow does not use it.
- `/favicon.ico`, `/apple-touch-icon.png` and `/apple-touch-icon-precomposed.png` all return an empty 204.

**Page routes** (all serve `frontend/<file>`):
- **With `Cache-Control: no-cache, no-store, must-revalidate`, `Pragma: no-cache`, `Expires: 0`:**
  - `/` (serves **login.html**)
  - `/login.html`, `/admin.html`, `/pending-quotes.html`, `/repair-order.html`, `/repair-orders-management.html`
  - `/finance-management.html`, `/daily-expenses.html`, `/major-expenses.html`, `/settings.html`
  - `/employees.html`, `/salaries-management.html`, `/attendance.html`, `/device-management.html`
  - `/low-stock-print.html`, `/transaction-history.html`, `/inventory-history.html`
- **With no cache headers:**
  - `/home.html`, `/monthly-ledger.html`, `/invoiceSystem.html`, `/invoice.html`, `/quote.html`
  - `/invoice-template.html`, `/invoice-management.html`, `/inventory.html`, `/car.html`, `/reports.html`, `/whatsapp-notifications.html`
- **Served by blueprints:**
  - `/hr` serves hr.html (`hr_routes.py:22`).
  - `/hr/<id>` serves worker_detail.html after a 404 check.
  - `/hr/device-management` serves device-management.html.
  - `/vendors` serves vendors.html (`vendor_routes.py:18`).
  - `/vendors/<id>` serves vendor_detail.html after a 404 check.
- **There is no `/hr.html` route.** The settings page links to `hr.html`, which gives a 404 (`settings.html:94`).
- Page routes do no server-side auth at all. Every HTML page is public; protection is client-side only.

**Static files (quirk)**
- `@app.route('/static/<path>')` (`app.py:352-365`) tries to serve from `frontend/static` with 1-year caching. **`frontend/static` does not exist**, and Flask's built-in static route (`static_folder='./static'`) is registered first.
- So the custom handler is effectively dead, and static files are served with Flask defaults. The hard-coded `Expires: Thu, 31 Dec 2025` is never applied.
- `static/uploads` is publicly served under `/static/uploads`.

---

## 0.2 static/js/auth_jwt.js: AuthManager (shared, loaded on every page except unused login.js)

A global singleton `auth = new AuthManager()`, also exposed as `window.auth` and `window.AuthManager` (`:311-315`).

**SUB_PAGE_PERMISSIONS** (`:4-9`). Client-side aliases:
- `vendor-detail` → `vendors`
- `worker-detail` → `hr`
- `search` → `invoice`
- `repair-orders-management` → `repair-order`

**init()** (`:20-35`). This runs from the constructor; `this.ready` is its promise.
- It synchronously reads `localStorage.accessToken`, `refreshToken` and `user` (JSON), and sets `isAuthenticated = !!accessToken` before the first `await`. So pages can read `auth.isAuthenticated` and `auth.user` immediately.
- If a token exists:
  - `verifyToken()`: `GET /api/auth/verify` with Bearer.
    - On 200 it stores `user`.
    - On non-200 it calls `refreshAccessToken()`.
    - On a **network error** it calls `clearAuth()` and returns false, so a network blip on page load logs the user out (`:57-61`).
  - If verify and refresh both fail, `requireAuth()` redirects to `login.html`.
  - Otherwise `loadPermissions()` runs.

**refreshAccessToken()** (`:64-99`)
- Sends `POST /api/auth/refresh` with `Authorization: Bearer <refreshToken>`.
- On success it stores the new `accessToken` and `user`. The refresh token stays the same.
- On failure or exception it calls `clearAuth()` and returns false.

**login(username, password)** (`:101-134`)
- Sends `POST /api/auth/login` with body `{username, password}`.
- On success:
  - It stores `accessToken`, `refreshToken` and `user`.
  - It **awaits `loadPermissions()`**, so permissions are cached before the redirect.
  - It returns `{success:true, user}`.
- On an HTTP error it returns `{success:false, error:data.error}`.
- On a network error it returns `"Network error. Please try again."`.

**loadPermissions()** (`:136-153`)
- Sends `GET /api/auth/permissions/my` and stores `localStorage.userPermissions = JSON.stringify(data.permissions)`.
- Errors are logged only.

**logout()** (`:155-177`)
- Sends `POST /api/auth/logout` with Bearer if a token exists.
- It always calls `clearAuth()` in `finally`.

**clearAuth()** removes `accessToken`, `refreshToken`, `user` and `userPermissions`.

**hasRole(r)**: admin covers every role; other roles cover only themselves. `isAdmin`, `isAccountant` and `isInventoryManager` wrap it.

**getCachedPermissions()** parses `userPermissions`. It returns an array, or null if the value is missing or invalid.

**canAccessPage(page)** (`:211-230`)
- Returns false if not authenticated.
- Returns true for admin or for `home`.
- Returns **true if permissions are not cached yet**.
- Otherwise returns `perms.includes(SUB_PAGE_PERMISSIONS[page] || page)`.

**requireAuth()** (`:232-240`)
- If not authenticated, it redirects to the **relative** `login.html` unless the pathname is `/` or ends in `login.html`.
- **Quirk:** the relative URL breaks on nested paths. On `/vendors/7` it goes to `/vendors/login.html`; on `/hr/device-management` it goes to `/hr/login.html`.

**requirePageAccess(page)** (`:242-255`)
- Calls requireAuth first.
- If permissions are cached, it enforces immediately.
- Otherwise it returns true and enforces once `this.ready` resolves.

**enforcePageAccess**
- On denial it shows `alert("You do not have permission to access this page.")` and then calls `redirectToHome()`.

**redirectToHome()** (`:267-287`). The URLs are relative.
- Unauthenticated users go to `login.html`.
- `inventory_manager` goes to `inventory.html`.
- `admin` goes to **`reports.html`**.
- `accountant` (and the default) goes to `home.html`.
- **Bug:** an inventory_manager whose `inventory` permission was removed loops forever between alert and redirect on inventory.html.

**Other getters:** `getCurrentUser()` and `getAccessToken()`.

**auth_jwt.test.js** (node `vm` sandbox) asserts:
- the hasRole semantics;
- that canAccessPage applies the aliases and that home is always allowed;
- that there is no redirect or alert while permissions are null;
- that a known denial redirects to `home.html` with one alert;
- that there is no login→login loop.

Run it with `node backend/static/js/auth_jwt.test.js`.

---

## 0.3 static/js/api-helper.js: APIHelper (shared)

A static class on `window.APIHelper`.

**request(url, options)** (`:412-428`)
- **In-flight de-duplication:** the key is `METHOD url body`. Only string or null bodies are keyed (`requestKey` `:384-392`); FormData is never de-duplicated. An identical concurrent request gets the same promise. This applies to GETs too.
- **Trigger lock (non-GET only):** `lockTrigger()` (`:399-410`) disables the last clicked `button` or `input[type=submit]` if it was clicked less than 1000 ms ago. The button is tracked by a capture-phase document click listener (`:564-575`). It sets `aria-busy="true"` and re-enables in `finally`.

**performRequest** (`:430-500`)
- Headers: `Content-Type: application/json` unless the body is FormData, plus `Authorization: Bearer <auth.getAccessToken()>`.
- **Bug:** `fetch(url, {...defaultOptions, ...options})`. If a caller passes `options.headers`, that object replaces the merged headers, so Authorization and Content-Type are lost.
- **On 401:**
  - It calls `auth.refreshAccessToken()`.
  - On success it retries once with the new token. A non-ok retry throws `responseError`. If the retry succeeds it returns the data and clears the banner, but does **not** dispatch `api:saved` on that path.
  - On failure it calls `auth.clearAuth()`, redirects to the relative `login.html`, and returns `null`. Callers must handle null.
- **Non-ok responses** throw `responseError`:
  - The message is `errorData.error`, or `HTTP <status>: <statusText>`.
  - `details[]` is appended as `"\n\nDetails:\n" + lines`.
  - `error.status` is set.
- **Success** parses JSON (a 204 or empty body would throw), clears the error banner, and dispatches `window` `CustomEvent("api:saved")` for any non-GET.
- **catch:**
  - If the page is unloading it rethrows silently.
  - Otherwise it logs, and shows the sticky top error banner unless `options.silent`, then rethrows.
- **Unloading flag:** `pagehide` or `beforeunload` sets `_unloading=true` (`:556-561`). **Quirk:** if the unsaved-changes prompt is cancelled, the flag stays true, and every later error on that page is silent (no banner).

**Banner: showErrorState** (`:186-222`)
- The `#api-error-state` div is prepended to body with `role=alert`.
- Title: "Could not load this data". Text: `<url without origin>: <message>`.
- Buttons: **Reload** (calls `location.reload()`) and **x** (dismisses).
- `clearErrorState()` removes it.

**Inline-state helpers.** Each accepts an element id or element. When the target is a `<tbody>`, the content is wrapped in a `<tr><td colspan=N>` that spans the column count of `thead tr` (`wrapForContainer`).
- `renderLoading(target, msg="Loading...")` shows a spinner and the message.
- `renderError(target, error, onRetry)`:
  - The title is "You do not have access to this data" for a 403, "Not found" for a 404, and "Could not load this data" otherwise.
  - The message is `error.message`.
  - A "Try again" button is shown when `onRetry` is given and the status is not 403.
- `renderNoMatches(target, query, data, onPick)`:
  - Shows `No matches for "q"`.
  - If `data.did_you_mean` is set it adds "Did you mean <button>?".
  - If `data.closest[]` is set it adds "Closest on file:" with the buttons joined by " · ".
  - Clicking a button calls `onPick(term)`.
- `renderEmpty(target, msg="No records found")`.
- `escapeHtml` handles `& < > " '`.
- Shorthands: `get`, `post`, `put`, `delete`, `patch`. post, put and patch JSON-stringify the body.
- Styles are injected once into `#api-error-state-styles`, with dark-theme variants and a reduced-motion spinner.

---

## 0.4 static/js/app-shell.js + static/css/app-shell.css: sidebar, command palette, header slimming, unsaved-changes guard (shared)

The script is an IIFE and is loaded after auth_jwt.js on every page except login.

**boot()** (`:433-456`). It runs on DOMContentLoaded, or immediately if the DOM is already parsed.
- It skips when:
  - the path ends in `login.html` or is `/`;
  - `auth` is missing or not authenticated;
  - an `.app-shell` already exists (idempotent).
- Otherwise it runs, in order: buildSidebar, slimHeader, guardUnsavedChanges, `window.load` → handleNewParam, and a global keydown handler for Cmd/Ctrl+K.
- It exports `window.AppShell = {open}`, which nothing else uses.

**Full sidebar menu (NAV, `:47-101`).** Labels, hrefs and permissions are exact.

| Group | Label | href | Permission | Icon |
|---|---|---|---|---|
| (none) | Dashboard | /home.html | home | home |
| Create | New invoice | /invoice.html | invoice | plus |
| Create | New quote | /quote.html | invoice | plus |
| Create | New repair order | /repair-order.html | repair-order | plus |
| Sales | Invoices | /invoice-management.html | invoice | invoice |
| Sales | Quotes | /pending-quotes.html | invoice | quote |
| Sales | Repair orders | /repair-orders-management.html | repair-order | wrench |
| Operations | Inventory | /inventory.html | inventory | box |
| Operations | Vendors | /vendors | vendors | truck |
| Operations | Cars & customers | /car.html | car | car |
| Finance | Daily expenses | /daily-expenses.html | daily-expenses | cash |
| Finance | Major expenses | /major-expenses.html | major-expenses | wallet |
| Finance | Monthly ledger | /monthly-ledger.html | daily-expenses | chart |
| Finance | Reports | /reports.html | reports | chart |
| People | Employees | /employees.html | hr | people |
| People | Attendance | /attendance.html | hr | clock |
| People | Salaries | /salaries-management.html | hr | wallet |
| Admin | Users & roles | /admin.html | admin | shield |
| Admin | WhatsApp | /whatsapp-notifications.html | admin | chat |
| Admin | Settings | /settings.html | settings | gear |

Not in the sidebar:
- the hub pages (`/invoiceSystem.html`, `/finance-management.html`, `/hr`);
- `/hr/device-management`, `/monthly-ledger` alternatives, `/low-stock-print.html`, `/inventory-history.html`, `/transaction-history.html`.

There is no nav item for the `logs` permission.

**Palette-only ACTIONS** (`:107-111`):
- "New vendor" → `/vendors?new=1` (vendors)
- "Record daily expense" → `/daily-expenses.html?new=1` (daily-expenses)
- "Add inventory item" → `/inventory.html?new=1` (inventory)

**Visibility: allowed(permission)** (`:115-124`)
- No `auth.user` means hidden.
- Admin, or the `home` permission, means shown.
- Otherwise it checks cached `userPermissions`. **If the cache is null, the item is shown.**
- Groups with no visible items are dropped.
- The admin-group items `admin` and the WhatsApp item need the `admin` permission. The admin matrix has no checkbox for it, so in practice they are admin-role only.
- Note: the sidebar is built once from whatever permissions are cached. It is never rebuilt after `auth.ready` or `loadPermissions` refreshes them.

**Active state: isCurrent(href)** (`:135-141`)
- Trailing slashes are stripped and the query is ignored.
- An exact match is current; so is a prefix match `href + "/"`, so `/vendors/7` highlights Vendors.
- Current links get `is-current` (maroon background, white text) and `aria-current="page"`. Every link gets `title=label`.

**Sidebar markup** (`:168-192`)
- Brand link to `/home.html` (logo plus "GermanATO").
- Search trigger: "Search or jump to" with `<kbd>`. The kbd reads `⌘K` if `navigator.platform` includes "Mac", otherwise `Ctrl K`.
- The groups.
- Footer:
  - Avatar: the first letter of the username, uppercased.
  - Username, or "Signed in" if missing.
  - Role with only the **first** `_` replaced by a space, capitalized in CSS.
  - Three icon buttons: Collapse, Switch theme, Sign out.

**Collapse** (`:208-223`)
- The body gets `shell-collapsed` if `localStorage.shellCollapsed === "1"`.
- The collapse button toggles the class and writes `"1"`/`"0"`.
- At `max-width: 900px` the same button instead closes the mobile drawer.
- Widths: 264 px expanded, 72 px collapsed. Collapsed hides the brand text, group labels, link labels, the search label and kbd, and the user meta, and centres the icons.

**Mobile, ≤900 px** (`app-shell.css:296-335`)
- The sidebar becomes an off-canvas drawer (`translateX(-100%)`).
- A fixed hamburger `.app-shell__toggle` at top-left (12 px, 40×40) toggles `body.shell-open`.
- A scrim (`rgba(0,0,0,.4)`) closes it on click.
- The collapsed state is ignored on mobile.
- The page gutter shrinks from 32 to 20 px, and there is 64 px top padding for the toggle.

**Theme button** (`:225-230`)
- `next = theme==="dark" ? "light" : "dark"`, written to `localStorage.theme`.
- It then calls `window.applyTheme` if defined, **otherwise reloads the page**.
- **Bug:** theme.js exposes `window.applyGlobalTheme`, not `applyTheme`, so every toggle does a full page reload.
- Starting from `auto`, the toggle goes to `dark`.

**Sign out** (`:232-235`) awaits `auth.logout()` and then goes to the absolute `/login.html`.

**Command palette** (`:242-352`)
- Opened by the sidebar search button or Cmd/Ctrl+K. The shortcut is global, toggles, and calls `preventDefault`, which overrides the browser's own Ctrl+K.
- It is a `div.cmdk` with `role=dialog`, `aria-modal`, a text input (autocomplete and spellcheck off), a listbox, and a footer reading "↑↓ Navigate / ↵ Open / esc Close".
- Entries: the visible ACTIONS (group "Actions") first, then the visible NAV items (their group name, or "Go to" for the ungrouped Dashboard).
- Filtering is a case-insensitive **substring** match on the label, re-run on every input with no debounce. The cursor resets to 0.
- Group headers render when the group changes. The current page shows a "current" hint.
- Empty state: `Nothing matches "<query>"` (the query is not escaped).
- Keys (handled only while focus is in the palette): ArrowDown/ArrowUp move with wrap-around and scrollIntoView; Enter navigates; Escape closes.
- Mouse: mousemove selects, click navigates, and mousedown on the backdrop closes.
- On open the input is cleared and focused.

**handleNewParam** (`:361-380`, runs on `window.load`)
- Only when `?new=1` is present.
- It calls the first global function that exists among `openAddVendorModal` and `openAddModal`.
- Otherwise it focuses the first visible form field (`form input:not([type=hidden]):not([disabled]), form select, form textarea`) with smooth scroll to centre.

**slimHeader** (`:387-401`)
- On `.top-header`: if the h1 text equals "germanato" (home only), it adds `page-header--redundant` and the whole header is hidden. Otherwise it adds `page-header`.
- In CSS, with the shell present, these are always hidden (not removed): `.back-btn`, `#back-btn`, `.back-button`, `.settings-btn`, `.logout-btn`, `.top-header .header-logo` (`app-shell.css:488-495`).
- So every page's Back, Settings and Logout header buttons are invisible whenever the user is authenticated.

**guardUnsavedChanges** (`:408-431`)
- Any `input` event inside a `<form>` marks the page dirty, except fields of `type=search` or whose `id+name` matches `/search|filter/i`.
- It is cleaned by a capture-phase `submit`, a `reset`, or `api:saved`.
- While dirty, `beforeunload` shows the native "leave site?" prompt.
- Quirk: closing a modal without saving does not clean it (for example the settings or admin modals), so the next navigation prompts.

**Page layout CSS**
- Max width 1400 px; content padding `24px 32px 48px`.
- `.main-content > * + *` gets a 24 px top margin.
- The footer is restyled.
- `body.has-app-shell` gets `padding-left` equal to the sidebar width.

**Print** (`app-shell.css:615-630`): the sidebar, toggle, scrim and palette are hidden, and the body padding is removed.

**Focus:** `:focus-visible` shows a 2 px maroon outline inside the shell and palette.

---

## 0.5 static/js/theme.js + static/css/theme.css: theming (shared)

**theme.js**
- An IIFE in `<head>`. It reads `localStorage.theme` (default `"light"`).
- `applyTheme(t)`:
  - removes `dark-theme`/`light-theme` from body;
  - `dark` adds `dark-theme`;
  - `auto` adds `dark-theme` or `light-theme` according to `prefers-color-scheme: dark`;
  - anything else adds `light-theme`.
- It is applied immediately if body exists. In `<head>` it does not, so in practice it only applies on DOMContentLoaded, which causes a flash of the light theme despite the comment.
- A listener on `prefers-color-scheme` changes re-applies when the theme is `auto`.
- It exports `window.applyGlobalTheme`.

**theme.css**
- `:root` light tokens (`--theme-primary #8b1538`, text, bg, card, hover, border, shadows, input, table).
- `body.dark-theme` overrides the tokens, and also the legacy page variables `--primary-maroon`, `--text-dark`, `--bg-white` and so on.
- The rest of the file (about 317 `body.dark-theme` rules) is dark-mode overrides for headers, cards, tables, inputs, buttons, links, modals, footers, scrollbars, badges, nav cards, the coming-soon modal, login, status colours, `div[style*=background]`, inline `#fff`/white backgrounds, SVG strokes and autofill.
- The only non-dark rule is `.customer-code` (a monospace customer id).
- **theme.css has no media queries: no responsive breakpoints and no print rules.**
- The `light-theme` class has no CSS rules.

---

## 0.6 static/js/notification-utils.js (shared toasts; global functions)

All toasts are fixed at `top:20px; right:20px; z-index:9999`.

- `showSuccess(msg)`:
  - Inline-styled green toast with "✓" and a × button. Auto-removed after **3 s**.
  - It defers until DOMContentLoaded if the page is still loading.
  - It injects the `@keyframes slideIn` once (`#notification-styles`).
- `showError(msg)`:
  - Uses Bootstrap classes `alert alert-danger … position-fixed` and `<i class="fas fa-exclamation-circle">`.
  - **Bootstrap and Font Awesome are not loaded on these pages**, so it renders as an unstyled text box with no background in light mode.
  - Auto-removed after **5 s**. It defers until DOMContentLoaded.
- `showInfo` (3 s) and `showWarning` (4 s) use the same Bootstrap-class approach and do not defer.
- `msg` is inserted as HTML, unescaped.

---

## 0.7 static/js/phone-formatter.js (shared; used by worker_detail, repair-order, employees, invoice, quote, vendors, car; not by any page in this area)

**formatPhoneNumber(v)** (`:9-61`) first strips everything except digits and `+`, then:
- **Starts with `+92`:** with no digits it returns `+92`. With up to 3 digits it returns `+92 ddd`. Up to 10 digits it returns `+92 ddd ddddddd`. Beyond 10 digits it truncates.
- **Starts with `0`:** up to 4 characters are returned as-is. Otherwise the result is `0xxx` + space + the rest, truncated at 11 digits.
- **Any other digits:** up to 3 are returned as-is. Otherwise a leading `0` is added: `0` + the first 3 + space + the rest, up to 11 digits.
- Note: `+` followed by anything other than 92 falls into the "other" branch with the `+` kept.

**setupPhoneFormatter(idOrEl)** (`:67-129`)
- Formats on `input`, preserving the cursor by counting digits before the caret.
- Formats on `paste` (setTimeout 0) and on `blur`.

**setupAllPhoneFormatters()** auto-runs on DOM ready. It wires these ids: `customer_phone`, `customer-phone`, `modal-customer-phone`, `phone`, `editPhone`, `editEmergencyContactPhone`. It also wires every `input[type=tel]` not in that list.

Exported: `window.formatPhoneNumber`, `setupPhoneFormatter`, `setupAllPhoneFormatters`.

Note: the server-side WhatsApp formatter is different (see §WhatsApp).

---

## 0.8 static/js/performance-utils.js (shared; included only by frontend/inventory.html:467)

The global instance is `window.PerformanceUtils`.
- monthlyLedger.js references it, but monthly-ledger.html does not include the script, so there it is always null.
- inventory.js uses only `showLoading`, `showError`, `hideLoading` and `fetchWithRetry`.

**fetchWithRetry(url, opts, cacheTime=300000)** (`:33-57`)
- An in-memory cache keyed by `url_JSON(opts)` with a 5-minute TTL.
- Concurrent identical calls share one promise.

**_fetchWithRetryInternal** (`:62-137`)
- Up to **3 attempts**, with delays of 1 s and then 2 s.
- It retries every error, including 4xx.
- Headers: JSON plus Bearer.
- On 401 it refreshes and retries once. If the refresh fails it calls `clearAuth` and redirects to `login.html`.

**Other helpers**
- `showLoading(id,msg)` injects a spinner and a `<style>` with `@keyframes spin`.
- `hideLoading(id)`.
- `showError(id,msg,retryCb)`: the Retry button uses `onclick="${retryCb.name}()"`, so it **breaks for anonymous or arrow callbacks**.
- `setCache`, `getFromCache`, `clearCache`, `delay`, `debounce`, `throttle`.
- **Dead code:** `batchRequests` and `loadInitialData` (which would hit `/api/customers`, `/api/cars`, `/api/inventory`). `debounce`, `throttle` and `clearCache` are unused in this area.
- It also exports `module.exports`.

---

## 0.9 static/js/script.js: dead

It is 16 lines with only a `console.warn` deprecation notice ("invoice functionality split into createInvoice.js / editInvoice.js"). No HTML or JS references it. Drop it.

## 0.10 static/js/login.js: confirmed unused (dead)

- No HTML includes it; login.html loads `login_jwt.js`.
- It is a session-cookie-era login:
  - `fetch('/api/auth/login', {credentials:'include'})`;
  - it stores `localStorage.user` and `localStorage.isAuthenticated="true"`;
  - it never stores tokens;
  - every role is redirected to `home.html`.
- It calls **`GET /api/auth/check-auth`, which does not exist** on the backend.
- Drop it.

---

## login.html: GermanATO - Login

**1. Purpose, URL and access**
- URLs: `/` and `/login.html`, both served with no-cache headers.
- Public. It has no app-shell (boot skips it), and it loads theme.css, login.css, theme.js, auth_jwt.js and login_jwt.js.
- **Already logged in:** `checkAuthStatus()` (`login_jwt.js:59-64`) runs on DOMContentLoaded. If `auth.isAuthenticated` (that is, any stored access token, before verification) it calls `auth.redirectToHome()`.
  - Quirk: if a token exists but `user` is null in storage, `this.user.role` throws.
  - Quirk: a stale or invalid token redirects to home, whose init then fails verification and bounces back to login.

**2. Layout**
- Logo, "Welcome Back", "Sign in to continue to your dashboard", the form, and the footer "© 2024 GermanATO. All rights reserved."

**3. Form `#login-form`**

| Label | name/id | Type | Rules |
|---|---|---|---|
| Username | `username` | text | required; placeholder "Enter your username"; trimmed client-side; case-insensitive on the server (`find_user` uses lower()) |
| Password | `password` | password | required; placeholder "Enter your password" |

- Submit button `.login-btn`: "Sign In" plus an arrow icon.
- **Client validation:** if either value is empty, show "Please enter both username and password".
- **Submit:**
  - The button is disabled and its text becomes "Logging in...".
  - It calls `auth.login(u,p)`, which sends **POST /api/auth/login** `{username,password}`.
  - On success it calls `auth.redirectToHome()`: admin goes to `reports.html`, inventory_manager to `inventory.html`, accountant to `home.html`.
  - On failure it shows `result.error`. Server errors are "Invalid username or password" (401, also for inactive users), "Username and password are required" (400), "No data provided" (400) or "Login failed" (500). The fallback text is "Login failed. Please try again.".
  - On an exception it shows "Network error. Please check your connection and try again.".
  - In `finally` the button is re-enabled, and its text is set to **"Login"**. Quirk: the original "Sign In" label and icon are lost after the first attempt.
- The server sets `user.last_login = utcnow` on a successful login.
- **Error box `#error-message`:** shown, then auto-hidden after **5 s**.

**4–9.** There are no tables. The browser's native required validation applies. Persisted state: auth_jwt writes `accessToken`, `refreshToken`, `user` and `userPermissions` (awaited before the redirect).

**10. Tokens:** see §0.2. The login response contains `access_token`, `refresh_token` and `user{id,username,email,role}`.

---

## home.html: GermanATO - Dashboard (`dashboard.js`)

**1. Purpose, URL and access**
- URL `/home.html`, no cache headers.
- Client-side: `auth.requirePageAccess("home")`, which is always true for any authenticated user. An unauthenticated visitor goes to `login.html`.
- Server-side: `GET /api/dashboard` is `login_required`. The sections returned are filtered by permission on the server.
- Admins never land here from login (they go to reports.html), but they can open it from the sidebar.

**2. Layout**
- The top header (GermanATO / Business Management System, with Settings and Logout buttons) is fully hidden by the shell (`page-header--redundant`).
- `.dash` contains:
  - `#dashGreeting` (initially "Today");
  - `#dashSubtitle` (initially "Your pending work");
  - a **Refresh** button `#dashRefresh`;
  - `#dashContent`.
- Footer "© 2025 GermanATO. All rights reserved."

**Greeting** (`dashboard.js:220-225`)
- "Good morning" if the local hour is under 12, "Good afternoon" under 17, otherwise "Good evening".
- The username is appended when it is known.

**Subtitle:** today's date as `toLocaleDateString("en-US",{weekday:"long",day:"numeric",month:"long",year:"numeric"})`.

**3. Actions**
- **Refresh** re-runs `loadDashboard()`. There is no polling or auto-refresh.
- Stat cards and rows are links.

**loadDashboard** (`:227-255`)
- `APIHelper.renderLoading(dashContent,"Loading your dashboard...")`, then **GET /api/dashboard**.
- If the HTML is empty it shows "Nothing is assigned to your role yet. Use the sidebar to get started."
- If `data.unavailable[]` is non-empty it calls `showError("Could not load: <list>. Try refreshing.")`.
- On a load error it calls `APIHelper.renderError(dashContent, err, loadDashboard)`, which includes a "Try again" button.

**Server response** (`reports_routes.py:644-671`): `{sections, unavailable[], role, generated_at}`.
- Section → required permission: invoices→`invoice`, quotes→`invoice`, repairs→`repair-order`, expenses→`daily-expenses`, inventory→`inventory`, insights→`reports`.
- Each builder is wrapped in try/except. A failure goes into `unavailable` and rolls back the session.
- Several inner helpers (`get_low_stock_items`, `get_pending_quotes`, `get_open_repair_orders`, `get_sales_data`, `get_expenses_data`, `get_receivables`) swallow their own errors and return empty or zero. Those failures show as empty or zero data, not as "unavailable".

**4. Stat cards** (`buildStats`, `:60-136`). Each card is shown only if its section is present.

| Card | Value | Meta | Link | Alert style |
|---|---|---|---|---|
| Sales this month | money(insights.sales_month) | – | /reports.html | – |
| Profit this month | money(insights.profit_month) | "`money(expenses_month)` expenses" | /reports.html | – |
| Unpaid invoices | invoices.unpaid_count | "`money(unpaid_total)` outstanding" | /invoice-management.html | when count > 0 |
| Pending quotes | quotes.pending_count | "`money(pending_value)` potential" | /pending-quotes.html | – |
| Open repair orders | repairs.open_count | "`completed_today` completed today" | /repair-orders-management.html | – |
| Expenses today | money(expenses.today_total) | "`money(month_total)` this month" | /daily-expenses.html | – |
| Low stock items | inventory.low_stock_count | – | /inventory.html | when count > 0 |

**Panels** (`buildPanels`, `:138-218`):
- **"Invoices awaiting payment"** ("View all" → /invoice-management.html)
  - Rows come from `invoices.oldest` (the 5 oldest unpaid, `created_at ASC`).
  - Each row: customer_name; "Invoice #id · raised <daysAgo>"; money(owed).
  - Each row links to `/invoice-management.html?id=<id>`. **Quirk:** invoiceManagement.js never reads `id`, so the link only opens the list.
  - Empty text: "Every invoice is settled."
- **"Quotes awaiting a decision"** (→ /pending-quotes.html)
  - Rows come from `quotes.items` (the 5 newest pending): customer_name; "Q-0001 · sent <daysAgo>"; money(total_amount).
  - Each row links to the list page, not the specific quote.
  - Empty text: "No quotes are waiting."
- **"Repair orders in progress"** (→ /repair-orders-management.html)
  - Status chips `<status> <count>` come from `by_status`.
  - Rows come from `repairs.items` (the 5 newest open): customer_name; "#id · status · opened <daysAgo>". They link to the list. There is no amount.
  - Empty text: "Nothing in the workshop right now."
- **"Stock to reorder"** (→ /inventory.html)
  - Rows come from `inventory.items` (the top 5 by `quantity/reorder_level` ascending): item_name; "category · reorder at N"; "N left".
  - The server's `urgency` field is ignored.
  - Empty text: "Stock levels are healthy."
- `insights.receivables`, `sales_daily` and `expenses_daily` are returned but **not rendered**.

**5. Calculations**

Client side:
- `money(n) = "Rs " + Number(n||0).toLocaleString("en-PK",{min 0, max 0 fraction digits})`.
- `daysAgo(iso) = floor((now - Date(iso))/86400000)`. Zero or less reads "today", 1 reads "1 day ago", otherwise "N days ago".
- Quirk: the server sends naive UTC ISO strings without "Z". The browser parses them as local time, so the result is off by the timezone offset.

Server side:
- Invoice due = `net_total + (include_tax ? tax_amount : 0) − discount`; paid = `advance + paid_amount`.
- An invoice is unpaid when due > paid. `unpaid_total = Σ(due−paid)`. Only `type_of='invoice'` rows count.
- Quotes: `type_of='quote' AND status='pending'`. The pending value is `Σ net_total`, with no tax or discount. The quote number is `Q-%04d` of the id.
- Repairs: open means `current_status NOT IN ('complete','completed')`. `completed_today` means status complete and `DATE(updated_at)=today`.
- Expenses: today_total is `Σ expense.amount where date=today`; month_total is `Σ where date ≥ the 1st of the month`.
- Inventory: low stock means `quantity <= reorder_level`.
- Insights: sales_month is `Σ invoice.net_total` (type invoice, created this month, which excludes tax and discount). expenses_month is `Σ expense.amount` this month. profit_month = sales − expenses.

**9. Coming Soon modal (dead code)**
- `#coming-soon-modal` ("Coming Soon / WhatsApp Notifications feature is under development…", "Got it").
- `showComingSoonPopup()` is never called.
- The close handlers (click outside, Escape) still exist.

**11. Quirks**
- The inline `handleLogout()` (`home.html:110-123`) belongs to the hidden logout button, so it is effectively dead.
- Even if reached, it does not await `auth.logout()`, so the request can be aborted and `clearAuth` may never run.

---

## admin.html: GermanATO - Users Management (`admin.js`)

**1. Purpose, URL and access**
- URL `/admin.html` with no-cache headers.
- Client-side: `auth.requirePageAccess("admin")`. Only the admin role passes in practice, because the `admin` permission is not grantable in the UI.
- While permissions are still loading the page initialises, and a denial later shows the alert and calls redirectToHome.
- If `auth` is undefined, admin.js retries after 100 ms and then redirects to `login.html` (`:6-22`).
- Server-side:
  - `/api/auth/users*`, `/register` and `/roles-permissions` are strict admin-role checks.
  - `/api/admin/app-logs` is `login_required` plus `admin_required`, which passes for admin **or** any role holding the `logs` permission when the permission table is non-empty.
- The sidebar shows "Users & roles" only for the `admin` permission.

**2. Layout**
- Header title "Users Management" / "Manage users and system settings". The Back link is hidden.
- Three tabs (`switchTab`, `:234-251`). The active tab button gets `active`; sections are toggled with `display`.
  1. **Users Management** (the default).
  2. **Roles & Permissions** (calls `loadRolePermissions()` on every switch).
  3. **App Action Logs** (calls `loadLogs(1)` on every switch).
- The tab state is not persisted.
- Footer "© 2025".

**Back link logic** (hidden by the shell):
- `from` param, else `localStorage.lastPage`, else "home".
- "home" goes to home.html, "invoiceSystem" to invoiceSystem.html, anything else to home.html.
- It writes `localStorage.lastPage = "admin"`.

**Users tab**
- On load: **GET /api/auth/users**, which returns an array ordered by id: `[{id, username, email, role, is_active, created_at, last_login}]`.
- Table columns:
  - Username
  - Email
  - Role: a badge `role-<role>` with the first `_` replaced by a space
  - Status ("Active"/"Inactive")
  - Created (`toLocaleDateString`, or "N/A")
  - Last Login (`toLocaleDateString`, or "Never")
  - Actions: **Edit** and **Delete**
- No sort, search or pagination.
- Empty state: "No users found / Click "Add New User" to get started".
- On a load error: `showError("Error loading users. Please check your connection.")`, plus the APIHelper banner.
- XSS: values are not escaped.

**Add/Edit User modal** (`#user-modal`)
- Opened via `display:block`. It closes via ×, Cancel, or a click on the backdrop. There is no Escape handling.

| Label | name/id | Type | Required | Notes |
|---|---|---|---|---|
| Username | username | text | yes | server: unique, case-insensitive |
| Email | email | email | yes | native email validation; server: unique, case-insensitive |
| Password | password | password | yes on add, **no on edit** | the edit form shows it blank; an empty value means unchanged |
| Role | role | select | yes | options "Select Role"(""), Admin(admin), Accountant(accountant), Inventory Manager(inventory_manager) |

- "Add New User" sets the title "Add New User" and resets the form.
- Edit fills username, email and role from the cached list and sets the title "Edit User".
- Submit (`:179-205`) sends the body `{username, email, role, password}`:
  - **Add:** **POST /api/auth/register**. The server requires all four and checks for duplicates ("Username already exists", "Email already exists") and valid roles ("Invalid role"). It returns 201.
  - **Edit:** **PUT /api/auth/users/:id**. The server updates the fields present; the password only if non-empty. It refuses `"Cannot update your own account"` (400).
  - On success the modal closes and the list reloads.
  - On any error it shows the generic "Error saving user. Please try again." Only the APIHelper banner carries the real server message.
- There is no UI to toggle `is_active`, although the server PUT supports it.
- **Delete:** `confirm("Are you sure you want to delete this user?")`, then **DELETE /api/auth/users/:id**, which is a hard delete. The server refuses self-deletion with "Cannot delete your own account".
  - On success the row is removed locally.
  - On error: "Error deleting user. Please try again."

**Roles & Permissions tab**
- Text: "Roles & Permissions Matrix" / "Configure module permissions for system roles below. Changes take effect on the next login or page refresh."
- Two cards: **Accountant Role** (`.accountant-chk`) and **Inventory Manager Role** (`.inventory-chk`).
- Each card has the same 11 checkboxes (value → label):
  - invoice → Invoices & Quotes
  - vendors → Vendors & Ledgers
  - daily-expenses → Daily Expenses & Cash Flow
  - major-expenses → Major Expenses (Restricted)
  - inventory → Inventory Management
  - car → Car & Customer
  - hr → HR & Employee Salaries
  - repair-order → Repair Orders (ROs)
  - reports → Reports & Analytics
  - logs → App Action Logs
  - settings → Settings
- Not grantable: `home`, `admin`, and the sub-page aliases `search`, `vendor-detail`, `worker-detail`, `repair-orders-management`. The client derives the aliases; `home` is always allowed client-side but is **not** included in dashboard permission sets (it is not needed there).
- Load: **GET /api/auth/roles-permissions** returns `{accountant:[...], inventory_manager:[...]}`.
  - All boxes are unchecked first, then the matching ones are checked.
  - **Quirk:** when the table is empty the server returns empty arrays, not the effective defaults (it falls back to defaults only on a DB error). The UI then shows everything unchecked while the defaults are actually in force.
- **Save Permissions** sends **PUT /api/auth/roles-permissions** with `{accountant:[checked], inventory_manager:[checked]}`.
  - The server deletes all rows for both roles and inserts the new ones.
  - Then it shows `showSuccess("Role permissions saved successfully!")` and calls `auth.loadPermissions()`.
  - On error: "Failed to save role permissions".
- **Consequences to preserve:**
  - Once any row exists, routes use only the permission rows, and the route role lists are ignored.
  - Saving with everything unchecked empties the table, which **re-activates the defaults**.
  - A role saved with zero boxes while the other role has some boxes loses all mapped API access.

**App Action Logs tab**

Filters (applied only on **Apply**; there is no debounce or live filtering):

| Label | id | Type | Options / notes |
|---|---|---|---|
| User | filter-username | text | **exact**, case-sensitive match on the server |
| Module | filter-module | select | All Modules(""), invoices, quotes, repair_orders, vendors, expenses, cash_received |
| Action | filter-action | select | All Actions(""), CREATE, UPDATE, DELETE, UPDATE_STATUS, UPDATE_BALANCE, CREATE_LEDGER, DELETE_LEDGER, CREATE_PO, DELETE_PO, UPDATE_PO_STATUS |
| Start Date | filter-start-date | date | `created_at >= start` |
| End Date | filter-end-date | date | `created_at < end + 1 day` (inclusive) |
| Keyword Search | filter-keyword | text | `details ILIKE %kw%` |

- **Missing from the filter lists**, although they are written by the backend:
  - modules `salary_advances`, `payroll`, `financial_periods`;
  - actions `UPDATE_PART_STATUS`, `UPDATE_LABOUR_STATUS`, `REOPEN`, `CLOSE`.
- **Reset** clears all filters and reloads page 1.
- Request: **GET /api/admin/app-logs?page=N&per_page=50[&username&module&action&start_date&end_date&keyword]** (the server default per_page is 100).
- Response: `{logs, total, pages, current_page}`, ordered by `created_at DESC`.
- Columns:
  - Timestamp: the raw server string `YYYY-MM-DD HH:MM:SS` in UTC naive time, monospace
  - User (bold; "system" if empty)
  - Module (badge)
  - Action (badge)
  - Ref ID (or "-")
  - Details (unescaped HTML)
  - IP Address (or "-")
- Pagination appears only if pages > 1: **Previous** (disabled on page 1), "Page X of Y", **Next** (disabled on the last page).
- Empty state: "No logs found / Try adjusting your search filters."
- On error: "Failed to load logs. Please try again."
- Log rows are written server-side by `log_utils.log_action`. IP is taken from `X-Forwarded-For` (the first entry) or `remote_addr`.

---

## settings.html: GermanATO - Settings (`settings.js`)

**1. Purpose, URL and access**
- URL `/settings.html` with no-cache headers.
- Client-side: **only `auth.requireAuth()`**. There is no `requirePageAccess("settings")`, so any logged-in user can open it even without the `settings` permission. The sidebar item is gated by `settings`.
- Control visibility is based on **role**, not permission:
  - Departments can be managed by admin or accountant.
  - Categories can be managed by admin or inventory_manager.
- When a role cannot manage a section, its Add button is hidden, its "Actions" header is hidden, and its rows carry no Actions cell.
- Server-side:
  - GET departments and categories are `login_required` only, so any user can read them.
  - POST, PUT and DELETE departments are `role_required(['admin','accountant'])`; POST, PUT and DELETE categories are `role_required(['admin','inventory_manager'])`. Both go through the `/api/settings` → `settings` path permission. **Once the permission table is non-empty, any role holding `settings` may write both**, which mismatches the UI's role-based hiding.

**2. Layout**
- Header "Settings" / "Manage system settings and preferences" (the Back link to home.html is hidden).
- Three sections:

**A. Color Theme**
- Select `#theme-select` with options Light(light), Dark(dark), Auto (System)(auto). It is initialised from `localStorage.theme` (default light), and `applyGlobalTheme` is applied on load.
- Two static preview cards (light and dark).
- On change it writes `localStorage.theme`, calls `applyGlobalTheme(theme)`, and shows the toast "Theme changed to <value>".
- Preference is per-browser only; nothing is stored on the server.

**B. Manage Departments**
- Description: "Departments are used in HR Management to organize workers by their department." The link goes to `hr.html`, which **404s**; the real URL is `/hr`.
- **Add Department** button.
- Table `#departments-table` columns: ID, Name (bold), Description (or "-"), Workers ("N worker/workers"), Actions (Edit, Delete).
- Load (`:147-176`), in parallel:
  - **GET /api/settings/departments?include_inactive=true**. The server ignores `include_inactive` and returns all rows, ordered by name.
  - **GET /api/workers**, with `.catch(()=>null)`. A failure is swallowed, but the APIHelper banner still appears.
- Worker counts are grouped by `worker.department` name (a string match).
- Inactive departments are shown with no status indicator.
- Empty state: "No departments found." plus, for managers, ' Click "Add Department" to create one.'
- On error: the toast "Failed to load departments".

**C. Manage Categories**
- Description: "Categories are used in Inventory Management…", linking to `inventory.html`.
- **Add Category** button.
- Columns: ID, Name, Description, Items ("N item/items"), Actions.
- Load: **GET /api/settings/categories?include_inactive=true** and **GET /api/inventory?per_page=1000** in a `Promise.all` **without a catch** on the inventory call, so an inventory failure kills the whole category list.
  - The server **caps per_page at 200**, so item counts are under-counted when there are more than 200 items.
  - Counts are matched by the `item.category` name.
- On error: "Failed to load categories".

**Department and Category modals** (`.modal.show` class)
- They close via ×, Cancel, or a click on the backdrop. There is no Escape handling.

| Field | id/name | Type | Required |
|---|---|---|---|
| Department Name * / Category Name * | department-name / category-name (`name`) | text | yes (HTML required, plus a JS trim check: "Department name is required" / "Category name is required") |
| Description | department-description / category-description | textarea, 3 rows | no |

- **Add:** **POST /api/settings/departments** (or `/categories`) with `{name, description}`, both trimmed.
  - The server rejects a duplicate name with a case-sensitive exact match: "Department with this name already exists" / "Category with this name already exists".
  - New rows are created with `is_active=True`.
  - On success: the toast "Department created successfully" (or "Category …"), the modal closes, and the list reloads.
- **Edit:**
  - It opens with the title "Edit Department" and re-fetches **GET /api/settings/departments** (without include_inactive) to find the row by id.
  - If the row is not found it shows "Department not found" and closes the modal.
  - Submit sends **PUT /api/settings/departments/:id** `{name, description}`, with the duplicate check. On success: "Department updated successfully". An empty description is stored as null.
  - The server also accepts `is_active`, but the UI never sends it.
- **Delete:**
  - `confirm('Are you sure you want to delete the department "<name>"? This action cannot be undone.')`, then **DELETE /api/settings/departments/:id**. This is a hard delete with no check for workers that use the department.
  - On success: "Department deleted successfully".
  - Categories work the same way.
- On a save error, the modal stays open and the toast shows `error.message` (for example "Insufficient permissions").

**Toasts** (`showNotification`, `:602-650`)
- Fixed top-right, z-index 3000, max width 300 px, gradient background by type (success green, error red-orange, warning yellow, info teal).
- Removed after 3 s, with a 300 ms slide-out.

**11. Quirks**
- `escapeHtml` (textContent→innerHTML) does not escape `'`. The Delete `onclick="deleteDepartment(id, '<name>')"` breaks for names containing an apostrophe.
- The edit `currentEditingId !== 0` guard means an id of 0 would be treated as create.
- `window.*` exports exist for the inline onclicks.

---

## whatsapp-notifications.html: WhatsApp Notifications - GermanATO (`whatsapp-notifications.js`)

**1. Purpose, URL and access**
- URL `/whatsapp-notifications.html`, no cache headers.
- **No client-side auth or page check.** The shell renders only if a token exists; otherwise the page loads and the API returns 401, followed by refresh or a redirect to login.
- The sidebar item needs the `admin` permission.
- The server: `GET /api/whatsapp/notifications` is `login_required` only, so **any authenticated user** can read every message.
- The page does not load notification-utils; it has its own toast.

**2. Layout**
- A "Back" `.back-button` (hidden by the shell). Its logic:
  - `from`, else `lastPage`, else "admin".
  - admin goes to admin.html, home to home.html, invoiceSystem to invoiceSystem.html, the default to admin.html.
  - It writes `lastPage="whatsapp-notifications"`.
- Header "WhatsApp Notifications" / "Manage and track automated WhatsApp messages sent to clients".
- Stat cards: **Total Sent** `#total-sent`, **Delivered**, **Failed**, **Success Rate** (initially "--").
- Controls:
  - Search `#search-input` ("Search by customer name or phone...").
  - Status `#status-filter`: All Status(all), Sent, Delivered, Failed, Pending.
  - Type `#type-filter`: All Types(all), Invoice(invoice), Quote(quote), Payment Reminder(payment_reminder), Repair Status(repair_status).
- "Recent Notifications" with a **Refresh** button.
- A list, a loading spinner ("Loading notifications..."), and an empty state ("No notifications found / No WhatsApp notifications match your current filters.").
- Footer "© 2024".

**3–4. Data and filtering**
- On load and on Refresh: **GET /api/whatsapp/notifications** with **no params**, so the server returns page 1 with **50 per page**, newest first.
- The server supports `page`, `per_page`, `status`, `type` and `search` (an ILIKE across name, phone and message) and returns `pagination{page, per_page, total, pages, has_next, has_prev}`. **The UI uses none of these.**
- Filtering is client-side over only those 50 rows. It re-runs on every input event and on select change, with no debounce:
  - name: lowercase includes;
  - phone: plain includes;
  - message: lowercase includes;
  - status equals the selection, or "all";
  - type equals the selection, or "all".
- Each list item shows:
  - customer name and phone (escaped);
  - a status badge `status-<status>` with the status capitalised (the icons are empty strings);
  - Type, title-cased from snake_case;
  - Document: `<related_document_type||N/A> #<related_document_id||N/A>`;
  - Message ID (`whatsapp_message_id` or N/A);
  - the message text (escaped);
  - an optional "Error: …";
  - "Sent: <created_at toLocaleString>", plus "Delivered: <sent_at>". **The labels are swapped/mislabelled**: created_at is labelled Sent, and sent_at is labelled Delivered.

**5. Stats** come from the server (`calculate_notification_stats`, `whatsapp_routes.py:165-233`), over all rows:
- total_sent, total_delivered, total_failed and total_pending are counts by status.
- `success_rate = (sent+delivered)/(sent+delivered+failed)*100`, displayed with `toFixed(1)+"%"`.
- The server also returns `total_notifications`, `recent_notifications` (the last 7 days) and `type_breakdown`, which are not displayed.

**9. Detail modal**
- Clicking any item opens a dynamically created modal "Notification Details": Customer, Phone, Type (raw), Status (raw), Created, Sent (if set), Error (if set), and the message in a monospace pre-wrap block.
- It closes only via ×. The backdrop and Escape do nothing.
- It appends a new `<style>` element to head **on every open** (a leak).

**Error toast:** "Failed to load notifications. Please try again." Fixed top-right, removed after 5 s.

**Backend behaviour the page depends on:**
- Records are created **only** in `routes.py:273-322`, when an invoice or quote is created through `POST /api/add`.
  - `whatsapp_notifier.send_invoice_notification` runs, and a `WhatsAppNotification` is saved with `notification_type` 'invoice' or 'quote', `related_document_type='invoice'`, and status taken from the result.
  - **When Twilio env vars (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`) are missing, the message is only logged, and the record is saved with status `'simulated'`.** That status is counted by no stat and matched by no filter option.
  - On failure the status is `'failed'` with `error_message`.
  - A notification failure never fails the invoice.
- `payment_reminder` and `repair_status` messages exist in `whatsapp_notifications.py` (`send_payment_reminder`, `send_repair_status_update`) but are **never called**.
- Message templates: invoice ("Invoice Generated…Status: Pending Payment"), quote ("Quote Generated…Pending Approval"), payment reminder (with an "Overdue by N days" line), and repair status (received, in_progress, completed, ready). All use placeholder contact details "+92-XXX-XXXXXXX" and "info@germanato.com", and amounts are formatted as `{:,.2f} PKR`.
- Server phone formatting (`format_phone_number`):
  - Digits only.
  - 10 digits not starting with 92: prefix 92.
  - 11 digits starting with 0: replace the 0 with 92.
  - The result is `whatsapp:+<digits>`.
- Twilio is called with `POST https://api.twilio.com/2010-04-01/Accounts/<sid>/Messages.json` and form fields From, To, Body.

**11. Unused endpoints** (no UI):
- `GET /api/whatsapp/notifications/<id>`
- `POST /api/whatsapp/notifications/<id>/resend` (admin/accountant, failed only)
- `GET /api/whatsapp/stats`
- `POST /api/whatsapp/test` (admin; sends a test invoice notification to the dummy number "1234567890")

There is also a duplicate model file, `whatsapp_notification_model.py`; `models.WhatsAppNotification` is the one used.

---

## invoiceSystem.html: Bill Management - GermanATO (hub)

**1. Purpose, URL and access**
- URL `/invoiceSystem.html`, no cache headers.
- Client-side: `auth.requirePageAccess("invoice")`. There is no server-side check (static page).
- Not in the sidebar. It is reached via the finance hub or the back links of other pages.
- Assets use **root-relative-without-slash** paths (`static/css/theme.css`, `static/js/theme.js`, `static/js/auth_jwt.js`, the logo). These only resolve correctly because the page is served at the root.

**2–3. Six navigation cards** (all plain links):

| Card | Link | Subtitle |
|---|---|---|
| Create Invoice | invoice.html?from=invoiceSystem | "Bill a customer for work done, and deduct the parts used" |
| Create Quote | quote.html?from=invoiceSystem | "Price up work for approval — no stock is deducted" |
| Manage Quotes | pending-quotes.html?from=invoiceSystem | "View and manage pending customer quotes" |
| Manage Invoices | invoice-management.html?from=invoiceSystem | "View, edit, and track invoice status" |
| Manage Repair Orders | repair-orders-management.html?from=invoiceSystem | "View and manage all repair orders" |
| Create Repair Order | repair-order.html?from=invoiceSystem | "Create new repair orders for vehicles" |

- None of the cards is filtered by permission; the repair-order cards are shown even without `repair-order`.

**Back link** (hidden by the shell):
- `from`, else `lastPage`, else "home".
- home goes to home.html, admin to admin.html, finance-management to finance-management.html, anything else to home.html.
- It writes `localStorage.lastPage="invoiceSystem"`.

**Text:** header "Bill Management" / "Invoices, Quotes and Repair Orders"; page header "Manage invoices, quotes, and repair orders"; footer "© 2025".

---

## finance-management.html: Finance Management - GermanATO (hub, `financeManagement.js`)

**1. Purpose, URL and access**
- URL `/finance-management.html` with no-cache headers.
- Client-side: only `auth.requireAuth()`. Not in the sidebar.
- Each card has `data-permission` and is hidden (`display:none`) when `!auth.canAccessPage(perm)`. While permissions are not yet cached, every card is shown.

**2–3. Cards:**

| Card | Link | data-permission | Subtitle |
|---|---|---|---|
| Bill Management | invoiceSystem.html?from=finance-management | invoice | "Create and manage invoices, quotes, and track payment status" |
| Daily Expenses | daily-expenses.html?from=finance-management | daily-expenses | "Track and manage daily business expenses and transactions" |
| Major Expenses (`#major-expenses-card`) | major-expenses.html?from=finance-management | major-expenses | "Track and manage significant business expenses and capital expenditures" |

- Header: "Finance Management" / "Manage bills and track expenses". Page header: "Select a module to manage your finances". Footer "© 2025".

**Back button** (a click handler; hidden by the shell):
- from=home goes to home.html, from=admin to admin.html, otherwise home.html.
- There is a duplicate immediate-setup branch (`:53-75`) that is effectively unreachable, because the script runs while readyState is still "loading".

**11. Dead code:** `navigateToBillManagement()` (to `invoiceSystem.html?from=finance`) and `navigateToDailyExpenses()` are never called. The `from=finance` value is not recognised by the targets anyway.

There is no lastPage write.

---

## hr.html: GermanATO - HR Management (hub, `hrHub.js`)

**1. Purpose, URL and access**
- URL **`/hr`** (`hr_routes.py:22`). `/hr.html` is not routed.
- **No client-side auth or permission check at all.** hrHub.js only wires the back button to `/home.html`, which is hidden by the shell. The shell only appears if a token exists.
- Not in the sidebar, although its sub-pages are.
- `notification-utils.js` is included twice (in the head and at line 141).

**2–3. Cards:**

| Card | Link | Subtitle |
|---|---|---|
| Employees Management | /employees.html | "Manage worker information, roles, and details" |
| Attendance | /attendance.html | "Record and view check-in / check-out attendance" |
| Salaries Management | /salaries-management.html | "View worker salaries and print salary slips (based on attendance)" |
| Device Management | /hr/device-management | "Add ZKTeco devices (PUSH). Device sends attendance to this server." (the route docstring says "pull method", a terminology mismatch) |

- Header "HR Management" / "Manage worker information and roles". Page header "Select a module to manage your HR". Footer "© 2025".
- No cards are filtered by permission.

---

## Persisted state summary (this area)

**localStorage**

| Key | Writers | Readers |
|---|---|---|
| `accessToken` | auth.login, refreshAccessToken; cleared by clearAuth and by the home.html fallback logout | auth.init (and via getAccessToken: APIHelper, PerformanceUtils) |
| `refreshToken` | auth.login; cleared by clearAuth | auth.init / refresh |
| `user` (JSON {id,username,email,role}) | login, verify, refresh | auth.init, app-shell (name, role, initial), dashboard greet |
| `userPermissions` (JSON array) | auth.loadPermissions (on login, every page init, and after the admin permissions save) | canAccessPage, app-shell allowed() |
| `theme` (light / dark / auto) | settings.js handleThemeChange, app-shell theme button | theme.js, settings.js |
| `shellCollapsed` ("1"/"0") | app-shell collapse button | app-shell boot |
| `lastPage` | invoiceSystem ("invoiceSystem"), admin ("admin"), whatsapp ("whatsapp-notifications"); many other pages also write it | back-button logic on invoiceSystem, admin, whatsapp and others |
| `isAuthenticated` | login.js only (dead) | nobody |

- **sessionStorage:** none.
- **Cookies:** none set by the client. The server would accept JWTs from cookies but never issues them.

**URL params**

| Param | Read by / written by | Meaning |
|---|---|---|
| `from` | read by invoiceSystem, admin, whatsapp, finance | home, admin, invoiceSystem, finance-management |
| `?from=invoiceSystem` | written by the invoiceSystem cards | – |
| `?from=finance-management` | written by the finance cards | – |
| `new=1` | read by app-shell on any page | auto-open the create modal or focus the first form field |
| `id` | written by the dashboard invoice rows; ignored by the target | – |

---

## Keyboard, timers and polling summary

- **Cmd/Ctrl+K:** toggles the palette globally.
- **Inside the palette:** ↑ and ↓ move (with wrap), Enter opens, Esc closes.
- **home.html:** Esc closes the (dead) coming-soon modal.
- No barcode handling, polling or auto-refresh anywhere in this area.
- **Timers:**
  - toast lifetimes: 3, 4 and 5 s;
  - login error: auto-hide after 5 s;
  - admin.js auth retry: 100 ms;
  - APIHelper trigger lock window: 1 s;
  - PerformanceUtils retry backoff: 1 s then 2 s, cache TTL 5 min.
- **Autofocus:** the palette input; `?new=1` field focus.

---

### Endpoints used

| METHOD | Path | Page / action |
|---|---|---|
| POST | /api/auth/login | login.html submit (auth.login) |
| GET | /api/auth/verify | every page: auth.init token check |
| POST | /api/auth/refresh | auth.init when verify fails; APIHelper and PerformanceUtils on 401 |
| GET | /api/auth/permissions/my | after login; every page init; after admin saves permissions |
| POST | /api/auth/logout | sidebar Sign out; home.html hidden logout button |
| GET | /api/dashboard | home.html load and Refresh |
| GET | /api/auth/users | admin.html Users tab load |
| POST | /api/auth/register | admin.html Add user |
| PUT | /api/auth/users/:id | admin.html Edit user |
| DELETE | /api/auth/users/:id | admin.html Delete user |
| GET | /api/auth/roles-permissions | admin.html Roles & Permissions tab |
| PUT | /api/auth/roles-permissions | admin.html Save Permissions |
| GET | /api/admin/app-logs?page&per_page=50&username&module&action&start_date&end_date&keyword | admin.html Logs tab, Apply, Reset, pagination |
| GET | /api/settings/departments?include_inactive=true | settings.html departments list (the param is ignored by the server) |
| GET | /api/settings/departments | settings.html edit-department prefill |
| POST | /api/settings/departments | settings.html add department |
| PUT | /api/settings/departments/:id | settings.html edit department |
| DELETE | /api/settings/departments/:id | settings.html delete department |
| GET | /api/workers | settings.html worker counts per department |
| GET | /api/settings/categories?include_inactive=true | settings.html categories list |
| GET | /api/settings/categories | settings.html edit-category prefill |
| POST | /api/settings/categories | settings.html add category |
| PUT | /api/settings/categories/:id | settings.html edit category |
| DELETE | /api/settings/categories/:id | settings.html delete category |
| GET | /api/inventory?per_page=1000 | settings.html item counts per category (the server caps it at 200) |
| GET | /api/whatsapp/notifications | whatsapp-notifications.html load and Refresh |
| GET | /api/auth/check-auth | login.js only (dead). **The endpoint does not exist** |
| GET | /api/customers, /api/cars, /api/inventory | PerformanceUtils.loadInitialData (dead code) |

Backend endpoints in this area with **no UI caller**:
- GET /api/whatsapp/notifications/:id
- POST /api/whatsapp/notifications/:id/resend
- GET /api/whatsapp/stats
- POST /api/whatsapp/test
- the `is_active` field of PUT /api/auth/users/:id
- the `is_active` field of the department and category PUT routes

### Files read

All of these were read in full unless noted otherwise:

| File | Lines | Notes |
|---|---|---|
| frontend/login.html | 109 | |
| frontend/home.html | 164 | |
| frontend/admin.html | 325 | |
| frontend/settings.html | 232 | |
| frontend/whatsapp-notifications.html | 151 | |
| frontend/invoiceSystem.html | 222 | |
| frontend/finance-management.html | 125 | |
| frontend/hr.html | 146 | |
| static/js/auth_jwt.js | 315 | |
| static/js/auth_jwt.test.js | 108 | |
| static/js/login_jwt.js | 65 | |
| static/js/login.js | 101 | confirmed unused |
| static/js/app-shell.js | 459 | |
| static/js/api-helper.js | 578 | |
| static/js/theme.js | 52 | |
| static/js/notification-utils.js | 132 | |
| static/js/performance-utils.js | 348 | |
| static/js/phone-formatter.js | 167 | |
| static/js/script.js | 16 | dead |
| static/js/dashboard.js | 255 | |
| static/js/admin.js | 425 | |
| static/js/settings.js | 660 | |
| static/js/whatsapp-notifications.js | 423 | |
| static/js/financeManagement.js | 75 | |
| static/js/hrHub.js | 11 | |
| static/css/app-shell.css | 630 | |
| static/css/theme.css | 1189 | behaviour pass only: all token blocks, every section header, and lines 42-66, 356-362, 996-1012 and 1042-1189 read; grep for `@media`, print, display and hover returned no media or print rules |
| app.py | 371 | |
| jwt_auth.py | 231 | |
| auth_routes_jwt.py | 396 | |
| reports_routes.py | 671 | 1-30, 128-310 and 369-671 read; the `/api/reports` body (31-127) and the growth helpers (309-368) were skipped as out of scope |
| settings_routes.py | 248 | |
| whatsapp_routes.py | 266 | |
| whatsapp_notifications.py | 288 | |
| routes.py | 992 | partial: imports 1-28, WhatsApp hook 260-330, `/api/admin/app-logs` 938-992 |

Spot-checked to verify cross-references:
- config.py: JWT settings
- models.py: RolePermission, AppLog.to_dict, WhatsAppNotification, Department.to_dict
- log_utils.py: log_action
- hr_routes.py: lines 18-42
- vendor_routes.py: lines 15-28
- inventory_routes.py: per_page cap
- static/js/invoiceManagement.js: lines 1-30
- static/js/inventory.js and monthlyLedger.js: PerformanceUtils usage
