import { useState, type FormEvent } from 'react'
import { CirclePlus, KeyRound, PencilLine, Save } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { mutate, url, useAction, useApi } from '../api'
import { useAuth } from '../auth'
import {
  Avatar, Badge, Empty, Field, FilterSelect, formatTimestamp, Modal, Notice, Options, PageHeading,
  Pagination, Panel, RequestState, SearchBox,
} from '../components/ui'
import { roles, type AuditEvent, type Page, type Role, type Settings, type SlaSettings, type User } from '../types'

function UserForm({ record, isSelf, onSave, onCancel }: {
  record: User | null; isSelf: boolean; onSave: (data: object) => Promise<void>; onCancel: () => void
}) {
  const [name, setName] = useState(record?.name ?? '')
  const [email, setEmail] = useState(record?.email ?? '')
  const [role, setRole] = useState<Role>(record?.role ?? 'employee')
  const [active, setActive] = useState(record?.active ?? true)
  const [password, setPassword] = useState('')
  const action = useAction()
  function submit(event: FormEvent) {
    event.preventDefault()
    const data = record ?
      (isSelf ? { name } : { name, role, active, ...(password ? { password } : {}) }) :
      { name, email, role, password }
    void action.run(() => onSave(data))
  }
  return <form className="form-stack" onSubmit={submit}>
    <Notice error={action.error} />
    <Field label="Full name"><input value={name} required minLength={2} maxLength={100}
      onChange={event => setName(event.target.value)} /></Field>
    <Field label="Email address"><input value={email} type="email" required maxLength={254} readOnly={Boolean(record)}
      onChange={event => setEmail(event.target.value)} /></Field>
    <Field label="Role"><select value={role} disabled={isSelf} onChange={event => setRole(event.target.value as Role)}>
      <Options labels={roles} />
    </select></Field>
    {record && !isSelf && <label className="checkbox-field">
      <input type="checkbox" checked={active} onChange={event => setActive(event.target.checked)} />Account is active
    </label>}
    {!isSelf && <Field label={record ? 'Reset password (optional)' : 'Initial password'}
      hint={record ? 'A reset signs the user out. Use at least 12 characters.' : 'Use at least 12 characters.'}>
      <input type="password" autoComplete="new-password" minLength={12} maxLength={128} required={!record}
        value={password} onChange={event => setPassword(event.target.value)} />
    </Field>}
    {isSelf && <p className="muted">Change your password in <Link className="text-link" to="/settings" onClick={onCancel}>Settings</Link>.</p>}
    <div className="form-actions">
      <button className="button button-primary" type="submit" disabled={action.busy}><Save size={16} />
        {action.busy ? 'Saving…' : record ? 'Save user' : 'Create user'}</button>
      <button className="button button-quiet" type="button" disabled={action.busy} onClick={onCancel}>Cancel</button>
    </div>
  </form>
}

export function UserManagement() {
  const auth = useAuth()
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [offset, setOffset] = useState(0)
  const [editor, setEditor] = useState<{ record: User | null } | null>(null)
  const [notice, setNotice] = useState('')
  const load = useApi<Page<User>>(url('/api/users', { search, role, offset, limit: 12 }))
  return <>
    <PageHeading title="User management" description="Manage staff accounts, roles and sign-in access.">
      <button type="button" className="button button-primary" onClick={() => setEditor({ record: null })}><CirclePlus size={17} />Add user</button>
    </PageHeading>
    <Notice success={notice} />
    <Panel title="Workspace users">
      <div className="table-toolbar">
        <SearchBox defaultValue={search} placeholder="Search name or email" onSearch={term => { setSearch(term); setOffset(0) }} />
        <div className="filters"><FilterSelect label="Role" value={role} onChange={next => { setRole(next); setOffset(0) }}
          options={roles} all="All roles" /></div>
      </div>
      {load.data ? <>
        {load.data.items.length > 0 ? <div className="table-scroll"><table className="data-table">
          <thead><tr><th scope="col">Account</th><th scope="col">Role</th><th scope="col">Status</th>
            <th scope="col">Created (UTC)</th><th scope="col">Actions</th></tr></thead>
          <tbody>{load.data.items.map(record => <tr key={record.id}>
            <th scope="row"><div className="table-person"><Avatar name={record.name} size="md" />
              <div>{record.name}{record.id === auth.user?.id && <small>Signed-in account</small>}<small>{record.email}</small></div></div></th>
            <td>{roles[record.role]}</td>
            <td><Badge value={record.active ? 'met' : 'retired'}>{record.active ? 'Active' : 'Inactive'}</Badge></td>
            <td>{formatTimestamp(record.created_at)}</td>
            <td><button type="button" className="button button-quiet button-small" aria-label={'Edit ' + record.name}
              onClick={() => setEditor({ record })}><PencilLine size={15} />Edit</button></td>
          </tr>)}</tbody>
        </table></div> : <Empty title="No users match these filters" />}
        <Pagination page={load.data} label="users" onOffset={setOffset} />
      </> : <RequestState load={load} />}
    </Panel>
    {editor && <Modal title={editor.record ? 'Edit staff account' : 'Create staff account'} onClose={() => setEditor(null)}>
      <UserForm record={editor.record} isSelf={editor.record?.id === auth.user?.id} onCancel={() => setEditor(null)}
        onSave={async payload => {
          const record = editor.record
          const saved = await mutate<User>(record ? '/api/users/' + record.id : '/api/users', record ? 'PATCH' : 'POST', payload)
          if (saved.id === auth.user?.id) auth.profileUpdated(saved)
          setNotice(record ? 'User changes saved.' : 'User created.')
          setEditor(null)
          load.reload()
        }} />
    </Modal>}
  </>
}

