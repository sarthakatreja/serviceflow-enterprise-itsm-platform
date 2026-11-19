import { useState, type FormEvent } from 'react'
import { Archive, ArrowRight, CirclePlus, Clock3, MessageSquare, PencilLine, RotateCcw, Save } from 'lucide-react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, mutate, SLA_REFRESH_INTERVAL, url, useAction, useApi } from '../api'
import { useAuth } from '../auth'
import { ReferencePicker } from '../components/reference-picker'
import { TicketTable } from '../components/ticket-table'
import {
  Avatar, BackLink, Empty, Field, FilterSelect, formatTimestamp, Modal, Notice, Options,
  PageHeading, Pagination, Panel, PriorityBadge, RequestState, SearchBox, SlaBadge, StatusBadge, TimeLeft,
} from '../components/ui'
import {
  categories, priorities, statuses, type Category, type Page, type Priority, type Role, type Status,
  type Ticket, type TicketDetail, type TicketDraft, type TicketSla,
} from '../types'

const sorting = {
  updated: 'Recently updated', newest: 'Newest created', oldest: 'Oldest created',
  priority: 'Highest priority', deadline: 'Earliest SLA deadline',
}

export function TicketQueue({ mine = false }: { mine?: boolean }) {
  const { user } = useAuth()
  const [filters, setFilters] = useSearchParams()
  const value = (key: string) => filters.get(key) ?? ''
  function update(key: string, next: string) {
    const query = new URLSearchParams(filters)
    if (key !== 'offset') query.delete('offset')
    if (next) query.set(key, next)
    else query.delete(key)
    setFilters(query)
  }
  const records = useApi<Page<Ticket>>(url('/api/tickets', {
    scope: mine ? 'mine' : 'visible', search: value('search'), status: value('status'),
    priority: value('priority'), category: value('category'), sort: value('sort'),
    offset: value('offset'), archived: !mine && value('archive') === 'archived' ? 'true' : undefined, limit: 12,
  }))
  return <>
    <PageHeading title={mine ? 'My tickets' : 'All tickets'}
      description={mine ? (user?.role === 'technician' ? 'Work assigned to your technician queue.' :
        'Requests you submitted to the service desk.') : 'Search, triage and assign requests across the service desk.'}>
      {user?.role !== 'technician' && <Link className="button button-primary" to="/new-ticket"><CirclePlus size={17} />Create ticket</Link>}
    </PageHeading>
    <Panel title="Ticket queue">
      <div className="table-toolbar">
        <SearchBox key={value('search')} defaultValue={value('search')} placeholder="Search title, description or ticket ID"
          onSearch={term => update('search', term)} />
        <div className="filters">
          <FilterSelect label="Status" value={value('status')} onChange={next => update('status', next)} options={statuses} all="All statuses" />
          <FilterSelect label="Priority" value={value('priority')} onChange={next => update('priority', next)} options={priorities} all="All priorities" />
          <FilterSelect label="Category" value={value('category')} onChange={next => update('category', next)} options={categories} all="All categories" />
          <FilterSelect label="Sort by" value={value('sort') || 'updated'} onChange={next => update('sort', next)} options={sorting} />
          {!mine && <FilterSelect label="Queue" value={value('archive') || 'current'}
            onChange={next => update('archive', next === 'current' ? '' : next)} options={{ current: 'Current', archived: 'Archived' }} />}
          {filters.size > 0 && <button type="button" className="button button-quiet" onClick={() => setFilters({})}>Clear filters</button>}
        </div>
      </div>
      {records.data ? <>
        <TicketTable tickets={records.data.items} />
        <Pagination page={records.data} label="tickets" onOffset={offset => update('offset', offset ? String(offset) : '')} />
      </> : <RequestState load={records} />}
    </Panel>
  </>
}

const initialDraft: TicketDraft = { title: '', description: '', category: 'general', priority: 'medium', asset_id: null }

