export const roles = { admin: 'Administrator', technician: 'Technician', employee: 'Employee' }
export const statuses = {
  open: 'Open', assigned: 'Assigned', in_progress: 'In progress',
  pending: 'Pending', resolved: 'Resolved', closed: 'Closed',
}
export const priorities = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' }
export const categories = {
  hardware: 'Hardware', software: 'Software', network: 'Network', account_access: 'Account access',
  email: 'Email', security: 'Security support', general: 'General IT support',
}
export const assetTypes = {
  laptop: 'Laptop', desktop: 'Desktop', server: 'Server', network_device: 'Network device',
  printer: 'Printer', mobile: 'Mobile device',
}
export const assetStatuses = { in_use: 'In use', in_stock: 'In stock', maintenance: 'Maintenance', retired: 'Retired' }
export const slaStates = {
  on_track: 'On track', due_soon: 'Due soon', overdue: 'Overdue', met: 'Met SLA', breached: 'Breached',
}
export type Role = keyof typeof roles
export type Status = keyof typeof statuses
export type Priority = keyof typeof priorities
export type Category = keyof typeof categories
export type AssetType = keyof typeof assetTypes
export type AssetStatus = keyof typeof assetStatuses
export type SlaState = keyof typeof slaStates

export interface UserRef { id: number; name: string }
export interface User extends UserRef {
  email: string
  role: Role
  active: boolean
  created_at: string
  updated_at: string
}

export interface AssetRef { id: number; tag: string; name: string }
export interface AssetFields {
  name: string
  tag: string
  type: AssetType
  manufacturer: string
  model: string
  serial_number: string
  location: string
  status: AssetStatus
  purchase_date: string | null
  notes: string
}
export interface Asset extends AssetFields {
  id: number
  assigned_user: UserRef | null
  created_at: string
  updated_at: string
}

export interface TicketDraft {
  title: string
  description: string
  category: Category
  priority: Priority
  asset_id: number | null
}
export interface Ticket extends Omit<TicketDraft, 'asset_id'> {
  id: number
  number: string
  version: number
  status: Status
  creator: UserRef
  assignee: UserRef | null
  asset: AssetRef | null
  created_at: string
  updated_at: string
  sla_deadline: string
  resolved_at: string | null
  archived_at: string | null
  resolution_notes: string
  sla_state: SlaState
  remaining_seconds: number | null
}
export interface Comment {
  id: number
  author: UserRef
  body: string
  created_at: string
}
export interface Activity {
  id: number
  actor: UserRef
  action: string
  detail: string
  created_at: string
}
export interface Resolution {
  id: number
  resolver: UserRef | null
  notes: string
  resolved_at: string
}
export interface TicketDetail extends Ticket {
  comments: Comment[]
  activity: Activity[]
  allowed_transitions: Status[]
  resolution_history: Resolution[]
}
export type TicketSla = Pick<Ticket, 'version' | 'sla_state' | 'remaining_seconds'>
export interface AuditEvent extends Omit<Activity, 'actor'> {
  actor: UserRef | null
  entity: string
  entity_id: number | null
}
export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}
export interface SlaSettings {
  critical_hours: number
  high_hours: number
  medium_hours: number
  low_hours: number
  warning_hours: number
}
export interface Settings extends SlaSettings { demo: boolean }
export interface DayCount { date: string; created: number; resolved: number }
export interface Workload { id: number | null; name: string; active: number; resolved: number }
export interface Metrics {
  total: number
  open: number
  in_progress: number
  resolved: number
  critical: number
  due_soon: number
  overdue: number
  assets: number
  sla_met: number
  sla_late: number
  sla_breaches: number
  compliance: number | null
  average_resolution_hours: number | null
  by_status: Record<Status, number>
  by_priority: Record<Priority, number>
  by_category: Record<Category, number>
  assets_by_type: Record<AssetType, number>
  assets_by_status: Record<AssetStatus, number>
  workload: Workload[]
  activity: DayCount[]
}
export interface Dashboard extends Metrics { recent: Ticket[] }
