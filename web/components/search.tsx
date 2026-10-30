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
  return <SearchInput value={text} onChange={setText} placeholder={placeholder} label={label} autoFocus={autoFocus} />;
}

/** The one look for every search box: a magnifier, a firm border, a clear button, and a Search button that does it now. */
export function SearchInput({ value, onChange, placeholder, label = "Search", autoFocus, onSearch }:
  { value: string; onChange: (v: string) => void; placeholder: string; label?: string; autoFocus?: boolean; onSearch?: () => void }) {
  return (
    <form role="search" className="flex min-w-[min(100%,18rem)] flex-1 gap-2" onSubmit={(e) => { e.preventDefault(); onSearch?.(); }}>
      <label className="relative block min-w-0 flex-1">
        <span className="sr-only">{label}</span>
        <svg className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-2" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
          <circle cx="11" cy="11" r="6.5" /><path d="M16 16l4.5 4.5" />
        </svg>
        <input
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoFocus={autoFocus}
          enterKeyHint="search"
          className="min-h-11 w-full cursor-text rounded-control border-2 border-ink-2 bg-surface pl-10 pr-10 text-base placeholder:text-muted hover:border-ink focus-visible:border-ink [&::-webkit-search-cancel-button]:hidden"
        />
        {value && (
          <button type="button" aria-label="Clear the search" onClick={() => onChange("")}
                  className="absolute right-1 top-1/2 flex size-9 -translate-y-1/2 cursor-pointer items-center justify-center rounded-control text-xl leading-none text-ink-2 hover:bg-paper-3">×</button>
        )}
      </label>
      <button type="submit" className="min-h-11 shrink-0 cursor-pointer rounded-control border border-action bg-action px-4 text-[0.9375rem] font-medium text-action-ink transition-colors duration-(--dur-micro) hover:border-action-2 hover:bg-action-2 active:border-action-3 active:bg-action-3 active:duration-0">Search</button>
    </form>
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
