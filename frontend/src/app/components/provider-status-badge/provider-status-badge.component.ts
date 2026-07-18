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
      (click)="togglePanel()">
      {{ service.statusBadgeText() }}
    </button>
    @if (showPanel) {
      <div class="overlay" (click)="togglePanel()"></div>
      <app-model-privacy-panel (close)="togglePanel()"></app-model-privacy-panel>
    }
  `,
  styles: [`
    .status-badge {
      padding: 0.3rem 0.75rem;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.35);
      cursor: pointer;
      font-size: 0.8rem;
      font-weight: 600;
      transition: opacity 0.2s;
      white-space: nowrap;
    }
    .status-badge:hover { opacity: 0.85; }

    .badge-green { background: rgba(255,255,255,0.18); color: #fff; }
    .badge-blue  { background: rgba(255,255,255,0.18); color: #fff; }
    .badge-red   { background: rgba(220,53,69,0.35);   color: #fff; }

    .overlay {
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.25);
      z-index: 99;
    }
  `],
})
export class ProviderStatusBadgeComponent implements OnInit {
  showPanel = false

  constructor(public service: ModelService) {}

  ngOnInit() { this.service.loadModelStatus() }

  togglePanel() { this.showPanel = !this.showPanel }
}
