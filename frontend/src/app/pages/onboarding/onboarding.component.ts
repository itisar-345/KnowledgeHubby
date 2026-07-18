import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { Router } from '@angular/router'
import { ModelService } from '../../services/model.service'
import { AuthService } from '../../services/auth.service'

@Component({
  selector: 'app-onboarding',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="onboarding-container">
      <div class="onboarding-content">
        <!-- Step 1: Welcome -->
        @if (currentStep === 1) {
          <div class="step welcome">
            <h1>Welcome to Knowledge Hubs</h1>
            <p class="step-number">Step 1 of 4</p>
            <div class="welcome-message">
              <p>Knowledge Hubs runs fully on your machine.</p>
              <p><strong>No API key needed.</strong></p>
              <p>Your data stays private. All AI processing happens locally by default.</p>
            </div>
            <button class="btn-primary" (click)="nextStep()">Get Started</button>
          </div>
        }

        <!-- Step 2: Install Local Model -->
        @if (currentStep === 2) {
          <div class="step model-install">
            <h1>Install a Local Model</h1>
            <p class="step-number">Step 2 of 4</p>
            @if (service.systemInfo()) {
              <div class="system-info">
                <p>Your system has <strong>{{ service.systemInfo()?.ramGb }}GB RAM</strong></p>
                <p>Recommended: <strong>{{ service.systemInfo()?.recommendedTier }}</strong></p>
              </div>
            }
            <div class="recommended-models">
              @for (model of recommendedForSystem; track model.id) {
                <div class="model-option" [class.selected]="selectedModel === model.id">
                  <label>
                    <input type="radio" [value]="model.id" [(ngModel)]="selectedModel" />
                    <span class="model-name">{{ model.name }}</span>
                    <span class="model-details">{{ model.size }} • {{ model.ramRequired }}</span>
                  </label>
                </div>
              }
            </div>
            @if (installError) { <p class="error-text">{{ installError }}</p> }
            <div class="step-actions">
              <button class="btn-secondary" (click)="previousStep()">Back</button>
              <button class="btn-primary" [disabled]="isInstalling" (click)="installSelectedModel()">
                Install Model
              </button>
            </div>
          </div>
        }

        <!-- Step 3: Optional Cloud Setup -->
        @if (currentStep === 3) {
          <div class="step cloud-setup">
            <h1>Optional: Add Cloud Provider</h1>
            <p class="step-number">Step 3 of 4</p>
            <p class="info-text">
              You can optionally add a cloud AI provider (like OpenAI) for enhanced answers.
              This is completely optional — you can skip this and use only local models.
            </p>
            <label class="toggle-label">
              <input type="checkbox" [(ngModel)]="enableCloud" />
              Enable cloud providers for this workspace
            </label>
            @if (enableCloud) {
              <div class="api-key-section">
                <label>OpenAI API Key</label>
                <input
                  type="password"
                  [(ngModel)]="apiKey"
                  placeholder="sk-..."
                  class="input-field"
                />
                <p class="info-text">
                  Your key is encrypted before being stored. Leave blank to skip for now.
                </p>
              </div>
            }
            @if (apiKeyError) { <p class="error-text">{{ apiKeyError }}</p> }
            <div class="step-actions">
              <button class="btn-secondary" (click)="previousStep()">Back</button>
              <button class="btn-primary" [disabled]="isSavingKey" (click)="continueFromCloud()">
                {{ isSavingKey ? 'Saving key…' : 'Continue' }}
              </button>
            </div>
          </div>
        }

        <!-- Step 4: Create Workspace -->
        @if (currentStep === 4) {
          <div class="step workspace-create">
            <h1>Create Workspace</h1>
            <p class="step-number">Step 4 of 4</p>
            <div class="form-group">
              <label>Username</label>
              <input type="text" [(ngModel)]="username" placeholder="your-username" class="input-field" />
            </div>
            <div class="form-group">
              <label>Password</label>
              <input type="password" [(ngModel)]="password" placeholder="••••••" class="input-field" />
            </div>
            <div class="form-group">
              <label>Workspace Name</label>
              <input type="text" [(ngModel)]="workspaceName" placeholder="My Knowledge Base" class="input-field" />
            </div>
            @if (setupError) { <p class="error-text">{{ setupError }}</p> }
            <div class="step-actions">
              <button class="btn-secondary" (click)="previousStep()">Back</button>
              <button class="btn-primary" [disabled]="!workspaceName || !username || !password || isFinishing" (click)="finishOnboarding()">
                {{ isFinishing ? 'Creating…' : 'Create & Continue' }}
              </button>
            </div>
          </div>
        }

        <!-- Installation overlay — indeterminate spinner, no fake percentage -->
        @if (isInstalling) {
          <div class="progress-overlay">
            <div class="progress-card">
              <div class="spinner"></div>
              <h2>Installing {{ selectedModel }}…</h2>
              <p class="info-text">
                Downloading from Ollama — this can take several minutes depending on
                model size ({{ selectedModelSize }}) and your connection speed.
              </p>
            </div>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .onboarding-container {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      padding: 2rem;
    }

    .onboarding-content {
      background: white;
      border-radius: 12px;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
      max-width: 500px;
      width: 100%;
      padding: 3rem 2rem;
    }

    .step { animation: slideIn 0.3s ease-out; }

    @keyframes slideIn {
      from { opacity: 0; transform: translateY(10px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    h1 { font-size: 2rem; margin: 0 0 0.5rem; color: #333; }

    .step-number { color: #999; font-size: 0.875rem; margin: 0 0 2rem; }

    .welcome-message {
      background: #f0f8ff;
      border-left: 4px solid #667eea;
      padding: 1.5rem;
      border-radius: 4px;
      margin: 2rem 0;
      line-height: 1.6;
    }
    .welcome-message p { margin: 0.5rem 0; font-size: 1rem; }

    .system-info {
      background: #f0f8ff;
      padding: 1rem;
      border-radius: 4px;
      margin: 1rem 0;
      font-size: 0.95rem;
    }
    .system-info p { margin: 0.5rem 0; }

    .recommended-models { margin: 2rem 0; }

    .model-option {
      border: 2px solid #e0e0e0;
      border-radius: 8px;
      padding: 1rem;
      margin-bottom: 0.75rem;
      cursor: pointer;
      transition: all 0.2s;
    }
    .model-option:hover  { border-color: #667eea; background: #f9f9f9; }
    .model-option.selected { border-color: #667eea; background: #f0f8ff; }
    .model-option label { display: flex; flex-direction: column; gap: 0.5rem; cursor: pointer; }
    .model-name  { font-weight: 500; font-size: 0.95rem; }
    .model-details { font-size: 0.8rem; color: #666; }

    .toggle-label {
      display: flex; align-items: center; gap: 0.75rem;
      cursor: pointer; margin: 1rem 0; font-weight: 500;
    }
    .toggle-label input { cursor: pointer; width: 18px; height: 18px; }

    .api-key-section { background: #f9f9f9; padding: 1rem; border-radius: 4px; margin: 1rem 0; }
    .api-key-section label { display: block; margin-bottom: 0.5rem; font-weight: 500; }

    .form-group { margin: 2rem 0; }
    .form-group label { display: block; margin-bottom: 0.5rem; font-weight: 500; }

    .input-field {
      width: 100%; padding: 0.75rem;
      border: 1px solid #d0d0d0; border-radius: 4px; font-size: 0.95rem;
    }
    .input-field:focus {
      outline: none; border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }

    .info-text  { font-size: 0.85rem; color: #666; margin: 0.75rem 0 0; }
    .error-text { font-size: 0.85rem; color: #b42318; margin: 0.5rem 0 0; }

    .step-actions { display: flex; gap: 1rem; margin-top: 2rem; }

    .btn-primary, .btn-secondary {
      flex: 1; padding: 0.75rem 1.5rem; border: none;
      border-radius: 4px; cursor: pointer; font-weight: 600;
      font-size: 0.95rem; transition: opacity 0.2s;
    }
    .btn-primary { background: #667eea; color: white; }
    .btn-primary:hover:not(:disabled) { opacity: 0.9; }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-secondary { background: #f0f0f0; color: #333; }
    .btn-secondary:hover { background: #e0e0e0; }

    /* Indeterminate install overlay */
    .progress-overlay {
      position: fixed; inset: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex; align-items: center; justify-content: center;
      z-index: 1000;
    }
    .progress-card {
      background: white; border-radius: 12px;
      padding: 2rem; text-align: center; max-width: 320px; width: 100%;
    }
    .progress-card h2 { font-size: 1.1rem; margin: 1rem 0 0.5rem; }

    /* CSS-only indeterminate spinner — makes no false claim about progress */
    .spinner {
      width: 48px; height: 48px; margin: 0 auto;
      border: 4px solid #e0e0e0;
      border-top-color: #667eea;
      border-radius: 50%;
      animation: spin 0.9s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  `],
})
export class OnboardingComponent implements OnInit {
  currentStep = 1
  selectedModel = 'llama3.1:8b'
  enableCloud = false
  apiKey = ''
  workspaceName = ''
  username = ''
  password = ''
  isInstalling = false
  isSavingKey = false
  isFinishing = false
  setupError = ''
  installError = ''
  apiKeyError = ''

  readonly recommendedForSystem = [
    { id: 'llama3.1:8b',  name: 'Llama 3.1 8B (Recommended)', size: '4.7 GB', ramRequired: '8 GB+' },
    { id: 'mistral:7b',   name: 'Mistral 7B',                  size: '4.1 GB', ramRequired: '8 GB+' },
    { id: 'llama3.1:70b', name: 'Llama 3.1 70B (High Perf.)',  size: '40 GB',  ramRequired: '64 GB+' },
  ]

  get selectedModelSize(): string {
    return this.recommendedForSystem.find(m => m.id === this.selectedModel)?.size ?? ''
  }

  constructor(readonly service: ModelService, private router: Router, private auth: AuthService) {}

  ngOnInit() { this.service.loadSystemInfo() }

  nextStep()     { if (this.currentStep < 4) this.currentStep++ }
  previousStep() { if (this.currentStep > 1) this.currentStep-- }

  async installSelectedModel() {
    this.isInstalling = true
    this.installError = ''
    try {
      await this.service.installModel(this.selectedModel)
      this.nextStep()
    } catch (e: any) {
      this.installError = e?.error?.detail || e?.message || 'Installation failed. Is Ollama running?'
    } finally {
      this.isInstalling = false
    }
  }

  async continueFromCloud() {
    if (!this.enableCloud || !this.apiKey) { this.nextStep(); return }
    this.isSavingKey = true
    this.apiKeyError = ''
    try {
      await this.service.saveApiKey('openai', this.apiKey)
      this.nextStep()
    } catch (e: any) {
      this.apiKeyError = e?.error?.detail || e?.message || 'Could not save API key. You can add it later in Workspace Settings.'
    } finally {
      this.isSavingKey = false
    }
  }

  async finishOnboarding() {
    this.isFinishing = true
    this.setupError = ''
    try {
      await this.auth.register(this.username, this.password, this.workspaceName)
      this.router.navigate(['/login'])
    } catch (e: any) {
      this.setupError = e?.error?.detail || 'Could not create workspace. Try a different username.'
    } finally {
      this.isFinishing = false
    }
  }
}
