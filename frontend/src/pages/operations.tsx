import { useState, type FormEvent } from 'react'
import { AlarmClock, ChevronRight, Clock3, ShieldAlert } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { fetchResponse, SLA_REFRESH_INTERVAL, url, useAction, useApi } from '../api'
import { Compliance, WorkloadBars } from '../components/charts'
import { TicketTable } from '../components/ticket-table'
import {
  DownloadButton, Field, FilterSelect, Notice, Options, PageHeading, Pagination, Panel, RankedBars, RequestState,
} from '../components/ui'
import {
  assetStatuses, assetTypes, categories, priorities, slaStates, statuses, type Dashboard, type Metrics,
  type Page, type Ticket,
} from '../types'

export function SlaMonitoring() {
  const [params, setParams] = useSearchParams()
  const state = params.get('state') ?? ''
  const records = useApi<Page<Ticket>>(url('/api/tickets', {
    sla: state, offset: params.get('offset'), sort: 'deadline', limit: 12,
  }), SLA_REFRESH_INTERVAL)
  const summary = useApi<Dashboard>('/api/dashboard/summary', SLA_REFRESH_INTERVAL)
  function refresh() { records.reload(); summary.reload() }
  return <>
    <PageHeading title="SLA monitoring" description="Track elapsed resolution time and the tickets closest to their deadline.">
      <button type="button" className="button button-quiet" onClick={refresh} disabled={records.pending || summary.pending}>Refresh queue</button>
    </PageHeading>
    {summary.data ? <div className="overview-bottom sla-cards">
      <Panel title="SLA compliance" className="padded-panel"><Compliance metrics={summary.data} /></Panel>
      <Panel title="Due soon" className="padded-panel">
        <div className="large-stat"><span className="metric-icon metric-amber"><AlarmClock size={21} /></span><strong>{summary.data.due_soon}</strong></div>
        <Link className="text-link" to="/sla?state=due_soon">Show due-soon tickets <ChevronRight size={15} /></Link>
      </Panel>
      <Panel title="SLA breaches" className="padded-panel">
        <div className="large-stat"><span className="metric-icon metric-red"><ShieldAlert size={21} /></span><strong>{summary.data.sla_breaches}</strong></div>
        <div className="inline-links"><Link className="text-link" to="/sla?state=overdue">{summary.data.overdue} overdue</Link>
          <Link className="text-link" to="/sla?state=breached">{summary.data.sla_late} resolved late</Link></div>
      </Panel>
    </div> : <RequestState load={summary} />}
    <Panel title="Resolution deadlines" caption="Deadlines use UTC. This queue refreshes every 30 seconds while visible.">
      <div className="table-toolbar"><div className="filters">
        <FilterSelect label="SLA state" value={state} onChange={next => setParams(next ? { state: next } : {})} options={slaStates} all="All SLA states" />
      </div></div>
      {records.data ? <>
        <TicketTable tickets={records.data.items} empty="No tickets in this SLA state" showDeadline />
        <Pagination page={records.data} label="tickets" onOffset={offset => {
          const next = new URLSearchParams(params)
          if (offset) next.set('offset', String(offset))
          else next.delete('offset')
          setParams(next)
        }} />
      </> : <RequestState load={records} />}
    </Panel>
  </>
}

const noFilters = { start: '', end: '', priority: '', status: '' }
type ReportFilters = typeof noFilters

