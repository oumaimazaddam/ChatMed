import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, UserRow } from '../core/api.service';
import { errMsg } from '../core/util';

@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [FormsModule],
  template: `
    <h3>Utilisateurs</h3>

    <div class="card">
      <h3>Créer un compte médecin</h3>
      <div class="grid3">
        <label>Email<input type="email" [(ngModel)]="email" /></label>
        <label>Nom complet<input [(ngModel)]="fullName" /></label>
        <label>Mot de passe (8 caractères min.)<input type="password" [(ngModel)]="password" autocomplete="new-password" /></label>
      </div>
      <button class="primary" (click)="create()">Créer le compte médecin</button>
    </div>

    @if (message()) {
      <p class="ok">{{ message() }}</p>
    }
    @if (error()) {
      <p class="error">{{ error() }}</p>
    }

    <div class="toolbar wrap">
      <select [ngModel]="role()" (ngModelChange)="role.set($event)">
        <option value="">Tous les rôles</option>
        <option value="patient">Patients</option>
        <option value="doctor">Médecins</option>
        <option value="admin">Administrateurs</option>
      </select>
      <input [ngModel]="query()" (ngModelChange)="query.set($event)" placeholder="Rechercher (nom ou email)" />
      <span class="muted">{{ filtered().length }} utilisateur(s)</span>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>#</th><th>Nom</th><th>Email</th><th>Rôle</th><th>Créé le</th><th>Dernière connexion</th><th>Actions</th></tr>
        </thead>
        <tbody>
          @for (u of filtered(); track u.id) {
            <tr>
              <td>{{ u.id }}</td>
              <td>{{ u.full_name }}</td>
              <td>{{ u.email }}</td>
              <td><span class="badge">{{ u.role }}</span></td>
              <td>{{ u.created_at }}</td>
              <td>{{ u.last_login || 'Jamais' }}</td>
              <td><button class="danger" (click)="remove(u)">Supprimer</button></td>
            </tr>
          } @empty {
            <tr><td colspan="7" class="muted">Aucun utilisateur.</td></tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class AdminUsersPage implements OnInit {
  private api = inject(ApiService);

  users = signal<UserRow[]>([]);
  role = signal('');
  query = signal('');
  message = signal('');
  error = signal('');
  email = '';
  fullName = '';
  password = '';

  filtered = computed(() => {
    const q = this.query().trim().toLowerCase();
    return this.users().filter(
      (u) =>
        (!this.role() || u.role === this.role()) &&
        (!q || u.full_name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q)),
    );
  });

  ngOnInit() {
    this.load();
  }

  load() {
    this.api.adminUsers().subscribe({
      next: (r) => this.users.set(r),
      error: (e) => this.error.set(errMsg(e)),
    });
  }

  create() {
    this.message.set('');
    this.error.set('');
    this.api
      .createDoctor({ email: this.email.trim(), full_name: this.fullName.trim(), password: this.password })
      .subscribe({
        next: (r) => {
          this.message.set(`Compte médecin créé : ${r.email}`);
          this.email = this.fullName = this.password = '';
          this.load();
        },
        error: (e) => this.error.set(errMsg(e)),
      });
  }

  remove(u: UserRow) {
    const detail =
      u.role === 'patient'
        ? 'Toutes ses données (messages, consultations, dossier) seront supprimées définitivement.'
        : u.role === 'doctor'
          ? 'Ses consultations déjà traitées sont conservées, sans médecin associé.'
          : 'Ce compte administrateur sera supprimé.';
    if (!confirm(`Supprimer ${u.full_name} (${u.email}) ?\n\n${detail}\nCette action est irréversible.`)) return;

    this.message.set('');
    this.error.set('');
    this.api.deleteUser(u.id).subscribe({
      next: () => {
        this.message.set(`Compte supprimé : ${u.email}`);
        this.load();
      },
      error: (e) => this.error.set(errMsg(e)),
    });
  }
}
