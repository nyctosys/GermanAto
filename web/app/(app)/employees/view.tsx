"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { EmployeeForm, type Employee } from "@/components/hr";
import { SearchBox, useQueryParam } from "@/components/search";
import { RequirePermission } from "@/components/shell";
import { Button, Card, EmptyState, ErrorState, PageHeader, SkeletonRows } from "@/components/ui";
import { useApi } from "@/lib/api";
import { money, phone } from "@/lib/format";

export default function EmployeesPage() {
  return (
    <RequirePermission permission="hr">
      <Suspense fallback={<Card flush><SkeletonRows /></Card>}>
        <List />
      </Suspense>
    </RequirePermission>
  );
}

function List() {
  const router = useRouter();
  const [q] = useQueryParam("q");
  const [adding, setAdding] = useState(false);
  const list = useApi<Employee[]>(`/api/employees?${new URLSearchParams({ q })}`, { swr: true });
  return (
    <>
      <PageHeader title="Employees" description="Everyone who works here: their pay, their shift and their number on the attendance device."
                  actions={!adding && <Button onClick={() => setAdding(true)}>Add an employee</Button>} />
      {adding && <div className="mb-4"><Card title="New employee"><EmployeeForm onCancel={() => setAdding(false)} onSaved={(e) => router.push(`/employees/${e.id}`)} /></Card></div>}
      <div className="mb-4 flex"><SearchBox placeholder="Name, number, phone or title" /></div>
      <Card flush>
        {list.error ? <ErrorState message={list.error} onRetry={list.reload} /> : !list.data ? <SkeletonRows />
          : !list.data.length ? <EmptyState title="No employees yet">{q ? `Nothing matches “${q}”.` : "Add each person once. Attendance and payroll are worked out from this list."}</EmptyState>
          : (
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <th className="px-4 py-2 font-normal shell:px-5">Employee</th><th className="px-4 py-2 font-normal">Phone</th><th className="px-4 py-2 text-right font-normal shell:pr-5">Salary</th>
              </tr></thead>
              <tbody>
                {list.data.map((e) => (
                  <tr key={e.id} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                      <Link href={`/employees/${e.id}`} className="font-medium underline">{e.full_name}</Link>
                      <span className="block text-sm text-muted">{e.number}{e.title ? `, ${e.title}` : ""}</span>
                    </td>
                    <td data-label="Phone" className="num px-4 py-3 max-sm:px-0">{e.phone ? phone(e.phone) : ""}</td>
                    <td data-label="Salary" className="num px-4 py-3 text-right shell:pr-5 max-sm:px-0">{money(e.monthly_salary)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </>
  );
}
