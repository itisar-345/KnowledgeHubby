import { Component, OnInit } from '@angular/core'
import { CommonModule, DecimalPipe } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { ModelService, LocalModel } from '../../services/model.service'

@Component({
  selector: 'app-model-manager',
  standalone: true,
  imports: [CommonModule, FormsModule, DecimalPipe],
  template: `
    <div class="model-manager">
      <h1>Model Manager</h1>

      @if (successMsg) {
        <div class="toast-success">{{ successMsg }}</div>
      }

      @if (!service.initialized()) {
        <div class="loading-state">
          <div class="spinner"></div>
          <p>Checking installed models…</p>
        </div>
      } @else {
        @if (service.systemInfo()) {
          <div class="info-card">
            <div class="info-stat">
              <div>
                <p class="info-stat__label">System RAM</p>
                <p class="info-stat__value">{{ service.systemInfo()?.ramGb }} GB</p>
              </div>
            </div>
            <div class="info-divider"></div>
            <div class="info-stat">
              <div>
                <p class="info-stat__label">Active Model</p>
                <p class="info-stat__value" [class.info-stat__value--muted]="!service.modelStatus()?.llm?.installed">
                  {{ service.modelStatus()?.llm?.installed ? service.modelStatus()?.llm?.model : 'None' }}
                </p>
              </div>
              <span [class]="'info-pill info-pill--' + overallStatus">{{ service.modelStatus()?.llm?.installed ? 'Active' : 'Inactive' }}</span>
            </div>
            <div class="info-divider"></div>
            <div class="info-stat">
              <div>
                <p class="info-stat__label">RAM Compatible</p>
                <p class="info-stat__value">{{ ramCompatCount }}/{{ CATALOGUE.length }} models</p>
              </div>
              <span [class]="'info-pill info-pill--' + ramStatus">{{ ramGb }} GB</span>
            </div>
          </div>
        }

        @if (!ollamaReachable) {
          <div class="warning-banner">
            ⚠ Ollama is not running. Start it with <code>ollama serve</code> before installing models.
          </div>
        }

        <section class="models-section">
          <div class="models-grid">
            @for (model of allModels; track model.id) {
              <div class="model-card" [class.is-installed]="model.installed" [class.ram-warn]="ramGb > 0 && ramGb < model.minRam">
                <div class="model-card-top">
                  <div>
                    <h3>{{ model.name }}</h3>
                    <p class="model-meta">{{ model.size }} · {{ model.ramRequired }}</p>
                  </div>
                  <div class="badge-group">
                    @if (model.installed && isDefault(model.id)) {
                      <span class="badge-default">Default</span>
                    }
                    <span [class]="'install-badge install-badge--' + (model.installed ? 'installed' : 'not-installed')">
                      {{ model.installed ? '✓ Installed' : 'Not installed' }}
                    </span>
                  </div>
                </div>

                @if (model.installed) {
                  <div class="model-actions">
                    @if (!isDefault(model.id)) {
                      <button class="btn-primary" (click)="setDefault(model.id)">Set Default</button>
                    }
                    <button class="btn-danger" [disabled]="removingId === model.id" (click)="removeModel(model.id)">
                      {{ removingId === model.id ? 'Removing…' : 'Remove' }}
                    </button>
                  </div>
                } @else if (installingId === model.id) {
                  <div class="progress-wrap">
                    <div class="progress-header">
                      <span class="progress-status">{{ service.installProgress()?.status || 'Connecting…' }}</span>
                      <span class="progress-pct">{{ service.installProgress()?.percent ?? 0 }}%</span>
                    </div>
                    <div class="progress-track">
                      <div class="progress-bar" [style.width.%]="service.installProgress()?.percent ?? 0"></div>
                    </div>
                    <p class="progress-bytes">
                      @if (service.installProgress()?.total) {
                        {{ (service.installProgress()!.completed / 1024 / 1024 / 1024 | number:'1.1-1') }} GB
                        / {{ (service.installProgress()!.total / 1024 / 1024 / 1024 | number:'1.1-1') }} GB
                      } @else {
                        Waiting for data…
                      }
                    </p>
                  </div>
                } @else {
                  <button class="btn-primary" [disabled]="!!installingId" (click)="installModel(model.id)">
                    {{ installingId ? 'Installing another…' : 'Install' }}
                  </button>
                }

                @if (errorId === model.id) {
                  <p class="error-text">{{ errorMsg }}</p>
                }
              </div>
            }
          </div>
        </section>
      }
    </div>
  `,
  styles: [`
    .model-manager { max-width: 960px; margin: 0 auto; padding: 2rem; }
    h1 { font-size: 1.75rem; margin-bottom: 0.25rem; color: #1f2933; }

    .info-card {
      display: grid;
      grid-template-columns: 1fr auto 1fr auto 1fr;
      align-items: center;
      background: #fff;
      border: 1px solid #e5ecea;
      border-radius: 12px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 2px 8px rgba(102,126,234,0.07);
    }

    .info-divider {
      width: 1px; height: 2.5rem;
      background: #e5ecea; margin: 0 1.25rem;
    }

    .info-stat {
      display: flex; align-items: center; gap: 0.75rem;
    }

    .info-stat__label {
      font-size: 0.7rem; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.05em; color: #94a3b8; margin: 0 0 0.15rem;
    }

    .info-stat__value {
      font-size: 0.95rem; font-weight: 700; color: #1f2933; margin: 0;
    }
    .info-stat__value--muted { color: #94a3b8; font-weight: 500; }

    .info-pill {
      margin-left: auto;
      font-size: 0.68rem; font-weight: 700;
      padding: 0.2rem 0.6rem; border-radius: 999px;
      white-space: nowrap; text-transform: uppercase; letter-spacing: 0.04em;
    }
    .info-pill--ready  { background: #dcfce7; color: #15803d; }
    .info-pill--none   { background: #fee2e2; color: #b91c1c; }

    .warning-banner {
      background: #fff8e1; border-left: 4px solid #f59e0b;
      padding: 0.85rem 1.25rem; border-radius: 6px;
      font-size: 0.875rem; color: #92400e; margin-bottom: 1rem;
    }
    .warning-banner code {
      background: #fef3c7; padding: 0.1rem 0.4rem;
      border-radius: 3px; font-size: 0.8rem;
    }

    .models-section { margin-top: 0.5rem; }
    .models-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 1.25rem;
    }

    .model-card {
      background: rgba(255,255,255,0.97);
      border: 1px solid #e5ecea;
      border-radius: 10px; padding: 1.25rem;
      box-shadow: 0 2px 8px rgba(102,126,234,0.07);
      display: flex; flex-direction: column; gap: 0.75rem;
      transition: box-shadow 0.2s;
    }
    .model-card:hover { box-shadow: 0 6px 20px rgba(102,126,234,0.14); }
    .model-card.is-installed { border-color: #a7f3d0; background: #f0fdf4; }
    .model-card.ram-warn { border-color: #fcd34d; background: #fffbeb; }

    .model-card-top { display: flex; justify-content: space-between; align-items: flex-start; }
    .model-card h3 { font-size: 1rem; color: #1f2933; margin: 0; }
    .model-meta { font-size: 0.8rem; color: #667085; margin-top: 0.2rem; }

    .badge-group { display: flex; flex-direction: column; align-items: flex-end; gap: 0.3rem; }

    .badge-default {
      background: #667eea; color: #fff;
      font-size: 0.7rem; font-weight: 600;
      padding: 0.2rem 0.5rem; border-radius: 999px;
      white-space: nowrap;
    }

    .install-badge {
      font-size: 0.7rem; font-weight: 600;
      padding: 0.2rem 0.55rem; border-radius: 999px;
      white-space: nowrap;
    }
    .install-badge--installed   { background: #dcfce7; color: #15803d; }
    .install-badge--not-installed { background: #f1f5f9; color: #64748b; }

    .status-badge--ready    { background: #dcfce7; color: #15803d; }
    .status-badge--none     { background: #fee2e2; color: #b91c1c; }

    .loading-state {
      display: flex; flex-direction: column; align-items: center;
      gap: 0.75rem; padding: 3rem 0; color: #667085; font-size: 0.9rem;
    }

    .model-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }

    .toast-success {
      position: fixed; top: 1.5rem; right: 1.5rem; z-index: 999;
      background: #16a34a; color: white;
      padding: 0.75rem 1.25rem; border-radius: 8px;
      font-size: 0.875rem; font-weight: 500;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      animation: fadeIn 0.2s ease;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: none; } }

    .progress-wrap { display: flex; flex-direction: column; gap: 0.4rem; }
    .progress-header { display: flex; justify-content: space-between; align-items: center; }
    .progress-status { font-size: 0.75rem; color: #667eea; font-weight: 500; }
    .progress-pct { font-size: 0.75rem; font-weight: 700; color: #1f2933; }
    .progress-track {
      height: 6px; background: #e5ecea; border-radius: 999px; overflow: hidden;
    }
    .progress-bar {
      height: 100%; background: linear-gradient(90deg, #667eea, #764ba2);
      border-radius: 999px; transition: width 0.3s ease;
    }
    .progress-bytes { font-size: 0.7rem; color: #94a3b8; margin: 0; }

    .error-text { color: #b42318; font-size: 0.78rem; margin: 0; }

    .btn-primary, .btn-danger {
      padding: 0.45rem 0.9rem; border: none; border-radius: 5px;
      cursor: pointer; font-weight: 500; font-size: 0.825rem;
      transition: opacity 0.2s; white-space: nowrap;
    }
    .btn-primary { background: #667eea; color: white; }
    .btn-primary:hover:not(:disabled) { opacity: 0.88; }
    .btn-primary:disabled { opacity: 0.45; cursor: not-allowed; }
    .btn-danger { background: #fee2e2; color: #b91c1c; }
    .btn-danger:hover:not(:disabled) { background: #fecaca; }
    .btn-danger:disabled { opacity: 0.45; cursor: not-allowed; }
  `],
})
export class ModelManagerComponent implements OnInit {
  installingId: string | null = null
  removingId: string | null = null
  errorId: string | null = null
  errorMsg = ''
  successMsg = ''
  ollamaReachable = true

