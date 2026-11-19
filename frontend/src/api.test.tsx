import { act, renderHook } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { SLA_REFRESH_INTERVAL, useApi } from './api'

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

it('refreshes a visible SLA request every 30 seconds and stops after closing the view', async () => {
  vi.useFakeTimers()
  let hidden = false
  vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden)
  const request = vi.fn().mockImplementation(async () => new Response('{}', {
    headers: { 'Content-Type': 'application/json' },
  }))
  vi.stubGlobal('fetch', request)

  const { unmount } = renderHook(() => useApi('/api/tickets/1/sla', SLA_REFRESH_INTERVAL))
  expect(request).toHaveBeenCalledTimes(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(SLA_REFRESH_INTERVAL) })
  expect(request).toHaveBeenCalledTimes(2)

  hidden = true
  await act(async () => { await vi.advanceTimersByTimeAsync(SLA_REFRESH_INTERVAL) })
  expect(request).toHaveBeenCalledTimes(2)
  hidden = false
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
  expect(request).toHaveBeenCalledTimes(3)

  unmount()
  await act(async () => { await vi.advanceTimersByTimeAsync(SLA_REFRESH_INTERVAL) })
  expect(request).toHaveBeenCalledTimes(3)
})
