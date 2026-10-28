"use client";

export type VisitSummary = {
  id: string; number: string; kind: "workshop" | "pre_purchase"; status: "open" | "closed" | "cancelled";
  checked_in_at: string; closed_at: string | null; odometer_in: number | null; complaint: string;
  car: { id: string; plate: string; make: string; model: string; year: number | null };
  customer: { id: string; name: string; phone: string; number: string };
  buyer: { id: string; name: string; phone: string; number: string } | null;
};

/** Fuel level in eighths: eight large taps instead of a fiddly slider. */
export function FuelGauge({ value, onChange }: { value: number | null; onChange: (v: number) => void }) {
  return (
    <div role="radiogroup" aria-label="Fuel level" className="flex gap-1">
      {Array.from({ length: 9 }, (_, i) => (
        <button
          key={i}
          type="button"
          role="radio"
          aria-checked={value === i}
          aria-label={i === 0 ? "Empty" : i === 8 ? "Full" : `${i}/8`}
          onClick={() => onChange(i)}
          className={`flex min-h-11 flex-1 items-end justify-center rounded-[3px] border pb-1 text-xs transition-colors duration-(--dur-micro) ${
            value !== null && i <= value && i > 0 ? "border-ink bg-ink text-surface" : "border-rule-strong bg-surface text-muted"
          } ${value === i ? "ring-2 ring-focus ring-offset-1" : ""}`}
        >
          {i === 0 ? "E" : i === 8 ? "F" : i === 4 ? "½" : ""}
        </button>
      ))}
    </div>
  );
}

export const elapsed = (from: string) => {
  const mins = Math.max(0, Math.round((Date.now() - new Date(from).getTime()) / 60000));
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  return h < 48 ? `${h} h` : `${Math.floor(h / 24)} days`;
};
