'use client'

import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { BookOpen, GitBranch, Lightbulb, Network, Plus, Search, ShieldAlert } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'

type KnowledgeItem = {
  id: string
  title: string
  type: string
  author: string
  date: string
  tags: string[]
  details: Record<string, unknown>
}

type KnowledgeResponse = {
  artifacts: Array<{ id: string; title: string; author: string; created_at: string }>
  knowledge_items: KnowledgeItem[]
  relationships: Array<{ from: string; to: string; type: string }>
  playbooks: Array<{ id: string; title: string; category: string }>
}

const typeIcons: Record<string, ReactNode> = {
  decision: <GitBranch size={16} />,
  risk: <ShieldAlert size={16} />,
  'best-practice': <Lightbulb size={16} />,
  checklist: <BookOpen size={16} />,
  how_to: <BookOpen size={16} />,
}

export default function KnowledgePage() {
  const [data, setData] = useState<KnowledgeResponse>({
    artifacts: [],
    knowledge_items: [],
    relationships: [],
    playbooks: [],
  })
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [tags, setTags] = useState('')
  const [content, setContent] = useState('')
  const [query, setQuery] = useState('')
  const [type, setType] = useState('all')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function loadKnowledge() {
    const response = await fetch(`${API_BASE}/knowledge`)
    if (!response.ok) throw new Error(`Knowledge API returned ${response.status}`)
    setData(await response.json())
  }

  useEffect(() => {
    loadKnowledge().catch(err => setError(err.message))
  }, [])

  async function ingest() {
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE}/knowledge/artifacts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          author: author || 'unknown',
          tags: tags.split(',').map(tag => tag.trim()).filter(Boolean),
          content,
          source: 'manual',
        }),
      })
      if (!response.ok) throw new Error(await response.text())
      setTitle('')
      setAuthor('')
      setTags('')
      setContent('')
      await loadKnowledge()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not ingest artifact')
    } finally {
      setLoading(false)
    }
  }

  const filteredItems = useMemo(() => {
    return data.knowledge_items.filter(item => {
      const matchesQuery = `${item.title} ${item.tags.join(' ')}`.toLowerCase().includes(query.toLowerCase())
      const matchesType = type === 'all' || item.type === type
      return matchesQuery && matchesType
    })
  }, [data.knowledge_items, query, type])

  const itemTypes = Array.from(new Set(data.knowledge_items.map(item => item.type))).sort()

  return (
    <div className="knowledge-shell">
      <section className="toolbar">
        <div>
          <h2>Knowledge Hub</h2>
          <p>{data.artifacts.length} artifacts, {data.knowledge_items.length} extracted items</p>
        </div>
        <button className="primary" onClick={loadKnowledge}>
          <Network size={16} />
          Refresh
        </button>
      </section>

      <section className="ingest-panel">
        <div>
          <h3>Ingest Artifact</h3>
          <p>Paste meeting notes, project docs, retros, process writeups, or team decisions.</p>
        </div>
        <div className="form-grid">
          <input value={title} onChange={event => setTitle(event.target.value)} placeholder="Title" />
          <input value={author} onChange={event => setAuthor(event.target.value)} placeholder="Author" />
          <input value={tags} onChange={event => setTags(event.target.value)} placeholder="Tags, comma separated" />
        </div>
        <textarea
          value={content}
          onChange={event => setContent(event.target.value)}
          placeholder="Paste knowledge source text here..."
          rows={8}
        />
        <div className="panel-actions">
          {error && <span className="error-text">{error}</span>}
          <button className="primary" disabled={loading || !title || !content} onClick={ingest}>
            <Plus size={16} />
            {loading ? 'Extracting' : 'Extract Knowledge'}
          </button>
        </div>
      </section>

      <section className="filters">
        <div className="search-box">
          <Search size={16} />
          <input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search extracted knowledge" />
        </div>
        <select value={type} onChange={event => setType(event.target.value)}>
          <option value="all">All types</option>
          {itemTypes.map(itemType => (
            <option key={itemType} value={itemType}>{itemType}</option>
          ))}
        </select>
      </section>

      <section className="knowledge-grid">
        {filteredItems.map(item => (
          <article key={item.id} className="knowledge-card">
            <div className="card-topline">
              <span className="type-pill">
                {typeIcons[item.type] || <BookOpen size={16} />}
                {item.type}
              </span>
              <span>{new Date(item.date).toLocaleDateString()}</span>
            </div>
            <h3>{item.title}</h3>
            <p>by {item.author}</p>
            <div className="tag-row">
              {item.tags.map(tag => <span key={tag}>#{tag}</span>)}
            </div>
          </article>
        ))}
        {filteredItems.length === 0 && (
          <div className="empty-state">
            <BookOpen size={28} />
            <h3>No knowledge items yet</h3>
            <p>Add an artifact above to extract decisions, risks, best practices, and checklists.</p>
          </div>
        )}
      </section>
    </div>
  )
}
