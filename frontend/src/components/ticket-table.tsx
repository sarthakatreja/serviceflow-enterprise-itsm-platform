import { Link } from 'react-router-dom'
import { categories, type Ticket } from '../types'
import { Avatar, Empty, formatTimestamp, PriorityBadge, SlaBadge, StatusBadge, TimeLeft } from './ui'

export function TicketTable({ tickets, empty = 'No tickets match this view', showDeadline = false }: {
  tickets: Ticket[]; empty?: string; showDeadline?: boolean
}) {
  if (!tickets.length) return <Empty title={empty} description="Create a request or change the filters to see more tickets." />
  return <div className="table-scroll">
    <table className="data-table">
      <thead><tr>
        <th scope="col">Ticket</th><th scope="col">Priority</th><th scope="col">Status</th>
        <th scope="col">Assigned to</th><th scope="col">{showDeadline ? 'SLA deadline (UTC)' : 'SLA'}</th>
      </tr></thead>
      <tbody>{tickets.map(ticket => <tr key={ticket.id}>
        <th scope="row" className="table-primary">
          <Link to={'/tickets/' + ticket.id}>{ticket.title}</Link>
          <small><span className="mono">{ticket.number}</span><span className="inline-dot" />{categories[ticket.category]}</small>
        </th>
        <td><PriorityBadge priority={ticket.priority} /></td>
        <td><StatusBadge status={ticket.status} /></td>
        <td>{ticket.assignee ? <span className="table-person"><Avatar name={ticket.assignee.name} />{ticket.assignee.name}</span>
          : <span className="muted">Unassigned</span>}</td>
        <td><SlaBadge state={ticket.sla_state} />{showDeadline &&
          <small className="table-date">{formatTimestamp(ticket.sla_deadline)} · <TimeLeft seconds={ticket.remaining_seconds} /></small>}</td>
      </tr>)}</tbody>
    </table>
  </div>
}
