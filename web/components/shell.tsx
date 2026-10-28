"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { CommandMenu, Kbd, useModKey, type Command } from "@/components/command-menu";
import { useSession } from "@/lib/session";

// One list drives the navigation; an entry shows only if the user holds its
// permission (the API enforces the same permission on the data).
/** A nav item or page needs one permission, or any of a list. */
type Needs = string | string[];
type NavItem = { href: string; label: string; permission: Needs; keys?: string };  // keys: "g" then a letter jumps here
export const MONEY: string[] = ["payments-in", "payments-out", "expenses", "reports-finance"];
export const PEOPLE: string[] = ["hr", "payroll"];
export const PURCHASING: string[] = ["vendors", "purchasing", "goods-receipt", "payments-out"];

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Workshop",
    items: [
      { href: "/", label: "Dashboard", permission: "dashboard", keys: "g d" },
      { href: "/visits", label: "Cars in the workshop", permission: "visits", keys: "g v" },
      { href: "/gate", label: "Cars ready to leave", permission: ["gate", "visits"], keys: "g l" },
      { href: "/quotations", label: "Quotations", permission: "quotations", keys: "g q" },
      { href: "/repair-orders", label: "Repair orders", permission: "repair-orders", keys: "g r" },
      { href: "/invoices", label: "Invoices and counter sales", permission: "invoices", keys: "g i" },
      { href: "/customers", label: "Customers", permission: "customers", keys: "g c" },
      { href: "/cars", label: "Cars", permission: "customers", keys: "g a" },
    ],
  },
  {
    section: "Stock and services",
    items: [
      { href: "/inventory", label: "Inventory", permission: "inventory", keys: "g s" },
      { href: "/labour-codes", label: "Labour codes", permission: "dashboard" },
    ],
  },
  {
    section: "Reports",
    items: [
      { href: "/reports/finance", label: "Finance reports", permission: "reports-finance" },
      { href: "/reports/operations", label: "Workshop report", permission: "reports-ops" },
      { href: "/reports/hr", label: "People report", permission: "hr" },
      { href: "/periods", label: "Month end", permission: ["period-close", "reports-finance"] },
    ],
  },
  {
    section: "Customers",
    items: [{ href: "/messages", label: "Messages", permission: "messages", keys: "g m" }],
  },
  {
    section: "People",
    items: [
      { href: "/employees", label: "Employees", permission: "hr" },
      { href: "/attendance", label: "Attendance", permission: "hr" },
      { href: "/payroll", label: "Payroll and advances", permission: "payroll" },
    ],
  },
  {
    section: "Money",
    items: [
      { href: "/money-in", label: "Money in", permission: MONEY },
      { href: "/money-out", label: "Money out", permission: MONEY },
      { href: "/cash-close", label: "Cash close", permission: ["cash-close", "reports-finance"] },
      { href: "/missing-evidence", label: "Missing proof", permission: MONEY },
    ],
  },
  {
    section: "Purchasing",
    items: [
      { href: "/vendors", label: "Vendors", permission: PURCHASING },
      { href: "/purchase-orders", label: "Purchase orders", permission: PURCHASING },
      { href: "/bills", label: "Bills and payments", permission: PURCHASING },
    ],
  },
  {
    section: "Administration",
    items: [
      { href: "/admin/users", label: "Users", permission: "users" },
      { href: "/admin/roles", label: "Roles and permissions", permission: "users" },
      { href: "/admin/audit", label: "Audit log", permission: "audit" },
      { href: "/settings/branch", label: "Branch settings", permission: "settings" },
      { href: "/settings/money", label: "Money settings", permission: "settings" },
      { href: "/settings/messages", label: "Message wording", permission: "messages" },
      { href: "/settings/sync", label: "Cloud sync", permission: "sync" },
    ],
  },
  { section: "Help", items: [{ href: "/help", label: "User manual", permission: [], keys: "g h" }] },  // for everyone
];

const allowed = (needs: Needs, can: (p: string) => boolean) => [needs].flat().length === 0 || [needs].flat().some(can);

// Things people start often, beside the pages, in the command menu.
const ACTIONS: { label: string; href: string; permission: Needs; keys: string }[] = [
  { label: "Check in a car", href: "/visits/new", permission: "visits", keys: "g n" },
  { label: "New counter sale", href: "/counter-sales/new", permission: "invoices", keys: "g p" },
];

function SearchButton({ onOpen, className = "" }: { onOpen: () => void; className?: string }) {
  const mod = useModKey();
  return (
    <button onClick={onOpen} className={`flex min-h-11 items-center gap-3 rounded-control border border-rule-strong bg-surface px-3 text-left text-ink-2 hover:bg-paper active:bg-paper-3 ${className}`}>
      <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true" className="shrink-0"><circle cx="9" cy="9" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M13.5 13.5L17 17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
      <span className="flex-1">Search</span>
      <span className="hidden shell:flex shell:gap-1"><Kbd>{mod}</Kbd><Kbd>K</Kbd></span>
    </button>
  );
}

