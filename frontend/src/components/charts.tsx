import { useState } from 'react'
import { Link } from 'react-router-dom'
import { url } from '../api'
import { statuses, type DayCount, type Metrics, type Status, type Workload } from '../types'
import { Empty, formatDay, Panel } from './ui'

const colours: Record<Status, string> = {
  open: '#557eed', assigned: '#a68bef', in_progress: '#14a39a',
  pending: '#e4a247', resolved: '#34ad79', closed: '#9aaac0',
}

export function TicketActivityChart({ days }: { days: DayCount[] }) {
  const [range, setRange] = useState(14)
  const activity = days.slice(-range)
  const max = Math.max(4, Math.ceil(Math.max(...activity.flatMap(day => [day.created, day.resolved]), 0) / 4) * 4)
  return <Panel title="Ticket activity" caption="Created and resolved by date (UTC)"
    action={<select className="chart-select" aria-label="Activity time range" value={range}
      onChange={event => setRange(Number(event.target.value))}>
      <option value={14}>Last 14 days</option><option value={7}>Last 7 days</option>
    </select>}>
    <div className="activity-chart">
      <div className="axis-labels" aria-hidden="true">{[4, 3, 2, 1, 0].map(step =>
        <span key={step}>{max * step / 4}</span>)}</div>
      <div className="activity-main">
        <div className="activity-plot">
          <div className="grid-lines" aria-hidden="true">{[0, 1, 2, 3, 4].map(line => <i key={line} />)}</div>
          {activity.map((day, index) => <div className={'plot-column' + (index <= 1 ? ' tip-left' :
            index >= activity.length - 2 ? ' tip-right' : '')} key={day.date} tabIndex={0}
            aria-label={formatDay(day.date) + ', ' + day.created + ' created, ' + day.resolved + ' resolved'}>
            <span className="plot-bar created-bar" style={{ height: day.created * 100 / max + '%' }} />
            <span className="plot-bar resolved-bar" style={{ height: day.resolved * 100 / max + '%' }} />
            <span className="plot-tip" aria-hidden="true"><strong>{formatDay(day.date)}</strong>
              {day.created} created · {day.resolved} resolved</span>
          </div>)}
        </div>
        <div className="plot-dates" aria-hidden="true">
          {activity.filter((_, index) => index % (range === 14 ? 3 : 2) === 0 || index === activity.length - 1)
            .map(day => <span key={day.date}>{formatDay(day.date)}</span>)}
        </div>
      </div>
    </div>
    <div className="chart-legend"><span><i className="created-bar" />Created</span><span><i className="resolved-bar" />Resolved</span></div>
  </Panel>
}

export function TicketStatusChart({ metrics, queue }: { metrics: Metrics; queue: string }) {
  let position = 0
  const distribution = (Object.keys(statuses) as Status[]).map(status => {
    const value = metrics.by_status[status]
    const start = position
    position += metrics.total ? value / metrics.total * 100 : 0
    return { status, value, segment: colours[status] + ' ' + start + '% ' + position + '%' }
  })
  const background = metrics.total > 0 ? 'conic-gradient(' + distribution.map(row => row.segment).join(', ') + ')' : '#e6edf5'
  return <Panel title="Ticket status" caption="Distribution across this queue" className="status-chart-panel">
    <div className="donut-layout">
      <div className="donut" style={{ background }} aria-label={metrics.total + ' total tickets'} role="img">
        <div><strong>{metrics.total}</strong><span>Total tickets</span></div>
      </div>
      <ul className="donut-legend">
        {distribution.map(row => <li key={row.status}><Link to={url(queue, { status: row.status })}>
          <i style={{ backgroundColor: colours[row.status] }} aria-hidden="true" />
          <span>{statuses[row.status]}</span><strong>{row.value}</strong>
        </Link></li>)}
      </ul>
    </div>
  </Panel>
}

export function Compliance({ metrics, linkToQueue = false }: {
  metrics: Pick<Metrics, 'compliance' | 'sla_met' | 'sla_late'>; linkToQueue?: boolean
}) {
  return <div className="compliance">
    <div className="compliance-top"><strong>{metrics.compliance === null ? '—' : metrics.compliance + '%'}</strong>
      <span>Resolved within target</span></div>
    <div className="compliance-track" role="meter" aria-label="SLA compliance" aria-valuenow={metrics.compliance ?? 0}
      aria-valuemin={0} aria-valuemax={100}>
      <span style={{ width: (metrics.compliance ?? 0) + '%' }} />
    </div>
    <div className="compliance-notes"><span><i />{linkToQueue ?
      <Link to="/sla?state=met">{metrics.sla_met} on time</Link> : metrics.sla_met + ' on time'}</span>
      <span><i />{linkToQueue ? <Link to="/sla?state=breached">{metrics.sla_late} resolved late</Link> :
        metrics.sla_late + ' resolved late'}</span></div>
  </div>
}

export function WorkloadBars({ rows, interactive = false }: { rows: Workload[]; interactive?: boolean }) {
  const [view, setView] = useState<'all' | 'active' | 'resolved'>('all')
  if (rows.length === 0) return <Empty title="No workload in this view" />
  const includeActive = view !== 'resolved'
  const includeResolved = view !== 'active'
  const workload = rows.map(row => ({ ...row,
    active: includeActive ? row.active : 0, resolved: includeResolved ? row.resolved : 0,
  }))
  const maximum = Math.max(1, ...workload.map(row => row.active + row.resolved))
  return <div className="workload-bars">
    {interactive && <select className="chart-select workload-select" aria-label="Workload view" value={view}
      onChange={event => setView(event.target.value as typeof view)}>
      <option value="all">All tickets</option><option value="active">Active only</option><option value="resolved">Resolved only</option>
    </select>}
    {workload.map(row => <div key={row.id ?? 'unassigned'} className="workload-row">
      <div><span>{row.name}</span><small>{[includeActive && row.active + ' active',
        includeResolved && row.resolved + ' resolved'].filter(Boolean).join(' · ')}</small></div>
      <div className="stacked-bar" aria-hidden="true">
        <span style={{ width: row.active * 100 / maximum + '%' }} />
        <span style={{ width: row.resolved * 100 / maximum + '%' }} />
      </div>
    </div>)}
  </div>
}
