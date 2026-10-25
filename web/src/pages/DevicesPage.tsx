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

type Device = {
  id: number
  name?: string
  serial_number?: string
  ip_address?: string
  location?: string
}

export function DevicesPage() {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    name: '',
    serial_number: '',
    ip_address: '',
    location: '',
  })

  const list = useQuery({
    queryKey: ['zkteco-devices'],
    queryFn: async () => {
      const data = await api.get<Device[] | { devices: Device[] }>('/api/zkteco/devices')
      return Array.isArray(data) ? data : data.devices || []
    },
  })

  const save = useMutation({
    mutationFn: () => api.post('/api/zkteco/devices', form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['zkteco-devices'] })
      setForm({ name: '', serial_number: '', ip_address: '', location: '' })
    },
  })

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/zkteco/devices/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['zkteco-devices'] }),
  })

  return (
    <div>
      <PageHeader title="Device management" />
      <Panel title="Add device">
        {save.error ? <ErrorBox error={save.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            save.mutate()
          }}
        >
          <Field label="Name">
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
          <Field label="Serial">
            <input
              value={form.serial_number}
              onChange={(e) => setForm({ ...form, serial_number: e.target.value })}
            />
          </Field>
          <Field label="IP">
            <input
              value={form.ip_address}
              onChange={(e) => setForm({ ...form, ip_address: e.target.value })}
            />
          </Field>
          <Field label="Location">
            <input
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
            />
          </Field>
          <button className="btn" type="submit">
            Add
          </button>
        </FormGrid>
      </Panel>
      <Panel title="Devices">
        {list.isLoading ? <Loading /> : null}
        {list.error ? <ErrorBox error={list.error} /> : null}
        {!list.isLoading && !(list.data || []).length ? <Empty /> : null}
        {(list.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Serial</th>
                  <th>IP</th>
                  <th>Location</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(list.data || []).map((d) => (
                  <tr key={d.id}>
                    <td>{d.name}</td>
                    <td>{d.serial_number || '—'}</td>
                    <td>{d.ip_address || '—'}</td>
                    <td>{d.location || '—'}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete device?')) remove.mutate(d.id)
                        }}
                      >
                        Delete
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