// Screens that sit under a list: a record, a form. They get a Back button; the list pages themselves do not.
const PARENT: Record<string, string> = {
  visits: "/visits", customers: "/customers", cars: "/cars", quotations: "/quotations", "repair-orders": "/repair-orders",
  invoices: "/invoices", "counter-sales": "/invoices", "job-cards": "/visits", inspections: "/visits", inventory: "/inventory",
  vendors: "/vendors", "purchase-orders": "/purchase-orders", bills: "/bills", employees: "/employees", payroll: "/payroll", periods: "/periods",
};

/** Back goes to the screen the person came from; when they opened this one directly, to its list. */
function BackButton() {
  const router = useRouter();
  const pathname = usePathname();
  const moved = useRef(false);
  const seen = useRef(pathname);
  useEffect(() => { if (seen.current !== pathname) { moved.current = true; seen.current = pathname; } }, [pathname]);
  const parts = pathname.split("/").filter(Boolean);
  const parent = parts.length >= 2 ? PARENT[parts[0]] : undefined;
  if (!parent) return null;
  return (
    <button onClick={() => (moved.current ? router.back() : router.push(parent))}
            className="no-print mb-4 inline-flex min-h-11 items-center gap-2 rounded-control border border-rule-strong bg-surface px-4 font-medium hover:bg-paper active:bg-paper-3 active:duration-0">
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M10 3L5 8l5 5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
      Back
    </button>
  );
}

