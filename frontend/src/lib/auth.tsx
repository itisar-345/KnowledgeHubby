'use client'

import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'

type AuthCtx = {
  token: string | null
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string, workspace: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthCtx>({
  token: null,
  login: async () => {},
  register: async () => {},
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    setToken(localStorage.getItem('kh_token'))
  }, [])

  async function login(username: string, password: string) {
    const body = new URLSearchParams({ username, password })
    const res = await fetch(`${API_BASE}/auth/token`, { method: 'POST', body })
    if (!res.ok) throw new Error('Invalid credentials')
    const data = await res.json()
    localStorage.setItem('kh_token', data.access_token)
    setToken(data.access_token)
  }

  async function register(username: string, password: string, workspace: string) {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, workspace_id: workspace }),
    })
    if (!res.ok) {
      const err = await res.json()
      throw new Error(err.detail || 'Registration failed')
    }
  }

  function logout() {
    localStorage.removeItem('kh_token')
    setToken(null)
  }

  return <AuthContext.Provider value={{ token, login, register, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}

export { API_BASE }
