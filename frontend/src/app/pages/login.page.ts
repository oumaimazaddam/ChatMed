import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../core/auth.service';
import { errMsg } from '../core/util';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="auth-box card">
      <h2>MedAssist</h2>
      <p class="muted">Assistant d'information sur les médicaments</p>

      <div class="tabs">
        <button [class.active]="mode() === 'login'" (click)="mode.set('login')">Connexion</button>
        <button [class.active]="mode() === 'register'" (click)="mode.set('register')">Créer un compte</button>
      </div>

      <label>Email<input type="email" [(ngModel)]="email" autocomplete="username" /></label>
      @if (mode() === 'register') {
        <label>Nom complet<input [(ngModel)]="fullName" autocomplete="name" /></label>
      }
      <label>Mot de passe<input type="password" [(ngModel)]="password" autocomplete="current-password" /></label>
      @if (mode() === 'register') {
        <label class="check">
          <input type="checkbox" [(ngModel)]="consent" />
          J'accepte le traitement de mes données de santé pour ce service
        </label>
      }

      <button class="primary" (click)="submit()" [disabled]="loading()">
        {{ mode() === 'login' ? 'Se connecter' : 'Créer mon compte patient' }}
      </button>
      @if (error()) {
        <p class="error">{{ error() }}</p>
      }
    </div>
  `,
})
export class LoginPage {
  private auth = inject(AuthService);
  private router = inject(Router);

  mode = signal<'login' | 'register'>('login');
  email = '';
  password = '';
  fullName = '';
  consent = false;
  error = signal('');
  loading = signal(false);

  submit() {
    this.error.set('');
    this.loading.set(true);
    const request =
      this.mode() === 'login'
        ? this.auth.login(this.email.trim(), this.password)
        : this.auth.register({
            email: this.email.trim(),
            password: this.password,
            full_name: this.fullName.trim(),
            consent: this.consent,
          });
    request.subscribe({
      next: () => this.router.navigate([this.auth.homeRoute()]),
      error: (e) => {
        this.error.set(errMsg(e));
        this.loading.set(false);
      },
    });
  }
}
