import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AdminDashboard, ApiService, SlaItem } from '../core/api.service';
import { errMsg, fmtMinutes, urgencyLabel } from '../core/util';
import { BarItem, DailyChart, HBars, Meter, StatCard } from '../shared/ui';

interface Alert {
  tone: 'red' | 'orange';
  text: string;
}

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [RouterLink, StatCard, DailyChart, HBars, Meter],
  template: `
    <div class="row-between">
      <h2>Tableau de bord administrateur</h2>
      <div class="toolbar">
        <span class="muted">Mis à jour à {{ updatedAt() }}</span>
        <div class="seg">
          <button [class.active]="days() === 7" (click)="setDays(7)">7 jours</button>
          <button [class.active]="days() === 30" (click)="setDays(30)">30 jours</button>
        </div>
        <button (click)="load()">Actualiser</button>
      </div>
    </div>

    @if (error()) {
      <p class="error">{{ error() }}</p>
    }

    @if (data(); as d) {
      <!-- Centre d'alertes -->
      @for (a of alerts(d); track a.text) {
        <div [class]="'alert ' + a.tone">{{ a.tone === 'red' ? '⚠️' : '⚡' }} {{ a.text }}</div>
      } @empty {
        <div class="alert green">✔ Tout est opérationnel : aucun incident à signaler.</div>
      }

      <div class="stats">
        <app-stat label="Patients" [value]="d.patients" tone="blue" />
        <app-stat label="Médecins" [value]="d.doctors" tone="green" />
        <app-stat label="Consultations" [value]="d.consultations_total" [hint]="d.consultations_pending + ' en attente'" />
        <app-stat label="Alertes d'urgence" [value]="d.emergency_alerts" tone="red" />
      </div>
      <div class="stats">
        <app-stat label="Questions au chat" [value]="d.questions_total" />
        <app-stat label="Temps moyen de réponse" [value]="fmt(d.avg_response_minutes)" />
        <app-stat label="Cas en retard" [value]="d.overdue_total" [tone]="d.overdue_total > 0 ? 'red' : 'green'" />
        <app-stat label="Échecs de connexion (24 h)" [value]="d.failed_logins_24h" [tone]="d.failed_logins_24h >= 5 ? 'orange' : 'default'" />
      </div>

      <div class="grid2">
        <!-- Respect des délais -->
        <div class="card">
          <h3>Respect des délais de réponse</h3>
          @for (u of urgencies; track u) {
            <app-meter
              [label]="label(u) + ' (cible : ' + fmt(d.sla[u].target_minutes) + ')'"
              [percent]="pct(d.sla[u])"
              [detail]="d.sla[u].on_time + ' / ' + d.sla[u].answered + ' dans les délais · ' + d.sla[u].overdue_pending + ' en retard'"
            />
          }
          @if (d.overdue_cases.length > 0) {
            <h3>Cas en retard</h3>
            @for (c of d.overdue_cases; track c.id) {
              <div class="list-item row-between">
                <span>#{{ c.id }} <span class="badge" [class.urgent]="c.urgency === 'urgent'">{{ label(c.urgency) }}</span></span>
                <span class="error">attend depuis {{ fmt(c.waiting_minutes) }} (cible {{ fmt(c.target_minutes) }})</span>
              </div>
            }
          }
        </div>

        <!-- Qualité de l'IA -->
        <div class="card">
          <h3>Qualité de l'assistant IA</h3>
          <app-meter
            label="Réponses sourcées"
            [percent]="d.ai_quality.answered_rate"
            detail="Part des questions qui ont reçu une réponse appuyée sur une notice"
          />
          <app-hbars [items]="aiBars(d)" />
          <p class="muted">
            Beaucoup de « je ne sais pas » signalent des notices manquantes ou un seuil de similarité trop strict.
          </p>
        </div>
      </div>

      <div class="grid2">
        <div class="card">
          <h3>Médicaments les plus consultés</h3>
          @if (d.top_drugs.length === 0) {
            <p class="muted">Pas encore de réponses sourcées.</p>
          } @else {
            <app-hbars [items]="drugBars(d)" />
          }
        </div>

        <div class="card">
          <h3>Consultations par urgence</h3>
          <app-hbars [items]="urgencyBars(d)" />
          <h3>Actions les plus fréquentes</h3>
          <app-hbars [items]="actionBars(d)" />
        </div>
      </div>

      <div class="card">
        <h3>Charge de travail des médecins</h3>
        @if (d.doctors_workload.length === 0) {
          <p class="muted">Aucun médecin. <a routerLink="/admin/users">Créer un compte médecin</a></p>
        } @else {
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>Médecin</th><th>Cas traités (7 j)</th><th>Total traités</th><th>Temps moyen</th></tr>
              </thead>
              <tbody>
                @for (w of d.doctors_workload; track w.name) {
                  <tr>
                    <td>{{ w.name }}</td>
                    <td>{{ w.answered_7d }}</td>
                    <td>{{ w.answered_total }}</td>
                    <td>{{ fmt(w.avg_minutes) }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </div>

      <div class="grid2">
        <div class="card">
          <h3>État du système</h3>
          <div class="status-row"><span [class]="'dot ' + (d.system.database ? 'green' : 'red')"></span> Base de données <strong>{{ d.system.database ? 'OK' : 'Hors service' }}</strong></div>
          <div class="status-row"><span [class]="'dot ' + (d.system.ollama ? 'green' : 'red')"></span> Serveur d'IA (Ollama) <strong>{{ d.system.ollama ? 'OK' : 'Hors service' }}</strong></div>
          <div class="status-row"><span [class]="'dot ' + (d.system.chunks > 0 ? 'green' : 'orange')"></span> Notices indexées <strong>{{ d.system.chunks }} morceaux</strong></div>
          <div class="actions">
            <a class="btn" routerLink="/admin/users">Gérer les utilisateurs</a>
            <a class="btn" routerLink="/admin/audit">Journal d'audit</a>
          </div>
        </div>

        <div class="card">
          <h3>Activité des {{ d.period_days }} derniers jours</h3>
          <app-daily-chart [days]="d.daily" />
        </div>
      </div>
    }
  `,
})
export class AdminDashboardPage implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private timer?: ReturnType<typeof setInterval>;

  data = signal<AdminDashboard | null>(null);
  error = signal('');
  days = signal(7);
  updatedAt = signal('—');
  fmt = fmtMinutes;
  label = urgencyLabel;
  urgencies = ['urgent', 'within_24h', 'routine'];

  ngOnInit() {
    this.load();
    this.timer = setInterval(() => this.load(), 30000); // actualisation automatique toutes les 30 s
  }

  ngOnDestroy() {
    clearInterval(this.timer);
  }

  setDays(n: number) {
    this.days.set(n);
    this.load();
  }

  load() {
    this.api.adminDashboard(this.days()).subscribe({
      next: (d) => {
        this.data.set(d);
        this.error.set('');
        this.updatedAt.set(new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }));
      },
      error: (e) => this.error.set(errMsg(e)),
    });
  }

  pct(s: SlaItem): number | null {
    return s.answered ? Math.round((100 * s.on_time) / s.answered) : null;
  }

  alerts(d: AdminDashboard): Alert[] {
    const list: Alert[] = [];
    if (!d.system.database) list.push({ tone: 'red', text: 'La base de données ne répond pas.' });
    if (!d.system.ollama) list.push({ tone: 'red', text: "Le serveur d'IA (Ollama) ne répond pas : le chat est indisponible." });
    if (d.system.chunks === 0) list.push({ tone: 'orange', text: "Aucune notice n'est indexée : lancez python ingest.py." });
    if (d.overdue_total > 0) list.push({ tone: 'red', text: `${d.overdue_total} cas en retard sur le délai de réponse cible.` });
    if (d.failed_logins_24h >= 5) list.push({ tone: 'orange', text: `${d.failed_logins_24h} échecs de connexion en 24 h : vérifiez le journal d'audit.` });
    return list;
  }

  aiBars(d: AdminDashboard): BarItem[] {
    const q = d.ai_quality;
    const bars: BarItem[] = [
      { label: 'Réponses sourcées', value: q.answered, tone: 'green' },
      { label: '« Je ne sais pas »', value: q.not_found, tone: 'orange' },
      { label: 'Refus de diagnostic', value: q.diagnosis, tone: 'blue' },
      { label: "Alertes d'urgence", value: q.emergency, tone: 'red' },
    ];
    if (q.other > 0) bars.push({ label: 'Autres', value: q.other, tone: 'blue' });
    return bars;
  }

  drugBars(d: AdminDashboard): BarItem[] {
    return d.top_drugs.map((x) => ({ label: x.drug, value: x.count, tone: 'blue' as const }));
  }

  urgencyBars(d: AdminDashboard): BarItem[] {
    return [
      { label: 'Urgent', value: d.urgency.urgent, tone: 'red' },
      { label: 'Sous 24 h', value: d.urgency.within_24h, tone: 'orange' },
      { label: 'Routine', value: d.urgency.routine, tone: 'green' },
    ];
  }

  actionBars(d: AdminDashboard): BarItem[] {
    return d.top_actions.map((a) => ({ label: a.action, value: a.count, tone: 'blue' as const }));
  }
}