  readonly CATALOGUE: (Omit<LocalModel, 'installed'> & { minRam: number })[] = [
    { id: 'llama3.1:8b',  name: 'Llama 3.1 8B',  size: '4.7 GB', ramRequired: '8 GB+',  provider: 'ollama', minRam: 8  },
    { id: 'mistral:7b',   name: 'Mistral 7B',     size: '4.1 GB', ramRequired: '8 GB+',  provider: 'ollama', minRam: 8  },
    { id: 'gpt-oss:20b',  name: 'GPT-OSS 20B',    size: '13 GB',  ramRequired: '16 GB+', provider: 'ollama', minRam: 16 },
  ]

  get allModels(): (LocalModel & { minRam: number })[] {
    const installed = new Set(this.service.localModels().filter(m => m.installed).map(m => m.id))
    return this.CATALOGUE.map(m => ({ ...m, installed: installed.has(m.id) }))
  }

  get ramGb(): number { return this.service.systemInfo()?.ramGb ?? 0 }

  get ramStatus(): 'ready' | 'none' {
    return this.ramGb > 0 ? 'ready' : 'none'
  }

  get ramCompatCount(): number {
    return this.CATALOGUE.filter(m => this.ramGb >= m.minRam).length
  }

  constructor(public service: ModelService) {}

