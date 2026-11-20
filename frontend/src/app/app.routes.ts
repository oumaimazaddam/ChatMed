import { Routes } from '@angular/router';
import { authGuard, homeGuard, roleGuard } from './core/guards';
import { ShellComponent } from './layout/shell';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./pages/login.page').then((m) => m.LoginPage),
  },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      // ----- Patient -----
      {
        path: 'patient',
        canActivate: [roleGuard('patient')],
        children: [
          { path: 'dashboard', loadComponent: () => import('./pages/patient-dashboard.page').then((m) => m.PatientDashboardPage) },
          { path: 'chat', loadComponent: () => import('./pages/chat.page').then((m) => m.ChatPage) },
          { path: 'symptoms', loadComponent: () => import('./pages/symptoms.page').then((m) => m.SymptomsPage) },
          { path: 'consultations', loadComponent: () => import('./pages/consultations.page').then((m) => m.ConsultationsPage) },
          { path: 'record', loadComponent: () => import('./pages/record.page').then((m) => m.RecordPage) },
          { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
        ],
      },
      // ----- Médecin -----
      {
        path: 'doctor',
        canActivate: [roleGuard('doctor')],
        children: [
          { path: 'dashboard', loadComponent: () => import('./pages/doctor-dashboard.page').then((m) => m.DoctorDashboardPage) },
          { path: 'cases', loadComponent: () => import('./pages/doctor.page').then((m) => m.DoctorPage) },
          { path: 'history', loadComponent: () => import('./pages/doctor-history.page').then((m) => m.DoctorHistoryPage) },
          { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
        ],
      },
      // ----- Administrateur -----
      {
        path: 'admin',
        canActivate: [roleGuard('admin')],
        children: [
          { path: 'dashboard', loadComponent: () => import('./pages/admin-dashboard.page').then((m) => m.AdminDashboardPage) },
          { path: 'users', loadComponent: () => import('./pages/admin-users.page').then((m) => m.AdminUsersPage) },
          { path: 'audit', loadComponent: () => import('./pages/admin.page').then((m) => m.AdminPage) },
          { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
        ],
      },
      { path: '', pathMatch: 'full', canActivate: [homeGuard], children: [] },
    ],
  },
  { path: '**', redirectTo: '' },
];
