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

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  const res = await fetch(path, {
    ...rest,
    headers: json !== undefined ? { "Content-Type": "application/json", ...headers } : headers,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
    credentials: "same-origin",
  });
  const body = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/api/auth/login")) {
    // A full reload (not router.push) drops every piece of the expired user's state.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
  }
  if (!res.ok) throw new ApiError(res.status, messageOf(body, res.status), (body as { detail?: unknown })?.detail);
  return body as T;
}

/** Load a GET endpoint; `reload()` refetches after a change. */
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!path) return;
    let live = true;
    api<T>(path)
      .then((d) => live && (setData(d), setError(null)))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [path, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading: data === null && error === null, reload };
}