const auditEntities = { ticket: 'Ticket', asset: 'Asset', user: 'User', session: 'Session', workspace: 'Workspace' }
const auditActions: Record<string, string> = {
  'auth.login': 'Signed in', 'auth.logout': 'Signed out', 'auth.login_failed': 'Sign-in failed',
  'auth.password_changed': 'Password changed', 'asset.created': 'Asset created', 'asset.updated': 'Asset updated',
  'ticket.created': 'Ticket created', 'ticket.assigned': 'Assignment changed', 'ticket.status_changed': 'Status changed',
  'ticket.priority_changed': 'Priority changed', 'ticket.updated': 'Ticket updated', 'ticket.comment_added': 'Comment added',
  'ticket.archived': 'Ticket archived', 'ticket.restored': 'Ticket restored',
  'user.created': 'User created', 'user.updated': 'User updated', 'settings.sla_updated': 'SLA targets updated',
}

function EventTarget({ entry }: { entry: AuditEvent }) {
  if (entry.entity === 'ticket' && entry.entity_id) return <Link className="text-link mono" to={'/tickets/' + entry.entity_id}>
    {'SF-' + String(entry.entity_id).padStart(5, '0')}
  </Link>
  if (entry.entity === 'asset' && entry.entity_id) return <Link className="text-link" to={'/assets/' + entry.entity_id}>Asset #{entry.entity_id}</Link>
  return <>{auditEntities[entry.entity as keyof typeof auditEntities] ?? entry.entity}
    {entry.entity_id === null ? '' : ' #' + entry.entity_id}</>
}

export function AuditLog() {
  const [params, setParams] = useSearchParams()
  const entity = params.get('entity') ?? ''
  const activity = useApi<Page<AuditEvent>>(url('/api/audit-logs', { entity, offset: params.get('offset'), limit: 15 }))
  return <>
    <PageHeading title="Audit logs" description="Review sign-ins, ticket changes and workspace administration.">
      <button type="button" className="button button-quiet" onClick={activity.reload} disabled={activity.pending}>Refresh log</button>
    </PageHeading>
    <Panel title="Workspace activity">
      <div className="table-toolbar"><div className="filters"><FilterSelect label="Target type" value={entity}
        options={auditEntities} all="All targets" onChange={next => setParams(next ? { entity: next } : {})} /></div></div>
      {activity.data ? <>
        {activity.data.items.length > 0 ? <div className="table-scroll"><table className="data-table audit-table">
          <thead><tr><th scope="col">Timestamp (UTC)</th><th scope="col">Actor</th><th scope="col">Action</th>
            <th scope="col">Target</th><th scope="col">Details</th></tr></thead>
          <tbody>{activity.data.items.map(entry => <tr key={entry.id}>
            <td><time dateTime={entry.created_at}>{formatTimestamp(entry.created_at)}</time></td>
            <td>{entry.actor?.name ?? 'Anonymous'}</td>
            <th scope="row">{auditActions[entry.action] ?? entry.action}</th>
            <td><EventTarget entry={entry} /></td><td>{entry.detail}</td>
          </tr>)}</tbody>
        </table></div> : <Empty title="No audit events in this view" />}
        <Pagination page={activity.data} label="events" onOffset={offset => {
          const next = new URLSearchParams(params)
          if (offset) next.set('offset', String(offset))
          else next.delete('offset')
          setParams(next)
        }} />
      </> : <RequestState load={activity} />}
    </Panel>
  </>
}

