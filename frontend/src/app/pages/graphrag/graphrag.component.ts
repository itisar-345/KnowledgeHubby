import { Component, OnInit, ViewChild, ElementRef, AfterViewChecked } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { HttpClient } from '@angular/common/http'
import { firstValueFrom } from 'rxjs'
import { AuthService, API_BASE } from '../../services/auth.service'
import { ModelService } from '../../services/model.service'

type ContextNode = { id: string; title?: string; label?: string; kind?: string; type?: string; score?: number; retrieved_by?: string }
type Message = { role: 'user' | 'assistant'; content: string; citations?: string[]; context_nodes?: ContextNode[]; retrieval_mode?: string; ts: number }

const PIPELINE_STAGES = [
  'Rewriting your question…',
  'Generating hypothetical answer…',
  'Searching knowledge graph…',
  'Retrieving context nodes…',
  'Ranking results…',
  'Filtering by relevance…',
  'Generating answer…',
  'Finalising response…',
]

@Component({
  selector: 'app-graphrag',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="chat-container">
      <div class="chat-header">
        <div>
          <strong style="display:flex;align-items:center;gap:0.5rem">🧠 GraphRAG Assistant</strong>
          <p style="color:#667085;font-size:0.8rem;margin-top:0.2rem">Graph-aware retrieval · answers grounded in your knowledge base</p>
        </div>
        <div class="chat-actions">
          <span class="provider-badge" [ngClass]="'provider-' + modelService.statusBadgeColor()" [attr.aria-label]="modelService.statusBadgeText()">
            {{ modelService.statusBadgeText() }}
          </span>
          <label style="font-size:0.8rem;color:#667085;display:flex;align-items:center;gap:0.4rem">
            Top-K
            <input type="number" min="1" max="20" [(ngModel)]="topK" style="width:52px;padding:0.25rem 0.4rem;font-size:0.8rem" />
          </label>
          <button (click)="messages = []" title="Clear chat">🗑</button>
        </div>
      </div>

      <div class="messages" #messagesEl>
        @if (messages.length === 0) {
          <div style="text-align:center;color:#667085;margin-top:3rem">
            <p>Ask a question about your knowledge base.</p>
          </div>
        }
        @for (m of messages; track m.ts; let idx = $index) {
          <div [class]="'message ' + m.role">
            <div class="message-header">
              <strong>{{ m.role === 'user' ? 'You' : 'Assistant' }}</strong>
              <span class="timestamp">{{ fmt(m.ts) }}</span>
            </div>
            <p style="white-space:pre-wrap;line-height:1.6">{{ m.content }}</p>
            @if (m.role === 'assistant' && m.context_nodes && m.context_nodes.length > 0) {
              <div style="margin-top:0.75rem">
                <button style="font-size:0.75rem;padding:0.2rem 0.5rem" (click)="toggleCtx(idx)">
                  {{ expandedCtx === idx ? 'Hide' : 'Show' }} {{ m.context_nodes.length }} context nodes
                  @if (m.retrieval_mode) { <span style="margin-left:0.4rem;color:#667085">· {{ m.retrieval_mode }}</span> }
                </button>
                @if (expandedCtx === idx) {
                  <div style="margin-top:0.5rem;display:flex;flex-direction:column;gap:0.3rem">
                    @for (n of m.context_nodes; track n.id) {
                      <div style="background:#f8fbfa;border:1px solid #e5ecea;border-radius:5px;padding:0.4rem 0.6rem;font-size:0.8rem">
                        <span style="color:#667085;margin-right:0.4rem">[{{ n.id.slice(0,16) }}…]</span>
                        <strong>{{ n.title || n.label }}</strong>
                        <span style="color:#667085;margin-left:0.4rem">
                          ({{ n.kind || n.type }}){{ n.score != null ? ' · ' + n.score.toFixed(3) : '' }}{{ n.retrieved_by ? ' · via ' + n.retrieved_by : '' }}
                        </span>
                      </div>
                    }
                  </div>
                }
              </div>
            }
          </div>
        }
        @if (loading) {
          <div class="typing-indicator" aria-live="polite" aria-atomic="true">
            {{ pipelineStage }} <span class="latency-hint">Generating locally — no data leaves this device</span>
          </div>
        }
        <div #bottomEl></div>
      </div>

      <div class="input-area">
        <textarea rows="2" placeholder="Ask about decisions, risks, lessons, best practices…"
          [(ngModel)]="input" (keydown)="onKey($event)" [disabled]="loading"></textarea>
        <button class="primary" (click)="send()" [disabled]="loading || !input.trim()" title="Send">➤</button>
      </div>
    </div>
  `,
  styles: [`
    .provider-badge {
      padding: 0.25rem 0.6rem;
      border-radius: 4px;
      font-size: 0.78rem;
      font-weight: 500;
    }
    .provider-green { background: #e6f7e6; color: #1a6b1a; }
    .provider-blue  { background: #e6f0ff; color: #0033cc; }
    .provider-red   { background: #ffe6e6; color: #cc0000; }
    .latency-hint   { color: #667085; font-size: 0.75rem; margin-left: 0.5rem; }
  `]
})
export class GraphragComponent implements AfterViewChecked {
  @ViewChild('bottomEl') bottomEl!: ElementRef
  messages: Message[] = []; input = ''; loading = false; topK = 8; expandedCtx: number | null = null
  pipelineStage = ''
  private shouldScroll = false
  private _stageInterval: any = null

  constructor(private http: HttpClient, public auth: AuthService, public modelService: ModelService) {}

  ngAfterViewChecked() {
    if (this.shouldScroll) { this.bottomEl?.nativeElement?.scrollIntoView({ behavior: 'smooth' }); this.shouldScroll = false }
  }

  toggleCtx(idx: number) { this.expandedCtx = this.expandedCtx === idx ? null : idx }

  onKey(e: KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.send() } }

  fmt(ts: number) { return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }

  private _startPipelineProgress() {
    let i = 0
    this.pipelineStage = PIPELINE_STAGES[0]
    this._stageInterval = setInterval(() => {
      i = Math.min(i + 1, PIPELINE_STAGES.length - 1)
      this.pipelineStage = PIPELINE_STAGES[i]
    }, 1200)
  }

  private _stopPipelineProgress() {
    if (this._stageInterval) { clearInterval(this._stageInterval); this._stageInterval = null }
    this.pipelineStage = ''
  }

  async send() {
    const q = this.input.trim()
    if (!q || this.loading) return
    this.input = ''
    // Capture history before pushing the new user message so the current
    // question isn't duplicated in both the history array and the question field.
    const history = this.messages.slice(-6).map(m => ({ role: m.role, content: m.content }))
    this.messages.push({ role: 'user', content: q, ts: Date.now() })
    this.loading = true; this.shouldScroll = true
    this._startPipelineProgress()
    try {
      const data: any = await firstValueFrom(this.http.post(`${API_BASE}/knowledge/graphrag/query`,
        { question: q, top_k: this.topK, history },
        { headers: this.auth.authHeaders() }
      ))
      this.messages.push({ role: 'assistant', content: data.answer, citations: data.citations, context_nodes: data.context_nodes, retrieval_mode: data.retrieval_mode, ts: Date.now() })
    } catch (e: any) {
      this.messages.push({ role: 'assistant', content: `Error: ${e?.message || 'Request failed'}`, ts: Date.now() })
    } finally { this._stopPipelineProgress(); this.loading = false; this.shouldScroll = true }
  }
}
