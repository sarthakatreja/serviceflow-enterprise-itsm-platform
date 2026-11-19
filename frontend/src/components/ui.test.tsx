import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Compliance, TicketActivityChart, WorkloadBars } from './charts'
import { FilterSelect, Pagination, PriorityBadge, SearchBox, SlaBadge, StatusBadge, TimeLeft } from './ui'

afterEach(cleanup)

describe('ServiceFlow queue components', () => {
  it('submits trimmed search text', () => {
    const search = vi.fn()
    render(<SearchBox defaultValue="" placeholder="Find tickets" onSearch={search} />)
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '  VPN  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(search).toHaveBeenCalledWith('VPN')
  })

  it('selects a status code to send to the API', () => {
    const change = vi.fn()
    render(<FilterSelect label="Status" value="" options={{ open: 'Open', resolved: 'Resolved' }}
      all="All statuses" onChange={change} />)
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'resolved' } })
    expect(change).toHaveBeenCalledWith('resolved')
  })

  it('navigates between real page offsets and disables the previous button on the first page', () => {
    const onOffset = vi.fn()
    render(<Pagination page={{ items: [1, 2], total: 5, limit: 2, offset: 0 }} onOffset={onOffset} label="tickets" />)
    expect((screen.getByRole('button', { name: 'Previous page' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }))
    expect(onOffset).toHaveBeenCalledWith(2)
    expect(screen.getByText('1–2 of 5 tickets')).toBeTruthy()
  })

  it('renders status, priority and SLA meanings as text', () => {
    render(<><StatusBadge status="in_progress" /><PriorityBadge priority="critical" />
      <SlaBadge state="overdue" /><TimeLeft seconds={-3900} /><TimeLeft seconds={null} /></>)
    for (const label of ['In progress', 'Critical', 'Overdue', '1h 5m overdue', 'Completed']) {
      expect(screen.getByText(label)).toBeTruthy()
    }
  })

  it('changes the visible trend data when the time range changes', () => {
    const days = Array.from({ length: 14 }, (_, index) => ({
      date: '2026-11-' + String(index + 1).padStart(2, '0'), created: index + 1, resolved: index,
    }))
    const { container } = render(<MemoryRouter><TicketActivityChart days={days} /></MemoryRouter>)
    expect(container.querySelectorAll('.plot-column')).toHaveLength(14)
    fireEvent.change(screen.getByLabelText('Activity time range'), { target: { value: '7' } })
    expect(container.querySelectorAll('.plot-column')).toHaveLength(7)
    expect(screen.getByLabelText('8 Nov, 8 created, 7 resolved')).toBeTruthy()
  })

  it('filters the technician workload to active or resolved tickets', () => {
    render(<WorkloadBars interactive rows={[{ id: 1, name: 'Nadia Patel', active: 4, resolved: 8 }]} />)
    expect(screen.getByText('4 active · 8 resolved')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Workload view'), { target: { value: 'active' } })
    expect(screen.getByText('4 active')).toBeTruthy()
    expect(screen.queryByText('8 resolved')).toBeNull()
    fireEvent.change(screen.getByLabelText('Workload view'), { target: { value: 'resolved' } })
    expect(screen.getByText('8 resolved')).toBeTruthy()
  })

  it('opens the queue for each SLA outcome from the dashboard', () => {
    render(<MemoryRouter><Compliance metrics={{ compliance: 80, sla_met: 8, sla_late: 2 }} linkToQueue /></MemoryRouter>)
    expect(screen.getByRole('link', { name: '8 on time' }).getAttribute('href')).toBe('/sla?state=met')
    expect(screen.getByRole('link', { name: '2 resolved late' }).getAttribute('href')).toBe('/sla?state=breached')
  })
})
