const FIELDS: Record<string, string> = {
  full_name: 'nom complet (2 caractères minimum)',
  password: 'mot de passe (8 à 72 caractères)',
  email: 'email',
  consent: 'consentement',
  question: 'question',
  symptoms: 'symptômes (5 caractères minimum)',
  duration_days: 'durée en jours',
  severity: 'intensité (1 à 10)',
  age: 'âge (0 à 120)',
  reply: 'réponse',
};

/** Transforme une erreur HTTP en message lisible pour l'utilisateur. */
export function errMsg(e: any): string {
  const detail = e?.error?.detail;
  if (Array.isArray(detail)) {
    const names = detail.map((d: any) => FIELDS[d?.loc?.[d.loc.length - 1]] ?? 'un champ');
    return 'Vérifiez : ' + [...new Set(names)].join(', ');
  }
  if (typeof detail === 'string') return detail;
  if (e?.status === 0) return 'Serveur injoignable : vérifiez que le backend tourne.';
  return e?.message ?? 'Erreur inattendue';
}

/** 95 -> "1,6 h", 12 -> "12 min", null -> "—" */
export function fmtMinutes(m: number | null | undefined): string {
  if (m === null || m === undefined) return '—';
  if (m < 60) return `${Math.round(m)} min`;
  if (m < 1440) return `${(m / 60).toFixed(1).replace('.', ',')} h`;
  return `${(m / 1440).toFixed(1).replace('.', ',')} j`;
}

export function urgencyLabel(u: string): string {
  return u === 'urgent' ? 'Urgent' : u === 'within_24h' ? 'Sous 24 h' : 'Routine';
}
