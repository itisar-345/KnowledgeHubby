'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, BookOpen, FileText, GitBranch, Lightbulb, Network, ShieldAlert, Tags, User } from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'

type Artifact = {
  id: string
  title: string
  content: string
  source: string
  author: string
  tags: string[]
  created_at: string
  metadata?: Record<string, unknown>
}

type KnowledgeItem = {
  id: string
  artifact_id: string
  title: string
  type: string
  author: string
  date: string
  tags: string[]
  details: Record<string, unknown>
}

type Relationship = {
  from: string
  to: string
  type: string
}

type KnowledgeResponse = {
  artifacts: Artifact[]
  knowledge_items: KnowledgeItem[]
  relationships: Relationship[]
  playbooks: Array<{ id: string; title: string; category: string }>
}

const typeIcons = {
  decision: GitBranch,
  risk: ShieldAlert,
  'best-practice': Lightbulb,
  checklist: BookOpen,
  'how-to': BookOpen,
}

export default function KnowledgeDetailPage({ params }: { params: { id: string } }) {
  const [data, setData] = useState<KnowledgeResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadKnowledge() {
      const response = await fetch(`${API_BASE}/knowledge`)
      if (!response.ok) throw new Error(`Knowledge API returned ${response.status}`)
      setData(await response.json())
    }

    loadKnowledge().catch(err => setError(err instanceof Error ? err.message : 'Could not load knowledge item'))
  }, [])

  const item = useMemo(() => data?.knowledge_items.find(entry => entry.id === params.id), [data, params.id])
  const artifact = useMemo(() => data?.artifacts.find(entry => entry.id === item?.artifact_id), [data, item?.artifact_id])
  const relationships = useMemo(() => {
    if (!data || !item) return []
    return data.relationships.filter(edge => edge.from === item.id || edge.to === item.id)
  }, [data, item])

  if (error) {
    return (
      <div className="detail-shell">
        <Link className="back-link" href="/knowledge"><ArrowLeft size={16} /> Back to hub</Link>
        <section className="empty-state">
          <ShieldAlert size={28} />
          <h3>Could not load this item</h3>
          <p>{error}</p>
        </section>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="detail-shell">
        <Link className="back-link" href="/knowledge"><ArrowLeft size={16} /> Back to hub</Link>
        <section className="empty-state">
          <BookOpen size={28} />
          <h3>Loading knowledge item</h3>
          <p>Fetching the latest local knowledge store.</p>
        </section>
      </div>
    )
  }

  if (!item) {
    return (
      <div className="detail-shell">
        <Link className="back-link" href="/knowledge"><ArrowLeft size={16} /> Back to hub</Link>
        <section className="empty-state">
          <BookOpen size={28} />
          <h3>Knowledge item not found</h3>
          <p>This item may have been removed or regenerated from source content.</p>
        </section>
      </div>
    )
  }

  const Icon = typeIcons[item.type as keyof typeof typeIcons] || BookOpen

  return (
    <div className="detail-shell">
      <Link className="back-link" href="/knowledge"><ArrowLeft size={16} /> Back to hub</Link>

      <section className="detail-hero">
        <div className="detail-title">
          <span className="type-pill">
            <Icon size={16} />
            {item.type}
          </span>
          <h2>{item.title}</h2>
        </div>
        <div className="detail-meta-grid">
          <div>
            <User size={16} />
            <span>{item.author}</span>
          </div>
          <div>
            <BookOpen size={16} />
            <span>{new Date(item.date).toLocaleString()}</span>
          </div>
          <div>
            <Network size={16} />
            <span>{relationships.length} relationship{relationships.length === 1 ? '' : 's'}</span>
          </div>
          <div>
            <Tags size={16} />
            <span>{item.tags.length} tag{item.tags.length === 1 ? '' : 's'}</span>
          </div>
        </div>
      </section>

      <div className="detail-grid">
        <section className="detail-panel">
          <h3>Extracted Details</h3>
          <DetailFields value={item.details} />
        </section>

        <aside className="detail-panel">
          <h3>Source Artifact</h3>
          {artifact ? (
            <div className="artifact-summary">
              <div className="artifact-icon"><FileText size={18} /></div>
              <div>
                <h4>{artifact.title}</h4>
                <p>{artifact.source} by {artifact.author}</p>
              </div>
            </div>
          ) : (
            <p className="muted-text">No source artifact found.</p>
          )}

          <div className="tag-row detail-tags">
            {item.tags.length > 0 ? item.tags.map(tag => <span key={tag}>#{tag}</span>) : <span>untagged</span>}
          </div>
        </aside>
      </div>

      <section className="detail-panel">
        <h3>Relationships</h3>
        {relationships.length > 0 ? (
          <div className="relationship-table">
            {relationships.map(edge => (
              <div key={`${edge.from}-${edge.to}-${edge.type}`}>
                <span>{edge.from === item.id ? 'Outgoing' : 'Incoming'}</span>
                <strong>{edge.type}</strong>
                <code>{edge.from === item.id ? edge.to : edge.from}</code>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted-text">No relationships recorded for this item yet.</p>
        )}
      </section>

      {artifact && (
        <section className="detail-panel">
          <h3>Source Preview</h3>
          <p className="source-preview">{artifact.content}</p>
        </section>
      )}
    </div>
  )
}

function DetailFields({ value }: { value: Record<string, unknown> }) {
  const entries = Object.entries(value)

  if (entries.length === 0) {
    return <p className="muted-text">No structured detail was captured.</p>
  }

  return (
    <dl className="detail-fields">
      {entries.map(([key, fieldValue]) => (
        <div key={key}>
          <dt>{humanize(key)}</dt>
          <dd>{formatValue(fieldValue)}</dd>
        </div>
      ))}
    </dl>
  )
}

function humanize(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, character => character.toUpperCase())
}

function formatValue(value: unknown) {
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object' && value !== null) return JSON.stringify(value, null, 2)
  if (value === null || value === undefined || value === '') return 'Not specified'
  return String(value)
}
