'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { LogIn, UserPlus } from 'lucide-react'

export default function LoginPage() {
  const { login, register } = useAuth()
  const router = useRouter()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [workspace, setWorkspace] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit() {
    setError('')
    setLoading(true)
    try {
      if (mode === 'register') {
        await register(username, password, workspace || username)
        await login(username, password)
      } else {
        await login(username, password)
      }
      router.push('/knowledge')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <h2>Knowledge Hubs</h2>
        <p className="muted-text">{mode === 'login' ? 'Sign in to your workspace' : 'Create a new workspace'}</p>

        <div className="form-stack">
          <input placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} />
          <input placeholder="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} />
          {mode === 'register' && (
            <input placeholder="Workspace name (e.g. team-alpha)" value={workspace} onChange={e => setWorkspace(e.target.value)} />
          )}
        </div>

        {error && <p className="error-text">{error}</p>}

        <button className="primary" disabled={loading || !username || !password} onClick={submit}>
          {mode === 'login' ? <LogIn size={16} /> : <UserPlus size={16} />}
          {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>

        <button onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
          {mode === 'login' ? 'No account? Register' : 'Have an account? Sign in'}
        </button>
      </div>
    </div>
  )
}
