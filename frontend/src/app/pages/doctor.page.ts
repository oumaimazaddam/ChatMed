import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, DoctorCase } from '../core/api.service';
import { errMsg, urgencyLabel } from '../core/util';

@Component({
  selector: 'app-doctor',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h3>Cas à traiter <span class="muted">(alertes et urgents en premier)</span></h3>

    @if (error()) {
      <p class="error">{{ error() }}</p>
    }

    @if (alertCount() > 0) {
      <div class="alert red chat-alert-banner">
        🚨 {{ alertCount() }} ALERTE(S) D'URGENCE détectée(s) dans le chat.
        Un patient décrit peut-être une situation grave : traitez ces cas en priorité.
      </div>
    }

    @if (cases().length === 0 && !error()) {
      <p class="muted">Aucun cas en attente.</p>
    }

    @for (c of cases(); track c.id) {
      <div
        class="card"
        [class.urgent-card]="c.urgency === 'urgent'"
        [class.alert-card]="c.is_alert"
      >
        <div class="row-between">
          <strong>#{{ c.id }} · {{ c.patient }}</strong>
          <span>
            @if (c.is_alert) {
              <span class="badge urgent chat-alert-badge">
                {{ c.alert_type === 'self_harm' ? '🚨 ALERTE : IDÉES SUICIDAIRES' : '🚨 ALERTE CHAT : URGENCE' }}
              </span>
            }
            @if (isVoice(c.summary)) {
              <span class="badge warn">🎤 Dictée vocale</span>
            }
            <span class="badge" [class.urgent]="c.urgency === 'urgent'">{{ label(c.urgency) }}</span>
            <small class="muted">{{ c.created_at }}</small>
          </span>
        </div>

        @if (c.is_alert) {
          <p class="alert-hint">
            Détecté automatiquement dans le chat. Le patient a reçu le message « appelez le 190 ».
            Vérifiez le message ci-dessous et contactez-le si nécessaire.
          </p>
        }

        <pre>{{ c.summary }}</pre>
        <textarea rows="3" placeholder="Réponse du médecin" [(ngModel)]="replies[c.id]"></textarea>
        <button class="primary" (click)="reply(c.id)">Valider et répondre</button>
      </div>
    }
  `,
  styles: [`
    .chat-alert-banner { font-weight: 600; margin-bottom: 12px; }
    .alert-card {
      border: 2px solid #d93025;
      border-left-width: 8px;
      background: rgba(217, 48, 37, 0.07);
    }
    .chat-alert-badge { background: #d93025; color: #fff; font-weight: 700; }
    .alert-hint { color: #b3261e; font-size: 0.9em; margin: 8px 0; }
  `],
})
export class DoctorPage implements OnInit {
  private api = inject(ApiService);

  cases = signal<DoctorCase[]>([]);
  alertCount = computed(() => this.cases().filter((c) => c.is_alert).length);
  error = signal('');
  replies: Record<number, string> = {};
  label = urgencyLabel;

  isVoice(summary: string) {
    return summary.includes('Mode de saisie : dictée vocale');
  }

  ngOnInit() {
    this.load();
  }

  load() {
    this.api.doctorCases().subscribe({
      next: (r) => this.cases.set(r),
      error: (e) => this.error.set(errMsg(e)),
    });
  }

  reply(id: number) {
    const text = (this.replies[id] ?? '').trim();
    if (!text) {
      this.error.set('Écrivez une réponse avant de valider.');
      return;
    }
    this.error.set('');
    this.api.doctorReply(id, text).subscribe({
      next: () => {
        delete this.replies[id];
        this.load();
      },
      error: (e) => this.error.set(errMsg(e)),
    });
  }
}