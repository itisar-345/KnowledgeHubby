import { Component, computed } from '@angular/core'
import { RouterOutlet, RouterLink, Router } from '@angular/router'
import { CommonModule } from '@angular/common'
import { AuthService } from './services/auth.service'

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, CommonModule],
  template: `
    <nav class="nav">
      <h1>Knowledge Hubs</h1>
      <div class="nav-links">
        @if (auth.isLoggedIn()) {
          <a routerLink="/knowledge">Hub</a>
          <a routerLink="/search">Search</a>
          <a routerLink="/review">Review</a>
          <a routerLink="/graphrag">GraphRAG</a>
          <a routerLink="/workspace-settings">Workspace</a>
          <button style="padding:0.25rem 0.75rem;font-size:0.875rem" (click)="logout()">Sign out</button>
        } @else {
          <a routerLink="/login">Sign in</a>
        }
      </div>
    </nav>
    <main>
      <router-outlet />
    </main>
  `
})
export class AppComponent {
  constructor(public auth: AuthService, private router: Router) {}

  logout() {
    this.auth.logout()
    this.router.navigate(['/login'])
  }
}
