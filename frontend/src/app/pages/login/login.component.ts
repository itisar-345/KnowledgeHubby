import { Component } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { Router } from '@angular/router'
import { CommonModule } from '@angular/common'
import { AuthService } from '../../services/auth.service'

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, CommonModule],
  template: `
    <div class="auth-shell">
      <div class="auth-card">
        <h2>Knowledge Hubs</h2>
        <p class="muted-text">{{ mode === 'login' ? 'Sign in to your workspace' : 'Create a new workspace' }}</p>
        <div class="form-stack">
          <input placeholder="Username" [(ngModel)]="username" />
          <input placeholder="Password" type="password" [(ngModel)]="password" />
          @if (mode === 'register') {
            <input placeholder="Workspace name (e.g. team-alpha)" [(ngModel)]="workspace" />
          }
        </div>
        @if (error) { <p class="error-text">{{ error }}</p> }
        <button class="primary" [disabled]="loading || !username || !password" (click)="submit()">
          {{ loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account' }}
        </button>
        <button (click)="toggleMode()">
          {{ mode === 'login' ? 'No account? Register' : 'Have an account? Sign in' }}
        </button>
      </div>
    </div>
  `
})
export class LoginComponent {
  mode: 'login' | 'register' = 'login'
  username = ''; password = ''; workspace = ''; error = ''; loading = false

  constructor(private auth: AuthService, private router: Router) {}

  toggleMode() { this.mode = this.mode === 'login' ? 'register' : 'login'; this.error = '' }

  async submit() {
    this.error = ''; this.loading = true
    try {
      if (this.mode === 'register') {
        await this.auth.register(this.username, this.password, this.workspace || this.username)
      }
      await this.auth.login(this.username, this.password)
      this.router.navigate(['/knowledge'])
    } catch (e: any) {
      this.error = e?.error?.detail || e?.message || 'Something went wrong'
    } finally { this.loading = false }
  }
}
