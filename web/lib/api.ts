"use client";

import { useCallback, useEffect, useState } from "react";

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

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const method = (rest.method ?? "GET").toUpperCase();
  const payload = json !== undefined ? JSON.stringify(json) : rest.body;
  // Only JSON writes: a file upload has no body we can compare, and sign-in must always be a fresh attempt.
  const fingerprint = method !== "GET" && json !== undefined && !path.startsWith("/api/auth/") ? `${method} ${path} ${payload}` : null;
  const res = await fetch(path, {
    ...rest,
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(fingerprint ? { "Idempotency-Key": keyFor(fingerprint) } : {}),
      ...headers,
    },
    body: payload,
    credentials: "same-origin",
  });
  if (fingerprint) pending.delete(fingerprint);  // answered (success or error): the next identical request is a new action
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/api/auth/login")) {
    // A full reload (not router.push) drops every piece of the expired user's state.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
  }
  if (!res.ok) throw new ApiError(res.status, messageOf(body, res.status), (body as { detail?: unknown })?.detail);
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
