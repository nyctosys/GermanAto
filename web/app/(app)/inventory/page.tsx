"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { type Item, ItemForm } from "@/components/inventory";
import { SearchBox, Segments, useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, ApiError, useApi } from "@/lib/api";
import { money, qty } from "@/lib/format";

export default function InventoryPage() {
  return (
    <RequirePermission permission="inventory">
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <Inventory />
      </Suspense>
    </RequirePermission>
  );
}

function Inventory() {
  const router = useRouter();
  const [q] = useQueryParam("q");
  const [stock, setStock] = useQueryParam("stock");
  const list = useApi<Item[]>(`/api/items?${new URLSearchParams({ q, stock: stock || "all", limit: "200" })}`);
  const [adding, setAdding] = useState<{ code?: string } | null>(null);

  return (
    <>
      <PageHeader title="Inventory" description="Stock in this branch. Scan a barcode to find an item, or add it if it's new."
                  actions={<Button onClick={() => setAdding({})}>Add item</Button>} />
      {adding && (
        <div className="mb-6">
          <Card title="New item">
            <ItemForm presetCode={adding.code} onCancel={() => setAdding(null)} onSaved={(i) => router.push(`/inventory/${i.id}`)} />
          </Card>
        </div>
      )}
      <Scan onUnknown={(code) => setAdding({ code })} />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchBox placeholder="Name, brand, part number or car it fits" />
        <Segments value={stock || "all"} onChange={(v) => setStock(v === "all" ? "" : v)}
                  options={[{ value: "all", label: "All" }, { value: "low", label: "Low" }, { value: "out", label: "Out" }]} />
      </div>
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} />
          : !list.data ? <SkeletonRows rows={6} />
          : !list.data.length ? (
            q || stock ? <EmptyState title="Nothing matches">Clear the search or the filter to see every item.</EmptyState>
              : <EmptyState title="No items yet" action={<Button onClick={() => setAdding({})}>Add item</Button>}>Scan a part&apos;s barcode to add your first item.</EmptyState>
          ) : (
            <table className="table-stack w-full text-left">
              <thead className="border-b border-rule text-sm text-muted">
                <tr>
                  <th className="px-5 py-3 font-medium">Item</th>
                  <th className="px-3 py-3 font-medium">Shelf</th>
                  <th className="px-3 py-3 text-right font-medium">In stock</th>
                  <th className="px-5 py-3 text-right font-medium">Sale price</th>
                </tr>
              </thead>
              <tbody>
                {list.data.map((i) => (
                  <tr key={i.id} className="cursor-pointer border-t border-rule first:border-t-0 hover:bg-paper-2" onClick={() => router.push(`/inventory/${i.id}`)}>
                    <td className="px-5 py-3 max-sm:px-0">
                      <Link href={`/inventory/${i.id}`} className="block font-medium" onClick={(e) => e.stopPropagation()}>{i.name}</Link>
                      <span className="num block text-sm text-muted">{[i.brand, i.codes[0]?.code].filter(Boolean).join(", ")}</span>
                    </td>
                    <td data-label="Shelf" className="px-3 py-3 max-sm:px-0">{i.location || <span className="text-muted">None</span>}</td>
                    <td data-label="In stock" className="num px-3 py-3 text-right max-sm:px-0">
                      <span className="inline-flex items-center gap-2">
                        {Number(i.on_hand) <= 0 ? <Badge tone="error">Out</Badge> : i.low_stock && <Badge tone="warning">Low</Badge>}
                        {qty(i.on_hand)} {i.unit}
                      </span>
                    </td>
                    <td data-label="Sale price" className="num px-5 py-3 text-right max-sm:px-0">{money(i.sale_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </>
  );
}

/** Scanner input: a USB/Bluetooth scanner types the code and Enter. */
function Scan({ onUnknown }: { onUnknown: (code: string) => void }) {
  const router = useRouter();
  const [unknown, setUnknown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const input = e.currentTarget.elements.namedItem("code") as HTMLInputElement;
    const code = input.value.trim();
    if (!code) return;
    setUnknown(null);
    setError(null);
    try {
      const item = await api<Item>(`/api/items/lookup?${new URLSearchParams({ code })}`);
      router.push(`/inventory/${item.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setUnknown(code);
      else setError((err as Error).message);
      input.select();
    }
  }

  return (
    <form onSubmit={submit} className="mb-4 rounded-card bg-surface p-4">
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-ink-2">Scan a barcode</span>
        <input name="code" autoFocus autoComplete="off" spellCheck={false} enterKeyHint="search" placeholder="Scan, or type a code and press Enter"
               className="min-h-12 w-full rounded-control border border-rule-strong bg-paper px-3 font-mono text-lg placeholder:font-sans placeholder:text-base placeholder:text-muted focus-visible:border-accent" />
      </label>
      {unknown && (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <p className="text-ink-2">No item has the code <span className="num font-semibold">{unknown}</span>.</p>
          <Button type="button" variant="secondary" onClick={() => onUnknown(unknown)}>Add it as a new item</Button>
        </div>
      )}
      <div className="mt-3 empty:hidden"><Notice>{error}</Notice></div>
    </form>
  );
}
