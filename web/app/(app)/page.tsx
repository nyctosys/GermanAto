"use client";

import { Card, PageTitle } from "@/components/ui";
import { useSession } from "@/lib/session";

// Placeholder until the workshop, money and report modules land (spec §9).
export default function Dashboard() {
  const { user, branch } = useSession();
  return (
    <>
      <PageTitle title={`Welcome, ${user.full_name}`} subtitle={`${branch.name} · branch ${branch.code}`} />
      <Card title="Coming next">
        <ul className="list-inside list-disc space-y-1 text-sm text-neutral-700">
          <li>Customers, cars, ownership transfers and car history</li>
          <li>Labour codes and inventory by barcode</li>
          <li>Visit → job card → quotation → repair order → invoice, and counter sales</li>
          <li>Money In / Money Out with proofs, month-end close, reports with drill-down</li>
        </ul>
      </Card>
    </>
  );
}
