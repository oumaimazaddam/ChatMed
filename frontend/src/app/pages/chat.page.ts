import { Component, ElementRef, OnDestroy, OnInit, ViewChild, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, ChatMessage } from '../core/api.service';
import { Dictation, SpeechService } from '../core/speech.service';
import { errMsg } from '../core/util';

const MAX = 500;
const LANGS = [
  { code: 'fr-FR', label: 'FR' },
  { code: 'ar-TN', label: 'عربي' },
  { code: 'en-US', label: 'EN' },
];

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="chat" #box>
      @if (messages().length === 0) {
        <p class="muted">Posez une question sur un médicament (contre-indications, effets indésirables, interactions…).</p>
      }
      @for (m of messages(); track $index) {
        <div class="msg" [class.user]="m.role === 'user'">
          <div class="bubble">{{ m.text }}</div>
        </div>
      }
    </div>

    <div class="row">
      <input
        [ngModel]="question()"
        (ngModelChange)="question.set($event)"
        (keydown.enter)="send()"
        [maxLength]="MAX"
        placeholder="Écrivez ou parlez : Quelles sont les contre-indications de l'ibuprofène ?"
        [disabled]="sending()"
      />
      @if (supported) {
        <select [ngModel]="lang()" (ngModelChange)="lang.set($event)" [disabled]="recording() || sending()" title="Langue de la dictée">
          @for (l of langs; track l.code) {
            <option [value]="l.code">{{ l.label }}</option>
          }
        </select>
        <button
          [class]="recording() ? 'mic on' : 'mic'"
          (click)="toggleRecording()"
          [disabled]="sending()"
          [title]="recording() ? 'Arrêter la dictée' : 'Parler'"
        >
          {{ recording() ? '⏹' : '🎤' }}
        </button>
      }
      <button class="primary" (click)="send()" [disabled]="sending()">
        {{ sending() ? '…' : 'Envoyer' }}
      </button>
    </div>

    @if (recording()) {
      <p class="rec-dot">● Écoute en cours… parlez maintenant, puis cliquez sur ⏹</p>
    }
    @if (interim()) {
      <p class="interim">{{ interim() }}</p>
    }
    @if (voiceError()) {
      <p class="error">{{ voiceError() }}</p>
    }
    @if (supported) {
      <p class="muted">
        🎤 Vous pouvez poser votre question à voix haute. Vérifiez le texte avant d'envoyer : les noms de
        médicaments sont parfois mal transcrits.
      </p>
    } @else {
      <p class="muted">La dictée vocale n'est pas disponible sur ce navigateur (utilisez Chrome ou Edge).</p>
    }
  `,
})
export class ChatPage implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private speech = inject(SpeechService);
  private dictation?: Dictation;

  @ViewChild('box') box?: ElementRef<HTMLElement>;

  readonly MAX = MAX;
  readonly langs = LANGS;
  readonly supported = this.speech.supported;

  messages = signal<ChatMessage[]>([]);
  sending = signal(false);
  question = signal('');

  lang = signal('fr-FR');
  recording = signal(false);
  interim = signal('');
  voiceError = signal('');

  ngOnInit() {
    this.api.history().subscribe({
      next: (h) => {
        this.messages.set(h);
        this.scroll();
      },
      error: () => {},
    });
  }

  ngOnDestroy() {
    this.stopRecording();
  }

  // ----- Dictée vocale -----
  toggleRecording() {
    if (this.recording()) this.stopRecording();
    else this.startRecording();
  }

  private startRecording() {
    this.voiceError.set('');
    this.dictation = this.speech.create(this.lang(), {
      onFinal: (t) => this.question.update((q) => ((q ? q.trimEnd() + ' ' : '') + t).slice(0, MAX)),
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

  // ----- Envoi de la question -----
  async send() {
    this.stopRecording();
    const q = this.question().trim();
    if (!q || this.sending()) return;
    this.question.set('');
    this.sending.set(true);
    this.messages.update((m) => [...m, { role: 'user', text: q }, { role: 'assistant', text: '' }]);
    this.scroll();
    try {
      await this.api.chatStream(q, (type, data) => {
        if (type === 'reset') this.patchLast((m) => ({ ...m, text: '' })); // le modèle a dérivé : on efface
        if (type === 'token' || type === 'error') this.patchLast((m) => ({ ...m, text: m.text + data.t }));
        this.scroll();
      });
    } catch (e) {
      this.patchLast((m) => ({ ...m, text: errMsg(e) }));
    } finally {
      this.sending.set(false);
    }
  }

  private patchLast(fn: (m: ChatMessage) => ChatMessage) {
    this.messages.update((list) => list.map((m, i) => (i === list.length - 1 ? fn(m) : m)));
  }

  private scroll() {
    setTimeout(() => {
      const el = this.box?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }
}