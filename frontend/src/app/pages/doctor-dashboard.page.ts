import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, DoctorDashboard } from '../core/api.service';
import { errMsg, fmtMinutes, urgencyLabel } from '../core/util';
import { StatCard } from '../shared/ui';

@Component({
  selector: 'app-doctor-dashboard',
  standalone: true,
  imports: [RouterLink, StatCard],
  template: `
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }
    @if (data(); as d) {
      <h2>Tableau de bord médecin</h2>

      @if (d.pending_alerts > 0) {
        <div class="alert red chat-alert-banner">
          🚨 {{ d.pending_alerts }} ALERTE(S) D'URGENCE détectée(s) dans le chat : un patient décrit
          peut-être une situation grave.
          <a routerLink="/doctor/cases">Traiter maintenant</a>
        </div>
      }

      @if (d.pending_urgent - d.pending_alerts > 0) {
        <div class="alert red">
          ⚠️ {{ d.pending_urgent - d.pending_alerts }} autre(s) cas urgent(s) en attente.
          <a routerLink="/doctor/cases">Traiter maintenant</a>
        </div>
      }

      <div class="stats">
        <app-stat label="Alertes chat" [value]="d.pending_alerts" tone="red" />
        <app-stat label="En attente" [value]="d.pending_total" tone="orange" />
        <app-stat label="Urgents" [value]="d.pending_urgent" tone="red" />
        <app-stat label="Sous 24 h" [value]="d.pending_24h" tone="blue" />
        <app-stat label="Routine" [value]="d.pending_routine" />
      </div>
      <div class="stats">
        <app-stat label="Traités aujourd'hui" [value]="d.answered_today" tone="green" />
        <app-stat label="Total traités" [value]="d.answered_total" tone="green" />
        <app-stat label="Temps moyen de réponse" [value]="fmt(d.avg_response_minutes)" />
        <app-stat label="Plus ancien en attente" [value]="fmt(d.oldest_pending_minutes)" tone="orange" />
      </div>

      <div class="grid2">
        <div class="card">
          <div class="row-between">
            <h3>Prochains cas à traiter</h3>
            <a class="btn primary" routerLink="/doctor/cases">Voir tous les cas</a>
          </div>
          @if (d.next_cases.length === 0) {
            <p class="muted">Aucun cas en attente. Bon travail !</p>
          }
          @for (c of d.next_cases; track c.id) {
            <div class="list-item" [class.alert-case]="c.is_alert">
              <div class="row-between">
                <strong>#{{ c.id }} · {{ c.patient }}</strong>
                @if (c.is_alert) {
                  <span class="badge urgent chat-alert-badge">🚨 ALERTE CHAT</span>
                } @else {
                  <span class="badge" [class.urgent]="c.urgency === 'urgent'">{{ label(c.urgency) }}</span>
                }
              </div>
              <p class="muted">Reçu {{ c.created_at }} · attend depuis {{ fmt(c.waiting_minutes) }}</p>
            </div>
          }
        </div>

        <div class="card">
          <div class="row-between">
            <h3>Mes dernières réponses</h3>
            <a routerLink="/doctor/history">Historique</a>
          </div>
          @if (d.recent.length === 0) {
            <p class="muted">Vous n'avez pas encore répondu à un cas.</p>
          }
          @for (c of d.recent; track c.id) {
            <div class="list-item">
              <div class="row-between">
                <strong>#{{ c.id }} · {{ c.patient }}</strong>
                <small class="muted">{{ c.answered_at }}</small>
              </div>
              <p class="muted">{{ c.reply }}</p>
            </div>
          }
        </div>
      </div>
    }
  `,
  styles: [`
    .chat-alert-banner { font-weight: 600; }
    .alert-case {
      border-left: 4px solid #d93025;
      background: rgba(217, 48, 37, 0.08);
      padding-left: 10px;
    }
    .chat-alert-badge { background: #d93025; color: #fff; font-weight: 700; }
  `],
})
export class DoctorDashboardPage implements OnInit {
  private api = inject(ApiService);
  data = signal<DoctorDashboard | null>(null);
  error = signal('');
  fmt = fmtMinutes;
  label = urgencyLabel;

  ngOnInit() {
    this.api.doctorDashboard().subscribe({
      next: (d) => this.data.set(d),
      error: (e) => this.error.set(errMsg(e)),
    });
  }
}