"use client";

import { useEffect, useId, useState } from "react";
import { Badge } from "@/components/ui";
import { api } from "@/lib/api";
import { money, qty } from "@/lib/format";

// --- types mirroring app/routers/estimates.py ----------------------------------------------
export type Pick = { kind: "labour" | "part"; id: string; code: string; name: string; category?: string; unit?: string;
  sale_price?: string; on_hand?: string };
type LineRef = {
  id: string; kind: "labour" | "part"; labour_code_id: string | null; item_id: string | null; qty: string;
  labour_code?: { code: string; name: string };
  item?: { number: string; name: string; unit: string; sale_price: string; on_hand: string; short: string };
};
export type JobLine = LineRef & { note: string; proposed_price?: string | null };
export type QuoteLine = LineRef & { description: string; unit_price: string; amount: string; declined: boolean };
export type QuoteStatus = "draft" | "sent" | "approved" | "rejected" | "expired" | "revised" | "converted";

export const QUOTE_STATUS: Record<QuoteStatus, { label: string; tone: "neutral" | "success" | "warning" | "error" | "accent" }> = {
  draft: { label: "Draft", tone: "warning" },
  sent: { label: "Sent, waiting for the customer", tone: "accent" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Rejected", tone: "error" },
  expired: { label: "Expired", tone: "neutral" },
  revised: { label: "Replaced by a revision", tone: "neutral" },
  converted: { label: "Repair order made", tone: "success" },
};

export const QuoteBadge = ({ status }: { status: QuoteStatus }) => <Badge tone={QUOTE_STATUS[status].tone}>{QUOTE_STATUS[status].label}</Badge>;

/** The link-styled button used for "go to the next document" actions. */
export const linkButton = "flex min-h-11 items-center rounded-control border border-rule-strong bg-surface px-4 font-medium hover:bg-paper-2 active:bg-paper-3 active:duration-0";

export const lineName = (l: LineRef) => (l.labour_code ? l.labour_code.name : l.item!.name);
export const lineCode = (l: LineRef) => (l.labour_code ? l.labour_code.code : l.item!.number);

/**
 * Add work to a job card or quotation: labour codes and stock items only, never
 * free text. Type to search, or scan a barcode (the scanner types it and Enter).
 */
export function CatalogPicker({ onPick }: { onPick: (p: Pick) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Pick[]>([]);
  const [active, setActive] = useState(0);
  const [open, setOpen] = useState(false);
  const listId = useId();

  useEffect(() => {
    if (!q.trim()) return;
    const t = setTimeout(() => {
      api<Pick[]>(`/api/estimate-catalog?${new URLSearchParams({ q: q.trim() })}`)
        .then((r) => { setResults(r); setActive(0); setOpen(true); })
        .catch(() => setResults([]));
    }, 180);
    return () => clearTimeout(t);
  }, [q]);

  const pick = (p: Pick) => { onPick(p); setQ(""); setOpen(false); };
  return (
    <div className="relative">
      <input
        role="combobox" aria-expanded={open} aria-controls={listId} aria-autocomplete="list" aria-label="Add labour or a part"
        value={q}
        onChange={(e) => { setQ(e.target.value); if (!e.target.value.trim()) setOpen(false); }}
        onKeyDown={(e) => {
          if (!open || !results.length) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => (a + 1) % results.length); }
          if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => (a - 1 + results.length) % results.length); }
          if (e.key === "Enter") { e.preventDefault(); pick(results[active]); }
          if (e.key === "Escape") setOpen(false);
        }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Add labour or a part: name, code, or scan a barcode"
        enterKeyHint="search"
        className="min-h-11 w-full rounded-control border border-rule-strong bg-surface px-3 text-base placeholder:text-muted focus-visible:border-ink"
      />
      {open && (
        <ul id={listId} role="listbox" className="absolute z-20 mt-1 max-h-80 w-full overflow-auto rounded-control border border-rule-strong bg-surface py-1">
          {results.length ? results.map((p, i) => (
            <li key={p.id} role="option" aria-selected={i === active} onMouseDown={(e) => { e.preventDefault(); pick(p); }}
                className={`flex min-h-11 cursor-pointer items-center justify-between gap-3 px-3 py-1.5 ${i === active ? "bg-accent-soft" : ""}`}>
              <span className="min-w-0">
                <span className="block font-medium">{p.name}</span>
                <span className="flex gap-3 text-sm text-muted">
                  <span>{p.kind === "labour" ? "Labour" : "Part"}</span><span>{p.code}</span>
                </span>
              </span>
              {p.kind === "part" && (
                <span className="num shrink-0 text-right text-sm text-muted">
                  <span className="block">{money(p.sale_price)}</span>
                  <span className={`block ${Number(p.on_hand) > 0 ? "" : "text-error"}`}>{Number(p.on_hand) > 0 ? `${qty(p.on_hand!)} ${p.unit} in stock` : "Out of stock"}</span>
                </span>
              )}
            </li>
          )) : <li className="px-3 py-3 text-muted">Nothing matches “{q}”. Add it under Labour codes or Inventory first.</li>}
        </ul>
      )}
    </div>
  );
}
