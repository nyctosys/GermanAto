"use client";

import Link from "next/link";
import { type ReactNode } from "react";
import { money } from "@/lib/format";

const ACCOUNT: Record<string, string> = { cash: "Cash", bank: "Bank", wallet: "Wallet" };
const MIX = ["#F98B00", "#C4A574", "#8E8E8E"] as const;

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

/** Catmull–Rom → cubic Bézier. */
function smoothPath(coords: readonly (readonly [number, number])[]): string {
  if (coords.length < 2) return "";
  let d = `M${coords[0][0].toFixed(1)},${coords[0][1].toFixed(1)}`;
  for (let i = 0; i < coords.length - 1; i++) {
    const p0 = coords[i - 1] ?? coords[i];
    const p1 = coords[i];
    const p2 = coords[i + 1];
    const p3 = coords[i + 2] ?? p2;
    d += ` C${(p1[0] + (p2[0] - p0[0]) / 6).toFixed(1)},${(p1[1] + (p2[1] - p0[1]) / 6).toFixed(1)} ${(p2[0] - (p3[0] - p1[0]) / 6).toFixed(1)},${(p2[1] - (p3[1] - p1[1]) / 6).toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
}

function series(level: number, shape: "rise" | "wave" | "pulse") {
  const base = clamp(level, 0.12, 1);
  if (shape === "rise") return [0.35, 0.42, 0.48, 0.55, 0.68, 0.82, 1].map((h) => base * h);
  if (shape === "pulse") return [0.45, 0.7, 0.4, 0.85, 0.55, 0.95, 0.65].map((h) => base * h);
  return [0.55, 0.48, 0.72, 0.6, 0.88, 0.7, 1].map((h) => base * h);
}

/** Smooth area graph. */
function AreaChart({ value, max, color }: { value: number; max: number; color: string }) {
  const level = Math.max(Math.abs(value) / Math.max(max, 1), 0.12);
  const pts = series(level, "wave");
  const w = 168, h = 48;
  const coords = pts.map((p, i) => [(i / (pts.length - 1)) * w, h - 4 - p * (h - 10)] as const);
  const line = smoothPath(coords);
  const last = coords[coords.length - 1];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-12 w-full" preserveAspectRatio="none" aria-hidden>
      <path d={`${line} L${last[0].toFixed(1)},${h} L0,${h} Z`} fill={color} fillOpacity="0.16" />
      <path d={line} fill="none" stroke={color} strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Rounded vertical bars. */
function BarChart({ value, max, color }: { value: number; max: number; color: string }) {
  const level = Math.max(Math.abs(value) / Math.max(max, 1), 0.12);
  const heights = series(level, "pulse");
  const w = 168, h = 48, gap = 5;
  const barW = (w - gap * (heights.length - 1)) / heights.length;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-12 w-full" preserveAspectRatio="none" aria-hidden>
      {heights.map((frac, i) => {
        const bh = frac * (h - 2);
        return (
          <rect key={i} x={i * (barW + gap)} y={h - bh} width={barW} height={bh} rx={3.5} ry={3.5}
                fill={color} fillOpacity={0.3 + frac * 0.6} />
        );
      })}
    </svg>
  );
}

/** Single horizontal meter (honest share of max). */
function MeterChart({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = clamp((Math.abs(value) / Math.max(max, 1)) * 100, value === 0 ? 0 : 4, 100);
  return (
    <div className="space-y-2" aria-hidden>
      <div className="flex h-12 items-end gap-1.5">
        {[0.35, 0.55, 0.45, 0.75, 0.6, 1].map((h, i) => (
          <span key={i} className="min-w-0 flex-1 rounded-t-sm transition-[height] duration-500 ease-out"
                style={{ height: `${Math.max(12, h * pct)}%`, background: color, opacity: 0.35 + h * 0.55 }} />
        ))}
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-paper-3">
        <div className="h-full rounded-full transition-[width] duration-500 ease-out" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

/** Donut / ring chart. */
function DonutChart({ value, max, color, track = "#EEEEEE" }: { value: number; max: number; color: string; track?: string }) {
  const pct = clamp(Math.abs(value) / Math.max(max, 1), 0, 1);
  const r = 18, c = 2 * Math.PI * r;
  const dash = `${(pct * c).toFixed(1)} ${c.toFixed(1)}`;
  return (
    <div className="flex items-center gap-3">
      <svg viewBox="0 0 48 48" className="size-12 shrink-0" aria-hidden>
        <circle cx="24" cy="24" r={r} fill="none" stroke={track} strokeWidth="5" />
        <circle cx="24" cy="24" r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
                strokeDasharray={dash} transform="rotate(-90 24 24)"
                className="transition-[stroke-dasharray] duration-500 ease-out" />
      </svg>
      <div className="min-w-0 flex-1">
        <div className="h-2 overflow-hidden rounded-full bg-paper-3">
          <div className="h-full rounded-full transition-[width] duration-500 ease-out" style={{ width: `${pct * 100}%`, background: color }} />
        </div>
        <p className="mt-1 text-sm text-muted">{Math.round(pct * 100)}% of the busiest figure</p>
      </div>
    </div>
  );
}

/** Cash mix as a soft donut + legend. */
function CashDonut({ parts }: { parts: { key: string; label: string; value: number; color: string }[] }) {
  const total = parts.reduce((s, p) => s + Math.max(0, p.value), 0) || 1;
  const r = 28, c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="mt-4 flex flex-wrap items-center gap-5">
      <svg viewBox="0 0 72 72" className="size-20 shrink-0" aria-hidden>
        <circle cx="36" cy="36" r={r} fill="none" stroke="rgb(255 255 255 / 0.12)" strokeWidth="10" />
        {parts.map((p) => {
          const frac = Math.max(0, p.value) / total;
          if (frac <= 0) return null;
          const dash = `${(frac * c).toFixed(2)} ${c.toFixed(2)}`;
          const el = (
            <circle key={p.key} cx="36" cy="36" r={r} fill="none" stroke={p.color} strokeWidth="10"
                    strokeDasharray={dash} strokeDashoffset={(-offset).toFixed(2)}
                    transform="rotate(-90 36 36)" />
          );
          offset += frac * c;
          return el;
        })}
        <circle cx="36" cy="36" r="18" fill="rgb(23 23 23)" />
      </svg>
      <ul className="min-w-0 flex-1 space-y-1.5 text-sm">
        {parts.map((p) => (
          <li key={p.key} className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 text-surface/70">
              <span className="size-2.5 rounded-full" style={{ background: p.color }} aria-hidden />
              {p.label}
            </span>
            <span className="num">{money(p.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ShareBar({ parts }: { parts: { key: string; value: number; color: string }[] }) {
  const total = parts.reduce((s, p) => s + Math.max(0, p.value), 0) || 1;
  return (
    <div className="flex h-2.5 overflow-hidden rounded-full bg-ink/20" role="img" aria-label="Share of cash accounts">
      {parts.map((p) => {
        const pct = (Math.max(0, p.value) / total) * 100;
        if (pct <= 0) return null;
        return <span key={p.key} className="h-full transition-[width] duration-500 ease-out" style={{ width: `${pct}%`, background: p.color }} />;
      })}
    </div>
  );
}

function ChartCard({ label, value, hint, href, tone, children }: {
  label: string; value: ReactNode; hint?: ReactNode; href?: string; tone?: "error" | "warning"; children: ReactNode;
}) {
  const body = (
    <>
      <p className="text-sm text-muted">{label}</p>
      <p className={`num mt-1 text-xl font-medium ${tone === "error" ? "text-error" : tone === "warning" ? "text-warning" : ""}`}>{value}</p>
      {hint && <p className="mt-0.5 text-sm text-muted">{hint}</p>}
      <div className="mt-3">{children}</div>
    </>
  );
  return href
    ? <Link href={href} className="row-link block rounded-card bg-surface p-4 pr-10 hover:bg-paper-3/40 active:bg-paper-3 shell:p-5 shell:pr-12">{body}</Link>
    : <div className="rounded-card bg-surface p-4 shell:p-5">{body}</div>;
}

/** Cash on hand hero card. */
export function CashHero({ cash, cashTotal, receivables, overdueReceivables, payables, overduePayables, stockValue }: {
  cash: Record<string, string>; cashTotal: string;
  receivables: string; overdueReceivables: string; payables: string; overduePayables: string; stockValue: string;
}) {
  const accounts = (["cash", "bank", "wallet"] as const).map((k, i) => ({
    key: k, label: ACCOUNT[k], value: Number(cash[k] ?? 0), color: MIX[i],
  }));
  return (
    <div className="rounded-card bg-ink p-5 text-surface shell:p-6">
      <p className="text-sm text-surface/70">Cash, bank and wallet</p>
      <p className="num mt-1 text-3xl font-medium tracking-tight">{money(cashTotal)}</p>
      <div className="mt-4"><ShareBar parts={accounts} /></div>
      <CashDonut parts={accounts} />
      <dl className="mt-5 grid gap-3 border-t border-surface/15 pt-4 sm:grid-cols-3">
        <div>
          <dt className="text-sm text-surface/70">Customers owe us</dt>
          <dd className="num mt-0.5 font-medium">{money(receivables)}</dd>
          <dd className="text-sm text-surface/55">{Number(overdueReceivables) ? `${money(overdueReceivables)} over 30 days` : "Nothing overdue"}</dd>
        </div>
        <div>
          <dt className="text-sm text-surface/70">We owe vendors</dt>
          <dd className="num mt-0.5 font-medium">{money(payables)}</dd>
          <dd className="text-sm text-surface/55">{Number(overduePayables) ? `${money(overduePayables)} past due` : "Nothing past due"}</dd>
        </div>
        <div>
          <dt className="text-sm text-surface/70">Stock at cost</dt>
          <dd className="num mt-0.5 font-medium">{money(stockValue)}</dd>
        </div>
      </dl>
      <Link href="/reports/finance?r=cashflow" className="mt-4 inline-flex text-sm font-medium text-action underline-offset-2 hover:underline">Open cash report</Link>
    </div>
  );
}

/** Month money KPIs as a compact 2×2 chart grid (sits beside Needs attention). */
export function MonthMoneyCharts({ revenue, profit, moneyIn, moneyOut }: {
  revenue: string; profit: string; moneyIn: string; moneyOut: string;
}) {
  const monthMax = Math.max(Math.abs(Number(revenue)), Math.abs(Number(profit)), Math.abs(Number(moneyIn)), Math.abs(Number(moneyOut)), 1);
  return (
    <div>
      <h2 className="mb-2">Money this month</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <ChartCard label="Revenue" value={money(revenue)} href="/reports/finance?r=pnl">
          <AreaChart value={Number(revenue)} max={monthMax} color="#0F766E" />
        </ChartCard>
        <ChartCard label="Profit" value={money(profit)} href="/reports/finance?r=pnl"
                   tone={Number(profit) < 0 ? "error" : undefined}
                   hint="Revenue less cost of parts and expenses">
          <BarChart value={Math.abs(Number(profit))} max={monthMax} color={Number(profit) < 0 ? "#B80800" : "#1E7B34"} />
        </ChartCard>
        <ChartCard label="Money in" value={money(moneyIn)} href="/money-in">
          <MeterChart value={Number(moneyIn)} max={monthMax} color="#F98B00" />
        </ChartCard>
        <ChartCard label="Money out" value={money(moneyOut)} href="/money-out">
          <DonutChart value={Number(moneyOut)} max={monthMax} color="#6D0000" />
        </ChartCard>
      </div>
    </div>
  );
}

/** Workshop KPIs: donut, bars, area, meter — one type each. */
export function WorkshopKpiCharts({ carsIn, openQuotes, quotesWaiting, repairOrders, ready, onHold, lowStock, items }: {
  carsIn: number; openQuotes: number; quotesWaiting: number; repairOrders: number; ready: number; onHold: number; lowStock: number; items: number;
}) {
  const max = Math.max(carsIn, openQuotes, repairOrders, lowStock, 1);
  return (
    <div className="grid gap-3 sm:grid-cols-2 shell:grid-cols-4">
      <ChartCard label="Cars in the workshop" value={carsIn} href="/visits">
        <DonutChart value={carsIn} max={max} color="#D10A01" />
      </ChartCard>
      <ChartCard label="Quotations open" value={openQuotes} hint={`${quotesWaiting} waiting for the customer`} href="/quotations?status=sent">
        <BarChart value={openQuotes} max={max} color="#0F766E" />
      </ChartCard>
      <ChartCard label="Repair orders under way" value={repairOrders} hint={`${ready} ready, ${onHold} on hold`} href="/repair-orders">
        <AreaChart value={repairOrders} max={max} color="#F98B00" />
      </ChartCard>
      <ChartCard label="Low on stock" value={lowStock} hint={`of ${items} items`} href="/inventory?stock=low" tone={lowStock ? "warning" : undefined}>
        <MeterChart value={lowStock} max={Math.max(items, 1)} color="#8A4B00" />
      </ChartCard>
    </div>
  );
}
