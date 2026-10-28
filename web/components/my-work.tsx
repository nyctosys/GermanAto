"use client";

import Link from "next/link";
import { Badge, Card, EmptyState, ErrorState, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";

type Item = { label: string; sub: string; href: string; waiting_hours: number | null };
type Group = { key: string; title: string; do: string; count: number; items: Item[]; href: string };
type Data = { groups: Group[]; total: number };

const waited = (h: number | null) => (h == null ? "" : h < 1 ? "just now" : h < 24 ? `${h} h` : `${Math.round(h / 24)} d`);

/**
 * What is waiting for this person, and only this person: the queues are made from the state of the records (an approved quotation,
 * a finished repair, a paid invoice), filtered to the work their permissions allow. Nobody has to be told anything.
 */
export function MyWork() {
  const w = useApi<Data>("/api/my-work", { swr: true });
  if (w.error) return <Card flush><ErrorState message={w.error} onRetry={w.reload} /></Card>;
  if (!w.data) return <Card flush><SkeletonRows rows={4} /></Card>;
  if (!w.data.groups.length) return <Card flush><EmptyState title="Nothing is waiting for you">New work appears here by itself as the people before you finish their part.</EmptyState></Card>;
  return (
    <div className="grid gap-4 shell:grid-cols-2">
      {w.data.groups.map((g) => (
        <Card key={g.key} title={g.title} flush actions={<Badge tone="accent">{g.count}</Badge>}>
          <p className="border-b border-rule px-4 py-2 text-sm text-muted shell:px-5">{g.do}</p>
          <ul>
            {g.items.map((it) => (
              <li key={it.label + it.sub}>
                <Link href={it.href} className="row-link flex min-h-14 flex-col justify-center border-t border-rule px-4 py-2 pr-10 first:border-t-0 hover:bg-paper-2 shell:px-5 shell:pr-12">
                  <span className="flex flex-wrap items-baseline justify-between gap-x-3"><span className="font-medium">{it.label}</span>{waited(it.waiting_hours) && <span className="text-sm text-muted">waiting {waited(it.waiting_hours)}</span>}</span>
                  <span className="text-sm text-muted">{it.sub}</span>
                </Link>
              </li>
            ))}
          </ul>
          {g.count > g.items.length && (
            <Link href={g.href} className="inline-flex min-h-11 items-center px-4 font-medium underline underline-offset-4 shell:px-5">See all {g.count}</Link>
          )}
        </Card>
      ))}
    </div>
  );
}
