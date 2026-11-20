import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, AuditItem } from '../core/api.service';
import { errMsg } from '../core/util';

const PAGE = 25;
const DANGER = ['emergency_alert', 'login_failed'];
const SENSITIVE = ['admin_create_doctor', 'admin_export_audit', 'doctor_view_consultation', 'doctor_view_history'];

@Component({
  selector: 'app-admin-audit',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h3>Journal d'audit</h3>

    <div class="toolbar wrap">
      <select [ngModel]="action()" (ngModelChange)="onAction($event)">
        <option value="">Toutes les actions</option>
        @for (a of actions(); track a) {
          <option [value]="a">{{ a }}</option>
        }
      </select>
      <input [(ngModel)]="search" (keydown.enter)="applySearch()" placeholder="Rechercher un utilisateur (nom ou email)" />
      <button (click)="applySearch()">Rechercher</button>
      <button (click)="exportCsv()">Exporter en CSV</button>
    </div>

    @if (error()) {
      <p class="error">{{ error() }}</p>
    }

    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Date</th><th>Utilisateur</th><th>Rôle</th><th>Action</th><th>Cible</th></tr>
        </thead>
        <tbody>
          @for (r of items(); track r.id) {
            <tr>
              <td>{{ r.time }}</td>
              <td>{{ r.user }} @if (r.user_id) {<small class="muted">#{{ r.user_id }}</small>}</td>
              <td>{{ r.role }}</td>
              <td><span [class]="badgeClass(r)">{{ r.action }}</span></td>
              <td>{{ r.target }}</td>
            </tr>
          } @empty {
            <tr><td colspan="5" class="muted">Aucune entrée pour ces filtres.</td></tr>
          }
        </tbody>
      </table>
    </div>

    <div class="toolbar pager">
      <button (click)="prev()" [disabled]="offset() === 0">← Précédent</button>
      <span class="muted">{{ from() }}–{{ to() }} sur {{ total() }}</span>
      <button (click)="next()" [disabled]="offset() + PAGE >= total()">Suivant →</button>
    </div>
  `,
})
export class AdminPage implements OnInit {
  private api = inject(ApiService);
  readonly PAGE = PAGE;

  items = signal<AuditItem[]>([]);
  actions = signal<string[]>([]);
  total = signal(0);
  offset = signal(0);
  action = signal('');
  error = signal('');
  search = '';
  private appliedSearch = '';

  ngOnInit() {
    this.load();
  }

  load() {
    this.api.auditLog({ action: this.action(), search: this.appliedSearch, limit: PAGE, offset: this.offset() }).subscribe({
      next: (r) => {
        this.items.set(r.items);
        this.total.set(r.total);
        this.actions.set(r.actions);
        this.error.set('');
      },
      error: (e) => this.error.set(errMsg(e)),
    });
  }

  onAction(a: string) {
    this.action.set(a);
    this.offset.set(0);
    this.load();
  }

  applySearch() {
    this.appliedSearch = this.search.trim();
    this.offset.set(0);
    this.load();
  }

  prev() {
    this.offset.update((o) => Math.max(0, o - PAGE));
    this.load();
  }

  next() {
    this.offset.update((o) => o + PAGE);
    this.load();
  }

  from() {
    return this.total() === 0 ? 0 : this.offset() + 1;
  }

  to() {
    return Math.min(this.offset() + PAGE, this.total());
  }

  badgeClass(r: AuditItem) {
    return 'badge' + (DANGER.includes(r.action) ? ' urgent' : SENSITIVE.includes(r.action) ? ' warn' : '');
  }

  exportCsv() {
    this.api.auditExport({ action: this.action(), search: this.appliedSearch }).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'audit.csv';
        a.click();
        URL.revokeObjectURL(url);
      },
      error: (e) => this.error.set(errMsg(e)),
    });
  }
}
