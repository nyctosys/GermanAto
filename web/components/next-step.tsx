import Link from "next/link";
import type { ReactNode } from "react";

/**
 * The one thing to do next in a workflow, set apart so nobody has to hunt for it:
 * a tinted card with a teal bar, an arrow, the instruction, and (optionally) the button that does it.
 */
export function NextStep({ children, who, href, label, onClick, disabled, target, open = true }:
  { children: ReactNode; who?: string; href?: string; label?: string; onClick?: () => void; disabled?: boolean;
    /** id of the button or field to go to. `open: false` only scrolls to it and focuses it (for buttons that commit an action). */
    target?: string; open?: boolean }) {
  const go = () => {
    const el = document.getElementById(target!);
    if (!el) return;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    if (open && el instanceof HTMLButtonElement) el.click(); else el.focus({ preventScroll: true });
  };
  const cls = "inline-flex min-h-11 items-center justify-center rounded-control border border-primary bg-primary px-5 text-[0.9375rem] font-medium text-primary-ink hover:bg-primary-2 active:bg-primary-3 active:duration-0 disabled:opacity-55";
  return (
    <div role="note" aria-label="Next step" className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-3 rounded-card border-l-4 border-primary bg-primary/10 px-4 py-3 shell:px-5">
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="mt-0.5 shrink-0 text-primary"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
        <p className="min-w-0"><span className="font-semibold text-primary">Next step: </span>{children}{who && <span className="text-sm text-muted"> For: {who}.</span>}</p>
      </div>
      {label && (href ? <Link href={href} className={cls}>{label}</Link> : <button type="button" className={cls} onClick={target ? go : onClick} disabled={disabled}>{label}</button>)}
    </div>
  );
}