function TicketForm({ ticket, showPriority, onSave, onCancel }: {
  ticket?: TicketDetail; showPriority: boolean; onSave: (data: TicketDraft) => Promise<void>; onCancel?: () => void
}) {
  const [draft, setDraft] = useState<TicketDraft>(ticket ? {
    title: ticket.title, description: ticket.description, category: ticket.category,
    priority: ticket.priority, asset_id: ticket.asset?.id ?? null,
  } : initialDraft)
  const action = useAction()
  function set<K extends keyof TicketDraft>(key: K, value: TicketDraft[K]) {
    setDraft(previous => ({ ...previous, [key]: value }))
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    void action.run(() => onSave(draft))
  }
  return <form className="form-stack" onSubmit={submit}>
    <Notice error={action.error} />
    <Field label="Title"><input required minLength={4} maxLength={160} value={draft.title}
      placeholder="Summarise the request" onChange={event => set('title', event.target.value)} /></Field>
    <div className="form-grid">
      <Field label="Category"><select value={draft.category} onChange={event => set('category', event.target.value as Category)}>
        <Options labels={categories} />
      </select></Field>
      {showPriority && <Field label="Priority"><select value={draft.priority} onChange={event => set('priority', event.target.value as Priority)}>
        <Options labels={priorities} />
      </select></Field>}
    </div>
    <Field label="Description" hint="Include the symptoms, impact, and any steps you have already tried.">
      <textarea required minLength={10} maxLength={8000} rows={6} value={draft.description}
        onChange={event => set('description', event.target.value)} />
    </Field>
    <ReferencePicker path="/api/assets/choices" label="Related asset (optional)" value={draft.asset_id} none="No linked asset"
      current={ticket?.asset ? { id: ticket.asset.id, label: ticket.asset.tag + ' · ' + ticket.asset.name } : undefined}
      onChange={value => set('asset_id', value)} />
    <div className="form-actions">
      <button className="button button-primary" type="submit" disabled={action.busy}>
        {ticket ? <Save size={17} /> : <ArrowRight size={17} />}{action.busy ? 'Saving…' : ticket ? 'Save changes' : 'Submit ticket'}
      </button>
      {onCancel && <button className="button button-quiet" type="button" disabled={action.busy} onClick={onCancel}>Cancel</button>}
    </div>
  </form>
}

export function NewTicket() {
  const navigate = useNavigate()
  const { user } = useAuth()
  return <>
    <BackLink to={user?.role === 'admin' ? '/tickets' : '/my-tickets'}>Ticket queue</BackLink>
    <PageHeading title="Create ticket" description="Submit a request to the IT service desk." />
    <Panel title="Request details" className="form-panel">
      <TicketForm showPriority onSave={async draft => {
        const ticket = await mutate<TicketDetail>('/api/tickets', 'POST', draft)
        navigate('/tickets/' + ticket.id, { replace: true, state: { created: true } })
      }} />
    </Panel>
  </>
}

const activityLabels: Record<string, string> = {
  'ticket.created': 'Ticket created', 'ticket.assigned': 'Assignment changed', 'ticket.status_changed': 'Status changed',
  'ticket.priority_changed': 'Priority changed', 'ticket.updated': 'Ticket updated', 'ticket.comment_added': 'Comment added',
  'ticket.archived': 'Ticket archived', 'ticket.restored': 'Ticket restored',
}

function TicketWorkflow({ ticket, role, onUpdate }: {
  ticket: TicketDetail; role: Role; onUpdate: (changes: object, success: string) => Promise<void>
}) {
  const statusAction = useAction()
  const assignmentAction = useAction()
  const priorityAction = useAction()
  const [status, setStatus] = useState<Status>(ticket.status)
  const [assignee, setAssignee] = useState(ticket.assignee?.id ?? null)
  const [priority, setPriority] = useState(ticket.priority)
  const [notes, setNotes] = useState(ticket.resolution_notes)
  const active = ticket.status !== 'resolved' && ticket.status !== 'closed'
  const busy = statusAction.busy || assignmentAction.busy || priorityAction.busy
  const transitions: Status[] = ticket.allowed_transitions.filter(next => next !== 'assigned' && next !== 'open')
  const displayStatus = transitions.includes(status) ? status : ticket.status
  const reopening = ticket.status === 'resolved' && displayStatus === 'in_progress'
  const needsNotes = displayStatus === 'resolved' || displayStatus === 'closed'
  function changeStatus(event: FormEvent) {
    event.preventDefault()
    if (reopening) {
      void statusAction.run(() => onUpdate({ status: displayStatus }, 'Ticket reopened.'))
      return
    }
    void statusAction.run(() => onUpdate({ status: displayStatus, resolution_notes: notes }, 'Status and resolution notes saved.'))
  }
  function assign(event: FormEvent) {
    event.preventDefault()
    void assignmentAction.run(() => onUpdate({ assignee_id: assignee }, assignee === null ? 'Assignment removed.' : 'Assignment saved.'))
  }
  function reprioritise(event: FormEvent) {
    event.preventDefault()
    void priorityAction.run(() => onUpdate({ priority }, 'Priority and SLA deadline updated.'))
  }
  return <Panel title="Ticket controls" className="padded-panel">
    {role === 'admin' && active && <>
      <form className="form-stack compact-form" onSubmit={assign}>
        <Notice error={assignmentAction.error} />
        <ReferencePicker path="/api/users/choices?role=technician" label="Assigned technician" value={assignee}
          current={ticket.assignee ? { id: ticket.assignee.id, label: ticket.assignee.name } : undefined}
          disabled={busy} none="Unassigned" onChange={setAssignee} />
        <button type="submit" className="button button-quiet" disabled={busy || assignee === (ticket.assignee?.id ?? null)}>
          Save assignment
        </button>
      </form>
      <form className="form-stack compact-form" onSubmit={reprioritise}>
        <Notice error={priorityAction.error} />
        <Field label="Priority"><select value={priority} onChange={event => setPriority(event.target.value as Priority)}>
          <Options labels={priorities} />
        </select></Field>
        <button type="submit" className="button button-quiet" disabled={busy || priority === ticket.priority}>Save priority</button>
      </form>
    </>}
    <form className="form-stack compact-form" onSubmit={changeStatus}>
      <Notice error={statusAction.error} />
      <Field label="Status"><select value={displayStatus} disabled={!transitions.length}
        onChange={event => setStatus(event.target.value as Status)}>
        <Options labels={statuses} only={[ticket.status, ...transitions]} />
      </select></Field>
      {!reopening && <Field label="Resolution notes" hint={displayStatus === 'resolved' ? 'Record what fixed the issue in this resolution.' : undefined}>
        <textarea rows={3} value={notes} maxLength={4000} required={needsNotes}
          onChange={event => setNotes(event.target.value)} />
      </Field>}
      <button type="submit" className="button button-primary"
        disabled={busy || (needsNotes && !notes.trim()) || (displayStatus === ticket.status && notes.trim() === ticket.resolution_notes)}>
        {reopening ? 'Reopen ticket' : 'Save status and notes'}
      </button>
    </form>
  </Panel>
}

