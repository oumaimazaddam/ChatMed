import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="top">
      <strong class="brand">MedAssist</strong>
      <nav>
        @if (auth.role() === 'patient') {
          <a routerLink="/patient/dashboard" routerLinkActive="active">Tableau de bord</a>
          <a routerLink="/patient/chat" routerLinkActive="active">Chat</a>
          <a routerLink="/patient/symptoms" routerLinkActive="active">Symptômes</a>
          <a routerLink="/patient/consultations" routerLinkActive="active">Mes consultations</a>
          <a routerLink="/patient/record" routerLinkActive="active">Mon dossier</a>
        }
        @if (auth.role() === 'doctor') {
          <a routerLink="/doctor/dashboard" routerLinkActive="active">Tableau de bord</a>
          <a routerLink="/doctor/cases" routerLinkActive="active">Cas à traiter</a>
          <a routerLink="/doctor/history" routerLinkActive="active">Historique</a>
        }
        @if (auth.role() === 'admin') {
          <a routerLink="/admin/dashboard" routerLinkActive="active">Tableau de bord</a>
          <a routerLink="/admin/users" routerLinkActive="active">Utilisateurs</a>
          <a routerLink="/admin/audit" routerLinkActive="active">Journal d'audit</a>
        }
      </nav>
      <span class="who">{{ auth.name() }} ({{ auth.role() }})</span>
      <button class="ghost" (click)="auth.logout()">Déconnexion</button>
    </header>
    <p class="warn">
      Information générale basée sur des notices. Ce n'est pas un avis médical. En cas d'urgence : appelez le 190.
    </p>
    <main><router-outlet /></main>
  `,
})
export class ShellComponent {
  auth = inject(AuthService);
}
