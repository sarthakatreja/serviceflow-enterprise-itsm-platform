import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { Shell } from './components/shell'
import { Loading, Notice, PageHeading } from './components/ui'
import { Assets, AssetDetails, NewAsset } from './pages/assets'
import { AuditLog, SettingsPage, UserManagement } from './pages/administration'
import { SignIn } from './pages/login'
import { Overview } from './pages/overview'
import { Reports, SlaMonitoring } from './pages/operations'
import { TicketQueue, NewTicket, TicketDetails } from './pages/tickets'
import type { Role } from './types'
import './styles.css'

function RouteGuard({ allowed, children }: { allowed: Role[]; children: ReactNode }) {
  const { user } = useAuth()
  if (user && allowed.includes(user.role)) return children
  return <PageMessage title="Access restricted" description="Your role does not have access to this page." />
}

function PageMessage({ title, description }: { title: string; description: string }) {
  return <PageHeading title={title} description={description}>
    <Link className="button button-quiet" to="/">Back to overview</Link>
  </PageHeading>
}

function ServiceFlow() {
  const auth = useAuth()
  if (auth.loading) return <div className="startup"><Loading /></div>
  if (auth.unavailable) return <div className="startup">
    <Notice error={auth.unavailable} />
    <button className="button button-quiet" onClick={auth.retry}>Retry connection</button>
  </div>
  if (!auth.user) return <SignIn />

  return <Routes>
    <Route element={<Shell />}>
      <Route index element={<Overview />} />
      <Route path="my-tickets" element={<TicketQueue key="mine" mine />} />
      <Route path="tickets" element={<RouteGuard allowed={['admin']}><TicketQueue key="all" /></RouteGuard>} />
      <Route path="tickets/:id" element={<TicketDetails />} />
      <Route path="new-ticket" element={<RouteGuard allowed={['admin', 'employee']}><NewTicket /></RouteGuard>} />
      <Route path="assets" element={<RouteGuard allowed={['admin', 'technician']}><Assets /></RouteGuard>} />
      <Route path="assets/new" element={<RouteGuard allowed={['admin']}><NewAsset /></RouteGuard>} />
      <Route path="assets/:id" element={<RouteGuard allowed={['admin', 'technician']}><AssetDetails /></RouteGuard>} />
      <Route path="sla" element={<SlaMonitoring />} />
      <Route path="reports" element={<RouteGuard allowed={['admin']}><Reports /></RouteGuard>} />
      <Route path="users" element={<RouteGuard allowed={['admin']}><UserManagement /></RouteGuard>} />
      <Route path="audit" element={<RouteGuard allowed={['admin']}><AuditLog /></RouteGuard>} />
      <Route path="settings" element={<SettingsPage />} />
      <Route path="*" element={<PageMessage title="Page not found" description="Choose a section from the service desk menu." />} />
    </Route>
  </Routes>
}

createRoot(document.getElementById('root')!).render(
  <StrictMode><BrowserRouter><AuthProvider><ServiceFlow /></AuthProvider></BrowserRouter></StrictMode>,
)
