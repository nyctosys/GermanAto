"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

/** Read and write one query-string value, so a search or filter survives reload and can be shared. */
export function useQueryParam(name: string): [string, (value: string) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const value = params.get(name) ?? "";
  const set = (next: string) => {
    const p = new URLSearchParams(params);
    if (next) p.set(name, next);
    else p.delete(name);
    const qs = p.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };
  return [value, set];
}

/** A search box that updates the URL 250ms after typing stops. */
export function SearchBox({ placeholder, label = "Search", autoFocus }: { placeholder: string; label?: string; autoFocus?: boolean }) {
  const [q, setQ] = useQueryParam("q");
  const [text, setText] = useState(q);
  useEffect(() => {
    if (text === q) return;
    const t = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(t);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <label className="block min-w-0 flex-1">
      <span className="sr-only">{label}</span>
      <input
        type="search"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        autoFocus={autoFocus}
        enterKeyHint="search"
        className="min-h-11 w-full rounded-control border border-rule-strong bg-surface px-3 text-base placeholder:text-muted hover:border-muted focus-visible:border-ink"
      />
    </label>
  );
}

/** Segmented filter pills, each one a 44px target. */
export function Segments({ value, onChange, options }:
  { value: string; onChange: (v: string) => void; options: { value: string; label: ReactNode }[] }) {
  return (
    <div role="radiogroup" className="inline-flex max-w-full flex-wrap rounded-control border border-rule-strong bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={`min-h-11 rounded-[3px] px-3.5 text-sm font-medium transition-colors duration-(--dur-micro) active:duration-0 ${
            value === o.value ? "bg-ink text-surface" : "text-ink-2 hover:bg-paper"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
