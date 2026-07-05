import { Routes } from '@angular/router'
import { authGuard } from './services/auth.guard'

export const routes: Routes = [
  { path: '', redirectTo: 'knowledge', pathMatch: 'full' },
  { path: 'login', loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent) },
  { path: 'knowledge', loadComponent: () => import('./pages/knowledge/knowledge.component').then(m => m.KnowledgeComponent), canActivate: [authGuard] },
  { path: 'knowledge/:id', loadComponent: () => import('./pages/knowledge-detail/knowledge-detail.component').then(m => m.KnowledgeDetailComponent), canActivate: [authGuard] },
  { path: 'review', loadComponent: () => import('./pages/review/review.component').then(m => m.ReviewComponent), canActivate: [authGuard] },
  { path: 'search', loadComponent: () => import('./pages/search/search.component').then(m => m.SearchComponent), canActivate: [authGuard] },
  { path: 'graphrag', loadComponent: () => import('./pages/graphrag/graphrag.component').then(m => m.GraphragComponent), canActivate: [authGuard] },
]
