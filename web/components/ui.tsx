import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

// Every control is at least 44px tall (a finger, not a cursor) and changes
// only colour on hover/press, never size.
const control =
  "min-h-11 rounded-control border px-3 text-base transition-colors duration-(--dur-micro) " +
  "disabled:cursor-not-allowed disabled:opacity-55";

const buttonVariants = {
  primary: "border-accent bg-accent text-accent-ink hover:bg-accent-2 hover:border-accent-2 active:bg-accent-2",
  secondary: "border-rule-strong bg-surface text-ink hover:bg-paper-2 active:bg-paper-3",
  danger: "border-error bg-surface text-error hover:bg-error-soft active:bg-error-soft",
  ghost: "border-transparent bg-transparent text-ink-2 hover:bg-paper-3 active:bg-paper-3",
};

export function Button({ variant = "primary", className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof buttonVariants }) {
  return (
    <button
      className={`${control} inline-flex shrink-0 items-center justify-center gap-2 px-4 font-medium ${buttonVariants[variant]} ${className}`}
      {...props}
    />
  );
}

const field =
  `${control} w-full border-rule-strong bg-surface text-ink placeholder:text-muted ` +
  "hover:border-muted focus-visible:border-accent aria-invalid:border-error";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={field} {...props} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${field} pr-8`} {...props} />;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5">
      <span className="text-sm font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="text-sm text-muted">{hint}</span>}
    </label>
  );
}

/** A checkbox whose whole row is the hit target. */
export function Checkbox({ label, hint, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; hint?: string }) {
  return (
    <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-control px-1 py-2.5 hover:bg-paper-2">
      <input type="checkbox" className="mt-0.5 size-5 shrink-0 accent-accent" {...props} />
      <span className="text-base leading-snug">
        {label}
        {hint && <span className="block text-sm text-muted">{hint}</span>}
      </span>
    </label>
  );
}

const tones = {
  error: "bg-error-soft text-error border-error/25",
  success: "bg-success-soft text-success border-success/25",
  warning: "bg-warning-soft text-warning border-warning/25",
};

export function Notice({ tone = "error", children }: { tone?: keyof typeof tones; children: ReactNode }) {
  if (!children) return null;
  return (
    <p role={tone === "error" ? "alert" : "status"} className={`whitespace-pre-line rounded-control border px-3 py-2.5 text-sm ${tones[tone]}`}>
      {children}
    </p>
  );
}

export function Card({ title, actions, children, flush = false }:
  { title?: string; actions?: ReactNode; children: ReactNode; flush?: boolean }) {
  return (
    <section className="min-w-0 rounded-card border border-rule bg-surface">
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-4 py-3 shell:px-5">
          {title && <h2>{title}</h2>}
          {actions}
        </header>
      )}
      <div className={flush ? "" : "p-4 shell:p-5"}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1>{title}</h1>
        {description && <p className="mt-1 max-w-[60ch] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

// The four states of anything that loads data: loading, empty, error, full.

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="space-y-3 p-4 shell:p-5">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex gap-4">
          <div className="skeleton h-5 w-1/3" />
          <div className="skeleton h-5 flex-1" />
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 p-6">
      <p className="font-medium">{title}</p>
      {children && <p className="max-w-[55ch] text-muted">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 p-6">
      <p className="font-medium text-error">This didn&apos;t load</p>
      <p className="max-w-[55ch] text-muted">{message}</p>
      {onRetry && <Button variant="secondary" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "success" | "warning" | "error" | "accent"; children: ReactNode }) {
  const styles = {
    neutral: "bg-paper-3 text-ink-2",
    success: "bg-success-soft text-success",
    warning: "bg-warning-soft text-warning",
    error: "bg-error-soft text-error",
    accent: "bg-accent-soft text-accent",
  }[tone];
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-medium ${styles}`}>{children}</span>;
}
