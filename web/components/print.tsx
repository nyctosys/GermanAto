"use client";

import Image from "next/image";
import Link from "next/link";
import { type ReactNode, useRef, useState } from "react";
import { phone } from "@/lib/format";
import { downloadXlsx, sheetFromDocument } from "@/lib/xlsx";

/** A4 at 96 dpi: the width the document is laid out at when it is turned into a PDF, whatever the screen. */
const A4_PX = 794;

/** Draws the document into an A4 PDF. The bar and anything marked no-print are left out. */
async function makePdf(root: HTMLElement): Promise<Blob> {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([import("html2canvas-pro"), import("jspdf")]);
  const clone = root.cloneNode(true) as HTMLElement;
  clone.querySelectorAll(".no-print").forEach((n) => n.remove());
  Object.assign(clone.style, { position: "fixed", left: "-10000px", top: "0", width: `${A4_PX}px`, maxWidth: "none", background: "#fff", padding: "40px" });
  document.body.appendChild(clone);
  try {
    await Promise.all([...clone.querySelectorAll("img")].map((i) => (i.complete ? Promise.resolve() : new Promise((r) => { i.onload = i.onerror = r; }))));
    const canvas = await html2canvas(clone, { scale: 2, useCORS: true, backgroundColor: "#ffffff", windowWidth: A4_PX });
    const pdf = new jsPDF({ unit: "mm", format: "a4" });
    const pageH = 297, width = 210, height = (canvas.height * width) / canvas.width;
    const img = canvas.toDataURL("image/jpeg", 0.92);
    for (let y = 0, page = 0; y < height - 0.5; y += pageH, page++) {
      if (page) pdf.addPage();
      pdf.addImage(img, "JPEG", 0, -y, width, height); // each page shows the next slice of the one tall image
    }
    return pdf.output("blob");
  } finally {
    clone.remove();
  }
}

const slug = (v: string) => v.replace(/[^A-Za-z0-9._-]+/g, "-");
const pill = "inline-flex min-h-11 items-center justify-center rounded-control border px-5 text-[0.9375rem] font-medium transition-colors duration-(--dur-micro) active:duration-0 disabled:cursor-not-allowed disabled:opacity-55";

/** Every printed document: A4 portrait with 12 mm margins, black on white, table headings repeated on each page,
 *  and no row, list item or heading left stranded across a page break. Applied by the bar, so no page can forget it. */
const A4_CSS = `@page { size: A4 portrait; margin: 12mm; }
@media print {
  html, body { background: #fff !important; color: #000; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  main { max-width: none !important; padding: 0 !important; }
  table { width: 100%; }
  thead { display: table-header-group; }
  tfoot { display: table-footer-group; }
  tr, li, figure, img { break-inside: avoid; }
  h1, h2, h3 { break-after: avoid; }
  a { color: inherit !important; text-decoration: none !important; }
}`;

/**
 * The bar above every printed document: back to where it came from, print or save as PDF, share
 * the PDF with another app (WhatsApp, email, Drive), and a shortcut that opens a WhatsApp chat
 * with the customer. It never prints itself.
 */
