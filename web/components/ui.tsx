import { Children, cloneElement, isValidElement, type ButtonHTMLAttributes, type ChangeEvent, type ClipboardEvent, type InputHTMLAttributes, type KeyboardEvent, type ReactElement, type ReactNode, type SelectHTMLAttributes } from "react";
import { qtyInputMode, qtyMin, qtyStep, qtyWhole, sanitizeQty } from "@/lib/format";

// Every control is at least 44px tall (a finger, not a cursor) and changes
// only colour on hover/press, never size.
const control =
  "min-h-11 cursor-pointer rounded-control border px-3 text-base transition-colors duration-(--dur-micro) " +
  "disabled:cursor-not-allowed disabled:opacity-55";

const buttonVariants = {
  primary: "border-action bg-action text-action-ink hover:bg-action-2 hover:border-action-2 active:bg-action-3 active:border-action-3",
  secondary: "border-rule-strong bg-surface text-ink hover:border-ink-2 hover:bg-paper-3 active:bg-silver active:border-ink-2",
  // Destructive: delete, discard, void, cancel permanently, reject.
  danger: "border-error bg-error text-error-ink hover:bg-error-2 hover:border-error-2 active:bg-error-3 active:border-error-3",
  // Persist / finish: save, save draft, mark complete.
  success: "border-success bg-success text-success-ink hover:bg-success-2 hover:border-success-2 active:bg-success-3 active:border-success-3",
  // A quiet button, but still a visible one: a filled pill, never bare text that could be a label.
  ghost: "border-transparent bg-paper-3 text-ink hover:border-rule-strong hover:bg-silver active:bg-rule-strong",
};

export function Button({ variant = "primary", className = "", ...props }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof buttonVariants }) {
  return (
    <button
      // Colour-only transitions (DESIGN.md); the pressed colour lands instantly so a tap feels immediate.
      className={`${control} inline-flex shrink-0 items-center justify-center gap-2 px-5 text-[0.9375rem] font-medium active:duration-0 ${buttonVariants[variant]} ${className}`}
      {...props}
    />
  );
}

const field =
  `${control} w-full border-rule-strong bg-surface text-ink placeholder:text-muted ` +
  "hover:border-ink-2 focus-visible:border-ink aria-invalid:border-error";

const TEXTY = new Set([undefined, "text", "search", "tel", "email", "url", "password"]);

/** A text box never takes endless text: 160 characters unless the field sets its own limit. */
export function Input({ maxLength, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={field} maxLength={maxLength ?? (TEXTY.has(props.type) ? 160 : undefined)} {...props} />;
}

type QtyInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "inputMode" | "step" | "onChange" | "value"> & {
  unit?: string;
  /** When set, the field is controlled; otherwise it is uncontrolled (forms that read FormData). */
  value?: string | number;
  onChange?: (value: string) => void;
};

/** Quantity field that refuses wrong keystrokes: pcs/set/pair/box = whole digits only; litre/kg/metre allow thousandths. */
export function QtyInput({ unit, value, defaultValue, onChange, min, className = "", ...props }: QtyInputProps) {
  const whole = qtyWhole(unit);
  function change(e: ChangeEvent<HTMLInputElement>) {
    const next = sanitizeQty(e.target.value, unit);
    if (value === undefined) e.target.value = next; // keep uncontrolled inputs clean as you type
    onChange?.(next);
  }
  function keyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const block = whole
      ? e.key === "." || e.key === "," || e.key === "e" || e.key === "E" || e.key === "+" || e.key === "-"
      : e.key === "e" || e.key === "E" || e.key === "+" || e.key === "-";
    if (block) e.preventDefault();
    props.onKeyDown?.(e);
  }
  function paste(e: ClipboardEvent<HTMLInputElement>) {
    const text = e.clipboardData.getData("text");
    const cleaned = sanitizeQty(text, unit);
    if (cleaned === text) { props.onPaste?.(e); return; }
    e.preventDefault();
    if (value === undefined) {
      const el = e.currentTarget;
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? el.value.length;
      const next = sanitizeQty(`${el.value.slice(0, start)}${cleaned}${el.value.slice(end)}`, unit);
      el.value = next;
      onChange?.(next);
    } else {
      onChange?.(sanitizeQty(`${String(value ?? "").slice(0, e.currentTarget.selectionStart ?? 0)}${cleaned}${String(value ?? "").slice(e.currentTarget.selectionEnd ?? 0)}`, unit));
    }
    props.onPaste?.(e);
  }
  const mode = qtyInputMode(unit) as "numeric" | "decimal";
  const shared = {
    ...props,
    type: "text" as const, // text + inputMode: native number inputs still allow "." on many browsers
    inputMode: mode,
    min: min ?? qtyMin(unit),
    step: qtyStep(unit),
    className: `${field} ${className}`,
    onChange: change,
    onKeyDown: keyDown,
    onPaste: paste,
  };
  return value !== undefined
    ? <input {...shared} value={String(value)} />
    : <input key={unit} {...shared} defaultValue={defaultValue !== undefined ? sanitizeQty(String(defaultValue), unit) : undefined} />;
}

export function Select({ className = "", ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`${field} pr-8 ${className}`} {...props} />;
}

/** A labelled control. `error` (from parseForm / liveForm) replaces the hint and outlines the control in red.
 *  Uses a group, not a <label>: wrapping buttons/checkboxes in a label makes the browser treat the first
 *  button as the labelled control, so a click near Fits chips removed a car without pressing ×. */
export function Field({ label, hint, error, required, children }: { label: string; hint?: string; error?: string; required?: boolean; children: ReactNode }) {
  // A star only where the control is really required (or the form says so with `required`).
  const childRequired = Children.toArray(children).some((c) => isValidElement(c) && !!(c.props as { required?: boolean }).required);
  const marked = Children.map(children, (child) => {
    if (!isValidElement(child)) return child;
    return cloneElement(child as ReactElement<{ "aria-invalid"?: boolean }>, { "aria-invalid": !!error || undefined });
  });
  return (
    <div role="group" className={`flex min-w-0 flex-col gap-1.5 ${error ? "[&_:is(input,select,textarea)]:border-error" : ""}`}>
      <span className="text-[0.9375rem] font-medium text-ink-2">{label}{(required ?? childRequired) && <span className="req ml-0.5 text-error" aria-hidden="true">*</span>}</span>
      {marked}
      {error ? <span aria-live="polite" className="text-sm text-error">{error === "Required" ? `Please fill in: ${label.replace(/\s*\(.*\)\s*$/, "").replace(/\b(?![A-Z]{2,}\b)\w+/g, (w) => w.toLowerCase())}` : error}</span>
        : hint && <span className="text-sm text-muted">{hint}</span>}
    </div>
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
  warning: "bg-warning-soft text-warning border-transparent border-l-[3px] border-l-amber",
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
    <section className="min-w-0 rounded-card bg-surface">
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
    <div aria-busy="true" aria-label="Loading" className="skeleton-wait space-y-3 p-4 shell:p-5">
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
    accent: "bg-paper-3 text-primary font-medium",
  }[tone];
  return <span className={`inline-flex items-center rounded-control px-2 py-0.5 text-sm font-medium ${styles}`}>{children}</span>;
}
