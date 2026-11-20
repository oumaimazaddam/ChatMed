import { Component, OnDestroy, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { Dictation, SpeechService } from '../core/speech.service';
import { errMsg } from '../core/util';

const LANGS = [
  { code: 'fr-FR', label: 'Français' },
  { code: 'ar-TN', label: 'العربية (تونس)' },
  { code: 'en-US', label: 'English' },
];

@Component({
  selector: 'app-symptoms',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="card">
      <h3>Décrire mes symptômes</h3>
      <p class="muted">
        Un médecin recevra un résumé et vous répondra. L'assistant ne pose pas de diagnostic.
      </p>

      <div class="seg">
        <button [class.active]="mode() === 'text'" (click)="setMode('text')">✍️ Écrire</button>
        <button [class.active]="mode() === 'voice'" (click)="setMode('voice')" [disabled]="!supported">🎤 Parler</button>
      </div>
      @if (!supported) {
        <p class="muted">La dictée vocale n'est pas disponible sur ce navigateur. Utilisez Chrome ou Edge.</p>
      }

      @if (mode() === 'voice') {
        <div class="voice-box">
          <div class="voice-row">
            <label class="inline">Langue
              <select [ngModel]="lang()" (ngModelChange)="lang.set($event)" [disabled]="recording()">
                @for (l of langs; track l.code) {
                  <option [value]="l.code">{{ l.label }}</option>
                }
              </select>
            </label>
            <button [class]="recording() ? 'mic on' : 'mic'" (click)="toggleRecording()">
              {{ recording() ? '⏹ Arrêter' : '🎤 Commencer à parler' }}
            </button>
            @if (recording()) {
              <span class="rec-dot">● Écoute en cours…</span>
            }
          </div>
          @if (interim()) {
            <p class="interim">{{ interim() }}</p>
          }
          @if (voiceError()) {
            <p class="error">{{ voiceError() }}</p>
          }
          <p class="muted">
            Votre voix est transformée en texte : le médecin reçoit ce texte. Relisez-le et corrigez-le avant d'envoyer.
            Selon le navigateur, la transcription peut passer par un service en ligne de celui-ci ; MedAssist
            n'enregistre aucun son.
          </p>
        </div>
      }

      <label>Que ressentez-vous ?
        <textarea
          rows="5"
          [maxLength]="MAX"
          [ngModel]="symptoms()"
          (ngModelChange)="symptoms.set($event)"
          [placeholder]="mode() === 'voice' ? 'Votre texte apparaîtra ici pendant que vous parlez' : 'Décrivez vos symptômes avec vos mots'"
        ></textarea>
      </label>
      <small class="muted">{{ symptoms().length }} / {{ MAX }} caractères</small>

      <div class="grid3">
        <label>Durée (jours)<input type="number" min="0" [ngModel]="duration()" (ngModelChange)="duration.set($event)" /></label>
        <label>Intensité (1 à 10)<input type="number" min="1" max="10" [ngModel]="severity()" (ngModelChange)="severity.set($event)" /></label>
        <label>Âge<input type="number" min="0" max="120" [ngModel]="age()" (ngModelChange)="age.set($event)" /></label>
      </div>

      <button class="primary" (click)="send()" [disabled]="loading()">Envoyer au médecin</button>
      @if (result(); as r) {
        <p [class.error]="r.urgent" [class.ok]="!r.urgent">{{ r.message }}</p>
      }
      @if (error()) {
        <p class="error">{{ error() }}</p>
      }
    </div>
  `,
})
export class SymptomsPage implements OnDestroy {
  private api = inject(ApiService);
  private speech = inject(SpeechService);
  private dictation?: Dictation;

  readonly langs = LANGS;
  readonly supported = this.speech.supported;
  readonly MAX = 1500;

  mode = signal<'text' | 'voice'>('text');
  lang = signal('fr-FR');
  recording = signal(false);
  interim = signal('');
  voiceError = signal('');
  voiceUsed = signal(false);

  symptoms = signal('');
  duration = signal<number | null>(null);
  severity = signal<number | null>(null);
  age = signal<number | null>(null);

  result = signal<{ message: string; urgent: boolean } | null>(null);
  error = signal('');
  loading = signal(false);

  setMode(m: 'text' | 'voice') {
    if (m === 'text') this.stopRecording();
    this.voiceError.set('');
    this.mode.set(m);
  }

  toggleRecording() {
    if (this.recording()) this.stopRecording();
    else this.startRecording();
  }

  private startRecording() {
    this.voiceError.set('');
    this.dictation = this.speech.create(this.lang(), {
      onFinal: (t) => {
        this.symptoms.update((s) => ((s ? s.trimEnd() + ' ' : '') + t).slice(0, this.MAX));
        this.voiceUsed.set(true);
      },
      onInterim: (t) => this.interim.set(t),
      onEnd: () => this.recording.set(false),
      onError: (m) => {
        this.voiceError.set(m);
        this.recording.set(false);
      },
    });
    try {
      this.dictation.start();
      this.recording.set(true);
    } catch {
      this.voiceError.set('Impossible de démarrer le microphone.');
    }
  }

  private stopRecording() {
    this.dictation?.stop();
    this.recording.set(false);
    this.interim.set('');
  }

  ngOnDestroy() {
    this.stopRecording();
  }

  send() {
    this.stopRecording();
    this.error.set('');
    this.result.set(null);
    this.loading.set(true);
    this.api
      .createConsultation({
        symptoms: this.symptoms().trim(),
        duration_days: this.duration() ?? 0,
        severity: this.severity() ?? 0,
        age: this.age() ?? 0,
        input_mode: this.voiceUsed() ? 'voice' : 'text',
      })
      .subscribe({
        next: (r) => {
          this.result.set({ message: r.message, urgent: r.urgency === 'urgent' });
          this.symptoms.set('');
          this.voiceUsed.set(false);
          this.loading.set(false);
        },
        error: (e) => {
          this.error.set(errMsg(e));
          this.loading.set(false);
        },
      });
  }
}
