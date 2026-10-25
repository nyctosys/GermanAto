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

type UserRow = {
  id: number
  username: string
  email: string
  role: string
  is_active: boolean
}

const ROLES = ['admin', 'accountant', 'inventory_manager']

export function AdminPage() {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    role: 'accountant',
  })
  const [permRole, setPermRole] = useState('accountant')
  const [selectedPerms, setSelectedPerms] = useState<string[]>([])

  const users = useQuery({
    queryKey: ['auth-users'],
    queryFn: () => api.get<UserRow[]>('/api/auth/users'),
  })

  const roles = useQuery({
    queryKey: ['roles-permissions'],
    queryFn: () => api.get<Record<string, string[]>>('/api/auth/roles-permissions'),
  })

  const createUser = useMutation({
    mutationFn: () => api.post('/api/auth/register', form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['auth-users'] })
      setForm({ username: '', email: '', password: '', role: 'accountant' })
    },
  })

  const toggleActive = useMutation({
    mutationFn: (u: UserRow) =>
      api.put(`/api/auth/users/${u.id}`, { is_active: !u.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auth-users'] }),
  })

  const deleteUser = useMutation({
    mutationFn: (id: number) => api.delete(`/api/auth/users/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['auth-users'] }),
  })

  const savePerms = useMutation({
    mutationFn: () =>
      api.put('/api/auth/roles-permissions', {
        ...(roles.data || {}),
        [permRole]: selectedPerms,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['roles-permissions'] }),
  })

  const allPerms = [
    'home',
    'invoice',
    'inventory',
    'car',
    'reports',
    'admin',
    'daily-expenses',
    'major-expenses',
    'vendors',
    'hr',
    'repair-order',
    'settings',
  ]

  function loadRolePerms(role: string) {
    setPermRole(role)
    setSelectedPerms(roles.data?.[role] || [])
  }

  return (
    <div>
      <PageHeader title="Users & roles" />
      <Panel title="Create user">
        {createUser.error ? <ErrorBox error={createUser.error} /> : null}
        <FormGrid
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            createUser.mutate()
          }}
        >
          <Field label="Username">
            <input
              required
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              required
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </Field>
          <Field label="Role">
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </Field>
          <button className="btn" type="submit">
            Create
          </button>
        </FormGrid>
      </Panel>

      <Panel title="Users">
        {users.isLoading ? <Loading /> : null}
        {users.error ? <ErrorBox error={users.error} /> : null}
        {!users.isLoading && !(users.data || []).length ? <Empty /> : null}
        {(users.data || []).length > 0 ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Active</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(users.data || []).map((u) => (
                  <tr key={u.id}>
                    <td>{u.username}</td>
                    <td>{u.email}</td>
                    <td>{u.role}</td>
                    <td>{u.is_active ? 'yes' : 'no'}</td>
                    <td className="row-actions">
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        onClick={() => toggleActive.mutate(u)}
                      >
                        {u.is_active ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => {
                          if (confirm('Delete user?')) deleteUser.mutate(u.id)
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

      <Panel title="Role permissions">
        {savePerms.error ? <ErrorBox error={savePerms.error} /> : null}
        <div className="form-grid" style={{ marginBottom: 12 }}>
          <Field label="Role">
            <select
              value={permRole}
              onChange={(e) => loadRolePerms(e.target.value)}
            >
              {ROLES.filter((r) => r !== 'admin').map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </Field>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => loadRolePerms(permRole)}
          >
            Load
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => savePerms.mutate()}
            disabled={savePerms.isPending}
          >
            Save permissions
          </button>
        </div>
        <div className="row-actions">
          {allPerms.map((p) => (
            <label key={p} className="tab" style={{ cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={selectedPerms.includes(p)}
                onChange={(e) => {
                  setSelectedPerms((prev) =>
                    e.target.checked ? [...prev, p] : prev.filter((x) => x !== p),
                  )
                }}
              />{' '}
              {p}
            </label>
          ))}
        </div>
      </Panel>
    </div>
  )
}
