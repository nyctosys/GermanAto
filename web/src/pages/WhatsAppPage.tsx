import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api } from '../api/client'
import {
  Empty,
  ErrorBox,
  Field,
  FormGrid,
  Loading,
  PageHeader,
  Panel,
} from '../components/ui'

type Notification = {
  id: number
  phone?: string
  message?: string
  status?: string
  created_at?: string
  type?: string
}

export function WhatsAppPage() {
  const qc = useQueryClient()
  const [testPhone, setTestPhone] = useState('')
  const [testMessage, setTestMessage] = useState('GermanATO test message')

  const list = useQuery({
    queryKey: ['whatsapp-notifications'],
    queryFn: async () => {
      const data = await api.get<
        Notification[] | { notifications: Notification[] }
      >('/api/whatsapp/notifications')
      return Array.isArray(data) ? data : data.notifications || []
    },
  })

  const stats = useQuery({
    queryKey: ['whatsapp-stats'],
    queryFn: () => api.get<Record<string, unknown>>('/api/whatsapp/stats'),
  })

  const resend = useMutation({
    mutationFn: (id: number) =>
      api.post(`/api/whatsapp/notifications/${id}/resend`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['whatsapp-notifications'] }),
  })

  const sendTest = useMutation({
    mutationFn: () =>
      api.post('/api/whatsapp/test', { phone: testPhone, message: testMessage }),
  })

  return (
    <div>
      <PageHeader title="WhatsApp notifications" />
      {stats.data ? (
        <div className="stat-grid">
          {Object.entries(stats.data)
            .filter(([, v]) => typeof v === 'number' || typeof v === 'string')
            .slice(0, 6)
            .map(([k, v]) => (
              <div className="stat" key={k}>
                <div className="label">{k.replaceAll('_', ' ')}</div>
                <div className="value">{String(v)}</div>
              </div>
            ))}
        </div>
      ) : null}

      <Panel title="Send test">
        {sendTest.error ? <ErrorBox error={sendTest.error} /> : null}
        {sendTest.isSuccess ? <p className="muted">Test sent.</p> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            sendTest.mutate()
          }}
        >
          <Field label="Phone">
            <input
              required
              value={testPhone}
              onChange={(e) => setTestPhone(e.target.value)}
            />
          </Field>
          <Field label="Message">
            <input
              required
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
            />
          </Field>
          <button className="btn" type="submit" disabled={sendTest.isPending}>
            Send test
          </button>
        </FormGrid>
      </Panel>

      <Panel title="Notifications">
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {!list.isLoading && !(list.data || []).length ? <Empty /> : null}
        {(list.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Phone</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Message</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data || []).map((n) => (
                  <tr key={n.id}>
                    <td>{n.created_at || '—'}</td>
                    <td>{n.phone}</td>
                    <td>{n.type || '—'}</td>
                    <td>{n.status}</td>
                    <td>{n.message}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => resend.mutate(n.id)}
                      >
                        Resend
                      </button>
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