function ReportFilterForm({ applied, onApply }: { applied: ReportFilters; onApply: (filters: ReportFilters) => void }) {
  const [filters, setFilters] = useState(applied)
  const [error, setError] = useState('')
  function submit(event: FormEvent) {
    event.preventDefault()
    if (filters.start && filters.end && filters.start > filters.end) {
      setError('End date must be on or after the start date.')
      return
    }
    setError('')
    onApply(filters)
  }
  return <form className="form-stack" onSubmit={submit}>
    <Notice error={error} />
    <div className="filters report-filters">
      <Field label="From date (UTC)"><input type="date" value={filters.start}
        onChange={event => setFilters({ ...filters, start: event.target.value })} /></Field>
      <Field label="To date (UTC)"><input type="date" value={filters.end}
        onChange={event => setFilters({ ...filters, end: event.target.value })} /></Field>
      <Field label="Priority"><select value={filters.priority} onChange={event => setFilters({ ...filters, priority: event.target.value })}>
        <option value="">All priorities</option><Options labels={priorities} />
      </select></Field>
      <Field label="Status"><select value={filters.status} onChange={event => setFilters({ ...filters, status: event.target.value })}>
        <option value="">All statuses</option><Options labels={statuses} />
      </select></Field>
      <button className="button button-primary" type="submit">Apply filters</button>
      <button className="button button-quiet" type="button" onClick={() => {
        setError(''); setFilters(noFilters); onApply(noFilters)
      }}>Reset</button>
    </div>
  </form>
}

function reportBars(labels: Record<string, string>, counts: Record<string, number>) {
  return Object.entries(labels).map(([key, label]) => ({ label, value: counts[key] }))
}

export function Reports() {
  const [applied, setApplied] = useState(noFilters)
  const report = useApi<Metrics>(url('/api/reports', applied))
  const action = useAction()
  function download() {
    void action.run(async () => {
      const response = await fetchResponse(url('/api/reports/export', applied))
      const localUrl = URL.createObjectURL(await response.blob())
      const link = document.createElement('a')
      link.href = localUrl
      link.download = 'serviceflow-ticket-report.csv'
      document.body.append(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(localUrl), 1000)
    }, 'Ticket report downloaded.')
  }
  return <>
    <PageHeading title="Reports and analytics" description="Review service desk performance and export the matching tickets.">
      <DownloadButton busy={action.busy} disabled={!report.data || report.pending} onClick={download} />
    </PageHeading>
    <Notice error={action.error} success={action.notice} />
    <Panel title="Ticket filters" caption="The date range applies to ticket creation. Inventory figures cover all assets." className="padded-panel">
      <ReportFilterForm applied={applied} onApply={setApplied} />
    </Panel>
    {!report.data ? <RequestState load={report} /> : <div className="stack report-results">
      <div className="overview-bottom">
        <Panel title="Matching tickets" className="padded-panel"><div className="large-stat"><strong>{report.data.total}</strong></div>
          <p className="muted">{report.data.resolved} resolved or closed</p></Panel>
        <Panel title="Average resolution time" className="padded-panel"><div className="large-stat">
          <span className="metric-icon metric-blue"><Clock3 size={20} /></span>
          <strong>{report.data.average_resolution_hours === null ? '—' : report.data.average_resolution_hours + ' h'}</strong>
        </div><p className="muted">Across completed tickets</p></Panel>
        <Panel title="SLA compliance" className="padded-panel"><Compliance metrics={report.data} /></Panel>
      </div>
      <div className="overview-bottom">
        <Panel title="Tickets by status" className="padded-panel"><RankedBars label="Status counts"
          rows={reportBars(statuses, report.data.by_status)} tone="blue" /></Panel>
        <Panel title="Tickets by priority" className="padded-panel"><RankedBars label="Priority counts"
          rows={reportBars(priorities, report.data.by_priority)} /></Panel>
        <Panel title="Tickets by category" className="padded-panel"><RankedBars label="Category counts"
          rows={reportBars(categories, report.data.by_category)} /></Panel>
      </div>
      <div className="overview-bottom">
        <Panel title="Technician workload" className="padded-panel"><WorkloadBars rows={report.data.workload} /></Panel>
        <Panel title="Assets by type" caption={report.data.assets + ' in inventory'} className="padded-panel">
          <RankedBars label="Asset types" rows={reportBars(assetTypes, report.data.assets_by_type)} tone="blue" /></Panel>
        <Panel title="Assets by status" className="padded-panel">
          <RankedBars label="Inventory status counts" rows={reportBars(assetStatuses, report.data.assets_by_status)} /></Panel>
      </div>
    </div>}
  </>
}
