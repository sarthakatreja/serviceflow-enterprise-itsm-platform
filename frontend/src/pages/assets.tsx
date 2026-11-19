import { useState, type FormEvent } from 'react'
import { Box, CirclePlus, PencilLine, Save } from 'lucide-react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { mutate, url, useAction, useApi } from '../api'
import { useAuth } from '../auth'
import { ReferencePicker } from '../components/reference-picker'
import {
  AssetBadge, BackLink, Empty, Field, FilterSelect, formatDay, formatTimestamp, Modal, Notice, Options,
  PageHeading, Pagination, Panel, RequestState, SearchBox,
} from '../components/ui'
import { assetStatuses, assetTypes, type Asset, type AssetFields, type AssetStatus, type AssetType, type Page } from '../types'

export function Assets() {
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
  const results = useApi<Page<Asset>>(url('/api/assets', {
    search: value('search'), type: value('type'), status: value('status'), offset: value('offset'), limit: 12,
  }))
  const canManage = user?.role === 'admin'
  return <>
    <PageHeading title="IT asset inventory"
      description={canManage ? 'Track hardware, ownership and lifecycle across the workspace.' :
        'Inventory linked to tickets in your assigned queue.'}>
      {canManage && <Link className="button button-primary" to="/assets/new"><CirclePlus size={17} />Add asset</Link>}
    </PageHeading>
    <Panel title="Asset register">
      <div className="table-toolbar">
        <SearchBox key={value('search')} defaultValue={value('search')} placeholder="Search assets by name, tag or location"
          onSearch={term => update('search', term)} />
        <div className="filters">
          <FilterSelect label="Type" value={value('type')} onChange={next => update('type', next)} options={assetTypes} all="All types" />
          <FilterSelect label="Status" value={value('status')} onChange={next => update('status', next)} options={assetStatuses} all="All statuses" />
          {filters.size > 0 && <button className="button button-quiet" type="button" onClick={() => setFilters({})}>Clear filters</button>}
        </div>
      </div>
      {results.data ? <>
        {results.data.items.length > 0 ? <div className="table-scroll"><table className="data-table">
          <thead><tr><th scope="col">Asset</th><th scope="col">Type</th><th scope="col">Assigned to</th>
            <th scope="col">Location</th><th scope="col">Status</th></tr></thead>
          <tbody>{results.data.items.map(asset => <tr key={asset.id}>
            <th scope="row" className="table-primary">
              <Link to={'/assets/' + asset.id}>{asset.name}</Link>
              <small className="mono">{asset.tag}</small>
            </th>
            <td>{assetTypes[asset.type]}</td><td>{asset.assigned_user?.name ?? 'Unassigned'}</td>
            <td>{asset.location || '—'}</td><td><AssetBadge status={asset.status} /></td>
          </tr>)}</tbody>
        </table></div> : <Empty title="No assets match this view" description="Try another search or update your filters." />}
        <Pagination page={results.data} label="assets" onOffset={offset => update('offset', offset ? String(offset) : '')} />
      </> : <RequestState load={results} />}
    </Panel>
  </>
}

interface AssetDraft extends AssetFields { assigned_user_id: number | null }
const emptyAsset: AssetDraft = {
  name: '', tag: '', type: 'laptop', manufacturer: '', model: '', serial_number: '',
  location: '', status: 'in_stock', purchase_date: null, notes: '', assigned_user_id: null,
}

