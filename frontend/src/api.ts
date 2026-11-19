import { useEffect, useState } from 'react'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

function responseMessage(data: unknown, status: number): string {
  if (typeof data === 'object' && data !== null && 'detail' in data) {
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      const issue = data.detail[0] as { loc?: string[]; msg?: string } | undefined
      if (issue?.msg) {
        const field = issue.loc?.slice(1).join(' ').replaceAll('_', ' ')
        return (field ? field[0].toUpperCase() + field.slice(1) + ' — ' : '') + issue.msg.replace(/^Value error, /, '')
      }
    }
  }
  return 'Request failed (' + status + ').'
}

export async function fetchResponse(path: string, init?: RequestInit): Promise<Response> {
  let response: Response
  try {
    response = await fetch(path, { credentials: 'same-origin', ...init })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'Could not reach ServiceFlow. Check that the API is running.')
  }
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null)
    if (response.status === 401 && !['/api/auth/login', '/api/auth/demo', '/api/auth/me'].includes(path)) {
      window.dispatchEvent(new Event('serviceflow:session-ended'))
    }
    throw new ApiError(response.status, responseMessage(data, response.status))
  }
  return response
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchResponse(path, init)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function mutate<T>(path: string, method: 'POST' | 'PATCH' | 'PUT' | 'DELETE', body?: object) {
  return api<T>(path, {
    method, headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
}

export function url(path: string, filters: Record<string, string | number | undefined | null>) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const query = params.toString()
  return query ? path + '?' + query : path
}

export function message(error: unknown): string {
  return error instanceof Error ? error.message : 'An unexpected error occurred.'
}

export interface Load<T> {
  data?: T
  error?: string
  pending: boolean
  reload: () => void
}

export const SLA_REFRESH_INTERVAL = 30_000

export function useApi<T>(path: string | null, refreshInterval = 0): Load<T> {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{ path: string; attempt: number; data?: T; error?: string }>()
  useEffect(() => {
    if (!path) return
    const request = new AbortController()
    api<T>(path, { signal: request.signal })
      .then(data => {
        if (!request.signal.aborted) setResult({ path, attempt, data })
      })
      .catch((error: unknown) => {
        if (!request.signal.aborted) setResult({ path, attempt, error: message(error) })
      })
    return () => request.abort()
  }, [path, attempt])
  useEffect(() => {
    if (!path || !refreshInterval) return
    function refreshVisible() {
      if (!document.hidden) setAttempt(value => value + 1)
    }
    const timer = window.setInterval(refreshVisible, refreshInterval)
    document.addEventListener('visibilitychange', refreshVisible)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', refreshVisible)
    }
  }, [path, refreshInterval])
  const current = result?.path === path ? result : undefined
  return {
    data: current?.data,
    error: current?.attempt === attempt ? current?.error : undefined,
    pending: path !== null && current?.attempt !== attempt,
    reload: () => setAttempt(value => value + 1),
  }
}

export function useAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  async function run(operation: () => Promise<void>, success = '') {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await operation()
      setNotice(success)
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }
  return { busy, error, notice, run }
}
