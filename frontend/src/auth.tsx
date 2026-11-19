import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, message, mutate } from './api'
import type { Role, User } from './types'

interface AuthState {
  user: User | null
  demo: boolean
  loading: boolean
  unavailable: string
  notice: string
  retry: () => void
  login: (email: string, password: string) => Promise<void>
  openDemo: (role: Role) => Promise<void>
  logout: () => Promise<void>
  profileUpdated: (user: User) => void
  passwordChanged: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [demo, setDemo] = useState(false)
  const [loading, setLoading] = useState(true)
  const [unavailable, setUnavailable] = useState('')
  const [notice, setNotice] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const options = { signal: controller.signal }
    Promise.all([
      api<{ demo: boolean }>('/api/auth/context', options),
      api<User>('/api/auth/me', options).catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) return null
        throw error
      }),
    ]).then(([context, session]) => {
      if (!controller.signal.aborted) {
        setDemo(context.demo)
        setUser(session)
        setUnavailable('')
      }
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setUnavailable(message(error))
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false)
    })
    return () => controller.abort()
  }, [attempt])

  useEffect(() => {
    function signedOut() {
      setUser(null)
      setNotice('Your session ended. Sign in to continue.')
    }
    window.addEventListener('serviceflow:session-ended', signedOut)
    return () => window.removeEventListener('serviceflow:session-ended', signedOut)
  }, [])

  return <AuthContext.Provider value={{
    user, demo, loading, unavailable, notice,
    retry: () => { setLoading(true); setAttempt(value => value + 1) },
    login: async (email, password) => {
      setUser(await mutate<User>('/api/auth/login', 'POST', { email, password }))
      setNotice('')
    },
    openDemo: async role => {
      setUser(await mutate<User>('/api/auth/demo', 'POST', { role }))
      setNotice('')
    },
    logout: async () => {
      await mutate('/api/auth/logout', 'POST')
      setUser(null)
      setNotice('')
    },
    profileUpdated: setUser,
    passwordChanged: () => {
      setUser(null)
      setNotice('Password changed. Sign in with your new password.')
    },
  }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('Authentication state is unavailable.')
  return context
}
