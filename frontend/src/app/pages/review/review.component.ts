import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { RouterLink } from '@angular/router'
import { HttpClient } from '@angular/common/http'
import { firstValueFrom } from 'rxjs'
import { AuthService, API_BASE } from '../../services/auth.service'

type ReviewItem = { id: string; title: string; type: string; author: string; date: string; tags: string[]; details: Record<string, unknown>; review_status: string; review_note: string; extraction_engine?: string }

@Component({
  selector: 'app-review',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="knowledge-shell">
      <section class="toolbar">
        <div>
          <h2>Review Queue</h2>
          <p>{{ items.length }} pending item{{ items.length === 1 ? '' : 's' }} awaiting review</p>
        </div>
        <a class="back-link" routerLink="/knowledge">← Back to hub</a>
      </section>

      @if (error) { <p class="error-text" style="padding:0 0.25rem">{{ error }}</p> }

      @if (items.length === 0 && !error) {
        <section class="empty-state">
          <h3>Queue is clear</h3>
          <p>All extracted knowledge has been reviewed.</p>
        </section>
      }

      <div class="review-list">
        @for (item of items; track item.id) {
          <div class="review-card">
            <div class="card-topline">
              <span class="type-pill">{{ item.type }}</span>
              <span class="engine-badge" [ngClass]="engineClass(item.extraction_engine)">{{ engineLabel(item.extraction_engine) }}</span>
              <span class="muted-text">{{ item.date | date }}</span>
            </div>
            @if (editingId === item.id) {
              <div class="form-stack" style="margin-top:0.75rem">
                <input [(ngModel)]="editTitle" />
                <input placeholder="Review note (optional)" [(ngModel)]="editNote" />
                <div style="display:flex;gap:0.5rem">
                  <button class="success" [disabled]="loading" (click)="decide(item.id, 'accepted', editTitle, editNote)">Accept edited</button>
                  <button (click)="editingId = null">Cancel</button>
                </div>
              </div>
            } @else {
              <h3 style="margin:0.75rem 0 0.25rem">{{ item.title }}</h3>
              <p class="muted-text">by {{ item.author }}</p>
              <div class="tag-row">@for (t of item.tags; track t) { <span>#{{ t }}</span> }</div>
              <div class="review-actions">
                <button class="success" [disabled]="loading" (click)="decide(item.id, 'accepted')">Accept</button>
                <button [disabled]="loading" (click)="startEdit(item)">Edit &amp; Accept</button>
                <button class="danger" [disabled]="loading" (click)="decide(item.id, 'rejected')">Reject</button>
              </div>
            }
          </div>
        }
      </div>
    </div>
  `
})
export class ReviewComponent implements OnInit {
  items: ReviewItem[] = []; editingId: string | null = null
  editTitle = ''; editNote = ''; loading = false; error = ''

  constructor(private http: HttpClient, public auth: AuthService) {}

  ngOnInit() { this.load() }

  async load() {
    const res: any = await firstValueFrom(this.http.get(`${API_BASE}/knowledge/review`, { headers: this.auth.authHeaders() })).catch(() => null)
    if (res) this.items = res; else this.error = 'Could not load review queue'
  }

  startEdit(item: ReviewItem) { this.editingId = item.id; this.editTitle = item.title; this.editNote = '' }

  engineLabel(engine?: string) {
    return engine === 'cloud_llm' ? 'Cloud LLM' : engine === 'local_llm' ? 'Local LLM' : 'Regex'
  }

  engineClass(engine?: string) {
    return engine === 'cloud_llm' ? 'engine-cloud' : engine === 'local_llm' ? 'engine-local' : 'engine-regex'
  }

  async decide(id: string, status: 'accepted' | 'rejected', title?: string, note?: string) {
    this.loading = true
    try {
      await firstValueFrom(this.http.patch(`${API_BASE}/knowledge/review/${id}`, { status, note: note || '', title }, { headers: this.auth.authHeaders() }))
      this.items = this.items.filter(i => i.id !== id); this.editingId = null
    } catch { this.error = 'Could not update item' }
    finally { this.loading = false }
  }
}
