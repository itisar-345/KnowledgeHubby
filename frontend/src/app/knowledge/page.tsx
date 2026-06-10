'use client'

import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import Link from 'next/link'
import { BookOpen, FileText, GitBranch, Lightbulb, Network, Plus, Search, ShieldAlert } from 'lucide-react'

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
  artifact: <FileText size={16} />,
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
  const [graph, setGraph] = useState<GraphResponse>({ nodes: [], edges: [], layout: 'force-directed' })
  const [selectedNodeId, setSelectedNodeId] = useState('')

  async function loadKnowledge() {
    const [knowledgeResponse, graphResponse] = await Promise.all([
      fetch(`${API_BASE}/knowledge`),
      fetch(`${API_BASE}/knowledge/graph`),
    ])
    if (!knowledgeResponse.ok) throw new Error(`Knowledge API returned ${knowledgeResponse.status}`)
    if (!graphResponse.ok) throw new Error(`Knowledge graph API returned ${graphResponse.status}`)
    setData(await knowledgeResponse.json())
    setGraph(await graphResponse.json())
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
  const selectedNode = graph.nodes.find(node => node.id === selectedNodeId)
  const selectedNodeLinks = selectedNode
    ? graph.edges.filter(edge => edge.source === selectedNode.id || edge.target === selectedNode.id)
    : []

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
          <Link key={item.id} className="knowledge-card knowledge-card-link" href={`/knowledge/${encodeURIComponent(item.id)}`}>
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
            <p>{graph.nodes.length} nodes, {graph.edges.length} relationships</p>
          </div>
          {selectedNode && (
            <Link className="detail-link" href={`/knowledge/${encodeURIComponent(selectedNode.id)}`}>
              Open details
            </Link>
          )}
        </div>
        {graph.nodes.length > 0 ? (
          <div className="graph-layout">
            <KnowledgeGraph graph={graph} selectedNodeId={selectedNodeId} onSelectNode={setSelectedNodeId} />
            <aside className="graph-inspector">
              {selectedNode ? (
                <>
                  <span className="type-pill">
                    {typeIcons[selectedNode.type] || <Network size={16} />}
                    {selectedNode.type}
                  </span>
                  <h4>{selectedNode.label}</h4>
                  <p>{selectedNodeLinks.length} connected relationship{selectedNodeLinks.length === 1 ? '' : 's'}</p>
                  <div className="relationship-list">
                    {selectedNodeLinks.map(edge => {
                      const otherNodeId = edge.source === selectedNode.id ? edge.target : edge.source
                      const otherNode = graph.nodes.find(node => node.id === otherNodeId)
                      return (
                        <button key={`${edge.source}-${edge.target}-${edge.label}`} onClick={() => setSelectedNodeId(otherNodeId)}>
                          <span>{edge.label}</span>
                          <strong>{otherNode?.label || otherNodeId}</strong>
                        </button>
                      )
                    })}
                  </div>
                </>
              ) : (
                <div className="graph-empty">
                  <Network size={24} />
                  <h4>Select a node</h4>
                  <p>Inspect its relationships and jump into the detail page.</p>
                </div>
              )}
            </aside>
          </div>
        ) : (
          <div className="empty-state">
            <Network size={28} />
            <h3>No graph yet</h3>
            <p>Ingest an artifact to generate artifact-to-knowledge relationships.</p>
          </div>
        )}
      </section>
    </div>
  )
}

function KnowledgeGraph({
  graph,
  selectedNodeId,
  onSelectNode,
}: {
  graph: GraphResponse
  selectedNodeId: string
  onSelectNode: (nodeId: string) => void
}) {
  const width = 760
  const height = 420
  const centerX = width / 2
  const centerY = height / 2
  const artifactNodes = graph.nodes.filter(node => node.type === 'artifact')
  const knowledgeNodes = graph.nodes.filter(node => node.type !== 'artifact')
  const positionedNodes = new Map<string, { x: number; y: number }>()

  artifactNodes.forEach((node, index) => {
    const offset = (index - (artifactNodes.length - 1) / 2) * 88
    positionedNodes.set(node.id, { x: centerX, y: Math.max(72, centerY + offset) })
  })

  knowledgeNodes.forEach((node, index) => {
    const angle = (index / Math.max(knowledgeNodes.length, 1)) * Math.PI * 2 - Math.PI / 2
    const radiusX = 300
    const radiusY = 165
    positionedNodes.set(node.id, {
      x: centerX + Math.cos(angle) * radiusX,
      y: centerY + Math.sin(angle) * radiusY,
    })
  })

  return (
    <svg className="knowledge-graph" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Knowledge graph visualization">
      {graph.edges.map(edge => {
        const source = positionedNodes.get(edge.source)
        const target = positionedNodes.get(edge.target)
        if (!source || !target) return null
        const isSelected = selectedNodeId === edge.source || selectedNodeId === edge.target
        return (
          <g key={`${edge.source}-${edge.target}-${edge.label}`}>
            <line className={isSelected ? 'graph-edge selected' : 'graph-edge'} x1={source.x} y1={source.y} x2={target.x} y2={target.y} />
            <text className="graph-edge-label" x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 6}>
              {edge.label}
            </text>
          </g>
        )
      })}
      {graph.nodes.map(node => {
        const position = positionedNodes.get(node.id)
        if (!position) return null
        const isSelected = selectedNodeId === node.id
        const shortLabel = node.label.length > 34 ? `${node.label.slice(0, 31)}...` : node.label
        return (
          <g
            key={node.id}
            className={isSelected ? 'graph-node selected' : `graph-node ${node.type}`}
            role="button"
            tabIndex={0}
            onClick={() => onSelectNode(node.id)}
            onKeyDown={event => {
              if (event.key === 'Enter' || event.key === ' ') onSelectNode(node.id)
            }}
          >
            <circle cx={position.x} cy={position.y} r={node.type === 'artifact' ? 24 : 18} />
            <text x={position.x} y={position.y + 42}>{shortLabel}</text>
          </g>
        )
      })}
    </svg>
  )
}
