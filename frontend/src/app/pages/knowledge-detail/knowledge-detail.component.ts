import { Component, OnInit } from '@angular/core'
import { ActivatedRoute, RouterLink } from '@angular/router'
import { CommonModule } from '@angular/common'
import { HttpClient } from '@angular/common/http'
import { firstValueFrom } from 'rxjs'
import { AuthService, API_BASE } from '../../services/auth.service'

type Artifact = { id: string; title: string; content: string; source: string; author: string; tags: string[]; created_at: string }
type KnowledgeItem = { id: string; artifact_id: string; title: string; type: string; author: string; date: string; tags: string[]; details: Record<string, unknown> }
type Relationship = { from: string; to: string; type: string }
type CrossLink = { item_id_a: string; item_id_b: string; score: number }
type RelatedItem = { item: KnowledgeItem; score: number }

@Component({
  selector: 'app-knowledge-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="detail-shell">
      <a class="back-link" routerLink="/knowledge">← Back to hub</a>

      <ng-container *ngIf="error">
        <section class="empty-state"><h3>Could not load this item</h3><p>{{ error }}</p></section>
      </ng-container>

      <ng-container *ngIf="!error && !item">
        <section class="empty-state"><h3>{{ data ? 'Knowledge item not found' : 'Loading…' }}</h3></section>
      </ng-container>

      <ng-container *ngIf="!error && item">
        <section class="detail-hero">
          <div class="detail-title">
            <span class="type-pill">{{ item.type }}</span>
            <h2>{{ item.title }}</h2>
          </div>
          <div class="detail-meta-grid">
            <div><span>{{ item.author }}</span></div>
            <div><span>{{ item.date | date:'medium' }}</span></div>
            <div><span>{{ relationships.length }} relationship{{ relationships.length === 1 ? '' : 's' }}</span></div>
            <div><span>{{ item.tags.length }} tag{{ item.tags.length === 1 ? '' : 's' }}</span></div>
          </div>
        </section>

        <div class="detail-grid">
          <section class="detail-panel">
            <h3>Extracted Details</h3>
            <p *ngIf="detailEntries.length === 0" class="muted-text">No structured detail was captured.</p>
            <dl *ngIf="detailEntries.length > 0" class="detail-fields">
              <div *ngFor="let entry of detailEntries">
                <dt>{{ humanize(entry.key) }}</dt>
                <dd>{{ formatValue(entry.value) }}</dd>
              </div>
            </dl>
          </section>

          <aside class="detail-panel">
            <h3>Source Artifact</h3>
            <ng-container *ngIf="artifact; else noArtifact">
              <div class="artifact-summary">
                <div class="artifact-icon">📄</div>
                <div>
                  <h4>{{ artifact.title }}</h4>
                  <p>{{ artifact.source }} by {{ artifact.author }}</p>
                </div>
              </div>
            </ng-container>
            <ng-template #noArtifact>
              <p class="muted-text">No source artifact found.</p>
            </ng-template>
            <div class="tag-row detail-tags">
              <ng-container *ngIf="item.tags.length > 0; else untagged">
                <span *ngFor="let tag of item.tags">#{{ tag }}</span>
              </ng-container>
              <ng-template #untagged><span>untagged</span></ng-template>
            </div>
          </aside>
        </div>

        <section class="detail-panel">
          <h3>Relationships</h3>
          <ng-container *ngIf="relationships.length > 0; else noRels">
            <div class="relationship-table">
              <div *ngFor="let edge of relationships">
                <span>{{ edge.from === item.id ? 'Outgoing' : 'Incoming' }}</span>
                <strong>{{ edge.type }}</strong>
                <code>{{ edge.from === item.id ? edge.to : edge.from }}</code>
              </div>
            </div>
          </ng-container>
          <ng-template #noRels>
            <p class="muted-text">No relationships recorded for this item yet.</p>
          </ng-template>
        </section>

        <section *ngIf="relatedItems.length > 0" class="detail-panel">
          <h3>Related Items <span style="font-weight:400;color:#667085;font-size:0.85rem">via cross-source linking</span></h3>
          <div class="relationship-table">
            <div *ngFor="let r of relatedItems" style="grid-template-columns:80px minmax(0,1fr) 60px">
              <span class="type-pill" style="font-size:0.72rem">{{ r.item.type }}</span>
              <a [routerLink]="['/knowledge', r.item.id]" style="color:#0066cc;text-decoration:none;font-weight:500;font-size:0.875rem">{{ r.item.title }}</a>
              <span style="color:#667085;font-size:0.75rem;text-align:right">{{ (r.score * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </section>

        <section *ngIf="artifact" class="detail-panel">
          <h3>Source Preview</h3>
          <p class="source-preview">{{ artifact.content }}</p>
        </section>
      </ng-container>
    </div>
  `
})
export class KnowledgeDetailComponent implements OnInit {
  data: any = null; error = ''; id = ''
  private crossLinks: CrossLink[] = []

  get item(): KnowledgeItem | undefined {
    return this.data?.knowledge_items?.find((i: KnowledgeItem) => i.id === this.id)
  }
  get artifact(): Artifact | undefined {
    return this.data?.artifacts?.find((a: Artifact) => a.id === this.item?.artifact_id)
  }
  get relationships(): Relationship[] {
    if (!this.data || !this.item) return []
    return this.data.relationships.filter((e: Relationship) => e.from === this.item!.id || e.to === this.item!.id)
  }
  get detailEntries(): { key: string; value: unknown }[] {
    return Object.entries(this.item?.details || {}).map(([key, value]) => ({ key, value }))
  }
  get relatedItems(): RelatedItem[] {
    if (!this.data || !this.item) return []
    const item = this.item
    return this.crossLinks
      .filter(l => l.item_id_a === item.id || l.item_id_b === item.id)
      .map(l => {
        const otherId = l.item_id_a === item.id ? l.item_id_b : l.item_id_a
        const other: KnowledgeItem | undefined = this.data.knowledge_items.find((i: KnowledgeItem) => i.id === otherId)
        return other ? { item: other, score: l.score } : null
      })
      .filter((x): x is RelatedItem => x !== null)
      .sort((a, b) => b.score - a.score)
  }

  constructor(private route: ActivatedRoute, private http: HttpClient, public auth: AuthService) {}

  ngOnInit() {
    this.id = this.route.snapshot.paramMap.get('id') || ''
    this.load()
  }

  async load() {
    try {
      const headers = this.auth.authHeaders()
      const [kr, lr]: any[] = await Promise.all([
        firstValueFrom(this.http.get(`${API_BASE}/knowledge`, { headers })),
        firstValueFrom(this.http.get(`${API_BASE}/knowledge/links`, { headers })).catch(() => []),
      ])
      this.data = kr; this.crossLinks = lr || []
    } catch (e: any) { this.error = e?.message || 'Could not load knowledge item' }
  }

  humanize(v: string) { return v.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) }
  formatValue(v: unknown): string {
    if (Array.isArray(v)) return v.join(', ')
    if (typeof v === 'object' && v !== null) return JSON.stringify(v, null, 2)
    if (v === null || v === undefined || v === '') return 'Not specified'
    return String(v)
  }
}
