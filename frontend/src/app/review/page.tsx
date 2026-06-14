'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useAuth, API_BASE } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { Check, Pencil, X, ArrowLeft, ClipboardList } from 'lucide-react'

type ReviewItem = {
  id: string
  title: string
  type: string
  author: string
  date: string
  tags: string[]
  details: Record<string, unknown>
  review_status: string
  review_note: string
}

export default function ReviewPage() {
  const { token } = useAuth()
  const router = useRouter()
  const [items, setItems] = useState<ReviewItem[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editNote, setEditNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) { router.push('/login'); return }
    load()
  }, [token])

  async function load() {
    const res = await fetch(`${API_BASE}/knowledge/review`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) { setError('Could not load review queue'); return }
    setItems(await res.json())
  }

  async function decide(id: string, status: 'accepted' | 'rejected', title?: string, note?: string) {
    setLoading(true)
    const res = await fetch(`${API_BASE}/knowledge/review/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ status, note: note || '', title }),
    })
    setLoading(false)
    if (res.ok) {
      setItems(prev => prev.filter(i => i.id !== id))
      setEditingId(null)
    } else {
      setError('Could not update item')
    }
  }

  if (!token) return null

  return (
    <div className="knowledge-shell">
      <section className="toolbar">
        <div>
          <h2>Review Queue</h2>
          <p>{items.length} pending item{items.length === 1 ? '' : 's'} awaiting review</p>
        </div>
        <Link className="back-link" href="/knowledge"><ArrowLeft size={16} /> Back to hub</Link>
      </section>

      {error && <p className="error-text" style={{ padding: '0 0.25rem' }}>{error}</p>}

      {items.length === 0 && !error && (
        <section className="empty-state">
          <ClipboardList size={28} />
          <h3>Queue is clear</h3>
          <p>All extracted knowledge has been reviewed.</p>
        </section>
      )}

      <div className="review-list">
        {items.map(item => (
          <div key={item.id} className="review-card">
            <div className="card-topline">
              <span className="type-pill">{item.type}</span>
              <span className="muted-text">{new Date(item.date).toLocaleDateString()}</span>
            </div>

            {editingId === item.id ? (
              <div className="form-stack" style={{ marginTop: '0.75rem' }}>
                <input value={editTitle} onChange={e => setEditTitle(e.target.value)} />
                <input placeholder="Review note (optional)" value={editNote} onChange={e => setEditNote(e.target.value)} />
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button className="success" disabled={loading} onClick={() => decide(item.id, 'accepted', editTitle, editNote)}>
                    <Check size={14} /> Accept edited
                  </button>
                  <button onClick={() => setEditingId(null)}>Cancel</button>
                </div>
              </div>
            ) : (
              <>
                <h3 style={{ margin: '0.75rem 0 0.25rem' }}>{item.title}</h3>
                <p className="muted-text">by {item.author}</p>
                <div className="tag-row">{item.tags.map(t => <span key={t}>#{t}</span>)}</div>
                <div className="review-actions">
                  <button className="success" disabled={loading} onClick={() => decide(item.id, 'accepted')}>
                    <Check size={14} /> Accept
                  </button>
                  <button disabled={loading} onClick={() => { setEditingId(item.id); setEditTitle(item.title); setEditNote('') }}>
                    <Pencil size={14} /> Edit &amp; Accept
                  </button>
                  <button className="danger" disabled={loading} onClick={() => decide(item.id, 'rejected')}>
                    <X size={14} /> Reject
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
