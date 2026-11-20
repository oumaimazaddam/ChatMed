import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AuthService } from './auth.service';

export interface Source {
  drug: string;
  ref: string;
}
export interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  sources?: Source[];
}
export interface PatientRecordData {
  allergies: string;
  treatments: string;
}
export interface SymptomsPayload {
  symptoms: string;
  duration_days: number;
  severity: number;
  age: number;
  input_mode: 'text' | 'voice';
}
export interface ConsultationResult {
  id: number;
  urgency: string;
  message: string;
}
export interface MyConsultation {
  id: number;
  urgency: string;
  status: string;
  created_at: string;
  reply: string;
}
export interface DoctorCase {
  id: number;
  urgency: string;
  patient: string;
  created_at: string;
  summary: string;
}

export interface PatientDashboard {
  name: string;
  total: number;
  pending: number;
  answered: number;
  urgent_pending: number;
  questions: number;
  record: { allergies: boolean; treatments: boolean };
  recent: { id: number; urgency: string; status: string; created_at: string; reply: string }[];
}
export interface DoctorDashboard {
  pending_total: number;
  pending_urgent: number;
  pending_24h: number;
  pending_routine: number;
  answered_total: number;
  answered_today: number;
  avg_response_minutes: number | null;
  oldest_pending_minutes: number | null;
  recent: { id: number; patient: string; urgency: string; answered_at: string; reply: string }[];
    pending_alerts: number;      
  next_cases: {
    id: number; urgency: string; patient: string; created_at: string;
    waiting_minutes: number;
    is_alert: boolean;           
  }[];
}
export interface DoctorHistoryItem {
  id: number;
  patient: string;
  urgency: string;
  created_at: string;
  answered_at: string;
  summary: string;
  reply: string;
}
export interface SlaItem {
  target_minutes: number;
  answered: number;
  on_time: number;
  overdue_pending: number;
}
export interface AdminDashboard {
  period_days: number;
  patients: number;
  doctors: number;
  admins: number;
  consultations_total: number;
  consultations_pending: number;
  consultations_answered: number;
  urgency: { urgent: number; within_24h: number; routine: number };
  questions_total: number;
  emergency_alerts: number;
  failed_logins_24h: number;
  avg_response_minutes: number | null;
  sla: Record<string, SlaItem>;
  overdue_total: number;
  overdue_cases: { id: number; urgency: string; waiting_minutes: number; target_minutes: number }[];
  ai_quality: {
    answered: number;
    not_found: number;
    diagnosis: number;
    emergency: number;
    other: number;
    answered_rate: number | null;
  };
  top_drugs: { drug: string; count: number }[];
  doctors_workload: { name: string; answered_total: number; answered_7d: number; avg_minutes: number | null }[];
  daily: { date: string; questions: number; consultations: number }[];
  top_actions: { action: string; count: number }[];
  system: { database: boolean; ollama: boolean; chunks: number };
}
export interface AuditItem {
  id: number;
  time: string;
  user_id: number | null;
  user: string;
  role: string;
  action: string;
  target: string;
}
export interface AuditPage {
  total: number;
  items: AuditItem[];
  actions: string[];
}
export interface AuditFilter {
  action: string;
  search: string;
}
export interface UserRow {
  id: number;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
  last_login: string;
}
export interface DoctorCase {
  id: number;
  urgency: string;
  patient: string;
  created_at: string;
  summary: string;
  is_alert: boolean;
  alert_type: 'emergency' | 'self_harm' | null;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private auth = inject(AuthService);

  history() {
    return this.http.get<ChatMessage[]>('/api/chat/history');
  }
  getRecord() {
    return this.http.get<PatientRecordData>('/api/me/record');
  }
  saveRecord(data: PatientRecordData) {
    return this.http.put<{ ok: boolean }>('/api/me/record', data);
  }
  createConsultation(data: SymptomsPayload) {
    return this.http.post<ConsultationResult>('/api/consultations', data);
  }
  myConsultations() {
    return this.http.get<MyConsultation[]>('/api/consultations/mine');
  }
  doctorCases() {
    return this.http.get<DoctorCase[]>('/api/doctor/consultations');
  }
  doctorReply(id: number, reply: string) {
    return this.http.post<{ ok: boolean }>(`/api/doctor/consultations/${id}/reply`, { reply });
  }
  auditLog(f: AuditFilter & { limit: number; offset: number }) {
    return this.http.get<AuditPage>('/api/admin/audit', { params: { ...f } });
  }
  auditExport(f: AuditFilter) {
    return this.http.get('/api/admin/audit/export', { params: { ...f }, responseType: 'blob' });
  }

  patientDashboard() {
    return this.http.get<PatientDashboard>('/api/patient/dashboard');
  }
  doctorDashboard() {
    return this.http.get<DoctorDashboard>('/api/doctor/dashboard');
  }
  doctorHistory() {
    return this.http.get<DoctorHistoryItem[]>('/api/doctor/history');
  }
  adminDashboard(days: number) {
    return this.http.get<AdminDashboard>('/api/admin/dashboard', { params: { days } });
  }
  adminUsers() {
    return this.http.get<UserRow[]>('/api/admin/users');
  }
  deleteUser(id: number) {
    return this.http.delete<{ ok: boolean }>(`/api/admin/users/${id}`);
  }
  createDoctor(data: { email: string; full_name: string; password: string }) {
    return this.http.post<{ id: number; email: string }>('/api/admin/doctors', data);
  }

  /** Chat en streaming (SSE). HttpClient ne gère pas le flux : on utilise fetch. */
  async chatStream(question: string, onEvent: (type: string, data: any) => void): Promise<void> {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${this.auth.token()}` },
      body: JSON.stringify({ question }),
    });
    if (res.status === 401) {
      this.auth.logout();
      throw new Error('Session expirée, reconnectez-vous.');
    }
    if (!res.ok || !res.body) {
      const error = await res.json().catch(() => ({}));
      throw { status: res.status, error };
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split('\n\n');
      buffer = events.pop() ?? '';
      for (const ev of events) {
        const type = /^event: (.*)$/m.exec(ev)?.[1] ?? 'message';
        const raw = /^data: (.*)$/m.exec(ev)?.[1] ?? '{}';
        onEvent(type, JSON.parse(raw));
      }
    }
  }
}
