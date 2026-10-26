import type { ReactNode } from 'react'
import './print.css'

export function PrintShell({
  title,
  meta,
  children,
}: {
  title: string
  meta?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="print-root">
      <div className="print-header">
        <div className="print-brand">GermanATO</div>
        <div className="print-doc-title">{title}</div>
      </div>
      {meta ? <div className="print-meta">{meta}</div> : null}
      {children}
      <div className="print-footer">
        <div className="print-sign">Advisor</div>
        <div className="print-sign">Customer</div>
        <div className="print-qr">QR / doc id</div>
      </div>
      <p className="no-print" style={{ marginTop: 16 }}>
        <button type="button" className="btn" onClick={() => window.print()}>
          Print
        </button>
      </p>
    </div>
  )
}