function Brand() {
  return (
    <Link href="/" className="flex min-h-11 items-center gap-2.5 rounded-control">
      <Image src="/logo.png" alt="" width={36} height={36} priority />
      <span className="text-lg font-semibold">
        <span className="text-oxblood">German</span><span className="text-logo-black">ATO</span>
      </span>
    </Link>
  );
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const session = useSession();
  const pathname = usePathname();
  const router = useRouter();

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  async function switchBranch(branchId: string) {
    await api("/api/auth/switch-branch", { method: "POST", json: { branch_id: branchId } });
    window.location.reload(); // every screen reloads for the new branch
  }

  return (
    <nav aria-label="Main" className="flex h-full flex-col gap-5 overflow-y-auto p-4">
      <div className="rounded-control bg-paper px-3 py-2.5">
        {session.branches.length > 1 ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm text-muted">Branch</span>
            <select
              className="min-h-11 rounded-control border border-rule-strong bg-surface px-2 text-base"
              value={session.branch.id}
              onChange={(e) => switchBranch(e.target.value)}
            >
              {session.branches.map((b) => (
                <option key={b.id} value={b.id}>{b.name} ({b.code})</option>
              ))}
            </select>
          </label>
        ) : (
          <>
            <p className="font-medium leading-snug">{session.branch.name}</p>
            <p className="text-sm text-muted">Branch {session.branch.code}</p>
          </>
        )}
      </div>

      {NAV.map(({ section, items }) => {
        const visible = items.filter((i) => [i.permission].flat().length === 0 || [i.permission].flat().some((p) => session.can(p)));
        if (!visible.length) return null;
        return (
          <div key={section}>
            <p className="mb-1 px-3 text-sm text-muted">{section}</p>
            <ul className="space-y-0.5">
              {visible.map((i) => {
                const active = i.href === "/" ? pathname === "/" : pathname.startsWith(i.href);
                return (
                  <li key={i.href}>
                    <Link
                      href={i.href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      className={`relative flex min-h-11 items-center rounded-control px-3 transition-colors duration-(--dur-micro) active:duration-0 ${
                        active ? "bg-paper-3 font-medium text-ink"
                          : "text-ink-2 hover:bg-paper hover:text-ink active:bg-paper-3"
                      }`}
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

      <div className="mt-auto border-t border-rule pt-4">
        <p className="px-3 font-medium leading-snug">{session.user.full_name}</p>
        <p className="px-3 text-sm text-muted">{session.role.name}</p>
        <button
          onClick={logout}
          className="mt-2 flex min-h-11 w-full items-center rounded-control px-3 text-left text-ink-2 transition-colors duration-(--dur-micro) hover:bg-paper-3 hover:text-ink"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const session = useSession();
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  // Swipe the menu left to close it: it follows the finger, and closes on distance or a quick flick.
  const [dx, setDx] = useState(0);
  const [dragging, setDragging] = useState(false);
  const swipe = useRef<{ x: number; at: number } | null>(null);
  const onSwipe = {
    onPointerDown: (e: React.PointerEvent) => { if (e.pointerType !== "mouse") swipe.current = { x: e.clientX, at: e.timeStamp }; },
    onPointerMove: (e: React.PointerEvent) => {
      if (!swipe.current) return;
      const d = e.clientX - swipe.current.x;
      if (d < -8) { setDragging(true); setDx(d); }
    },
    onPointerUp: (e: React.PointerEvent) => {
      const s = swipe.current;
      swipe.current = null;
      setDragging(false);
      if (!s) return;
      const d = e.clientX - s.x;
      const speed = d / Math.max(e.timeStamp - s.at, 1);  // px per ms, negative = leftwards
      if (d < -(drawer.current?.offsetWidth ?? 320) * 0.35 || (d < -40 && speed < -0.5)) { setOpen(false); setDx(0); }
      else setDx(0);
    },
    onPointerCancel: () => { swipe.current = null; setDragging(false); setDx(0); },
  };
  const commands = useMemo<Command[]>(() => [
    ...NAV.flatMap(({ section, items }) => items.filter((i) => allowed(i.permission, session.can)).map((i) => ({ label: i.label, group: section, href: i.href, keys: i.keys }))),
    ...ACTIONS.filter((a) => allowed(a.permission, session.can)).map((a) => ({ label: a.label, group: "Start", href: a.href, keys: a.keys })),
  ], [session]);
  const menuButton = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLDivElement>(null);

  // Drawer: Escape closes, focus moves in and back out, the page behind can't scroll.
  useEffect(() => {
    if (!open) return;
    const trigger = menuButton.current;
    drawer.current?.querySelector<HTMLElement>("a, button, select")?.focus();
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
      trigger?.focus();
    };
  }, [open]);

  return (
    <div className="flex min-h-dvh">
      <aside className="no-print sticky top-0 hidden h-dvh w-64 shrink-0 flex-col bg-surface shell:flex">
        <div className="px-4 py-3"><Brand /></div>
        <div className="px-3 pb-2"><SearchButton onOpen={() => setSearching(true)} className="w-full" /></div>
        <Navigation />
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 shell:hidden">
          <button aria-label="Close menu" className="absolute inset-0 bg-scrim" onClick={() => setOpen(false)} />
          <div
            ref={drawer}
            role="dialog"
            aria-modal="true"
            aria-label="Menu"
            style={{ transform: `translateX(${Math.min(dx, 0)}px)`, transition: dragging ? "none" : "transform var(--dur-micro) ease-out" }}
            {...onSwipe}
            className="absolute inset-y-0 left-0 flex w-[min(20rem,85vw)] touch-pan-y flex-col bg-surface pb-[env(safe-area-inset-bottom)] pl-[env(safe-area-inset-left)] pt-[env(safe-area-inset-top)]"
          >
            <div className="flex items-center justify-between px-4 py-2">
              <Brand />
              <button
                aria-label="Close menu"
                onClick={() => setOpen(false)}
                className="flex size-11 items-center justify-center rounded-control text-ink-2 hover:bg-paper-3"
              >
                <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
              </button>
            </div>
            <Navigation onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-30 flex items-center gap-2 bg-surface/85 px-2 pb-1.5 pt-[max(0.375rem,env(safe-area-inset-top))] backdrop-blur shell:hidden">
          <button
            ref={menuButton}
            aria-label="Open menu"
            aria-expanded={open}
            onClick={() => setOpen(true)}
            className="flex size-11 items-center justify-center rounded-control text-ink-2 hover:bg-paper-3"
          >
            <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M3 6h16M3 11h16M3 16h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
          </button>
          <Brand />
          <button aria-label="Search pages and actions" onClick={() => setSearching(true)} className="ml-auto flex size-11 items-center justify-center rounded-control text-ink-2 hover:bg-paper-3">
            <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><circle cx="9" cy="9" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M13.5 13.5L17 17" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
          </button>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 shell:px-10 shell:py-10"><BackButton />{children}</main>
      </div>
      <CommandMenu commands={commands} open={searching} setOpen={setSearching} />
    </div>
  );
}

/** Wrap a page that needs a permission; the API refuses the data anyway. */
export function RequirePermission({ permission, children }: { permission: Needs; children: ReactNode }) {
  const session = useSession();
  const needs = [permission].flat();
  if (!needs.some((p) => session.can(p))) {
    return (
      <div className="rounded-card bg-surface p-6">
        <p className="font-medium">You don&apos;t have access to this page</p>
        <p className="mt-1 text-muted">Ask an administrator to add the “{needs[0]}” permission to your role.</p>
      </div>
    );
  }
  return <>{children}</>;
}
