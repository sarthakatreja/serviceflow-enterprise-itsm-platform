import { useEffect, useId, useState } from 'react'
import { api, message, url } from '../api'
import type { AssetRef, Page, UserRef } from '../types'
import { Field } from './ui'

interface Choice { id: number; label: string }

async function fetchChoices(path: string, signal: AbortSignal): Promise<Choice[]> {
  const choices: Choice[] = []
  const { pathname, searchParams } = new URL(path, window.location.origin)
  const filters = Object.fromEntries(searchParams)
  let offset = 0
  while (true) {
    const page = await api<Page<UserRef | AssetRef>>(url(pathname, { ...filters, limit: 100, offset }), { signal })
    choices.push(...page.items.map(item => ({
      id: item.id,
      label: 'tag' in item ? item.tag + ' · ' + item.name : item.name,
    })))
    offset += page.items.length
    if (offset >= page.total || !page.items.length) return choices
  }
}

export function ReferencePicker({ path, label, value, current, onChange, none, disabled }: {
  path: string; label: string; value: number | null; current?: Choice; onChange: (value: number | null) => void
  none: string; disabled?: boolean
}) {
  const errorId = useId()
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{ path: string; attempt: number; choices?: Choice[]; error?: string }>()
  useEffect(() => {
    const request = new AbortController()
    fetchChoices(path, request.signal).then(choices => {
      if (!request.signal.aborted) setResult({ path, attempt, choices })
    }).catch((error: unknown) => {
      if (!request.signal.aborted) setResult({ path, attempt, error: message(error) })
    })
    return () => request.abort()
  }, [path, attempt])
  const latest = result?.path === path && result.attempt === attempt ? result : undefined
  const choices = latest?.choices ?? []
  const options = current && !choices.some(option => option.id === current.id) ? [current, ...choices] : choices
  return <div className="reference-picker">
    <Field label={label}><select value={value ?? ''} disabled={!latest?.choices || disabled}
      aria-describedby={latest?.error ? errorId : undefined}
      onChange={event => onChange(event.target.value ? Number(event.target.value) : null)}>
      <option value="">{latest ? none : 'Loading options…'}</option>
      {options.map(choice => <option key={choice.id} value={choice.id}>{choice.label}</option>)}
    </select></Field>
    {latest?.error && <div id={errorId} className="inline-error">
      {latest.error} <button className="text-link" type="button" onClick={() => setAttempt(count => count + 1)}>Retry</button>
    </div>}
  </div>
}
