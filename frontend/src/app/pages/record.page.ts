import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../core/api.service';
import { errMsg } from '../core/util';

@Component({
  selector: 'app-record',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="card">
      <h3>Mon dossier</h3>
      <p class="muted">Ces informations sont chiffrées et transmises au médecin avec vos consultations.</p>
      <label>Allergies
        <textarea rows="2" [ngModel]="allergies()" (ngModelChange)="allergies.set($event)"></textarea>
      </label>
      <label>Traitements en cours
        <textarea rows="2" [ngModel]="treatments()" (ngModelChange)="treatments.set($event)"></textarea>
      </label>
      <button class="primary" (click)="save()">Enregistrer</button>
      @if (message()) {
        <p class="ok">{{ message() }}</p>
      }
      @if (error()) {
        <p class="error">{{ error() }}</p>
      }
    </div>
  `,
})
export class RecordPage implements OnInit {
  private api = inject(ApiService);

  allergies = signal('');
  treatments = signal('');
  message = signal('');
  error = signal('');

  ngOnInit() {
    this.api.getRecord().subscribe({
      next: (r) => {
        this.allergies.set(r.allergies);
        this.treatments.set(r.treatments);
      },
      error: (e) => this.error.set(errMsg(e)),
    });
  }

  save() {
    this.message.set('');
    this.error.set('');
    this.api.saveRecord({ allergies: this.allergies(), treatments: this.treatments() }).subscribe({
      next: () => this.message.set('Dossier enregistré.'),
      error: (e) => this.error.set(errMsg(e)),
    });
  }
}
