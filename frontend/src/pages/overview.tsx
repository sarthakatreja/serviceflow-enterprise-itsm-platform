import {
  AlarmClock, ArrowRight, Box, CircleAlert, CircleCheck, CircleDot, Hourglass,
  Tickets, type LucideIcon,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { SLA_REFRESH_INTERVAL, url, useApi } from '../api'
import { useAuth } from '../auth'
import { Compliance, TicketActivityChart, TicketStatusChart, WorkloadBars } from '../components/charts'
import { TicketTable } from '../components/ticket-table'
import { PageHeading, Panel, RankedBars, RequestState } from '../components/ui'
import { priorities, type Dashboard, type Priority } from '../types'

interface MetricCardProps {
  label: string; count: number; icon: LucideIcon; tint: string; detail: string; to?: string
}

function MetricCard({ label, count, icon: Icon, tint, detail, to }: MetricCardProps) {
  const content = <>
    <span className="metric-caption">{label}</span>
    <span className={'metric-icon metric-' + tint}><Icon size={20} strokeWidth={1.9} /></span>
    <strong>{count}</strong><small>{detail}</small>
  </>
  return to ? <Link to={to} className="metric-card metric-link">{content}</Link> :
    <div className="metric-card">{content}</div>
}

export function Overview() {
  const { user } = useAuth()
  const data = useApi<Dashboard>('/api/dashboard/summary', SLA_REFRESH_INTERVAL)
  const queue = user?.role === 'admin' ? '/tickets' : '/my-tickets'
  const title = user?.role === 'admin' ? 'Service desk overview' : 'My service desk'
  const scope = user?.role === 'admin' ? 'Monitor support demand, workload and service deadlines.' :
    user?.role === 'technician' ? 'Track the tickets assigned to you and their resolution deadlines.' :
      'Track your support requests and resolution deadlines.'
  if (!data.data) return <><PageHeading title={title} description={scope} /><RequestState load={data} /></>
  const metrics = data.data
  const cards: MetricCardProps[] = [
    { label: 'Total tickets', count: metrics.total, icon: Tickets, tint: 'blue', detail: 'In this workspace view', to: queue },
    { label: 'Open tickets', count: metrics.open, icon: CircleDot, tint: 'slate', detail: 'Awaiting assignment', to: url(queue, { status: 'open' }) },
    { label: 'In progress', count: metrics.in_progress, icon: Hourglass, tint: 'teal', detail: 'Currently being worked', to: url(queue, { status: 'in_progress' }) },
    { label: 'Resolved', count: metrics.resolved, icon: CircleCheck, tint: 'green', detail: 'Includes closed tickets' },
  ]
  return <>
    <PageHeading title={title} description={scope}>
      <Link className="button button-quiet" to="/sla">View SLA queue <ArrowRight size={16} /></Link>
    </PageHeading>
    <div className="metric-grid">{cards.map(card => <MetricCard key={card.label} {...card} />)}</div>
    <div className="queue-strip" aria-label="Priority and asset indicators">
      <div><span className="strip-icon metric-red"><CircleAlert size={17} /></span><div>
        <span>Active critical</span><strong>{metrics.critical}</strong></div></div>
      <Link to="/sla?state=due_soon"><span className="strip-icon metric-amber"><AlarmClock size={17} /></span><div>
        <span>Approaching SLA</span><strong>{metrics.due_soon}</strong></div></Link>
      <Link to="/sla?state=overdue"><span className="strip-icon metric-red"><Hourglass size={17} /></span><div>
        <span>Overdue</span><strong>{metrics.overdue}</strong></div></Link>
      {user?.role === 'employee' ?
        <div><span className="strip-icon metric-blue"><Box size={17} /></span><div>
          <span>My assets</span><strong>{metrics.assets}</strong></div></div> :
        <Link to="/assets"><span className="strip-icon metric-blue"><Box size={17} /></span><div>
          <span>Managed assets</span><strong>{metrics.assets}</strong></div></Link>}
    </div>
    <div className="overview-charts">
      <TicketActivityChart days={metrics.activity} />
      <TicketStatusChart metrics={metrics} queue={queue} />
    </div>
    <Panel title="Recent tickets" caption="Most recently updated"
      action={<Link className="text-link" to={queue}>View ticket queue <ArrowRight size={15} /></Link>}>
      <TicketTable tickets={metrics.recent} empty="No recent tickets" />
    </Panel>
    <div className="overview-bottom">
      <Panel title="Tickets by priority" className="padded-panel">
        <RankedBars rows={(Object.keys(priorities) as Priority[]).map(priority => ({
          label: priorities[priority], value: metrics.by_priority[priority], link: url(queue, { priority }),
        }))} label="Ticket priorities" tone="blue" />
      </Panel>
      <Panel title="Technician workload" className="padded-panel"><WorkloadBars rows={metrics.workload} interactive /></Panel>
      <Panel title="SLA compliance" className="padded-panel"><Compliance metrics={metrics} linkToQueue /></Panel>
    </div>
  </>
}
