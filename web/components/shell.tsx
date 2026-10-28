"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

// One list drives the sidebar; an entry shows only if the user holds its
// permission (the API enforces the same permission on the data).
const NAV: { section: string; items: { href: string; label: string; permission: string }[] }[] = [
  { section: "Overview", items: [{ href: "/", label: "Dashboard", permission: "dashboard" }] },
  {
    section: "Administration",
    items: [
      { href: "/admin/users", label: "Users", permission: "users" },
      { href: "/admin/roles", label: "Roles & permissions", permission: "users" },
      { href: "/admin/audit", label: "Audit log", permission: "audit" },
      { href: "/settings/branch", label: "Branch settings", permission: "settings" },
    ],
  },
];

export function Shell({ children }: { children: ReactNode }) {
  const session = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  async function switchBranch(branchId: string) {
    await api("/api/auth/switch-branch", { method: "POST", json: { branch_id: branchId } });
    window.location.reload();
  }

  const sidebar = (
    <nav className="flex h-full flex-col gap-6 p-4">
      <div>
        <p className="text-lg font-semibold text-brand">GermanATO</p>
        {session.branches.length > 1 ? (
          <select
            aria-label="Branch"
            className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1 text-xs"
            value={session.branch.id}
            onChange={(e) => switchBranch(e.target.value)}
          >
            {session.branches.map((b) => (
              <option key={b.id} value={b.id}>{b.name} ({b.code})</option>
            ))}
          </select>
        ) : (
          <p className="text-xs text-neutral-500">{session.branch.name} · {session.branch.code}</p>
        )}
      </div>
      {NAV.map(({ section, items }) => {
        const visible = items.filter((i) => session.can(i.permission));
        if (!visible.length) return null;
        return (
          <div key={section}>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-neutral-400">{section}</p>
            <ul className="space-y-0.5">
              {visible.map((i) => {
                const active = i.href === "/" ? pathname === "/" : pathname.startsWith(i.href);
                return (
                  <li key={i.href}>
                    <Link
                      href={i.href}
                      onClick={() => setOpen(false)}
                      className={`block rounded-md px-2 py-1.5 text-sm ${active ? "bg-brand-light font-medium text-brand" : "text-neutral-700 hover:bg-neutral-100"}`}
                    >
                      {i.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
      <div className="mt-auto border-t border-neutral-200 pt-3 text-sm">
        <p className="font-medium">{session.user.full_name}</p>
        <p className="text-xs text-neutral-500">{session.role.name}</p>
        <button onClick={logout} className="mt-2 text-xs text-brand hover:underline">Sign out</button>
      </div>
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="no-print hidden w-60 shrink-0 border-r border-neutral-200 bg-white md:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 md:hidden" onClick={() => setOpen(false)}>
          <div className="absolute inset-0 bg-black/30" />
          <aside className="absolute inset-y-0 left-0 w-64 bg-white" onClick={(e) => e.stopPropagation()}>{sidebar}</aside>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print flex items-center gap-3 border-b border-neutral-200 bg-white px-4 py-3 md:hidden">
          <button aria-label="Open menu" onClick={() => setOpen(true)} className="rounded border border-neutral-300 px-2 py-1">☰</button>
          <span className="font-semibold text-brand">GermanATO</span>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 p-4 md:p-8">{children}</main>
      </div>
    </div>
  );
}

/** Wrap a page that needs a permission; the API refuses the data anyway. */
export function RequirePermission({ permission, children }: { permission: string; children: ReactNode }) {
  const session = useSession();
  if (!session.can(permission)) {
    return <p className="rounded-md bg-amber-50 p-4 text-sm text-amber-900">You don&apos;t have access to this page.</p>;
  }
  return <>{children}</>;
}
