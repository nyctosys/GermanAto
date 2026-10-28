"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";

export type Uploaded = { id: string; url: string; name: string; mime?: string };

export async function upload(file: Blob, name: string, note = ""): Promise<Uploaded> {
  const form = new FormData();
  form.set("file", file, name);
  if (note) form.set("note", note);
  const a = await api<{ id: string; url: string; original_name: string; mime: string }>("/api/attachments", { method: "POST", body: form });
  return { id: a.id, url: a.url, name: a.original_name, mime: a.mime };
}

/** Take or pick photos (or PDFs); each uploads as soon as it is chosen. */
export function PhotoCapture({ value, onChange, note, label = "Add photos", accept = "image/*" }:
  { value: Uploaded[]; onChange: (v: Uploaded[]) => void; note?: string; label?: string; accept?: string }) {
  const [busy, setBusy] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function add(files: FileList | null) {
    if (!files?.length) return;
    setError(null);
    setBusy(files.length);
    const added: Uploaded[] = [];
    for (const f of Array.from(files)) {
      try {
        added.push(await upload(f, f.name, note));
      } catch (e) {
        setError(`${f.name}: ${(e as Error).message}`);
      }
      setBusy((b) => b - 1);
    }
    onChange([...value, ...added]);
  }

  return (
    <div className="space-y-3">
      {value.length > 0 && (
        <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4 shell:grid-cols-6">
          {value.map((p) => (
            <li key={p.id} className="relative aspect-square overflow-hidden rounded-control border border-rule bg-paper-2">
              {p.mime === "application/pdf" ? (
                <a href={p.url} target="_blank" rel="noreferrer" className="flex h-full items-center justify-center p-2 text-center text-sm underline">{p.name}</a>
              ) : (
                // eslint-disable-next-line @next/next/no-img-element -- authenticated API files, not static assets
                <img src={p.url} alt={p.name} className="h-full w-full object-cover" />
              )}
              <button type="button" aria-label={`Remove ${p.name}`} onClick={() => onChange(value.filter((x) => x.id !== p.id))}
                      className="absolute right-1 top-1 flex size-9 items-center justify-center rounded-full bg-ink/70 text-accent-ink">
                <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
              </button>
            </li>
          ))}
        </ul>
      )}
      <label className="flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-control border border-dashed border-rule-strong bg-surface px-4 text-ink-2 hover:bg-paper-2 active:bg-paper-3">
        <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 6.5h3l1.5-2h5L14 6.5h3v9H3z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /><circle cx="10" cy="11" r="2.8" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
        {busy > 0 ? `Uploading ${busy}` : label}
        <input type="file" accept={accept} multiple capture="environment" className="sr-only" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      </label>
      {error && <p role="alert" className="text-sm text-error">{error}</p>}
    </div>
  );
}

/**
 * Finger or stylus signature. The stroke follows the pointer 1:1 and keeps
 * tracking if it leaves the pad (pointer capture), drawn at device resolution.
 */
export function SignaturePad({ label, onChange }: { label: string; onChange: (blob: Blob | null) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const [empty, setEmpty] = useState(true);

  useEffect(() => {
    const c = canvas.current!;
    const ratio = window.devicePixelRatio || 1;
    const { width, height } = c.getBoundingClientRect();
    c.width = width * ratio;
    c.height = height * ratio;
    const ctx = c.getContext("2d")!;
    ctx.scale(ratio, ratio);
    ctx.lineWidth = 2.2;
    ctx.lineCap = ctx.lineJoin = "round";
    ctx.strokeStyle = getComputedStyle(c).color;
  }, []);

  const point = (e: React.PointerEvent) => {
    const r = canvas.current!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top] as const;
  };

  function finish() {
    if (!drawing.current) return;
    drawing.current = false;
    canvas.current!.toBlob((b) => onChange(b), "image/png");
  }

  function clear() {
    const c = canvas.current!;
    c.getContext("2d")!.clearRect(0, 0, c.width, c.height);
    setEmpty(true);
    onChange(null);
  }

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-sm font-medium text-ink-2">{label}</span>
        {!empty && <Button type="button" variant="ghost" onClick={clear}>Clear</Button>}
      </div>
      <canvas
        ref={canvas}
        aria-label={label}
        className="h-40 w-full touch-none rounded-control border border-rule-strong bg-surface text-ink"
        onPointerDown={(e) => {
          try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* capture is a nicety; drawing still works */ }
          drawing.current = true;
          setEmpty(false);
          const ctx = e.currentTarget.getContext("2d")!;
          const [x, y] = point(e);
          ctx.beginPath();
          ctx.moveTo(x, y);
          ctx.lineTo(x + 0.1, y + 0.1); // a tap leaves a dot
          ctx.stroke();
        }}
        onPointerMove={(e) => {
          if (!drawing.current) return;
          const ctx = e.currentTarget.getContext("2d")!;
          // Coalesced events keep fast strokes smooth instead of joining sparse samples.
          for (const ev of e.nativeEvent.getCoalescedEvents?.() ?? [e.nativeEvent]) {
            const r = e.currentTarget.getBoundingClientRect();
            ctx.lineTo(ev.clientX - r.left, ev.clientY - r.top);
          }
          ctx.stroke();
        }}
        onPointerUp={finish}
        onPointerCancel={finish}
      />
      {empty && <p className="mt-1 text-sm text-muted">Sign with a finger or stylus.</p>}
    </div>
  );
}
