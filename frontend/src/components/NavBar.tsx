'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { LogOut } from 'lucide-react'

export default function NavBar() {
  const { token, logout } = useAuth()
  const router = useRouter()

  function handleLogout() {
    logout()
    router.push('/login')
  }

  return (
    <nav className="nav">
      <h1>Knowledge Hubs</h1>
      <div className="nav-links">
        {token ? (
          <>
            <Link href="/knowledge">Hub</Link>
            <Link href="/search">Search</Link>
            <Link href="/review">Review</Link>
            <button style={{ padding: '0.25rem 0.75rem', fontSize: '0.875rem' }} onClick={handleLogout}>
              <LogOut size={14} /> Sign out
            </button>
          </>
        ) : (
          <Link href="/login">Sign in</Link>
        )}
      </div>
    </nav>
  )
}
