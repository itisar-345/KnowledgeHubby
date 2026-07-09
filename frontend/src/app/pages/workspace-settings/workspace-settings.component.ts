import { Component } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { HttpClient } from '@angular/common/http'
import { AuthService } from '../../services/auth.service'

interface ProviderConfig {
  id: string
  provider_type: string
  provider_name: string
  model_name?: string
  config_json?: any
  api_key_ref?: string
  is_active: boolean
  created_at: string
}

@Component({
  selector: 'app-workspace-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="page-shell">
      <h2>Workspace Settings</h2>
      <div class="section-card">
        <h3>Provider policy</h3>
        <label>
          <input type="checkbox" [(ngModel)]="settings.allow_cloud_providers" /> Allow cloud providers
        </label>
        <div class="form-row">
          <label>Default LLM provider</label>
          <input [(ngModel)]="settings.default_llm_provider" placeholder="ollama or openai" />
        </div>
        <div class="form-row">
          <label>Default embedding provider</label>
          <input [(ngModel)]="settings.default_embedding_provider" placeholder="local or openai" />
        </div>
        <button class="primary" (click)="save()" [disabled]="saving">Save settings</button>
      </div>

      <div class="section-card">
        <h3>Provider configurations</h3>
        <div *ngIf="configs.length === 0" style="color:#667085">No workspace provider configs yet.</div>
        <div *ngFor="let cfg of configs" class="config-card">
          <div><strong>{{ cfg.provider_type }} / {{ cfg.provider_name }}</strong></div>
          <div style="font-size:0.85rem;color:#475569;">Model: {{ cfg.model_name || 'default' }}</div>
          <div style="font-size:0.85rem;color:#475569;">Active: {{ cfg.is_active }}</div>
          <button (click)="removeConfig(cfg.id)">Delete</button>
        </div>
        <div class="form-row">
          <label>Type</label>
          <input [(ngModel)]="newConfig.provider_type" placeholder="llm or embedding" />
        </div>
        <div class="form-row">
          <label>Name</label>
          <input [(ngModel)]="newConfig.provider_name" placeholder="ollama, openai, local" />
        </div>
        <div class="form-row">
          <label>Model</label>
          <input [(ngModel)]="newConfig.model_name" placeholder="e.g. gpt-4o-mini" />
        </div>
        <div class="form-row">
          <label>API Key Ref</label>
          <input [(ngModel)]="newConfig.api_key_ref" placeholder="optional secret ref" />
        </div>
        <div class="form-row checkbox-row">
          <label><input type="checkbox" [(ngModel)]="newConfig.is_active" /> Active</label>
        </div>
        <button class="secondary" (click)="addConfig()" [disabled]="creating">Create config</button>
      </div>

      <div *ngIf="error" class="error-text">{{ error }}</div>
    </div>
  `,
  styles: [
    `.page-shell { max-width: 840px; margin: 2rem auto; padding: 0 1rem }`
  ]
})
export class WorkspaceSettingsComponent {
  settings = { allow_cloud_providers: false, default_llm_provider: 'ollama', default_embedding_provider: 'local' }
  configs: ProviderConfig[] = []
  newConfig: Partial<ProviderConfig> = { provider_type: '', provider_name: '', model_name: '', api_key_ref: '', is_active: true }
  saving = false
  creating = false
  error = ''

  constructor(private auth: AuthService, private http: HttpClient) {
    this.load()
  }

  async load() {
    try {
      const data: any = await this.auth.getWorkspaceSettings()
      this.settings = {
        allow_cloud_providers: data.allow_cloud_providers,
        default_llm_provider: data.default_llm_provider,
        default_embedding_provider: data.default_embedding_provider,
      }
      this.configs = await this.auth.listProviderConfigs()
    } catch (e: any) {
      this.error = e?.error?.detail || e?.message || 'Unable to load workspace settings.'
    }
  }

  async save() {
    this.saving = true; this.error = ''
    try {
      await this.auth.updateWorkspaceSettings(this.settings)
      await this.load()
    } catch (e: any) {
      this.error = e?.error?.detail || e?.message || 'Unable to save workspace settings.'
    } finally { this.saving = false }
  }

  async addConfig() {
    this.creating = true; this.error = ''
    try {
      const body = {
        provider_type: this.newConfig.provider_type,
        provider_name: this.newConfig.provider_name,
        model_name: this.newConfig.model_name,
        config_json: {},
        api_key_ref: this.newConfig.api_key_ref,
        is_active: this.newConfig.is_active,
      }
      await this.auth.createProviderConfig(body)
      this.newConfig = { provider_type: '', provider_name: '', model_name: '', api_key_ref: '', is_active: true }
      await this.load()
    } catch (e: any) {
      this.error = e?.error?.detail || e?.message || 'Unable to create provider config.'
    } finally { this.creating = false }
  }

  async removeConfig(id: string) {
    try {
      await this.auth.deleteProviderConfig(id)
      this.configs = this.configs.filter(c => c.id !== id)
    } catch (e: any) {
      this.error = e?.error?.detail || e?.message || 'Unable to delete provider config.'
    }
  }
}
