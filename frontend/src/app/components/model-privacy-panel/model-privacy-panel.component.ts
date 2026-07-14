import { Component, EventEmitter, Output } from '@angular/core'
import { CommonModule } from '@angular/common'
import { RouterLink } from '@angular/router'
import { ModelService } from '../../services/model.service'

@Component({
  selector: 'app-model-privacy-panel',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="privacy-panel">
      <div class="panel-header">
        <h2>Model & Privacy</h2>
        <button class="close-btn" (click)="close.emit()">✕</button>
      </div>

      <div class="panel-content">
        <section class="config-section">
          <h3>Current Configuration</h3>
          <div class="config-item">
            <label>LLM Provider:</label>
            <span class="value">{{ service.currentLlmProvider() }}</span>
          </div>
          <div class="config-item">
            <label>LLM Model:</label>
            <span class="value">{{ service.currentLlmModel() }}</span>
          </div>
          @if (service.modelStatus()?.embedding) {
            <div class="config-item">
              <label>Embedding Provider:</label>
              <span class="value">{{ service.modelStatus()?.embedding?.provider }}</span>
            </div>
            <div class="config-item">
              <label>Embedding Model:</label>
              <span class="value">{{ service.modelStatus()?.embedding?.model || 'all-MiniLM-L6-v2' }}</span>
            </div>
          }
        </section>

        <section class="config-section">
          <h3>Cloud Provider Access</h3>
          <label class="toggle-label">
            <input type="checkbox" [checked]="service.cloudEnabled()" (change)="toggleCloudProviders($event)" />
            Allow cloud providers for this workspace
          </label>
          <p class="info-text">Admin-only setting. When disabled, all processing happens on your local machine.</p>
        </section>

        <section class="config-section">
          <h3>Actions</h3>
          <button class="btn-primary" routerLink="/settings/models">
            Download a local model
          </button>
        </section>

        <section class="config-section">
          <h3>Data Privacy</h3>
          <a routerLink="/privacy-policy" class="info-link">
            What data ever leaves this device? →
          </a>
          <p class="info-text">Plain language explanation of our data handling practices.</p>
        </section>
      </div>
    </div>
  `,
  styles: [`
    .privacy-panel {
      position: fixed;
      right: 0;
      top: 0;
      bottom: 0;
      width: 400px;
      background: white;
      box-shadow: -2px 0 8px rgba(0, 0, 0, 0.15);
      z-index: 100;
      display: flex;
      flex-direction: column;
      animation: slideIn 0.3s ease-out;
    }

    @keyframes slideIn {
      from {
        transform: translateX(100%);
      }
      to {
        transform: translateX(0);
      }
    }

    .panel-header {
      padding: 1.5rem;
      border-bottom: 1px solid #e0e0e0;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .panel-header h2 {
      font-size: 1.25rem;
      margin: 0;
    }

    .close-btn {
      background: none;
      border: none;
      font-size: 1.5rem;
      cursor: pointer;
      color: #666;
    }

    .panel-content {
      overflow-y: auto;
      flex: 1;
      padding: 1.5rem;
    }

    .config-section {
      margin-bottom: 2rem;
    }

    .config-section h3 {
      font-size: 0.875rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #666;
      margin-bottom: 1rem;
      font-weight: 600;
    }

    .config-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.75rem 0;
      border-bottom: 1px solid #f0f0f0;
    }

    .config-item label {
      font-weight: 500;
      color: #333;
    }

    .config-item .value {
      color: #0066cc;
      font-family: monospace;
      font-size: 0.875rem;
    }

    .toggle-label {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      cursor: pointer;
      font-weight: 500;
    }

    .toggle-label input {
      cursor: pointer;
    }

    .info-text {
      font-size: 0.875rem;
      color: #666;
      margin-top: 0.5rem;
      line-height: 1.4;
    }

    .btn-primary {
      width: 100%;
      padding: 0.75rem 1rem;
      background: #0066cc;
      color: white;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-weight: 500;
      transition: background 0.2s;
    }

    .btn-primary:hover {
      background: #0052a3;
    }

    .info-link {
      display: block;
      color: #0066cc;
      text-decoration: none;
      font-weight: 500;
      margin-bottom: 0.5rem;
    }

    .info-link:hover {
      text-decoration: underline;
    }
  `],
})
export class ModelPrivacyPanelComponent {
  @Output() close = new EventEmitter<void>()

  constructor(public service: ModelService) {}

  toggleCloudProviders(event: any) {
    this.service.toggleCloudProvider(event.target.checked)
  }
}