export function PrintBar({ back, name, whatsapp, children }:
  { back: { href: string; label: string }; name: string; whatsapp?: { phone?: string; text: string }; children?: ReactNode }) {
  const bar = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState<"share" | "whatsapp" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const filename = `${slug(name)}.pdf`;

  const pdf = () => makePdf(bar.current!.parentElement as HTMLElement);
  const save = (blob: Blob) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  };

  async function share() {
    setBusy("share");
    setMessage(null);
    try {
      const file = new File([await pdf()], filename, { type: "application/pdf" });
      if (typeof navigator.share === "function" && navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: name, text: whatsapp?.text });
      } else {
        save(file);
        setMessage("This browser can't share files directly, so the PDF was saved to your downloads. Attach it in the app you want to send it with.");
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") setMessage(`The PDF could not be made: ${(err as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  async function chat() {
    if (!whatsapp) return;
    setBusy("whatsapp");
    setMessage(null);
    const digits = (whatsapp.phone ?? "").replace(/\D/g, "");
    // Opened first, straight from the tap, so the browser doesn't block it as a pop-up.
    window.open(`https://wa.me/${digits}?text=${encodeURIComponent(whatsapp.text)}`, "_blank", "noopener");
    try {
      save(await pdf());
      setMessage("WhatsApp opened with the message. The PDF is in your downloads: attach it to the chat.");
    } catch (err) {
      setMessage(`The PDF could not be made: ${(err as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div ref={bar} className="no-print mb-4 space-y-2">
      <style>{A4_CSS}</style>
      <div className="flex flex-wrap items-center gap-2">
        <Link href={back.href} className={`${pill} border-rule-strong bg-surface text-ink hover:bg-paper active:bg-paper-3`}>
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" className="mr-2"><path d="M10 3L5 8l5 5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
          {back.label}
        </Link>
        <button onClick={() => window.print()} className={`${pill} border-action bg-action text-action-ink hover:bg-action-2 hover:border-action-2 active:bg-action-3 active:border-action-3`}>Print or save as PDF</button>
        <button onClick={share} disabled={busy !== null} className={`${pill} border-rule-strong bg-surface text-ink hover:bg-paper active:bg-paper-3`}>{busy === "share" ? "Making the PDF" : "Share as PDF"}</button>
        <button onClick={() => downloadXlsx(`${slug(name)}.xlsx`, [sheetFromDocument(bar.current!.parentElement as HTMLElement, name.slice(0, 31))])} className={`${pill} border-rule-strong bg-surface text-ink hover:bg-paper active:bg-paper-3`}>Download for Excel</button>
        {whatsapp && <button onClick={chat} disabled={busy !== null} className={`${pill} border-rule-strong bg-surface text-ink hover:bg-paper active:bg-paper-3`}>{busy === "whatsapp" ? "Opening" : "Send on WhatsApp"}</button>}
      </div>
      {children}
      {message && <p role="status" className="rounded-control border border-rule bg-paper-2 px-3 py-2 text-sm text-ink-2">{message}</p>}
    </div>
  );
}

export function Letterhead({ branch, title, right }: { branch: { name: string; address: string; phone: string; ntn?: string }; title: string; right: ReactNode }) {
  return (
    <header className="mb-4 flex items-start justify-between gap-4 border-b-2 border-ink pb-3">
      <div className="flex items-center gap-3">
        <Image src="/logo.png" alt="" width={56} height={56} />
        <div>
          <p className="text-xl font-bold tracking-tight">{branch.name.toUpperCase()}</p>
          <p className="text-muted">{[branch.address, branch.phone && phone(branch.phone)].filter(Boolean).join(", ")}</p>
          {branch.ntn ? <p className="text-muted">NTN {branch.ntn}</p> : null}
        </div>
      </div>
      <div className="text-right">
        <p className="text-lg font-bold">{title}</p>
        {right}
      </div>
    </header>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-4 break-inside-avoid-page">
      <p className="mb-1 bg-ink px-2 py-1 font-bold text-accent-ink [print-color-adjust:exact]">{title.toUpperCase()}</p>
      {children}
    </section>
  );
}

export function Grid({ head, rows, right = [] }: { head: string[]; rows: ReactNode[][]; right?: number[] }) {
  return (
    <div className="mb-2 overflow-x-auto print:overflow-visible">
    <table className="w-full border-collapse">
      <thead><tr className="[print-color-adjust:exact]">{head.map((h, i) => <th key={h} className={`border border-rule bg-paper-2 px-2 py-1 ${right.includes(i) ? "text-right" : "text-left"}`}>{h}</th>)}</tr></thead>
      <tbody>
        {rows.length ? rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={`border border-rule px-2 py-1 align-top ${right.includes(j) ? "num text-right" : ""}`}>{c}</td>)}</tr>)
          : <tr><td colSpan={head.length} className="border border-rule px-2 py-1 text-muted">None</td></tr>}
      </tbody>
    </table>
    </div>
  );
}
