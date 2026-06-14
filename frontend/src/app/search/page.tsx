'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useAuth, API_BASE } from '@/lib/auth'
import { BookOpen, FileText, GitBranch, Lightbulb, Link2, Search, ShieldAlert, Zap } from 'lucide-react'

type KnowledgeItem = {
  id: string
  title: string
  type: string
  author: string
  date: string
  tags: string[]
  review_status: string
}

type Artifact = {
  id: string
  title: string
  author: string
  source_type: string
  created_at: string
  tags: string[]
}

type SearchResult = {
  query: string
  filters: { type: string | null; source_type: string | null; tag: string | null }
  knowledge_items: KnowledgeItem[]
  artifacts: Artifact[]
  total: number
}

const typeIcons: Record<string, React.ReactNode> = {
  decision: <GitBranch size={14} />,
  risk: <ShieldAlert size={14} />,
  'best-practice': <Lightbulb size={14} />,
  'action-item': <Zap size={14} />,
  artifact: <FileText size={14} />,
}

const SOURCE_TYPES = ['manual', 'file', 'url', 'transcript', 'email', 'slack']
const ITEM_TYPES = ['decision', 'action-item', 'risk', 'best-practice', 'checklist', 'how-to', 'lesson']

export default function SearchPage() {
  const { token } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()

  const [q, setQ] = useState(searchParams.get('q') || '')
  const [typeFilter, setTypeFilter] = useState(searchParams.get('type') || '')
  const [sourceFilter, setSourceFilter] = useState(searchParams.get('source') || '')
  const [tagFilter, setTagFilter] = useState(searchParams.get('tag') || '')
  const [result, setResult] = useState<SearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!token) { router.push('/login'); return }
    // run search on mount if params present
    if (q || typeFilter || sourceFilter || tagFilter) runSearch()
  }, [token])

  function buildQueryString(overrides: Record<string, string> = {}) {
    const params = new URLSearchParams()
    const vals = { q, type: typeFilter, source: sourceFilter, tag: tagFilter, ...overrides }
    Object.entries(vals).forEach(([k, v]) => { if (v) params.set(k, v) })
    return params.toString()
  }

  async function runSearch() {
    if (!token) return
    setLoading(true)
    const qs = buildQueryString()
    // update URL so the current search is shareable
    router.replace(`/search${qs ? `?${qs}` : ''}`, { scroll: false })
    try {
      const apiQs = new URLSearchParams()
      if (q) apiQs.set('q', q)
      if (typeFilter) apiQs.set('type', typeFilter)
      if (sourceFilter) apiQs.set('source_type', sourceFilter)
      if (tagFilter) apiQs.set('tag', tagFilter)
      const res = await fetch(`${API_BASE}/knowledge/search?${apiQs}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.status === 401) { router.push('/login'); return }
      setResult(await res.json())
    } finally {
      setLoading(false)
    }
  }

  function copyShareLink() {
    const url = `${window.location.origin}/search?${buildQueryString()}`
    navigator.clipboard.writeText(url)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!token) return null

  return (
    <div className="knowledge-shell">
      <section className="toolbar">
        <div>
          <h2>Search Knowledge Base</h2>
          {result && <p>{result.total} result{result.total === 1 ? '' : 's'} for &ldquo;{result.query || 'all'}&rdquo;</p>}
        </div>
        <button onClick={copyShareLink} title="Copy shareable link">
          <Link2 size={15} />
          {copied ? 'Copied!' : 'Share link'}
        </button>
      </section>

      <section className="search-controls">
        <div className="search-box">
          <Search size={16} />
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && runSearch()}
            placeholder="Search decisions, risks, action items…"
            autoFocus
          />
        </div>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
          <option value="">All types</option>
          {ITEM_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}>
          <option value="">All sources</option>
          {SOURCE_TYPES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <input
          value={tagFilter}
          onChange={e => setTagFilter(e.target.value)}
          placeholder="Filter by tag"
          style={{ maxWidth: 160 }}
        />
        <button className="primary" onClick={runSearch} disabled={loading}>
          <Search size={15} />
          {loading ? 'Searching…' : 'Search'}
        </button>
      </section>

      {result && (
        <>
          {result.knowledge_items.length > 0 && (
            <section>
              <h3 style={{ padding: '0 0.25rem 0.5rem', fontSize: '0.85rem', color: '#667085', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Knowledge Items ({result.knowledge_items.length})
              </h3>
              <div className="knowledge-grid">
                {result.knowledge_items.map(item => (
                  <Link key={item.id} className="knowledge-card knowledge-card-link" href={`/knowledge/${encodeURIComponent(item.id)}`}>
                    <div className="card-topline">
                      <span className="type-pill">{typeIcons[item.type] || <BookOpen size={14} />}{item.type}</span>
                      <span>{new Date(item.date).toLocaleDateString()}</span>
                    </div>
                    <h3>{item.title}</h3>
                    <p>by {item.author}</p>
                    <div className="tag-row">{item.tags.map(t => <span key={t}>#{t}</span>)}</div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {result.artifacts.length > 0 && (
            <section>
              <h3 style={{ padding: '0 0.25rem 0.5rem', fontSize: '0.85rem', color: '#667085', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Artifacts ({result.artifacts.length})
              </h3>
              <div className="knowledge-grid">
                {result.artifacts.map(a => (
                  <div key={a.id} className="knowledge-card">
                    <div className="card-topline">
                      <span className="type-pill"><FileText size={14} />{a.source_type}</span>
                      <span>{new Date(a.created_at).toLocaleDateString()}</span>
                    </div>
                    <h3>{a.title}</h3>
                    <p>by {a.author}</p>
                    <div className="tag-row">{a.tags.map(t => <span key={t}>#{t}</span>)}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {result.total === 0 && (
            <div className="empty-state">
              <Search size={28} />
              <h3>No results</h3>
              <p>Try a different query or remove a filter.</p>
            </div>
          )}
        </>
      )}

      {!result && !loading && (
        <div className="empty-state">
          <Search size={28} />
          <h3>Start searching</h3>
          <p>Enter a query above — results are instant and links are shareable.</p>
        </div>
      )}
    </div>
  )
}
