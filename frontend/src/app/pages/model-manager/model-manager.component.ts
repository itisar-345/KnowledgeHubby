import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { ModelService, LocalModel } from '../../services/model.service'

@Component({
  selector: 'app-model-manager',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="model-manager">
      <h1>Model Manager</h1>

      @if (service.systemInfo()) {
        <section class="system-info">
          <h2>System Resources</h2>
          <div class="info-card">
            <p><strong>Available RAM:</strong> {{ service.systemInfo()?.ramGb }}GB</p>
            <p><strong>Recommended Tier:</strong> {{ service.systemInfo()?.recommendedTier }}</p>
            <p class="info-text">Choose models that fit your system's RAM for reliable performance.</p>
          </div>
        </section>
      }

      <section class="models-section">
        <h2>Available Models</h2>
        <div class="models-grid">
          @for (model of recommendedModels; track model.id) {
            <div class="model-card">
              <h3>{{ model.name }}</h3>
              <div class="model-details">
                <p><strong>Size:</strong> {{ model.size }}</p>
                <p><strong>RAM Required:</strong> {{ model.ramRequired }}</p>
              </div>

              @if (model.installed) {
                <p class="status-installed">✓ Installed</p>
                <button class="btn-secondary" (click)="removeModel(model.id)">Remove</button>
              } @else if (installingId === model.id) {
                <!-- Indeterminate spinner — makes no false claim about download % -->
                <div class="spinner-wrap">
                  <div class="spinner"></div>
                  <p class="status-downloading">Installing… this can take several minutes</p>
                </div>
              } @else {
                <button class="btn-primary" [disabled]="!!installingId" (click)="installModel(model.id)">
                  Install
                </button>
              }

              @if (errorId === model.id) {
                <p class="error-text">{{ errorMsg }}</p>
              }
            </div>
          }
        </div>
      </section>

      @if (installedModels.length > 0) {
        <section class="models-section">
          <h2>Installed Models</h2>
          <div class="models-list">
            @for (model of installedModels; track model.id) {
              <div class="model-item">
                <div class="model-info">
                  <h3>{{ model.name }}</h3>
                  <p>{{ model.size }} • {{ model.ramRequired }}</p>
                </div>
                <div class="model-actions">
                  <button class="btn-primary" (click)="setDefault(model.id)">Set as Default</button>
                  <button class="btn-secondary" (click)="removeModel(model.id)">Remove</button>
                </div>
              </div>
            }
          </div>
        </section>
      }
    </div>
  `,
  styles: [`
    .model-manager { max-width: 1000px; margin: 0 auto; padding: 2rem; }
    h1 { font-size: 2rem; margin-bottom: 2rem; }
    h2 { font-size: 1.25rem; margin: 2rem 0 1rem; color: #333; }

    .system-info { margin-bottom: 2rem; }
    .info-card {
      background: #f0f8ff; border-left: 4px solid #0066cc;
      padding: 1.5rem; border-radius: 4px;
    }
    .info-card p { margin: 0.5rem 0; font-size: 0.95rem; }
    .info-text { color: #666; font-size: 0.875rem; margin-top: 1rem !important; }

    .models-section { margin-bottom: 3rem; }

    .models-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
      gap: 1.5rem; margin-top: 1rem;
    }

    .model-card {
      background: white; border: 1px solid #e0e0e0;
      border-radius: 8px; padding: 1.5rem;
      transition: box-shadow 0.2s;
    }
    .model-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    .model-card h3 { font-size: 1.1rem; margin: 0 0 1rem; color: #333; }
    .model-details { margin: 1rem 0; font-size: 0.875rem; color: #666; }
    .model-details p { margin: 0.5rem 0; }

    .status-installed { color: #16a34a; font-weight: 500; margin: 1rem 0 0.5rem; }

    /* Indeterminate spinner */
    .spinner-wrap { display: flex; flex-direction: column; align-items: center; gap: 0.75rem; margin: 1rem 0; }
    .spinner {
      width: 36px; height: 36px;
      border: 3px solid #e0e0e0; border-top-color: #0066cc;
      border-radius: 50%; animation: spin 0.9s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .status-downloading { color: #0066cc; font-size: 0.8rem; text-align: center; margin: 0; }

    .error-text { color: #b42318; font-size: 0.8rem; margin-top: 0.5rem; }

    .models-list {
      background: white; border: 1px solid #e0e0e0;
      border-radius: 8px; overflow: hidden;
    }
    .model-item {
      display: flex; justify-content: space-between; align-items: center;
      padding: 1rem 1.5rem; border-bottom: 1px solid #f0f0f0;
    }
    .model-item:last-child { border-bottom: none; }
    .model-info h3 { font-size: 0.95rem; margin: 0 0 0.25rem; color: #333; }
    .model-info p  { font-size: 0.8rem; color: #666; margin: 0; }
    .model-actions { display: flex; gap: 0.75rem; }

    .btn-primary, .btn-secondary {
      padding: 0.5rem 1rem; border: none; border-radius: 4px;
      cursor: pointer; font-weight: 500; font-size: 0.875rem; transition: opacity 0.2s;
    }
    .btn-primary { background: #0066cc; color: white; }
    .btn-primary:hover:not(:disabled) { opacity: 0.9; }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-secondary { background: #f0f0f0; color: #333; }
    .btn-secondary:hover { background: #e0e0e0; }
  `],
})
export class ModelManagerComponent implements OnInit {
  installingId: string | null = null
  errorId: string | null = null
  errorMsg = ''

  recommendedModels: LocalModel[] = [
    { id: 'llama3.1:8b',  name: 'Llama 3.1 8B',  size: '4.7 GB', ramRequired: '8 GB+',  provider: 'ollama', installed: false },
    { id: 'llama3.1:70b', name: 'Llama 3.1 70B', size: '40 GB',  ramRequired: '64 GB+', provider: 'ollama', installed: false },
    { id: 'mistral:7b',   name: 'Mistral 7B',    size: '4.1 GB', ramRequired: '8 GB+',  provider: 'ollama', installed: false },
  ]

  get installedModels(): LocalModel[] {
    return this.recommendedModels.filter(m => m.installed)
  }

  constructor(public service: ModelService) {}

  ngOnInit() {
    this.service.loadLocalModels()
    this.syncInstalled()
  }

  private syncInstalled() {
    const installed = this.service.localModels()
    this.recommendedModels = this.recommendedModels.map(rm => ({
      ...rm,
      installed: installed.some(m => m.id === rm.id),
    }))
  }

  async installModel(modelId: string) {
    this.installingId = modelId
    this.errorId = null
    this.errorMsg = ''
    try {
      await this.service.installModel(modelId)
      this.syncInstalled()
    } catch (e: any) {
      this.errorId = modelId
      this.errorMsg = e?.error?.detail || e?.message || 'Install failed. Is Ollama running?'
    } finally {
      this.installingId = null
    }
  }

  async removeModel(modelId: string) {
    if (!confirm('Remove this model?')) return
    await this.service.removeModel(modelId)
    this.syncInstalled()
  }

  async setDefault(modelId: string) {
    await this.service.setDefaultModel(modelId)
  }
}
