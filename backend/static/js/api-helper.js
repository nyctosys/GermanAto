// JWT-based API Helper
class APIHelper {
  static ensureErrorStyles() {
    if (typeof document === "undefined" || !document.head) return;
    if (document.getElementById("api-error-state-styles")) return;

    const style = document.createElement("style");
    style.id = "api-error-state-styles";
    style.textContent = `
      .api-error-state {
        position: sticky;
        top: 0;
        z-index: 10000;
        margin: 0;
        padding: 12px 16px;
        background: #fff4f2;
        color: #7a1f16;
        border-bottom: 1px solid #f1b3aa;
        box-shadow: 0 2px 10px rgba(122, 31, 22, 0.12);
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }

      .api-error-state__inner {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        max-width: 1180px;
        margin: 0 auto;
      }

      .api-error-state__title {
        margin: 0 0 2px;
        font-size: 14px;
        font-weight: 700;
      }

      .api-error-state__message {
        margin: 0;
        font-size: 13px;
        line-height: 1.4;
        word-break: break-word;
      }

      .api-error-state__actions {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
      }

      .api-error-state button {
        border: 1px solid #d76455;
        border-radius: 6px;
        background: #ffffff;
        color: #7a1f16;
        cursor: pointer;
        font: inherit;
        font-size: 13px;
        padding: 7px 10px;
      }

      .api-error-state__close {
        width: 32px;
        padding-left: 0;
        padding-right: 0;
      }

      @media (max-width: 640px) {
        .api-error-state__inner {
          align-items: stretch;
          flex-direction: column;
        }

        .api-error-state__actions {
          justify-content: flex-end;
        }
      }

      .api-inline-state {
        grid-column: 1 / -1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
        padding: 36px 20px;
        text-align: center;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }

      .api-inline-state__title {
        margin: 0;
        font-size: 15px;
        font-weight: 600;
        color: #7a1f16;
      }

      .api-inline-state__message {
        margin: 0;
        max-width: 46ch;
        font-size: 13px;
        line-height: 1.5;
        color: #6b7280;
        white-space: pre-wrap;
        word-break: break-word;
      }

      .api-inline-state__retry {
        margin-top: 2px;
        padding: 8px 16px;
        border: 1px solid #d76455;
        border-radius: 6px;
        background: #ffffff;
        color: #7a1f16;
        cursor: pointer;
        font: inherit;
        font-size: 13px;
      }

      .api-inline-state__retry:hover {
        background: #fff4f2;
      }

      .api-suggest {
        border: 0;
        background: none;
        padding: 0;
        margin: 0 2px;
        font: inherit;
        font-weight: 600;
        color: #8b1538;
        cursor: pointer;
        text-decoration: underline;
        text-underline-offset: 2px;
      }

      .api-suggest:hover {
        color: #6d1029;
      }

      body.dark-theme .api-suggest {
        color: #e0819c;
      }

      .api-inline-state--loading .api-inline-state__message {
        color: #6b7280;
      }

      .api-inline-state__spinner {
        width: 26px;
        height: 26px;
        border: 3px solid rgba(139, 21, 56, 0.18);
        border-top-color: #8b1538;
        border-radius: 50%;
        animation: api-inline-spin 0.8s linear infinite;
      }

      @keyframes api-inline-spin {
        to {
          transform: rotate(360deg);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .api-inline-state__spinner {
          animation-duration: 2.4s;
        }
      }

      body.dark-theme .api-inline-state__title {
        color: #ff9d8e;
      }

      body.dark-theme .api-inline-state__message {
        color: #9aa4b2;
      }

      body.dark-theme .api-inline-state__retry {
        background: transparent;
        color: #ff9d8e;
      }
    `;
    document.head.appendChild(style);
  }

  static showErrorState(error, url) {
    if (typeof document === "undefined" || !document.body) return;

    this.ensureErrorStyles();

    let banner = document.getElementById("api-error-state");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "api-error-state";
      banner.className = "api-error-state";
      banner.setAttribute("role", "alert");
      document.body.prepend(banner);
    }

    const message = error?.message || "The server did not respond. Please try again.";
    const shortUrl = String(url || "request").replace(window.location.origin, "");

    banner.innerHTML = `
      <div class="api-error-state__inner">
        <div>
          <p class="api-error-state__title">Could not load this data</p>
          <p class="api-error-state__message">${this.escapeHtml(shortUrl)}: ${this.escapeHtml(message)}</p>
        </div>
        <div class="api-error-state__actions">
          <button type="button" data-api-error-reload>Reload</button>
          <button type="button" class="api-error-state__close" data-api-error-close aria-label="Dismiss error">x</button>
        </div>
      </div>
    `;

