import { Component, EventEmitter, Output } from '@angular/core'
import { CommonModule } from '@angular/common'
import { Router } from '@angular/router'
import { ModelService } from '../../services/model.service'

@Component({
  selector: 'app-model-privacy-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">Model &amp; Privacy</span>
        <button class="close-btn" (click)="close.emit()" aria-label="Close">✕</button>
      </div>

      <div class="panel-body">

        <!-- LLM status -->
        <div class="section">
          <p class="section-label">LLM</p>
          <div class="row">
            <span class="row-key">Provider</span>
            <span class="pill" [class]="providerClass()">{{ service.currentLlmProvider() }}</span>
          </div>
          <div class="row">
            <span class="row-key">Model</span>
            <span class="row-val">{{ service.currentLlmModel() }}</span>
          </div>
          <div class="row">
            <span class="row-key">Status</span>
            @if (service.modelStatus()?.llm?.installed) {
              <span class="pill pill-green">● Installed</span>
            } @else {
              <span class="pill pill-red">● Not installed</span>
            }
          </div>
        </div>

        <!-- Embedding status -->
        @if (service.modelStatus()?.embedding) {
          <div class="section">
            <p class="section-label">Embeddings</p>
            <div class="row">
              <span class="row-key">Provider</span>
              <span class="row-val">{{ service.modelStatus()?.embedding?.provider }}</span>
            </div>
            <div class="row">
              <span class="row-key">Model</span>
              <span class="row-val">{{ service.modelStatus()?.embedding?.model || 'all-MiniLM-L6-v2' }}</span>
            </div>
          </div>
        }

        <!-- Cloud toggle -->
        <div class="section">
          <p class="section-label">Cloud Access</p>
          <label class="toggle-row">
            <div class="toggle" [class.on]="service.cloudEnabled()" (click)="toggleCloud()">
              <div class="toggle-thumb"></div>
            </div>
            <span>{{ service.cloudEnabled() ? 'Cloud providers enabled' : 'Local-only mode' }}</span>
          </label>
          <p class="hint">When off, all AI processing stays on this device.</p>
        </div>

        <!-- Actions -->
        <div class="section">
          <p class="section-label">Actions</p>
          <button class="action-btn" (click)="goTo('/settings/models')">
            <span>🤖</span> Manage local models
          </button>
          <button class="action-btn" (click)="goTo('/workspace-settings')">
            <span>⚙️</span> Workspace settings
          </button>
          <button class="action-btn secondary" (click)="goTo('/privacy-policy')">
            <span>🔒</span> Data privacy policy
          </button>
        </div>

      </div>
    </div>
  `,
  styles: [`
    .panel {
      position: fixed; right: 0; top: 0; bottom: 0; width: 340px;
      background: #fff; z-index: 100;
      display: flex; flex-direction: column;
      box-shadow: -4px 0 24px rgba(0,0,0,0.12);
      animation: slideIn 0.22s ease-out;
    }
    @keyframes slideIn { from { transform: translateX(100%) } to { transform: none } }

    .panel-header {
      display: flex; justify-content: space-between; align-items: center;
      padding: 1rem 1.25rem;
      border-bottom: 1px solid #e5ecea;
      background: #f8f7ff;
    }
    .panel-title { font-weight: 700; font-size: 0.95rem; color: #1f2933; }
    .close-btn {
      background: none; border: none; cursor: pointer;
      color: #667085; font-size: 1rem; padding: 0.25rem; line-height: 1;
    }
    .close-btn:hover { color: #1f2933; }

    .panel-body { flex: 1; overflow-y: auto; padding: 0.75rem 0; }

    .section {
      padding: 0.75rem 1.25rem;
      border-bottom: 1px solid #f0f0f0;
    }
    .section:last-child { border-bottom: none; }

    .section-label {
      font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.06em; color: #98a2b3; margin: 0 0 0.6rem;
    }

    .row {
      display: flex; justify-content: space-between; align-items: center;
      padding: 0.35rem 0;
    }
    .row-key { font-size: 0.85rem; color: #475467; }
    .row-val { font-size: 0.85rem; color: #1f2933; font-weight: 500; }

    .pill {
      font-size: 0.75rem; font-weight: 600;
      padding: 0.2rem 0.55rem; border-radius: 999px;
    }
    .pill-green  { background: #dcfce7; color: #15803d; }
    .pill-red    { background: #fee2e2; color: #b91c1c; }
    .pill-purple { background: #ede9ff; color: #5a3fc0; }
    .pill-blue   { background: #dbeafe; color: #1d4ed8; }

    .toggle-row {
      display: flex; align-items: center; gap: 0.75rem;
      cursor: pointer; font-size: 0.875rem; color: #1f2933; font-weight: 500;
    }
    .toggle {
      width: 36px; height: 20px; border-radius: 999px;
      background: #d1d5db; position: relative;
      transition: background 0.2s; flex-shrink: 0; cursor: pointer;
    }
    .toggle.on { background: #667eea; }
    .toggle-thumb {
      position: absolute; top: 2px; left: 2px;
      width: 16px; height: 16px; border-radius: 50%;
      background: #fff; transition: transform 0.2s;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    }
    .toggle.on .toggle-thumb { transform: translateX(16px); }

    .hint { font-size: 0.78rem; color: #98a2b3; margin: 0.4rem 0 0; line-height: 1.4; }

    .action-btn {
      display: flex; align-items: center; gap: 0.6rem;
      width: 100%; padding: 0.65rem 0.85rem;
      background: #f8f7ff; border: 1px solid #e0d9ff;
      border-radius: 7px; cursor: pointer;
      font-size: 0.875rem; font-weight: 500; color: #3b2a7a;
      margin-bottom: 0.5rem; text-align: left;
      transition: background 0.15s;
    }
    .action-btn:last-child { margin-bottom: 0; }
    .action-btn:hover { background: #ede9ff; }
    .action-btn.secondary {
      background: #f8fbfa; border-color: #e5ecea; color: #344054;
    }
    .action-btn.secondary:hover { background: #f0f4f8; }
  `],
})
export class ModelPrivacyPanelComponent {
  @Output() close = new EventEmitter<void>()

  constructor(public service: ModelService, private router: Router) {}

  providerClass(): string {
    const p = this.service.currentLlmProvider()
    if (p === 'local') return 'pill pill-green'
    if (p === 'cloud') return 'pill pill-blue'
    return 'pill pill-red'
  }

  toggleCloud() {
    this.service.toggleCloudProvider(!this.service.cloudEnabled())
  }

  goTo(path: string) {
    this.close.emit()
    this.router.navigate([path])
  }
}