  get overallStatus(): 'ready' | 'none' {
    return this.service.modelStatus()?.llm?.installed ? 'ready' : 'none'
  }

  get overallStatusLabel(): string {
    const status = this.service.modelStatus()?.llm
    return status?.installed ? `⚡ Active: ${status.model}` : '⚠ Nothing activated'
  }

  async ngOnInit() {
    await this.service.loadAll()
  }

  isDefault(modelId: string): boolean {
    return this.service.modelStatus()?.llm?.model === modelId
  }

  async installModel(modelId: string) {
    this.installingId = modelId
    this.errorId = null
    this.errorMsg = ''
    this.successMsg = ''
    this.ollamaReachable = true
    try {
      await this.service.installModel(modelId)
      this.successMsg = `✓ ${modelId} installed successfully`
      setTimeout(() => this.successMsg = '', 5000)
    } catch (e: any) {
      this.errorId = modelId
      const detail = e?.message || ''
      this.errorMsg = detail || 'Install failed. Is Ollama running?'
      if (detail.toLowerCase().includes('ollama') || detail.toLowerCase().includes('connect')) {
        this.ollamaReachable = false
      }
    } finally {
      this.installingId = null
    }
  }

  async removeModel(modelId: string) {
    if (!confirm(`Remove ${modelId}?`)) return
    this.removingId = modelId
    this.errorId = null
    try {
      await this.service.removeModel(modelId)
      this.successMsg = `✓ ${modelId} removed`
      setTimeout(() => this.successMsg = '', 3000)
    } catch (e: any) {
      this.errorId = modelId
      this.errorMsg = e?.error?.detail || e?.message || 'Remove failed'
    } finally {
      this.removingId = null
    }
  }

  async setDefault(modelId: string) {
    try {
      await this.service.setDefaultModel(modelId)
      this.successMsg = `✓ ${modelId} set as default`
      setTimeout(() => this.successMsg = '', 3000)
    } catch (e: any) {
      this.errorId = modelId
      this.errorMsg = e?.error?.detail || e?.message || 'Failed to set default'
    }
  }
}
