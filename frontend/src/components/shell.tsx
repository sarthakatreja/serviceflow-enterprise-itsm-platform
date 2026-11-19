import { useEffect, useState, type FormEvent } from 'react'
import {
  Activity, Archive, Boxes, ChartNoAxesCombined, ChevronRight, CirclePlus, ClipboardList,
  Gauge, LayoutDashboard, LogOut, Menu, Search, Settings as SettingsIcon, Ticket, Users, X,
  type LucideIcon,
} from 'lucide-react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useAction, url } from '../api'
import { roles, type Role } from '../types'
import { Avatar, Notice } from './ui'

interface NavigationItem {
  to: string
  text: string
  icon: LucideIcon
  roles?: Role[]
}

const navigation: { label: string; items: NavigationItem[] }[] = [
  { label: 'Workspace', items: [
    { to: '/', text: 'Overview', icon: LayoutDashboard },
    { to: '/my-tickets', text: 'My tickets', icon: Ticket },
    { to: '/tickets', text: 'All tickets', icon: ClipboardList, roles: ['admin'] },
    { to: '/new-ticket', text: 'Create ticket', icon: CirclePlus, roles: ['admin', 'employee'] },
  ] },
  { label: 'Operations', items: [
    { to: '/assets', text: 'IT assets', icon: Boxes, roles: ['admin', 'technician'] },
    { to: '/sla', text: 'SLA monitoring', icon: Gauge },
    { to: '/reports', text: 'Reports', icon: ChartNoAxesCombined, roles: ['admin'] },
  ] },
  { label: 'Administration', items: [
    { to: '/users', text: 'User management', icon: Users, roles: ['admin'] },
    { to: '/audit', text: 'Audit logs', icon: Archive, roles: ['admin'] },
    { to: '/settings', text: 'Settings', icon: SettingsIcon },
  ] },
]

export function Brand() {
  return <span className="brand"><span className="brand-mark"><Activity strokeWidth={2.5} size={23} /></span>
    <span>Service<span className="brand-accent">Flow</span><small>IT SERVICE MANAGEMENT</small></span></span>
}

export function Shell() {
  const auth = useAuth()
  const user = auth.user!
  const navigate = useNavigate()
  const location = useLocation()
  const signOut = useAction()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [search, setSearch] = useState('')
  const canCreate = user.role !== 'technician'
  const queue = user.role === 'admin' ? '/tickets' : '/my-tickets'
  const activeLink = navigation.flatMap(group => group.items).find(item => item.to === location.pathname)
  const page = activeLink?.text ?? (location.pathname.startsWith('/tickets/') ? 'Ticket details' :
    location.pathname.startsWith('/assets/') ? 'Asset inventory' : 'Workspace')

  useEffect(() => {
    document.title = page + ' | ServiceFlow'
  }, [page])
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  function searchTickets(event: FormEvent) {
    event.preventDefault()
    navigate(url(queue, { search: search.trim() }))
    setSearch('')
  }

  return <div className="app-shell">
    <a href="#main-content" className="skip-link" onClick={event => {
      event.preventDefault()
      document.getElementById('main-content')?.focus()
    }}>Skip to content</a>
    {mobileOpen && <button className="mobile-overlay" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <aside className={'sidebar ' + (mobileOpen ? 'sidebar-open' : '')}>
      <div className="side-head"><Link to="/" className="brand-link" onClick={() => setMobileOpen(false)}><Brand /></Link>
        <button className="icon-button close-nav" type="button" aria-label="Close menu"
          onClick={() => setMobileOpen(false)}><X size={20} /></button></div>
      <nav aria-label="Workspace navigation" className="side-nav">
        {navigation.map(group => {
          const visible = group.items.filter(item => !item.roles || item.roles.includes(user.role))
          return visible.length > 0 && <div className="nav-group" key={group.label}>
            <p>{group.label === 'Administration' && user.role !== 'admin' ? 'Account' : group.label}</p>
            {visible.map(item => <NavLink key={item.to} to={item.to} end
              className={({ isActive }) => 'nav-link' + (isActive ? ' nav-active' : '')}
              onClick={() => setMobileOpen(false)}>
              <item.icon size={17} strokeWidth={1.8} aria-hidden="true" /><span>{item.text}</span>
            </NavLink>)}
          </div>
        })}
      </nav>
      <div className="side-foot">
        {auth.demo && <span className="workspace-mode"><i />Demo workspace</span>}
        <div className="account">
          <Avatar name={user.name} size="md" />
          <div><strong>{user.name}</strong><small>{roles[user.role]}</small></div>
          <button title="Sign out" aria-label="Sign out" type="button" className="icon-button" disabled={signOut.busy}
            onClick={() => void signOut.run(auth.logout)}><LogOut size={17} /></button>
        </div>
      </div>
    </aside>
    <div className="main-shell">
      <header className="topbar">
        <div className="breadcrumbs">
          <button className="icon-button open-nav" aria-label="Open menu" aria-expanded={mobileOpen}
            type="button" onClick={() => setMobileOpen(true)}><Menu size={22} /></button>
          <span>Service desk</span><ChevronRight size={14} /><strong>{page}</strong>
        </div>
        <div className="top-actions">
          <form className="top-search" role="search" onSubmit={searchTickets}>
            <Search size={16} aria-hidden="true" />
            <input aria-label="Search all visible tickets" placeholder="Search tickets" type="search" maxLength={120}
              value={search} onChange={event => setSearch(event.target.value)} />
          </form>
          {canCreate && <Link to="/new-ticket" className="button button-primary">
            <CirclePlus size={16} aria-hidden="true" />New ticket
          </Link>}
        </div>
      </header>
      <main id="main-content" tabIndex={-1}>
        <Notice error={signOut.error} />
        <Outlet />
      </main>
    </div>
  </div>
}
