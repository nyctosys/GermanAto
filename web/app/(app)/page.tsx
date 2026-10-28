"use client";

import Link from "next/link";
import { Card, PageHeader, SkeletonRows, ErrorState } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useSession } from "@/lib/session";

type Branch = { name: string; code: string; address: string; phone: string; email: string; tax_rate: string; currency: string };

// No workshop figures exist yet (Phase 1), so the dashboard shows the branch
// record it does have rather than invented numbers.
export default function Dashboard() {
  const { can } = useSession();
  const branch = useApi<Branch>("/api/branch");

  return (
    <>
      <PageHeader title="Dashboard" description="Visits, money and stock will appear here as each part of the system is switched on." />
      <div className="grid gap-4 shell:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card
          title="This branch"
          actions={can("settings") ? <Link href="/settings/branch" className="flex min-h-11 items-center text-accent underline">Edit settings</Link> : undefined}
          flush
        >
          {branch.error ? <ErrorState message={branch.error} onRetry={branch.reload} />
            : !branch.data ? <SkeletonRows rows={5} />
            : (
              <dl className="grid gap-x-6 gap-y-4 p-4 sm:grid-cols-2 shell:p-5">
                {[
                  ["Workshop", branch.data.name],
                  ["Branch code", branch.data.code],
                  ["Phone", branch.data.phone || "Not set"],
                  ["Email", branch.data.email || "Not set"],
                  ["Address", branch.data.address || "Not set"],
                  ["Tax rate", `${Number(branch.data.tax_rate)}% (${branch.data.currency})`],
                ].map(([label, value]) => (
                  <div key={label} className="min-w-0">
                    <dt className="text-sm text-muted">{label}</dt>
                    <dd className={`mt-0.5 break-words ${value === "Not set" ? "text-muted" : ""}`}>{value}</dd>
                  </div>
                ))}
              </dl>
            )}
        </Card>
        <Card title="Being built">
          <ol className="list-inside list-decimal space-y-2 text-ink-2">
            <li>Customers, cars and car history</li>
            <li>Labour codes and inventory by barcode</li>
            <li>Check-in, inspection, job card, quotation, repair order, invoice</li>
            <li>Money in and money out, with proofs</li>
          </ol>
        </Card>
      </div>
    </>
  );
}
