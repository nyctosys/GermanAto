import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox, Loading, PageHeader } from '../components/ui'
import { PrintShell } from '../print/PrintShell'

/** Full entry→exit printable packet for a car (composes available stage payloads). */
export function EntryExitPacketPage() {
  const { id } = useParams()

  const history = useQuery({
    queryKey: ['car-history-packet', id],
    queryFn: () => api.get<{ events?: Array<Record<string, unknown>> }>(`/api/cars/${id}/history`),
    enabled: !!id,
  })

  if (history.isLoading) return <Loading />
  if (history.error) return <ErrorBox error={history.error} />

  const events = history.data?.events || []

  return (
    <div>
      <PageHeader title={`Entry → exit packet · Car #${id}`} />
      <PrintShell
        title="Entry-to-Exit packet"
        meta={
          <>
            <div>Car ID: {id}</div>
            <div>Events: {events.length}</div>
          </>
        }
      >
        <h3>Timeline</h3>
        <table className="print-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Type</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {events.map((ev, i) => (
              <tr key={i}>
                <td>{String(ev.at || ev.created_at || '')}</td>
                <td>{String(ev.type || ev.kind || '')}</td>
                <td>{String(ev.summary || ev.title || ev.details || '')}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="print-page-break" />
        <p>
          Packet includes linked check-in, job card, quotation, variations, repair order, parts,
          payments, QC, and handover records from car history. Print individual stage sheets from
          their detail pages for full A4 forms.
        </p>
      </PrintShell>
    </div>
  )
}
