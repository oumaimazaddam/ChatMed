import { Component, OnInit, inject, signal } from '@angular/core';
import { ApiService, DoctorHistoryItem } from '../core/api.service';
import { errMsg, urgencyLabel } from '../core/util';

@Component({
  selector: 'app-doctor-history',
  standalone: true,
  template: `
    <h3>Historique de mes réponses <span class="muted">(50 dernières)</span></h3>
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }
    @if (items().length === 0 && !error()) {
      <p class="muted">Aucune réponse pour le moment.</p>
    }
    @for (c of items(); track c.id) {
      <div class="card">
        <div class="row-between">
          <strong>#{{ c.id }} · {{ c.patient }}</strong>
          <span>
            @if (c.summary.includes('Mode de saisie : dictée vocale')) {
              <span class="badge warn">🎤 Dictée vocale</span>
            }
            <span class="badge" [class.urgent]="c.urgency === 'urgent'">{{ label(c.urgency) }}</span>
            <small class="muted">Répondu le {{ c.answered_at }}</small>
          </span>
        </div>
        <pre>{{ c.summary }}</pre>
        <p><strong>Ma réponse :</strong> {{ c.reply }}</p>
      </div>
    }
  `,
})
export class DoctorHistoryPage implements OnInit {
  private api = inject(ApiService);
  items = signal<DoctorHistoryItem[]>([]);
  error = signal('');
  label = urgencyLabel;

  ngOnInit() {
    this.api.doctorHistory().subscribe({
      next: (r) => this.items.set(r),
      error: (e) => this.error.set(errMsg(e)),
    });
  }
}
