"use client";

import { Suspense } from "react";
import { MoneyBook } from "@/components/moneybook";
import { MONEY, RequirePermission } from "@/components/shell";
import { Card, SkeletonRows } from "@/components/ui";

export default function MoneyInPage() {
  return (
    <RequirePermission permission={MONEY}>
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <MoneyBook direction="in" />
      </Suspense>
    </RequirePermission>
  );
}
