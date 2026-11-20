import { Component, OnInit, inject, signal } from '@angular/core';
import { ApiService, MyConsultation } from '../core/api.service';
import { errMsg } from '../core/util';

@Component({
  selector: 'app-consultations',
  standalone: true,
  template: `
    <h3>Mes consultations</h3>
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }
    @if (items().length === 0 && !error()) {
      <p class="muted">Aucune consultation pour le moment.</p>
    }
    @for (c of items(); track c.id) {
      <div class="card">
        <div class="row-between">
          <strong>#{{ c.id }} · {{ c.created_at }}</strong>
          <span>
            <span class="badge" [class.urgent]="c.urgency === 'urgent'">{{ urgencyLabel(c.urgency) }}</span>
            <span class="badge">{{ c.status === 'answered' ? 'Répondu' : 'En attente' }}</span>
          </span>
        </div>
        <p>{{ c.reply || 'En attente de la réponse du médecin.' }}</p>
      </div>
    }
  `,
})
export class ConsultationsPage implements OnInit {
  private api = inject(ApiService);
  items = signal<MyConsultation[]>([]);
  error = signal('');

  ngOnInit() {
    this.api.myConsultations().subscribe({
      next: (r) => this.items.set(r),
      error: (e) => this.error.set(errMsg(e)),
    });
  }

  urgencyLabel(u: string) {
    return u === 'urgent' ? 'Urgent' : u === 'within_24h' ? 'Sous 24 h' : 'Routine';
  }
}
