"use client";

import { Suspense, useEffect, useState, type FormEvent } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { RequirePermission } from "@/components/shell";
import { Badge, Button, Card, EmptyState, ErrorState, Field, Input, Notice, PageHeader, SkeletonRows } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { day, moneyDiff, moneyExact, today } from "@/lib/format";
import { useLiveErrors } from "@/lib/form";
import { closeSchema, issuesToFieldErrors } from "@/lib/schemas";
import { useSession } from "@/lib/session";

type Movement = { at: string; entry_date: string; memo: string; amount: string; source_type: string | null; number: string };
type PostClosing = {
  needed: boolean;
  original: { sequence: number; expected: string; counted: string; difference: string; at: string; closed_by: string | null };
  prior_closes: { sequence: number; expected: string; counted: string; difference: string; at: string }[];
  movements: Movement[];
  books_now: string; last_signed: string; change_since_sign: string;
};
type Status = {
  account: string; name: string; expected: string;
  last_close: { close_date: string; sequence?: number; counted: string; difference: string; at?: string; closed_by?: string | null } | null;
  closed_today: boolean;
  signed_today?: boolean;
  next_close_date: string | null;
  expected_on_next: string | null;
  days_behind: number;
  may_close_earlier: boolean;
  post_closing?: PostClosing | null;
};
type Close = { id: string; account: string; close_date: string; sequence?: number; expected: string; counted: string; difference: string; reason: string; closed_by: string | null; post_closing?: boolean; created_at?: string };
type MissedLine = { account: string; name: string; expected: string };
type MissedDay = { date: string; accounts: string[]; names: string[]; lines: MissedLine[]; total: string };
type DayExpected = {
  account: string; close_date: string; expected: string;
  already_closed: boolean; gap_fill: boolean; post_closing?: boolean; can_sign: boolean;
  later_through: string | null; must_close_first: string | null;
};
const KIND: Record<string, string> = { cash: "Cash", bank: "Bank", wallet: "Mobile wallet" };
const whenStamp = (v: string) => new Date(v).toLocaleString("en-PK", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });

export default function CashClosePage() {
  return (
    <RequirePermission permission={["cash-close", "reports-finance"]}>
      <PageHeader title="Cash close" description="Sign each account at the end of the day. Urgent money can still be recorded after signing — the original close stays, and you sign a post-closing count for the new total." />
      <Suspense fallback={<Card flush><SkeletonRows rows={3} /></Card>}>
        <Body />
      </Suspense>
    </RequirePermission>
  );
}

function earliestOpenDay(rows: Status[]): string | null {
  const days = rows.map((s) => s.next_close_date).filter((d): d is string => !!d).sort();
  return days[0] ?? null;
}