const slaFields: { key: keyof SlaSettings; title: string }[] = [
  { key: 'critical_hours', title: 'Critical target (hours)' },
  { key: 'high_hours', title: 'High target (hours)' },
  { key: 'medium_hours', title: 'Medium target (hours)' },
  { key: 'low_hours', title: 'Low target (hours)' },
  { key: 'warning_hours', title: 'Due-soon window (hours)' },
]

function SlaForm({ initial, readOnly }: { initial: SlaSettings; readOnly: boolean }) {
  const values = Object.fromEntries(slaFields.map(({ key }) => [key, String(initial[key])])) as Record<keyof SlaSettings, string>
  const [sla, setSla] = useState(values)
  const action = useAction()
  function save(event: FormEvent) {
    event.preventDefault()
    void action.run(async () => {
      const payload = Object.fromEntries(slaFields.map(({ key }) => [key, Number(sla[key])]))
      await mutate('/api/settings/sla', 'PUT', payload)
    }, 'SLA targets saved.')
  }
  if (readOnly) return <dl className="facts">{slaFields.map(({ key, title }) => <div key={key}><dt>{title}</dt><dd>{initial[key]}</dd></div>)}</dl>
  return <form className="form-stack" onSubmit={save}>
    <Notice error={action.error} success={action.notice} />
    <div className="form-grid">{slaFields.map(({ key, title }) => <Field key={key} label={title}>
      <input type="number" required min={1} max={720} value={sla[key]}
        onChange={event => setSla({ ...sla, [key]: event.target.value })} />
    </Field>)}</div>
    <div><button className="button button-primary" disabled={action.busy} type="submit"><Save size={16} />Save SLA targets</button></div>
  </form>
}

function PasswordForm() {
  const { passwordChanged } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const action = useAction()
  function submit(event: FormEvent) {
    event.preventDefault()
    void action.run(async () => {
      if (next !== confirmation) throw new Error('The new passwords must match.')
      await mutate('/api/auth/password', 'POST', { current_password: current, new_password: next })
      passwordChanged()
    })
  }
  return <form className="form-stack" onSubmit={submit}>
    <Notice error={action.error} />
    <Field label="Current password"><input type="password" autoComplete="current-password" required maxLength={128}
      value={current} onChange={event => setCurrent(event.target.value)} /></Field>
    <Field label="New password" hint="Use at least 12 characters."><input type="password" autoComplete="new-password"
      required minLength={12} maxLength={128} value={next} onChange={event => setNext(event.target.value)} /></Field>
    <Field label="Confirm new password"><input type="password" autoComplete="new-password" required minLength={12}
      maxLength={128} value={confirmation} onChange={event => setConfirmation(event.target.value)} /></Field>
    <div><button className="button button-primary" disabled={action.busy} type="submit"><KeyRound size={16} />Change password</button></div>
  </form>
}

export function SettingsPage() {
  const { user, demo } = useAuth()
  const load = useApi<Settings>('/api/settings')
  const administrator = user?.role === 'admin'
  return <>
    <PageHeading title="Settings" description="Review your account and the workspace’s SLA policy." />
    <div className="detail-grid settings-grid">
      <Panel title="SLA policy"
        caption={administrator ? 'Targets apply when tickets are created or reprioritised.' : 'Workspace targets are managed by administrators.'}
        className="padded-panel">
        {load.data ? <SlaForm initial={load.data} readOnly={!administrator} /> : <RequestState load={load} />}
      </Panel>
      <div className="stack">
        <Panel title="Your account" className="padded-panel">
          {user && <dl className="facts"><div><dt>Name</dt><dd>{user.name}</dd></div>
            <div><dt>Email</dt><dd>{user.email}</dd></div>
            <div><dt>Role</dt><dd>{roles[user.role]}</dd></div>
            <div><dt>Workspace</dt><dd>{demo ? 'Demonstration' : 'Local'}</dd></div></dl>}
        </Panel>
        <Panel title="Change password" caption="Changing your password signs you out of all sessions." className="padded-panel">
          <PasswordForm />
        </Panel>
      </div>
    </div>
  </>
}
