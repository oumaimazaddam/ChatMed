import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, PatientDashboard } from '../core/api.service';
import { errMsg, urgencyLabel } from '../core/util';
import { StatCard } from '../shared/ui';

@Component({
  selector: 'app-patient-dashboard',
  standalone: true,
  imports: [RouterLink, StatCard],
  template: `
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }
    @if (data(); as d) {
      <h2>Bonjour {{ d.name }}</h2>

      @if (d.urgent_pending > 0) {
        <div class="alert red">
          ⚠️ {{ d.urgent_pending }} demande(s) urgente(s) en attente. En cas de danger, appelez le 190 sans attendre.
        </div>
      }

      <div class="stats">
        <app-stat label="Consultations" [value]="d.total" tone="blue" />
        <app-stat label="En attente" [value]="d.pending" tone="orange" />
        <app-stat label="Répondues" [value]="d.answered" tone="green" />
        <app-stat label="Questions posées" [value]="d.questions" />
      </div>

      <div class="grid2">
        <div class="card">
          <h3>Que voulez-vous faire ?</h3>
          <p class="muted">Posez une question sur un médicament, ou envoyez vos symptômes à un médecin.</p>
          <div class="actions">
            <a class="btn primary" routerLink="/patient/chat">Poser une question</a>
            <a class="btn" routerLink="/patient/symptoms">Décrire mes symptômes</a>
          </div>
        </div>

        <div class="card">
          <h3>Mon dossier</h3>
          <div class="progress"><div [style.width.%]="completion(d) * 50"></div></div>
          <ul class="checklist">
            <li [class.done]="d.record.allergies">Allergies {{ d.record.allergies ? 'renseignées' : 'à renseigner' }}</li>
            <li [class.done]="d.record.treatments">Traitements {{ d.record.treatments ? 'renseignés' : 'à renseigner' }}</li>
          </ul>
          <a class="btn" routerLink="/patient/record">Compléter mon dossier</a>
        </div>
      </div>

      <div class="card">
        <div class="row-between">
          <h3>Dernières consultations</h3>
          <a routerLink="/patient/consultations">Tout voir</a>
        </div>
        @if (d.recent.length === 0) {
          <p class="muted">Aucune consultation pour le moment.</p>
        }
        @for (c of d.recent; track c.id) {
          <div class="list-item">
            <div class="row-between">
              <strong>#{{ c.id }} · {{ c.created_at }}</strong>
              <span>
                <span class="badge" [class.urgent]="c.urgency === 'urgent'">{{ label(c.urgency) }}</span>
                <span class="badge">{{ c.status === 'answered' ? 'Répondu' : 'En attente' }}</span>
              </span>
            </div>
            <p class="muted">{{ c.reply || 'En attente de la réponse du médecin.' }}</p>
          </div>
        }
      </div>
    }
  `,
})
export class PatientDashboardPage implements OnInit {
  private api = inject(ApiService);
  data = signal<PatientDashboard | null>(null);
  error = signal('');
  label = urgencyLabel;

  ngOnInit() {
    this.api.patientDashboard().subscribe({
      next: (d) => this.data.set(d),
      error: (e) => this.error.set(errMsg(e)),
    });
  }

  completion(d: PatientDashboard) {
    return (d.record.allergies ? 1 : 0) + (d.record.treatments ? 1 : 0);
  }
}