function TicketView({ initial }: { initial: TicketDetail }) {
  const [ticket, setTicket] = useState(initial)
  const { user } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [comment, setComment] = useState('')
  const [notice, setNotice] = useState(location.state?.created ? 'Ticket created.' : '')
  const discussion = useAction()
  const archive = useAction()
  const endpoint = '/api/tickets/' + ticket.id
  const liveSla = useApi<TicketSla>(ticket.resolved_at ? null : endpoint + '/sla', SLA_REFRESH_INTERVAL)
  const sla = liveSla.data?.version === ticket.version ? liveSla.data : ticket
  const role = user!.role
  const queue = role === 'admin' ? '/tickets' : '/my-tickets'
  const canEdit = ticket.status !== 'closed' && (role === 'admin' || (role === 'employee' && ticket.status === 'open'))

  async function refresh() {
    setTicket(await api<TicketDetail>(endpoint))
  }
  async function update(fields: object, success: string) {
    const saved = await mutate<TicketDetail>(endpoint, 'PATCH', { ...fields, version: ticket.version })
    setTicket(saved)
    setNotice(success)
  }
  function submitComment(event: FormEvent) {
    event.preventDefault()
    void discussion.run(async () => {
      await mutate(endpoint + '/comments', 'POST', { body: comment })
      setComment('')
      await refresh()
    }, 'Comment posted.')
  }
  function changeArchive() {
    const restored = Boolean(ticket.archived_at)
    setNotice('')
    void archive.run(async () => {
      if (restored) setTicket(await mutate<TicketDetail>(endpoint + '/restore', 'POST'))
      else { await mutate(endpoint, 'DELETE'); await refresh() }
    }, restored ? 'Ticket restored to the closed queue.' : 'Ticket moved to the archive.')
  }
  return <>
    <BackLink to={queue}>Ticket queue</BackLink>
    <PageHeading title={ticket.title} description={ticket.number + ' · ' + categories[ticket.category]}>
      <button className="button button-quiet" onClick={() => {
        setNotice('')
        void discussion.run(async () => { await refresh(); if (location.state) navigate(location.pathname, { replace: true, state: null }) })
      }} disabled={discussion.busy}>Refresh</button>
      {canEdit && <button className="button button-quiet" onClick={() => setEditing(true)}><PencilLine size={16} />Edit ticket</button>}
      {role === 'admin' && ticket.status === 'closed' && <button className="button button-quiet" type="button"
        onClick={changeArchive} disabled={archive.busy}>
        {ticket.archived_at ? <><RotateCcw size={16} />Restore ticket</> : <><Archive size={16} />Archive ticket</>}
      </button>}
    </PageHeading>
    <Notice error={archive.error} success={archive.notice} />
    <Notice success={notice} />
    <div className="detail-grid">
      <div className="stack">
        <Panel title="Request details" className="padded-panel">
          <div className="badge-row"><StatusBadge status={ticket.status} /><PriorityBadge priority={ticket.priority} />
            <SlaBadge state={sla.sla_state} /></div>
          <p className="ticket-description preserve-text">{ticket.description}</p>
          {ticket.resolution_notes && !ticket.resolution_history.length && <div className="resolution"><strong>{ticket.resolved_at ? 'Resolution notes' : 'Resolution draft'}</strong>
            <p className="preserve-text">{ticket.resolution_notes}</p></div>}
        </Panel>
        {ticket.resolution_history.length > 0 && <Panel title="Resolution history" className="padded-panel">
          <ol className="resolution-history">
            {ticket.resolution_history.map(entry => <li key={entry.id}>
              <div className="comment-meta"><strong>{entry.resolver?.name ?? 'Imported record'}</strong>
                <time dateTime={entry.resolved_at}>{formatTimestamp(entry.resolved_at)} UTC</time></div>
              <p className="preserve-text">{entry.notes}</p>
            </li>)}
          </ol>
        </Panel>}
        <Panel title="Comments" caption={ticket.comments.length + ' in this conversation'} className="padded-panel">
          {ticket.comments.length ? <ul className="comment-list">{ticket.comments.map(entry => <li key={entry.id}>
            <Avatar name={entry.author.name} size="md" />
            <div><div className="comment-meta"><strong>{entry.author.name}</strong><time dateTime={entry.created_at}>{formatTimestamp(entry.created_at)} UTC</time></div>
              <p className="preserve-text">{entry.body}</p></div>
          </li>)}</ul> : <Empty title="No comments yet" />}
          <Notice error={discussion.error} success={discussion.notice} />
          {ticket.status !== 'closed' && <form className="form-stack" onSubmit={submitComment}>
            <Field label="Add a comment"><textarea required maxLength={4000} rows={3} value={comment}
              onChange={event => setComment(event.target.value)} /></Field>
            <div><button type="submit" className="button button-primary" disabled={discussion.busy || !comment.trim()}>
              <MessageSquare size={16} />Post comment
            </button></div>
          </form>}
        </Panel>
        <Panel title="Activity history" className="padded-panel">
          <ol className="timeline">{ticket.activity.map(entry => <li key={entry.id}>
            <span className="timeline-icon"><Clock3 size={15} /></span>
            <div><strong>{activityLabels[entry.action] ?? entry.action}</strong><p>{entry.detail}</p>
              <small>{entry.actor.name} · <time dateTime={entry.created_at}>{formatTimestamp(entry.created_at)} UTC</time></small></div>
          </li>)}</ol>
        </Panel>
      </div>
      <div className="stack">
        <Panel title="Ticket record" className="padded-panel">
          <dl className="facts">
            <div><dt>Requested by</dt><dd>{ticket.creator.name}</dd></div>
            <div><dt>Assigned to</dt><dd>{ticket.assignee?.name ?? 'Unassigned'}</dd></div>
            <div><dt>Related asset</dt><dd>{ticket.asset ?
              (role === 'employee' ? ticket.asset.tag : <Link className="text-link" to={'/assets/' + ticket.asset.id}>{ticket.asset.tag}</Link>)
              : 'No linked asset'}</dd></div>
            <div><dt>Created (UTC)</dt><dd>{formatTimestamp(ticket.created_at)}</dd></div>
            <div><dt>Updated (UTC)</dt><dd>{formatTimestamp(ticket.updated_at)}</dd></div>
            <div><dt>SLA deadline (UTC)</dt><dd>{formatTimestamp(ticket.sla_deadline)}<br /><TimeLeft seconds={sla.remaining_seconds} /></dd></div>
            {ticket.resolved_at && <div><dt>Resolved (UTC)</dt><dd>{formatTimestamp(ticket.resolved_at)}</dd></div>}
            {ticket.archived_at && <div><dt>Archived (UTC)</dt><dd>{formatTimestamp(ticket.archived_at)}</dd></div>}
          </dl>
        </Panel>
        {role !== 'employee' && ticket.status !== 'closed' && <TicketWorkflow ticket={ticket} role={role} onUpdate={update}
          key={[ticket.id, ticket.status, ticket.assignee?.id, ticket.priority, ticket.resolution_notes].join('|')} />}
      </div>
    </div>
    {editing && <Modal title="Edit request details" onClose={() => setEditing(false)}>
      <TicketForm ticket={ticket} showPriority={false} onCancel={() => setEditing(false)} onSave={async draft => {
        const { title, description, category, asset_id } = draft
        await update({ title, description, category, asset_id }, 'Ticket updated.')
        setEditing(false)
      }} />
    </Modal>}
  </>
}

export function TicketDetails() {
  const { id } = useParams()
  const load = useApi<TicketDetail>('/api/tickets/' + id)
  if (!load.data) return <><PageHeading title="Ticket details" /><RequestState load={load} /></>
  return <TicketView key={load.data.id} initial={load.data} />
}
