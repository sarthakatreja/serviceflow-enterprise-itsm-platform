import { useState, type FormEvent } from 'react'
import { ArrowRight, Boxes, Eye, EyeOff, Gauge, Headphones, ShieldCheck } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAction } from '../api'
import { useAuth } from '../auth'
import { Brand } from '../components/shell'
import { Field, Notice } from '../components/ui'
import type { Role } from '../types'

const examples: Record<Role, string> = { admin: 'Administrator', technician: 'Technician', employee: 'Employee' }

export function SignIn() {
  const auth = useAuth()
  const action = useAction()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [reveal, setReveal] = useState(false)
  function signIn(event: FormEvent) {
    event.preventDefault()
    void action.run(async () => { await auth.login(email, password); navigate('/', { replace: true }) })
  }
  return <div className="login-layout">
    <section className="login-branding">
      <Brand />
      <div className="login-value">
        <h1>One workspace for<br />IT support.</h1>
        <p>Track requests from intake to resolution, manage inventory, and see which tickets need attention.</p>
        <ul>
          <li><Headphones size={20} />Ticket queues and assignments</li>
          <li><Boxes size={20} />IT asset inventory</li>
          <li><Gauge size={20} />SLA monitoring and reporting</li>
        </ul>
      </div>
    </section>
    <section className="login-main">
      <div className="login-card">
        <span className="login-icon"><ShieldCheck size={23} /></span>
        <h2>Sign in to ServiceFlow</h2>
        <p>Enter your service desk account details.</p>
        <Notice error={action.error} success={action.error ? undefined : auth.notice} />
        <form className="form-stack" onSubmit={signIn}>
          <Field label="Email address"><input autoComplete="username" type="email" required maxLength={254}
            placeholder="you@example.com" value={email} onChange={event => setEmail(event.target.value)} /></Field>
          <Field label="Password"><div className="password-field">
            <input autoComplete="current-password" type={reveal ? 'text' : 'password'} required maxLength={128}
              placeholder="Enter your password" value={password} onChange={event => setPassword(event.target.value)} />
            <button type="button" className="icon-button" aria-label={reveal ? 'Hide password' : 'Show password'}
              onClick={() => setReveal(!reveal)}>{reveal ? <EyeOff size={18} /> : <Eye size={18} />}</button>
          </div></Field>
          <button className="button button-primary sign-in-button" disabled={action.busy} type="submit">
            {action.busy ? 'Signing in…' : 'Sign in'} <ArrowRight size={17} />
          </button>
        </form>
        {auth.demo && <div className="demo-accounts">
          <h3>Demo accounts</h3>
          <p>Open the fictional workspace as a demo role.</p>
          <div>{(Object.keys(examples) as Role[]).map(role => <button key={role} type="button" className="button button-quiet"
            disabled={action.busy} onClick={() => void action.run(async () => {
              await auth.openDemo(role)
              navigate('/', { replace: true })
            })}>{examples[role]}</button>)}</div>
        </div>}
      </div>
    </section>
  </div>
}
