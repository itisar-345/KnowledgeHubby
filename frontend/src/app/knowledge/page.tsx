'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useAuth, API_BASE } from '@/lib/auth'
import { BookOpen, FileText, GitBranch, Link2, Lightbulb, Network, Plus, Search, ShieldAlert, Upload, Zap } from 'lucide-react'

type KnowledgeItem = {
  id: string; title: string; type: string; author: string
  date: string; tags: string[]; details: Record<string, unknown>; review_status: string
}
type KnowledgeResponse = {
  artifacts: Array<{ id: string; title: string; author: string; created_at: string }>
  knowledge_items: KnowledgeItem[]
  relationships: Array<{ from: string; to: string; type: string }>
  playbooks: Array<{ id: string; title: string; category: string }>
}
type GraphResponse = {
  nodes: Array<{ id: string; label: string; type: string }>
  edges: Array<{ source: string; target: string; label: string }>
  layout: string
}

const typeIcons: Record<string, ReactNode> = {
  decision: <GitBranch size={16} />,
  risk: <ShieldAlert size={16} />,
  'best-practice': <Lightbulb size={16} />,
  checklist: <BookOpen size={16} />,
  'how-to': <BookOpen size={16} />,
  'action-item': <Zap size={16} />,
  artifact: <FileText size={16} />,
}

type IngestMode = 'text' | 'file' | 'url' | 'transcript'

