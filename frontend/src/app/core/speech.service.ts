import { Injectable } from '@angular/core';

export interface DictationHandlers {
  onFinal: (text: string) => void; // phrase terminée
  onInterim: (text: string) => void; // phrase en cours
  onEnd: () => void;
  onError: (message: string) => void;
}

const ERRORS: Record<string, string> = {
  'not-allowed': "Accès au microphone refusé : autorisez-le avec l'icône à gauche de la barre d'adresse.",
  'service-not-allowed': "Accès au microphone refusé : autorisez-le avec l'icône à gauche de la barre d'adresse.",
  'no-speech': 'Aucune voix détectée. Rapprochez-vous du micro et réessayez.',
  'audio-capture': 'Aucun microphone détecté sur cet appareil.',
  network: 'La reconnaissance vocale du navigateur a besoin d’une connexion internet.',
  'language-not-supported': 'Cette langue n’est pas prise en charge par votre navigateur.',
};

/** Dictée vocale : transforme la voix en texte (Web Speech API du navigateur). */
export class Dictation {
  private rec: any;
  private wanted = false;
  private failed = false;

  constructor(lang: string, private h: DictationHandlers) {
    const Ctor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    this.rec = new Ctor();
    this.rec.lang = lang;
    this.rec.continuous = true;
    this.rec.interimResults = true;

    this.rec.onresult = (e: any) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) this.h.onFinal(r[0].transcript.trim());
        else interim += r[0].transcript;
      }
      this.h.onInterim(interim);
    };
    this.rec.onerror = (e: any) => {
      this.failed = true;
      this.wanted = false;
      this.h.onError(ERRORS[e.error] ?? `Erreur de reconnaissance vocale (${e.error}).`);
    };
    this.rec.onend = () => {
      // Le navigateur coupe parfois après un silence : on relance tant que le patient n'a pas arrêté.
      if (this.wanted && !this.failed) {
        try {
          this.rec.start();
          return;
        } catch {
          /* on termine proprement ci-dessous */
        }
      }
      this.wanted = false;
      this.h.onInterim('');
      this.h.onEnd();
    };
  }

  start() {
    this.wanted = true;
    this.failed = false;
    this.rec.start();
  }

  stop() {
    this.wanted = false;
    try {
      this.rec.stop();
    } catch {
      /* déjà arrêté */
    }
  }
}

@Injectable({ providedIn: 'root' })
export class SpeechService {
  readonly supported =
    typeof window !== 'undefined' && !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

  create(lang: string, handlers: DictationHandlers): Dictation {
    return new Dictation(lang, handlers);
  }
}