function Body() {
  const { can } = useSession();
  const search = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const onParam = search.get("on");
  const futureOn = !!onParam && onParam > today();
  const status = useApi<Status[]>("/api/cash-closes/status");
  const history = useApi<Close[]>("/api/cash-closes");
  const missed = useApi<MissedDay[]>("/api/cash-closes/missed");
  const [sessionDay, setSessionDay] = useState<string | null>(onParam && onParam <= today() ? onParam : null);
  const [pickingMissed, setPickingMissed] = useState(false);
  const reload = () => { status.reload(); history.reload(); missed.reload(); };

  useEffect(() => {
    if (onParam && onParam <= today()) setSessionDay(onParam);
    else if (futureOn) setSessionDay(null);
  }, [onParam, futureOn]);

  function openDay(d: string) {
    setSessionDay(d);
    setPickingMissed(false);
    const p = new URLSearchParams(search.toString());
    p.set("on", d);
    router.replace(`${pathname}?${p}`, { scroll: false });
  }

  function leaveDay() {
    setSessionDay(null);
    const p = new URLSearchParams(search.toString());
    p.delete("on");
    const qs = p.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }

  const rows = status.data ?? [];
  const nextDay = earliestOpenDay(rows);
  const catchingUp = !!nextDay && nextDay < today();
  const postClosingRows = rows.filter((s) => s.post_closing?.needed);
  const allClosedToday = rows.length > 0 && rows.every((s) => s.closed_today) && !postClosingRows.length;
  const mayEarlier = rows.some((s) => s.may_close_earlier);
  const openOnNext = rows.filter((s) => s.next_close_date === nextDay).length;

  return (
    <div className="space-y-4">
      {futureOn && !sessionDay && (
        <Notice tone="warning">
          {day(onParam!)} has not ended yet, so it cannot be signed. Month end only needs a count on the last day after that day has passed.
          {catchingUp ? ` Close ${day(nextDay!)} first if it is still open, or come back after ${day(onParam!)}.` : ` Come back after ${day(onParam!)}.`}
        </Notice>
      )}
      {catchingUp && !sessionDay && (
        <Notice tone="warning">
          Yesterday (or an earlier day) is still open. Close that day first — you will count against{" "}
          <strong>{day(nextDay!)}</strong>&apos;s books (not today&apos;s). After it is signed for cash, bank and wallet, today unlocks.
        </Notice>
      )}
      {!!postClosingRows.length && !sessionDay && (
        <Notice tone="warning">
          Today was already signed, then more money was recorded. The original closes are kept. Sign a post-closing count for{" "}
          {postClosingRows.map((s) => s.name).join(", ")} so the books match the drawer again.
        </Notice>
      )}

      {status.error ? <Card flush><ErrorState message={status.error} onRetry={status.reload} /></Card> : !status.data ? <Card flush><SkeletonRows rows={3} /></Card>
        : sessionDay ? (
          <DaySession
            closeDate={sessionDay}
            accounts={rows}
            canClose={can("cash-close")}
            onDone={reload}
            onLeave={leaveDay}
            onContinue={openDay}
          />
        ) : (
          <Card title={catchingUp ? `Close previous day first — ${day(nextDay!)}` : postClosingRows.length ? "Sign post-closing counts" : "Close today"}>
            <p className="text-sm text-muted">
              {catchingUp
                ? `Open ${day(nextDay!)} to see cash, bank and mobile wallet with that day's book totals. Sign all three, then come back for today.`
                : postClosingRows.length
                  ? "Additional transactions came in after today's close. Review the original signed amount, the new movements, and the updated total, then sign again."
                  : "Open today to see cash, bank and mobile wallet with today's book totals, then sign each account."}
            </p>
            {allClosedToday ? (
              <div className="mt-4 space-y-3">
                <Badge tone="success">All three accounts are closed for today</Badge>
              </div>
            ) : postClosingRows.length && can("cash-close") ? (
              <div className="mt-4 space-y-3">
                <Button onClick={() => openDay(today())}>Sign post-closing counts</Button>
              </div>
            ) : can("cash-close") && nextDay && (
              <div className="mt-4 space-y-3">
                <Button onClick={() => openDay(nextDay)}>
                  {catchingUp ? `Close ${day(nextDay)} first` : "Close today"}
                </Button>
                {openOnNext > 0 && catchingUp && (
                  <p className="text-sm text-muted">{openOnNext} account{openOnNext === 1 ? "" : "s"} still need a signed count for {day(nextDay)}.</p>
                )}
                {mayEarlier && !pickingMissed && (
                  <Button type="button" variant="secondary" onClick={() => setPickingMissed(true)}>
                    Close an even earlier day first
                  </Button>
                )}
                {pickingMissed && (
                  <div className="flex flex-wrap items-end gap-2">
                    <Field label="Which day?">
                      <Input type="date" max={today()}
                        onChange={(e) => { if (e.target.value) openDay(e.target.value); }} />
                    </Field>
                    <Button type="button" variant="ghost" onClick={() => setPickingMissed(false)}>Cancel</Button>
                  </div>
                )}
              </div>
            )}
            {!!postClosingRows.length && (
              <ul className="mt-5 grid gap-4">
                {postClosingRows.map((s) => {
                  const pc = s.post_closing!;
                  return (
                    <li key={s.account} className="rounded-control border border-warning bg-paper-2 px-4 py-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="font-medium text-ink">{s.name}</p>
                          <Badge tone="warning">Needs post-closing sign</Badge>
                        </div>
                        {can("cash-close") && (
                          <Button type="button" variant="secondary" onClick={() => openDay(today())}>Sign this account</Button>
                        )}
                      </div>
                      <dl className="mt-4 grid gap-3 sm:grid-cols-3">
                        <div className="rounded-control border border-rule bg-surface px-3 py-2">
                          <dt className="text-sm text-muted">Original close</dt>
                          <dd className="num mt-0.5 text-lg font-medium">{moneyExact(pc.original.counted)}</dd>
                          <dd className="mt-1 text-sm text-muted">{whenStamp(pc.original.at)}{pc.original.closed_by ? ` · ${pc.original.closed_by}` : ""}</dd>
                        </div>
                        <div className="rounded-control border border-rule bg-surface px-3 py-2">
                          <dt className="text-sm text-muted">New transactions</dt>
                          <dd className="num mt-0.5 text-lg font-medium">{Number(pc.change_since_sign) >= 0 ? "+" : "-"}{moneyExact(Math.abs(Number(pc.change_since_sign)))}</dd>
                          <dd className="mt-1 text-sm text-muted">{pc.movements.length} movement{pc.movements.length === 1 ? "" : "s"} after signing</dd>
                        </div>
                        <div className="rounded-control border border-rule bg-surface px-3 py-2">
                          <dt className="text-sm text-muted">Updated books now</dt>
                          <dd className="num mt-0.5 text-lg font-medium">{moneyExact(pc.books_now)}</dd>
                          <dd className="mt-1 text-sm text-muted">Sign this amount next</dd>
                        </div>
                      </dl>
                      {!!pc.movements.length && (
                        <ul className="mt-3 space-y-2 border-t border-rule pt-3">
                          {pc.movements.map((m, i) => (
                            <li key={`${m.number}-${i}`} className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                              <span className="text-ink-2">{whenStamp(m.at)} · {m.memo || m.number}</span>
                              <span className="num font-medium">{Number(m.amount) >= 0 ? "+" : "-"}{moneyExact(Math.abs(Number(m.amount)))}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            <ul className="mt-5 grid gap-3 sm:grid-cols-3">
              {rows.map((s) => {
                const forDay = nextDay && s.next_close_date === nextDay ? s.expected_on_next : null;
                const showCatchUp = catchingUp && forDay != null;
                return (
                  <li key={s.account} className="rounded-control border border-rule px-4 py-3">
                    <p className="font-medium">{s.name}</p>
                    {showCatchUp ? (
                      <>
                        <p className="mt-1 text-sm text-muted">Books at end of {day(nextDay!)}</p>
                        <p className="num text-lg">{moneyExact(forDay)}</p>
                        <p className="mt-2 text-sm text-muted">Today now: {moneyExact(s.expected)} (closes after {day(nextDay!)})</p>
                      </>
                    ) : (
                      <>
                        <p className="mt-1 text-sm text-muted">{nextDay === today() ? "Books for today" : "Books now"}</p>
                        <p className="num text-lg">{moneyExact(s.expected_on_next ?? s.expected)}</p>
                      </>
                    )}
                    <p className="mt-2 text-sm text-muted">
                      {s.post_closing?.needed ? "Signed earlier — needs post-closing recount"
                        : s.closed_today ? "Closed for today"
                          : s.last_close ? `Last counted ${day(s.last_close.close_date)}`
                            : "Never counted"}
                    </p>
                    {s.days_behind > 0 && s.next_close_date && (
                      <p className="mt-1 text-sm text-warning">
                        {s.days_behind === 1 ? `${day(s.next_close_date)} still open` : `${s.days_behind} days behind — next is ${day(s.next_close_date)}`}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </Card>
        )}

      {!sessionDay && (missed.error || missed.data) && (
        <Card title="Missed days">
          {missed.error ? <ErrorState message={missed.error} onRetry={missed.reload} />
            : !missed.data ? <SkeletonRows rows={3} />
              : (
                <div className="space-y-4">
                  {!missed.data.length ? (
                    <p className="text-sm text-muted">No skipped days found. Every signed stretch is complete.</p>
                  ) : (
                    <>
                      <Notice tone="warning">
                        {missed.data.length === 1
                          ? "One day still needs a signed count. Open it to sign the accounts listed."
                          : `${missed.data.length} days still need a signed count. Open each day and sign the accounts listed.`}
                      </Notice>
                      <ul className="grid gap-3">
                        {missed.data.map((m) => (
                          <li key={m.date} className="flex flex-wrap items-start justify-between gap-3 rounded-control border border-rule-strong bg-paper-2 px-4 py-3">
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                                <p className="font-medium text-ink">{day(m.date)}</p>
                                <p className="num text-sm font-medium text-ink">Day total {moneyExact(m.total)}</p>
                              </div>
                              <ul className="mt-3 grid gap-2 sm:grid-cols-3">
                                {(m.lines ?? []).map((line) => (
                                  <li key={line.account} className="rounded-control border border-rule bg-surface px-3 py-2">
                                    <p className="text-sm text-muted">{line.name}</p>
                                    <p className="num mt-0.5 font-medium">{moneyExact(line.expected)}</p>
                                  </li>
                                ))}
                              </ul>
                            </div>
                            {can("cash-close") && (
                              <Button type="button" variant="secondary" className="shrink-0 self-center" onClick={() => openDay(m.date)}>Sign this day</Button>
                            )}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                  {can("cash-close") && (
                    <div className={missed.data.length ? "border-t border-rule pt-4" : ""}>
                      {!pickingMissed
                        ? <Button type="button" variant="secondary" onClick={() => setPickingMissed(true)}>
                            {missed.data.length ? "Pick another date" : "Sign a missed day"}
                          </Button>
                        : (
                          <div className="flex flex-wrap items-end gap-2">
                            <Field label="Which day?">
                              <Input type="date" max={today()}
                                onChange={(e) => { if (e.target.value) openDay(e.target.value); }} />
                            </Field>
                            <Button type="button" variant="ghost" onClick={() => setPickingMissed(false)}>Cancel</Button>
                          </div>
                        )}
                    </div>
                  )}
                </div>
              )}
        </Card>
      )}

      <Card title="Past closes" flush>
        {history.error ? <ErrorState message={history.error} onRetry={history.reload} /> : !history.data ? <SkeletonRows rows={4} />
          : !history.data.length ? <EmptyState title="No closes yet">Each signed count appears here and cannot be changed.</EmptyState> : (
            <table className="table-stack w-full">
              <thead><tr className="text-left text-sm text-muted">
                <th className="px-4 py-2 font-normal shell:px-5">Day</th><th className="px-4 py-2 font-normal">Account</th>
                <th className="px-4 py-2 text-right font-normal">Books said</th><th className="px-4 py-2 text-right font-normal">Counted</th>
                <th className="px-4 py-2 text-right font-normal shell:pr-5">Difference</th>
              </tr></thead>
              <tbody>
                {history.data.map((c) => (
                  <tr key={c.id} className="border-t border-rule">
                    <td className="px-4 py-3 shell:px-5 max-sm:px-0">
                      <span className="font-medium">{day(c.close_date)}</span>
                      {c.closed_by && <span className="block text-sm text-muted">Signed by {c.closed_by}</span>}
                      {c.created_at && <span className="block text-sm text-muted">{whenStamp(c.created_at)}</span>}
                      {(c.sequence ?? 1) > 1 && <Badge tone="warning">Post-closing #{c.sequence}</Badge>}
                    </td>
                    <td data-label="Account" className="px-4 py-3 max-sm:px-0">{KIND[c.account]}</td>
                    <td data-label="Books said" className="num px-4 py-3 text-right max-sm:px-0">{moneyExact(c.expected)}</td>
                    <td data-label="Counted" className="num px-4 py-3 text-right max-sm:px-0">{moneyExact(c.counted)}</td>
                    <td data-label="Difference" className="px-4 py-3 text-right shell:pr-5 max-sm:px-0">
                      {Number(c.difference) === 0 ? <Badge tone="success">Matched</Badge> : <><span className="num block text-warning">{Number(c.difference) > 0 ? "+" : "-"}{moneyExact(Math.abs(Number(c.difference)))}</span><span className="block text-sm text-muted">{c.reason}</span></>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </Card>
    </div>
  );
}

function DaySession({ closeDate, accounts, canClose, onDone, onLeave, onContinue }: {
  closeDate: string; accounts: Status[]; canClose: boolean;
  onDone: () => void; onLeave: () => void; onContinue: (day: string) => void;
}) {
  const isToday = closeDate === today();
  const nextAfter = earliestOpenDay(accounts);
  const stillSequential = accounts.some((s) => s.next_close_date === closeDate);
  const postClosing = isToday && accounts.some((s) => s.post_closing?.needed);

  return (
    <div className="space-y-4">
      <Card
        title={postClosing ? "Post-closing recount for today" : isToday ? "Closing today" : `Closing ${day(closeDate)}`}
        actions={
          <div className="flex flex-wrap gap-2">
            {!stillSequential && nextAfter && nextAfter !== closeDate && (
              <Button type="button" onClick={() => onContinue(nextAfter)}>
                {nextAfter === today() ? "Close today next" : `Close ${day(nextAfter)} next`}
              </Button>
            )}
            <Button type="button" variant="secondary" onClick={onLeave}>Back</Button>
          </div>
        }
      >
        <p className="text-sm text-muted">
          {postClosing
            ? "Original closes are kept. Sign each account that still has new transactions after the last sign."
            : isToday
              ? "These are today's book totals. Sign cash, bank and mobile wallet."
              : `These are the books as of the end of ${day(closeDate)}. Sign each account that still needs this day — including a skipped month-end day after later closes.`}
        </p>
      </Card>
      <div className="grid gap-4 shell:grid-cols-3">
        {accounts.map((s) => (
          <AccountForDay key={`${s.account}-${closeDate}`} s={s} closeDate={closeDate} canClose={canClose} onDone={onDone} />
        ))}
      </div>
    </div>
  );
}

function AccountForDay({ s, closeDate, canClose, onDone }: { s: Status; closeDate: string; canClose: boolean; onDone: () => void }) {
  const [info, setInfo] = useState<DayExpected | null>(null);
  const [counting, setCounting] = useState(false);
  const [expected, setExpected] = useState<number | null>(null);
  const [counted, setCounted] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const diff = expected != null && /^\d/.test(counted) ? moneyDiff(counted, expected) : null;
  const { errors, activate, live } = useLiveErrors({ counted, reason, note: "" }, (v) => {
    if (expected == null) return {};
    const r = closeSchema(expected).safeParse(v);
    return r.success ? {} : issuesToFieldErrors(r.error.issues);
  });

  async function load() {
    setLoading(true);
    try {
      const r = await api<DayExpected>(`/api/cash-closes/expected?account=${s.account}&on=${closeDate}`);
      setInfo(r);
      setExpected(Number(r.expected));
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [s.account, closeDate]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (expected == null) return;
    activate();
    const r = closeSchema(expected).safeParse({ counted, reason, note: "" });
    if (!r.success) return;
    setBusy(true);
    setError(null);
    try {
      await api("/api/cash-closes", { method: "POST", json: { account: s.account, close_date: closeDate, counted, reason: diff ? reason : "" } });
      setCounting(false);
      await load();
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  const already = !!info?.already_closed && !info?.post_closing;
  const canSign = !!info?.can_sign;
  const pc = closeDate === today() ? s.post_closing : null;

  return (
    <Card title={s.name}>
      <p className="text-sm text-muted">{info?.post_closing ? "Updated books now (after new transactions)" : `Books at the end of ${day(closeDate)}`}</p>
      <p className="num text-xl">{loading && expected == null ? "…" : moneyExact(expected ?? 0)}</p>
      {expected != null && expected < 0 && (
        <p className="mt-1 text-sm text-error">Less than nothing? The opening balance may be missing. The owner can set it under Money settings.</p>
      )}

      {pc?.needed && (
        <div className="mt-3 space-y-2 rounded-control border border-warning bg-paper-2 px-3 py-2 text-sm">
          <p className="font-medium text-ink">Original close {moneyExact(pc.original.counted)} · {whenStamp(pc.original.at)}</p>
          <p className="text-muted">New movements {Number(pc.change_since_sign) >= 0 ? "+" : "-"}{moneyExact(Math.abs(Number(pc.change_since_sign)))} · updated total {moneyExact(pc.books_now)}</p>
        </div>
      )}

      {already && !counting && <div className="mt-3"><Badge tone="success">Signed for this day</Badge></div>}
      {info?.post_closing && !counting && <div className="mt-3"><Badge tone="warning">Post-closing recount needed</Badge></div>}
      {info?.gap_fill && !info?.already_closed && (
        <p className="mt-3 text-sm text-warning">
          Later days are already signed (through {info.later_through ? day(info.later_through) : "…"}). Signing here records the missed day for month end without changing today&apos;s books.
        </p>
      )}
      {info?.must_close_first && (
        <p className="mt-3 text-sm text-warning">Close {day(info.must_close_first)} for this account first.</p>
      )}
      {!loading && !canSign && !info?.must_close_first && !info?.post_closing && (
        <p className="mt-3 text-sm text-muted">Nothing to sign for this day on this account.</p>
      )}

      {canClose && canSign && !counting && (
        <div className="mt-4">
          <Button onClick={() => {
            setCounting(true);
            setError(null);
            setReason("");
            if (expected != null) setCounted(expected.toFixed(2));
          }}>{info?.post_closing ? "Count and sign post-closing" : "Count and sign"}</Button>
        </div>
      )}

      {counting && expected != null && (
        <form noValidate onSubmit={submit} className="mt-4 space-y-4" {...live}>
          <Field label="What was really in it (Rs)" error={errors.counted}>
            <Input inputMode="decimal" value={counted} onChange={(e) => setCounted(e.target.value)} autoFocus />
          </Field>
          {diff !== null && diff !== 0 && (
            <>
              <Notice tone="warning">{`${moneyExact(Math.abs(diff))} ${diff > 0 ? "over" : "short"} compared with the books.`}</Notice>
              <Field label="Why does it differ?" error={errors.reason}><Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} /></Field>
            </>
          )}
          {diff === 0 && <p className="text-sm text-success">Matches the books.</p>}
          <Notice>{error}</Notice>
          <p className="text-sm text-muted">
            {info?.gap_fill
              ? "Signing records this missed day for the month-end checklist. Today's running books stay as they are."
              : "Signing is final. A difference is recorded in the books so the next day starts from what you counted."}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={busy}>{busy ? "Signing" : "Sign the count"}</Button>
            <Button type="button" variant="secondary" onClick={() => setCounting(false)}>Cancel</Button>
          </div>
        </form>
      )}
      <Notice>{!counting ? error : null}</Notice>
    </Card>
  );
}