    banner.querySelector("[data-api-error-reload]").addEventListener("click", () => {
      window.location.reload();
    });
    banner.querySelector("[data-api-error-close]").addEventListener("click", () => {
      banner.remove();
    });
  }

  static clearErrorState() {
    const banner = typeof document !== "undefined" && document.getElementById("api-error-state");
    if (banner) banner.remove();
  }

  static resolveElement(target) {
    if (typeof document === "undefined") return null;
    if (typeof target === "string") return document.getElementById(target);
    return target || null;
  }

  // A <tbody> state has to live in a cell that spans the whole table.
  static wrapForContainer(el, html) {
    if (el.tagName !== "TBODY") return html;

    const headRow = el.closest("table") &&
      el.closest("table").querySelector("thead tr");
    const columns = headRow ? headRow.children.length : 1;
    return `<tr><td colspan="${columns}" style="padding:0">${html}</td></tr>`;
  }

  /**
   * Loading placeholder for a table body or container.
   * Replaces the unstyled Bootstrap spinner markup the pages used to inline.
   */
  static renderLoading(target, message = "Loading...") {
    const el = this.resolveElement(target);
    if (!el) return;

    this.ensureErrorStyles();
    el.innerHTML = this.wrapForContainer(
      el,
      `<div class="api-inline-state api-inline-state--loading">
        <div class="api-inline-state__spinner"></div>
        <p class="api-inline-state__message">${this.escapeHtml(message)}</p>
      </div>`
    );
  }

  /**
   * Error state for a table body or container. Without this a failed load left
   * the loading spinner running forever and the page looked hung.
   */
  static renderError(target, error, onRetry) {
    const el = this.resolveElement(target);
    if (!el) return;

    this.ensureErrorStyles();

    const status = error && error.status;
    const title =
      status === 403
        ? "You do not have access to this data"
        : status === 404
        ? "Not found"
        : "Could not load this data";
    const message =
      (error && error.message) ||
      String(error || "") ||
      "The server did not respond. Please try again.";

    el.innerHTML = this.wrapForContainer(
      el,
      `<div class="api-inline-state">
        <p class="api-inline-state__title">${this.escapeHtml(title)}</p>
        <p class="api-inline-state__message">${this.escapeHtml(message)}</p>
        ${
          onRetry && status !== 403
            ? `<button type="button" class="api-inline-state__retry">Try again</button>`
            : ""
        }
      </div>`
    );

    const retry = el.querySelector(".api-inline-state__retry");
    if (retry) retry.addEventListener("click", () => onRetry());
  }

  /**
   * Empty state with "did you mean" suggestions.
   *
   * `data` is a search response carrying `did_you_mean` and/or `closest`.
   * `onPick` receives the term the user chose so the caller can re-run its own
   * search - this helper does not know how any particular page searches.
   */
  static renderNoMatches(target, query, data, onPick) {
    const el = this.resolveElement(target);
    if (!el) return;

    this.ensureErrorStyles();
    const suggestion = data && data.did_you_mean;
    const closest = (data && data.closest) || [];

    const parts = [
      `<p class="api-inline-state__message">No matches for &ldquo;${this.escapeHtml(query)}&rdquo;</p>`,
    ];

    if (suggestion) {
      parts.push(
        `<p class="api-inline-state__message">Did you mean ` +
          `<button type="button" class="api-suggest" data-term="${this.escapeHtml(suggestion)}">` +
          `${this.escapeHtml(suggestion)}</button>?</p>`
      );
    }

    if (closest.length) {
      parts.push(
        `<p class="api-inline-state__message">Closest on file:</p>` +
          `<p class="api-inline-state__message">` +
          closest
            .map(
              (c) =>
                `<button type="button" class="api-suggest" data-term="${this.escapeHtml(c)}">` +
                `${this.escapeHtml(c)}</button>`
            )
            .join(" · ") +
          `</p>`
      );
    }

    el.innerHTML = this.wrapForContainer(
      el,
      `<div class="api-inline-state">${parts.join("")}</div>`
    );

    if (typeof onPick === "function") {
      el.querySelectorAll(".api-suggest").forEach((b) =>
        b.addEventListener("click", () => onPick(b.dataset.term))
      );
    }
  }

  /** Empty state, so "no rows" never looks like a failed load. */
  static renderEmpty(target, message = "No records found") {
    const el = this.resolveElement(target);
    if (!el) return;

    this.ensureErrorStyles();
    el.innerHTML = this.wrapForContainer(
      el,
      `<div class="api-inline-state">
        <p class="api-inline-state__message">${this.escapeHtml(message)}</p>
      </div>`
    );
  }

  static escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  /**
   * Key for in-flight de-duplication. An impatient double-click used to fire
   * two identical POSTs; both passed the server's "already exists?" check
   * before either committed, so two records were created.
   */
  static requestKey(url, options) {
    const body = options.body;
    // Only JSON/string bodies can be compared. A FormData stringifies to
    // "[object FormData]", so two different uploads to the same URL would look
    // identical and the second would be silently dropped - which for a payment
    // means a lost payment. Anything not comparable is never de-duplicated.
    if (body != null && typeof body !== "string") return null;
    return `${(options.method || "GET").toUpperCase()} ${url} ${body || ""}`;
  }

  /**
   * Disable the button that started this request until it settles, so the user
   * gets feedback instead of clicking again. Tracked via a capture-phase click
   * listener because clicking a button does not focus it in every browser.
   */
  static lockTrigger() {
    const btn = this._lastButton;
    const fresh = btn && Date.now() - this._lastButtonAt < 1000;
    if (!fresh || btn.disabled) return () => {};

    btn.disabled = true;
    btn.setAttribute("aria-busy", "true");
    return () => {
      btn.disabled = false;
      btn.removeAttribute("aria-busy");
    };
  }

  static async request(url, options = {}) {
    const key = this.requestKey(url, options);
    const pending = key && this._inflight.get(key);
    if (pending) return pending;

    const unlock = (options.method || "GET").toUpperCase() === "GET"
      ? () => {}
      : this.lockTrigger();

    const call = this.performRequest(url, options).finally(() => {
      if (key) this._inflight.delete(key);
      unlock();
    });

    if (key) this._inflight.set(key, call);
    return call;
  }

  static async performRequest(url, options = {}) {
    const defaultOptions = {
      headers: {
        ...options.headers,
      },
    };

    // Only set Content-Type for JSON requests, not for FormData
    if (!(options.body instanceof FormData)) {
      defaultOptions.headers["Content-Type"] = "application/json";
    }

    try {
      // Add authorization header if we have a token
      if (window.auth && auth.getAccessToken()) {
        defaultOptions.headers[
          "Authorization"
        ] = `Bearer ${auth.getAccessToken()}`;
      }

      const response = await fetch(url, { ...defaultOptions, ...options });

      // Handle 401 responses (token expired)
      if (response.status === 401) {
        // Try to refresh the token
        const refreshSuccess = await auth.refreshAccessToken();

        if (refreshSuccess) {
          // Retry the original request with new token
          defaultOptions.headers[
            "Authorization"
          ] = `Bearer ${auth.getAccessToken()}`;
          const retryResponse = await fetch(url, {
            ...defaultOptions,
            ...options,
          });
          if (!retryResponse.ok) {
            throw await this.responseError(retryResponse);
          }
          const data = await retryResponse.json();
          this.clearErrorState();
          return data;
        } else {
          // Refresh failed, redirect to login
          auth.clearAuth();
          window.location.href = "login.html";
          return null;
        }
      }

      // Check if response is ok
      if (!response.ok) {
        throw await this.responseError(response);
      }

      // Parse and return JSON response
      const data = await response.json();
      this.clearErrorState();
      if ((options.method || "GET").toUpperCase() !== "GET") {
        window.dispatchEvent(new CustomEvent("api:saved"));
      }
      return data;
    } catch (error) {
      if (this._unloading) throw error;
      console.error("API request failed:", error);
      if (!options.silent) {
        this.showErrorState(error, url);
      }
      throw error;
    }
  }

  static async responseError(response) {
    const errorData = await response
      .json()
      .catch(() => ({ error: "Unknown error" }));

    let errorMessage = errorData.error || `HTTP ${response.status}: ${response.statusText}`;
    if (errorData.details && Array.isArray(errorData.details) && errorData.details.length > 0) {
      errorMessage += "\n\nDetails:\n" + errorData.details.join("\n");
    }

    const error = new Error(errorMessage);
    error.status = response.status;
    return error;
  }

  static async get(url) {
    return this.request(url, { method: "GET" });
  }

  static async post(url, data) {
    return this.request(url, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  static async put(url, data) {
    return this.request(url, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  static async delete(url) {
    return this.request(url, { method: "DELETE" });
  }

  static async patch(url, data) {
    return this.request(url, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }
}

APIHelper._inflight = new Map();
APIHelper._lastButton = null;
APIHelper._lastButtonAt = 0;
APIHelper._unloading = false;

if (typeof window !== "undefined") {
  // Navigating away aborts in-flight requests, which surface as
  // "TypeError: Failed to fetch". That is the page closing, not a real
  // failure, so it must not raise an alarm on the way out.
  window.addEventListener("pagehide", () => {
    APIHelper._unloading = true;
  });
  window.addEventListener("beforeunload", () => {
    APIHelper._unloading = true;
  });
}

if (typeof document !== "undefined") {
  document.addEventListener(
    "click",
    (e) => {
      const btn = e.target.closest("button, input[type=submit]");
      if (!btn) return;
      APIHelper._lastButton = btn;
      APIHelper._lastButtonAt = Date.now();
    },
    true
  );
}

// Export for use in other scripts
window.APIHelper = APIHelper;
