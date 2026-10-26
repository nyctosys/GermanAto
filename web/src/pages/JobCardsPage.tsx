import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { Empty, ErrorBox, Loading, PageHeader, Panel } from '../components/ui'

type JobCardRow = {
  id: number
  customer_name?: string
  customer_reg_no?: string
  status?: string
  visit_id?: number
  quote_invoice_id?: number
  created_at?: string
}

export function JobCardsPage() {
  const qc = useQueryClient()
  const list = useQuery({
    queryKey: ['job-cards'],
    queryFn: () => api.get<JobCardRow[]>('/api/job-cards'),
  })

  const makeQuote = useMutation({
    mutationFn: (id: number) => api.post(`/api/job-cards/${id}/quote`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['job-cards'] }),
  })

  return (
    <div>
      <PageHeader
        title="Job cards"
        actions={
          <Link className="btn" to="/job-cards/new">
            New job card
          </Link>
        }
      />
      <Panel title="Open / recent">
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {makeQuote.error ? <ErrorBox error={makeQuote.error} /> : null}
        {!list.isLoading && !(list.data || []).length ? <Empty /> : null}
        {(list.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Customer</th>
                  <th>Reg</th>
                  <th>Status</th>
                  <th>Visit</th>
                  <th>Quote</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data || []).map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link to={`/job-cards/${r.id}`}>{r.id}</Link>
                    </td>
                    <td>{r.customer_name}</td>
                    <td>{r.customer_reg_no}</td>
                    <td>{r.status}</td>
                    <td>{r.visit_id || '—'}</td>
                    <td>{r.quote_invoice_id || '—'}</td>
                    <td>
                      {!r.quote_invoice_id ? (
                        <button type="button" className="btn btn-ghost" onClick={() => makeQuote.mutate(r.id)}>
                          Build quote
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Panel>
    </div>
  )
}