export default function KnowledgePage() {
  const { token } = useAuth()
  const router = useRouter()

  const [data, setData] = useState<KnowledgeResponse>({ artifacts: [], knowledge_items: [], relationships: [], playbooks: [] })
  const [graph, setGraph] = useState<GraphResponse>({ nodes: [], edges: [], layout: 'force-directed' })
  const [query, setQuery] = useState('')
  const [type, setType] = useState('all')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedNodeId, setSelectedNodeId] = useState('')
  const [ingestMode, setIngestMode] = useState<IngestMode>('text')

  // text form
  const [title, setTitle] = useState('')
  const [author, setAuthor] = useState('')
  const [tags, setTags] = useState('')
  const [content, setContent] = useState('')

  // file form
  const [fileTitle, setFileTitle] = useState('')
  const [fileAuthor, setFileAuthor] = useState('')
  const [fileTags, setFileTags] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // url form
  const [urlValue, setUrlValue] = useState('')
  const [urlTitle, setUrlTitle] = useState('')
  const [urlAuthor, setUrlAuthor] = useState('')
  const [urlTags, setUrlTags] = useState('')

  // transcript / email / slack form
  const [txTitle, setTxTitle] = useState('')
  const [txAuthor, setTxAuthor] = useState('')
  const [txTags, setTxTags] = useState('')
  const [txContent, setTxContent] = useState('')
  const [txSourceType, setTxSourceType] = useState('transcript')
  const [txSummary, setTxSummary] = useState('')

  // cross-linking
  const [linkingCross, setLinkingCross] = useState(false)
  const [crossLinkCount, setCrossLinkCount] = useState<number | null>(null)

  useEffect(() => {
    if (!token) { router.push('/login'); return }
    loadKnowledge()
  }, [token])

  function authHeaders(): Record<string, string> {
    return { Authorization: `Bearer ${token}` }
  }

  async function loadKnowledge() {
    try {
      const [kr, gr] = await Promise.all([
        fetch(`${API_BASE}/knowledge`, { headers: authHeaders() }),
        fetch(`${API_BASE}/knowledge/graph`, { headers: authHeaders() }),
      ])
      if (kr.status === 401) { router.push('/login'); return }
      if (!kr.ok) throw new Error(`Knowledge API returned ${kr.status}`)
      if (!gr.ok) throw new Error(`Graph API returned ${gr.status}`)
      setData(await kr.json())
      setGraph(await gr.json())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Load failed')
    }
  }

  async function ingestText() {
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/knowledge/artifacts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ title, author: author || 'unknown', tags: tags.split(',').map(t => t.trim()).filter(Boolean), content, source: 'manual' }),
      })
      if (!res.ok) throw new Error(await res.text())
      setTitle(''); setAuthor(''); setTags(''); setContent('')
      await loadKnowledge()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ingestion failed')
    } finally { setLoading(false) }
  }

  async function ingestFile() {
    const file = fileInputRef.current?.files?.[0]
    if (!file || !fileTitle) return
    setLoading(true); setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('title', fileTitle)
      form.append('author', fileAuthor || 'unknown')
      form.append('tags', fileTags)
      const res = await fetch(`${API_BASE}/knowledge/artifacts/upload`, { method: 'POST', headers: authHeaders(), body: form })
      if (!res.ok) throw new Error(await res.text())
      setFileTitle(''); setFileAuthor(''); setFileTags('')
      if (fileInputRef.current) fileInputRef.current.value = ''
      await loadKnowledge()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally { setLoading(false) }
  }

  async function ingestUrl() {
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API_BASE}/knowledge/artifacts/url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ url: urlValue, title: urlTitle, author: urlAuthor || 'unknown', tags: urlTags.split(',').map(t => t.trim()).filter(Boolean) }),
      })
      if (!res.ok) throw new Error(await res.text())
      setUrlValue(''); setUrlTitle(''); setUrlAuthor(''); setUrlTags('')
      await loadKnowledge()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'URL fetch failed')
    } finally { setLoading(false) }
  }

  async function ingestTranscript() {
    setLoading(true); setError(''); setTxSummary('')
    try {
      const res = await fetch(`${API_BASE}/knowledge/artifacts/transcript`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          title: txTitle, content: txContent,
          source_type: txSourceType,
          author: txAuthor || 'unknown',
          tags: txTags.split(',').map(t => t.trim()).filter(Boolean),
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      const result = await res.json()
      if (result.summary) setTxSummary(result.summary)
      setTxTitle(''); setTxAuthor(''); setTxTags(''); setTxContent('')
      await loadKnowledge()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transcript ingestion failed')
    } finally { setLoading(false) }
  }

  async function runCrossLink() {
    setLinkingCross(true); setCrossLinkCount(null)
    try {
      const res = await fetch(`${API_BASE}/knowledge/link`, { method: 'POST', headers: authHeaders() })
      if (!res.ok) throw new Error(await res.text())
      const result = await res.json()
      setCrossLinkCount(result.links_created)
      await loadKnowledge()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cross-link failed')
    } finally { setLinkingCross(false) }
  }

  const filteredItems = useMemo(() => data.knowledge_items.filter(item => {
    const matchesQuery = `${item.title} ${item.tags.join(' ')}`.toLowerCase().includes(query.toLowerCase())
    const matchesType = type === 'all' || item.type === type
    return matchesQuery && matchesType
  }), [data.knowledge_items, query, type])

  const itemTypes = Array.from(new Set(data.knowledge_items.map(i => i.type))).sort()
  const selectedNode = graph.nodes.find(n => n.id === selectedNodeId)
  const selectedNodeLinks = selectedNode
    ? graph.edges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
    : []
  const pendingCount = data.knowledge_items.filter(i => i.review_status === 'pending').length

  if (!token) return null

  const modeMeta: Record<IngestMode, { icon: ReactNode; label: string }> = {
    text: { icon: <FileText size={14} />, label: 'Text' },
    file: { icon: <Upload size={14} />, label: 'File' },
    url: { icon: <Link2 size={14} />, label: 'URL' },
    transcript: { icon: <Zap size={14} />, label: 'Transcript / Email / Slack' },
  }

  return (
    <div className="knowledge-shell">
      <section className="toolbar">
        <div>
          <h2>Knowledge Hub</h2>
          <p>{data.artifacts.length} artifacts · {data.knowledge_items.length} items{pendingCount > 0 ? ` · ${pendingCount} pending review` : ''}</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <Link href="/search"><button><Search size={15} />Search</button></Link>
          <button onClick={runCrossLink} disabled={linkingCross} title="Find related items across sources">
            <Network size={15} />
            {linkingCross ? 'Linking…' : crossLinkCount !== null ? `${crossLinkCount} links found` : 'Cross-link'}
          </button>
          {pendingCount > 0 && <Link href="/review"><button className="warning"><BookOpen size={15} />Review ({pendingCount})</button></Link>}
          <button className="primary" onClick={loadKnowledge}><Network size={15} />Refresh</button>
        </div>
      </section>

      <section className="ingest-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h3>Ingest Artifact</h3>
            <p>Paste text, upload a file, fetch a URL, or extract decisions from a meeting transcript / email / Slack thread using AI.</p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {(Object.entries(modeMeta) as [IngestMode, typeof modeMeta[IngestMode]][]).map(([m, meta]) => (
              <button key={m} className={ingestMode === m ? 'primary' : ''} onClick={() => setIngestMode(m)}>
                {meta.icon}{meta.label}
              </button>
            ))}
          </div>
        </div>

        {ingestMode === 'text' && (
          <>
            <div className="form-grid">
              <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title" />
              <input value={author} onChange={e => setAuthor(e.target.value)} placeholder="Author" />
              <input value={tags} onChange={e => setTags(e.target.value)} placeholder="Tags, comma separated" />
            </div>
            <textarea value={content} onChange={e => setContent(e.target.value)} placeholder="Paste knowledge source text here…" rows={8} />
            <div className="panel-actions">
              {error && <span className="error-text">{error}</span>}
              <button className="primary" disabled={loading || !title || !content} onClick={ingestText}>
                <Plus size={16} />{loading ? 'Extracting…' : 'Extract Knowledge'}
              </button>
            </div>
          </>
        )}

        {ingestMode === 'file' && (
          <>
            <div className="form-grid">
              <input value={fileTitle} onChange={e => setFileTitle(e.target.value)} placeholder="Title" />
              <input value={fileAuthor} onChange={e => setFileAuthor(e.target.value)} placeholder="Author" />
              <input value={fileTags} onChange={e => setFileTags(e.target.value)} placeholder="Tags, comma separated" />
            </div>
            <input ref={fileInputRef} type="file" accept=".pdf,.txt,.md" style={{ padding: '0.5rem 0' }} />
            <div className="panel-actions">
              {error && <span className="error-text">{error}</span>}
              <button className="primary" disabled={loading || !fileTitle} onClick={ingestFile}>
                <Upload size={16} />{loading ? 'Uploading…' : 'Upload & Extract'}
              </button>
            </div>
          </>
        )}

        {ingestMode === 'url' && (
          <>
            <div className="form-grid">
              <input value={urlTitle} onChange={e => setUrlTitle(e.target.value)} placeholder="Title" />
              <input value={urlAuthor} onChange={e => setUrlAuthor(e.target.value)} placeholder="Author" />
              <input value={urlTags} onChange={e => setUrlTags(e.target.value)} placeholder="Tags, comma separated" />
            </div>
            <input value={urlValue} onChange={e => setUrlValue(e.target.value)} placeholder="https://…" />
            <div className="panel-actions">
              {error && <span className="error-text">{error}</span>}
              <button className="primary" disabled={loading || !urlValue || !urlTitle} onClick={ingestUrl}>
                <Link2 size={16} />{loading ? 'Fetching…' : 'Fetch & Extract'}
              </button>
            </div>
          </>
        )}

        {ingestMode === 'transcript' && (
          <>
            <div className="form-grid" style={{ gridTemplateColumns: 'repeat(4, minmax(0,1fr))' }}>
              <input value={txTitle} onChange={e => setTxTitle(e.target.value)} placeholder="Title" />
              <input value={txAuthor} onChange={e => setTxAuthor(e.target.value)} placeholder="Author" />
              <input value={txTags} onChange={e => setTxTags(e.target.value)} placeholder="Tags, comma separated" />
              <select value={txSourceType} onChange={e => setTxSourceType(e.target.value)}>
                <option value="transcript">Transcript</option>
                <option value="email">Email thread</option>
                <option value="slack">Slack thread</option>
              </select>
            </div>
            <textarea
              value={txContent}
              onChange={e => setTxContent(e.target.value)}
              placeholder="Paste your meeting transcript, email thread, or Slack conversation…"
              rows={10}
            />
            {txSummary && (
              <div className="summary-box">
                <strong>AI Summary:</strong> {txSummary}
              </div>
            )}
            <div className="panel-actions">
              {error && <span className="error-text">{error}</span>}
              <button className="primary" disabled={loading || !txTitle || !txContent} onClick={ingestTranscript}>
                <Zap size={16} />{loading ? 'Extracting with AI…' : 'Extract with AI'}
              </button>
            </div>
          </>
        )}
      </section>

      <section className="filters">
        <div className="search-box">
          <Search size={16} />
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Filter extracted knowledge" />
        </div>
        <select value={type} onChange={e => setType(e.target.value)}>
          <option value="all">All types</option>
          {itemTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <Link href={`/search${query ? `?q=${encodeURIComponent(query)}` : ''}`} style={{ fontSize: '0.85rem', alignSelf: 'center', color: '#0066cc', textDecoration: 'none' }}>
          Advanced search →
        </Link>
      </section>

      <section className="knowledge-grid">
        {filteredItems.map(item => (
          <Link key={item.id} className="knowledge-card knowledge-card-link" href={`/knowledge/${encodeURIComponent(item.id)}`}>
            <div className="card-topline">
              <span className="type-pill">{typeIcons[item.type] || <BookOpen size={16} />}{item.type}</span>
              <span>{new Date(item.date).toLocaleDateString()}</span>
            </div>
            <h3>{item.title}</h3>
            <p>by {item.author}</p>
            {item.review_status === 'pending' && <span className="review-badge">pending review</span>}
            <div className="tag-row">{item.tags.map(t => <span key={t}>#{t}</span>)}</div>
          </Link>
        ))}
        {filteredItems.length === 0 && (
          <div className="empty-state">
            <BookOpen size={28} />
            <h3>No knowledge items yet</h3>
            <p>Add an artifact above to extract decisions, risks, best practices, and checklists.</p>
          </div>
        )}
      </section>

      <section className="graph-panel">
        <div className="graph-header">
          <div>
            <h3>Knowledge Graph</h3>
            <p>{graph.nodes.length} nodes · {graph.edges.length} relationships</p>
          </div>
          {selectedNode && <Link className="detail-link" href={`/knowledge/${encodeURIComponent(selectedNode.id)}`}>Open details</Link>}
        </div>
        {graph.nodes.length > 0 ? (
          <div className="graph-layout">
            <KnowledgeGraph graph={graph} selectedNodeId={selectedNodeId} onSelectNode={setSelectedNodeId} />
            <aside className="graph-inspector">
              {selectedNode ? (
                <>
                  <span className="type-pill">{typeIcons[selectedNode.type] || <Network size={16} />}{selectedNode.type}</span>
                  <h4>{selectedNode.label}</h4>
                  <p>{selectedNodeLinks.length} relationship{selectedNodeLinks.length === 1 ? '' : 's'}</p>
                  <div className="relationship-list">
                    {selectedNodeLinks.map(edge => {
                      const otherId = edge.source === selectedNode.id ? edge.target : edge.source
                      const other = graph.nodes.find(n => n.id === otherId)
                      return (
                        <button key={`${edge.source}-${edge.target}-${edge.label}`} onClick={() => setSelectedNodeId(otherId)}>
                          <span>{edge.label}</span>
                          <strong>{other?.label || otherId}</strong>
                        </button>
                      )
                    })}
                  </div>
                </>
              ) : (
                <div className="graph-empty">
                  <Network size={24} /><h4>Select a node</h4>
                  <p>Inspect its relationships and jump into the detail page.</p>
                </div>
              )}
            </aside>
          </div>
        ) : (
          <div className="empty-state">
            <Network size={28} /><h3>No graph yet</h3>
            <p>Ingest an artifact to generate artifact-to-knowledge relationships.</p>
          </div>
        )}
      </section>
    </div>
  )
}

function KnowledgeGraph({ graph, selectedNodeId, onSelectNode }: {
  graph: GraphResponse; selectedNodeId: string; onSelectNode: (id: string) => void
}) {
  const width = 760, height = 420, cx = width / 2, cy = height / 2
  const artifactNodes = graph.nodes.filter(n => n.type === 'artifact')
  const knowledgeNodes = graph.nodes.filter(n => n.type !== 'artifact')
  const pos = new Map<string, { x: number; y: number }>()

  artifactNodes.forEach((n, i) => {
    const offset = (i - (artifactNodes.length - 1) / 2) * 88
    pos.set(n.id, { x: cx, y: Math.max(72, cy + offset) })
  })
  knowledgeNodes.forEach((n, i) => {
    const angle = (i / Math.max(knowledgeNodes.length, 1)) * Math.PI * 2 - Math.PI / 2
    pos.set(n.id, { x: cx + Math.cos(angle) * 300, y: cy + Math.sin(angle) * 165 })
  })

  return (
    <svg className="knowledge-graph" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Knowledge graph visualization">
      {graph.edges.map(edge => {
        const s = pos.get(edge.source), t = pos.get(edge.target)
        if (!s || !t) return null
        const selected = selectedNodeId === edge.source || selectedNodeId === edge.target
        return (
          <g key={`${edge.source}-${edge.target}-${edge.label}`}>
            <line className={selected ? 'graph-edge selected' : 'graph-edge'} x1={s.x} y1={s.y} x2={t.x} y2={t.y} />
            <text className="graph-edge-label" x={(s.x + t.x) / 2} y={(s.y + t.y) / 2 - 6}>{edge.label}</text>
          </g>
        )
      })}
      {graph.nodes.map(node => {
        const p = pos.get(node.id)
        if (!p) return null
        const selected = selectedNodeId === node.id
        return (
          <g key={node.id} className={selected ? 'graph-node selected' : `graph-node ${node.type}`}
            role="button" tabIndex={0}
            onClick={() => onSelectNode(node.id)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') onSelectNode(node.id) }}>
            <circle cx={p.x} cy={p.y} r={node.type === 'artifact' ? 24 : 18} />
            <text x={p.x} y={p.y + 42}>{node.label.length > 34 ? `${node.label.slice(0, 31)}…` : node.label}</text>
          </g>
        )
      })}
    </svg>
  )
}