function AssetForm({ initial, onSave, onCancel }: {
  initial?: Asset; onSave: (data: AssetDraft) => Promise<void>; onCancel?: () => void
}) {
  const [asset, setAsset] = useState<AssetDraft>(() => initial ? {
    tag: initial.tag, name: initial.name, type: initial.type, manufacturer: initial.manufacturer, model: initial.model,
    serial_number: initial.serial_number, location: initial.location, status: initial.status,
    purchase_date: initial.purchase_date, notes: initial.notes, assigned_user_id: initial.assigned_user?.id ?? null,
  } : emptyAsset)
  const action = useAction()
  function set<K extends keyof AssetDraft>(field: K, value: AssetDraft[K]) {
    setAsset(previous => ({ ...previous, [field]: value }))
  }
  function submit(event: FormEvent) {
    event.preventDefault()
    void action.run(() => onSave(asset))
  }
  return <form className="form-stack" onSubmit={submit}>
    <Notice error={action.error} />
    <div className="form-grid">
      <Field label="Asset tag" hint="2–40 letters, numbers, hyphens or underscores.">
        <input required minLength={2} maxLength={40} pattern={'[A-Za-z0-9][A-Za-z0-9_\\-]{1,39}'}
          placeholder="LAP-1024" value={asset.tag} onChange={event => set('tag', event.target.value.toUpperCase())} />
      </Field>
      <Field label="Asset name"><input required minLength={2} maxLength={120} value={asset.name}
        onChange={event => set('name', event.target.value)} /></Field>
      <Field label="Asset type"><select value={asset.type} onChange={event => set('type', event.target.value as AssetType)}>
        <Options labels={assetTypes} />
      </select></Field>
      <Field label="Inventory status"><select value={asset.status} onChange={event => set('status', event.target.value as AssetStatus)}>
        <Options labels={assetStatuses} />
      </select></Field>
      <Field label="Manufacturer"><input required minLength={2} maxLength={100} value={asset.manufacturer}
        onChange={event => set('manufacturer', event.target.value)} /></Field>
      <Field label="Model"><input required minLength={2} maxLength={120} value={asset.model}
        onChange={event => set('model', event.target.value)} /></Field>
      <Field label="Serial number"><input maxLength={100} value={asset.serial_number}
        onChange={event => set('serial_number', event.target.value)} /></Field>
      <Field label="Location"><input maxLength={120} value={asset.location}
        onChange={event => set('location', event.target.value)} /></Field>
      <ReferencePicker path="/api/users/choices" label="Assigned staff member" value={asset.assigned_user_id}
        current={initial?.assigned_user ? { id: initial.assigned_user.id, label: initial.assigned_user.name } : undefined}
        none="Unassigned" onChange={value => set('assigned_user_id', value)} />
      <Field label="Purchase date"><input type="date" value={asset.purchase_date ?? ''}
        onChange={event => set('purchase_date', event.target.value || null)} /></Field>
    </div>
    <Field label="Inventory notes"><textarea rows={3} maxLength={4000} value={asset.notes}
      onChange={event => set('notes', event.target.value)} /></Field>
    <div className="form-actions">
      <button className="button button-primary" disabled={action.busy} type="submit">
        <Save size={16} />{action.busy ? 'Saving…' : initial ? 'Save changes' : 'Create asset'}
      </button>
      {onCancel && <button className="button button-quiet" disabled={action.busy} type="button" onClick={onCancel}>Cancel</button>}
    </div>
  </form>
}

export function NewAsset() {
  const navigate = useNavigate()
  return <>
    <BackLink to="/assets">Asset inventory</BackLink>
    <PageHeading title="Add asset" description="Register inventory and assign its custodian." />
    <Panel title="Asset details" className="form-panel">
      <AssetForm onSave={async draft => {
        const asset = await mutate<Asset>('/api/assets', 'POST', draft)
        navigate('/assets/' + asset.id, { replace: true, state: { created: true } })
      }} />
    </Panel>
  </>
}

function AssetRecord({ initial }: { initial: Asset }) {
  const [asset, setAsset] = useState(initial)
  const { user } = useAuth()
  const location = useLocation()
  const [notice, setNotice] = useState(location.state?.created ? 'Asset added to inventory.' : '')
  const [editing, setEditing] = useState(false)
  return <>
    <BackLink to="/assets">Asset inventory</BackLink>
    <PageHeading title={asset.name} description={asset.tag + ' · ' + assetTypes[asset.type]}>
      {user?.role === 'admin' && <button type="button" className="button button-primary" onClick={() => setEditing(true)}>
        <PencilLine size={17} />Edit asset
      </button>}
    </PageHeading>
    <Notice success={notice} />
    <div className="detail-grid">
      <Panel title="Inventory record" className="padded-panel">
        <div className="asset-summary"><span className="metric-icon metric-blue"><Box size={24} /></span>
          <div><strong>{asset.manufacturer} {asset.model}</strong><span>{assetTypes[asset.type]}</span></div>
          <AssetBadge status={asset.status} />
        </div>
        <dl className="facts facts-wide">
          <div><dt>Asset tag</dt><dd className="mono">{asset.tag}</dd></div>
          <div><dt>Serial number</dt><dd className="mono">{asset.serial_number || '—'}</dd></div>
          <div><dt>Assigned to</dt><dd>{asset.assigned_user?.name ?? 'Unassigned'}</dd></div>
          <div><dt>Location</dt><dd>{asset.location || '—'}</dd></div>
          <div><dt>Purchased</dt><dd>{asset.purchase_date ? formatDay(asset.purchase_date, true) : '—'}</dd></div>
          <div><dt>Updated (UTC)</dt><dd>{formatTimestamp(asset.updated_at)}</dd></div>
        </dl>
      </Panel>
      <Panel title="Inventory notes" className="padded-panel">
        {asset.notes ? <p className="preserve-text">{asset.notes}</p> : <Empty title="No notes recorded" />}
      </Panel>
    </div>
    {editing && <Modal title="Edit inventory record" onClose={() => setEditing(false)}>
      <AssetForm initial={asset} onCancel={() => setEditing(false)} onSave={async draft => {
        setAsset(await mutate<Asset>('/api/assets/' + asset.id, 'PATCH', draft))
        setNotice('Asset changes saved.')
        setEditing(false)
      }} />
    </Modal>}
  </>
}

export function AssetDetails() {
  const { id } = useParams()
  const load = useApi<Asset>('/api/assets/' + id)
  if (!load.data) return <><PageHeading title="Asset details" /><RequestState load={load} /></>
  return <AssetRecord key={id} initial={load.data} />
}
