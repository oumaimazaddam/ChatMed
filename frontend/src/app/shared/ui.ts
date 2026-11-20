import { Component, computed, input } from '@angular/core';

/** Carte de statistique : un chiffre et son libellé. */
@Component({
  selector: 'app-stat',
  standalone: true,
  template: `
    <div [class]="'stat ' + tone()">
      <div class="stat-value">{{ value() }}</div>
      <div class="stat-label">{{ label() }}</div>
      @if (hint()) {
        <div class="stat-hint">{{ hint() }}</div>
      }
    </div>
  `,
})
export class StatCard {
  label = input.required<string>();
  value = input.required<string | number>();
  hint = input('');
  tone = input<'default' | 'red' | 'green' | 'orange' | 'blue'>('default');
}

export interface DailyPoint {
  date: string;
  questions: number;
  consultations: number;
}

/** Histogramme des 7 derniers jours (deux séries), en CSS pur. */
@Component({
  selector: 'app-daily-chart',
  standalone: true,
  template: `
    <div class="chart" [class.dense]="dense()">
      @for (d of days(); track $index; let i = $index) {
        <div class="chart-col">
          <div class="chart-bars">
            <div class="bar blue" [style.height.%]="pct(d.questions)" [title]="d.questions + ' question(s)'"></div>
            <div class="bar green" [style.height.%]="pct(d.consultations)" [title]="d.consultations + ' consultation(s)'"></div>
          </div>
          <div class="chart-label">{{ !dense() || i % 5 === 0 ? d.date : '' }}</div>
          @if (!dense()) {
            <div class="chart-values">{{ d.questions }} · {{ d.consultations }}</div>
          }
        </div>
      }
    </div>
    <div class="legend">
      <span class="dot blue"></span> Questions au chat
      <span class="dot green"></span> Consultations
    </div>
  `,
})
export class DailyChart {
  days = input.required<DailyPoint[]>();
  dense = computed(() => this.days().length > 10);
  private max = computed(() => Math.max(1, ...this.days().flatMap((d) => [d.questions, d.consultations])));
  pct(v: number) {
    return (v / this.max()) * 100;
  }
}

export interface BarItem {
  label: string;
  value: number;
  tone: 'red' | 'orange' | 'green' | 'blue';
}

/** Barres horizontales (répartition). */
@Component({
  selector: 'app-hbars',
  standalone: true,
  template: `
    @for (i of items(); track i.label) {
      <div class="hbar">
        <span class="hbar-label">{{ i.label }}</span>
        <div class="hbar-track"><div [class]="'hbar-fill ' + i.tone" [style.width.%]="pct(i.value)"></div></div>
        <span class="hbar-val">{{ i.value }}</span>
      </div>
    }
  `,
})
export class HBars {
  items = input.required<BarItem[]>();
  private max = computed(() => Math.max(1, ...this.items().map((i) => i.value)));
  pct(v: number) {
    return (v / this.max()) * 100;
  }
}

/** Jauge de pourcentage (ex. respect des délais). Vert >= 90 %, orange >= 70 %, rouge sinon. */
@Component({
  selector: 'app-meter',
  standalone: true,
  template: `
    <div class="meter">
      <div class="row-between">
        <span>{{ label() }}</span>
        <strong>{{ percent() === null ? '—' : percent() + ' %' }}</strong>
      </div>
      <div class="meter-track"><div [class]="'meter-fill ' + tone()" [style.width.%]="percent() ?? 0"></div></div>
      <small class="muted">{{ detail() }}</small>
    </div>
  `,
})
export class Meter {
  label = input.required<string>();
  percent = input.required<number | null>();
  detail = input('');
  tone = computed(() => {
    const p = this.percent();
    return p === null ? 'blue' : p >= 90 ? 'green' : p >= 70 ? 'orange' : 'red';
  });
}
