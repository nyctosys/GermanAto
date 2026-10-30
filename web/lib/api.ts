"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "@/lib/toast";

export class ApiError extends Error {
  /** `detail` keeps structured errors, e.g. {code: "duplicate_phone", matches: [...]}. */
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message);
  }
}

/** FastAPI errors are {detail: string} or, for validation, {detail: [{loc, msg}]}. */
function messageOf(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: (string | number)[]; msg?: string }) => {
        const field = d.loc?.filter((p) => p !== "body").join(".");
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join("\n");
  }
  return `Request failed (${status})`;
}

/**
 * One Idempotency-Key per thing the person does. The same request sent again while it is still unanswered
 * (a double click) or after the connection dropped (a retry) reuses its key, so the server does it once and
 * replays the answer. Once the server has answered, the key is dropped: sending the same payment again later
 * is a new payment. Keyed by method, address and body, so changing anything makes a new key.
 */
const pending = new Map<string, string>();
const keyFor = (fingerprint: string) => {
  let key = pending.get(fingerprint);
  if (!key) pending.set(fingerprint, (key = crypto.randomUUID()));
  return key;
};

// What to tell the person after a successful write, by what was done. First match wins; the fallback is by method.
const DONE: [RegExp, string][] = [
  [/\/payroll-runs\/[^/]+\/void$/, "Draft thrown away"],
  [/\/payments$/, "Payment recorded"], [/\/advances$/, "Advance recorded"], [/\/refund$|\/refunds?$/, "Refund recorded"],
  [/\/credit-notes$/, "Credit note issued"], [/\/invoices\/[^/]+\/issue$/, "Invoice issued"], [/\/lines\/[^/]+\/(issue|return)$/, "Stock updated"], [/\/gate-pass$/, "Car released"], [/\/purchase-orders\/[^/]+\/send$/, "Sent to the vendor"], [/\/quotations\/[^/]+\/send$/, "Sent to the customer"],
  [/\/approve$/, "Approval recorded"], [/\/reject$/, "Marked as rejected"], [/\/revise$/, "New version made"], [/\/sign$/, "Signed"],
  [/\/void$/, "Cancelled (voided). It stays on the list, crossed out."], [/\/cancel$/, "Cancelled"], [/\/status$/, "Status updated"],
  [/\/receive$/, "Goods received"], [/\/bill$/, "Bill recorded"], [/\/close$/, "Closed"], [/\/reopen$/, "Reopened"],
  [/^\/api\/visits$/, "Car checked in"], [/^\/api\/customers$/, "Customer saved"], [/^\/api\/cars$/, "Car saved"],
  [/^\/api\/counter-sales/, "Counter sale saved"], [/\/repair-order$/, "Repair order made"], [/\/quotation$/, "Quotation made"],
  [/\/invoice$/, "Invoice made"], [/\/job-card$/, "Job card started"], [/^\/api\/attachments$/, "File uploaded"],
  [/\/activity$/, "Note added"], [/^\/api\/money-entries$|^\/api\/cash-closes$/, "Recorded"],
];
// Quiet by design: sign-in, autosave while typing, and calls whose screen already says what happened.
const NO_TOAST = /^\/api\/(auth\/|inspections\/[^/]+$|messages\/(send|run-reminders)|sync\/run)/;
const doneMessage = (method: string, path: string) =>
  DONE.find(([re]) => re.test(path.split("?")[0]))?.[1] ?? (method === "DELETE" ? "Removed" : method === "POST" ? "Done" : "Saved");

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown; toast?: string | false } = {}): Promise<T> {
  const { json, headers, toast: say, ...rest } = init;
  const method = (rest.method ?? "GET").toUpperCase();
  const payload = json !== undefined ? JSON.stringify(json) : rest.body;
  // Only JSON writes: a file upload has no body we can compare, and sign-in must always be a fresh attempt.
  const fingerprint = method !== "GET" && json !== undefined && !path.startsWith("/api/auth/") ? `${method} ${path} ${payload}` : null;
  let res: Response;
  try {
    res = await fetch(path, {
    ...rest,
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(fingerprint ? { "Idempotency-Key": keyFor(fingerprint) } : {}),
      ...headers,
    },
    body: payload,
    credentials: "same-origin",
    });
  } catch (e) {
    if (method !== "GET") toast.error("Could not reach the server. Nothing was changed; check the connection and try again.");
    throw e;
  }
  if (fingerprint) pending.delete(fingerprint);  // answered (success or error): the next identical request is a new action
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/api/auth/login")) {
    // A full reload (not router.push) drops every piece of the expired user's state.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
  }
  if (!res.ok) {
    if (res.status >= 500 && method !== "GET") toast.error("Something went wrong on the server. Nothing was changed. Try again, or tell your administrator if it keeps happening.");
    throw new ApiError(res.status, messageOf(body, res.status), (body as { detail?: unknown })?.detail);
  }
  if (method !== "GET" && say !== false && !NO_TOAST.test(path.split("?")[0])) toast.success(say ?? doneMessage(method, path));
  return body as T;
}

const cache = new Map<string, unknown>();

/**
 * Load a GET endpoint; `reload()` refetches after a change.
 * With `swr` the last answer for this address is shown at once while a fresh one is fetched, and it is
 * fetched again when the window regains focus or the network comes back. Only for lists where a few
 * seconds of age costs nothing: never for balances, stock counts or anything that moves money.
 */
export function useApi<T>(path: string | null, opts: { swr?: boolean } = {}) {
  const swr = !!opts.swr;
  const [state, setState] = useState<{ path: string | null; data: T | null }>({ path: null, data: null });
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!path) return;
    let live = true;
    api<T>(path)
      .then((d) => {
        if (!live) return;
        if (swr) cache.set(path, d);
        setState({ path, data: d });
        setError(null);
      })
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [path, tick, swr]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  useEffect(() => {
    if (!swr) return;
    const again = () => document.visibilityState !== "hidden" && reload();
    window.addEventListener("focus", again);
    window.addEventListener("online", again);
    document.addEventListener("visibilitychange", again);
    return () => {
      window.removeEventListener("focus", again);
      window.removeEventListener("online", again);
      document.removeEventListener("visibilitychange", again);
    };
  }, [swr, reload]);

  // A different address shows its own cached answer when there is one, otherwise keeps what was on screen.
  const cached = swr && path && state.path !== path ? (cache.get(path) as T | undefined) : undefined;
  const data = cached ?? state.data;
  return { data, error, loading: data === null && error === null, reload };
}
