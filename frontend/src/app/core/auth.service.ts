import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs';

export interface AuthResponse {
  token: string;
  role: string;
  name: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);

  // sessionStorage : la session disparaît à la fermeture de l'onglet
  readonly token = signal<string | null>(sessionStorage.getItem('token'));
  readonly role = signal<string | null>(sessionStorage.getItem('role'));
  readonly name = signal<string>(sessionStorage.getItem('name') ?? '');
  readonly loggedIn = computed(() => !!this.token());

  login(email: string, password: string) {
    return this.http.post<AuthResponse>('/api/auth/login', { email, password }).pipe(tap((r) => this.save(r)));
  }

  register(data: { email: string; password: string; full_name: string; consent: boolean }) {
    return this.http.post<AuthResponse>('/api/auth/register', data).pipe(tap((r) => this.save(r)));
  }

  logout() {
    sessionStorage.clear();
    this.token.set(null);
    this.role.set(null);
    this.name.set('');
    this.router.navigate(['/login']);
  }

  homeRoute(): string {
    switch (this.role()) {
      case 'doctor':
        return '/doctor/dashboard';
      case 'admin':
        return '/admin/dashboard';
      default:
        return '/patient/dashboard';
    }
  }

  private save(r: AuthResponse) {
    sessionStorage.setItem('token', r.token);
    sessionStorage.setItem('role', r.role);
    sessionStorage.setItem('name', r.name);
    this.token.set(r.token);
    this.role.set(r.role);
    this.name.set(r.name);
  }
}
