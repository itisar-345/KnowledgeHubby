import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { ModelService } from '../../services/model.service'
import { ModelPrivacyPanelComponent } from '../model-privacy-panel/model-privacy-panel.component'

@Component({
  selector: 'app-provider-status-badge',
  standalone: true,
  imports: [CommonModule, ModelPrivacyPanelComponent],
  template: `
    <button class="status-badge" [ngClass]="'badge-' + service.statusBadgeColor()"
      [attr.aria-label]="service.statusBadgeText()"
      (click)="togglePanel()">
      {{ service.statusBadgeText() }}
    </button>
    @if (showPanel) {
      <div class="panel-overlay" (click)="togglePanel()"></div>
      <app-model-privacy-panel (close)="togglePanel()"></app-model-privacy-panel>
    }
  `,
  styles: [`
    .status-badge {
      padding: 0.5rem 1rem;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 0.875rem;
      font-weight: 500;
      transition: opacity 0.2s;
    }

    .status-badge:hover {
      opacity: 0.8;
    }

    .badge-green {
      background: #e6f7e6;
      color: #1a6b1a;
    }

    .badge-blue {
      background: #e6f0ff;
      color: #0033cc;
    }

    .badge-red {
      background: #ffe6e6;
      color: #cc0000;
    }

    .panel-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.3);
      z-index: 99;
    }
  `],
})
export class ProviderStatusBadgeComponent implements OnInit {
  showPanel = false

  constructor(public service: ModelService) {}

  ngOnInit() {
    this.service.loadModelStatus()
  }

  togglePanel() {
    this.showPanel = !this.showPanel
  }
}
