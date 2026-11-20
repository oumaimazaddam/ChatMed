"""
app/intake.py - Dialogue guidé de recueil des symptômes dans le chat (FR / AR)

Quand un patient écrit « عندي الم » ou « j'ai mal au ventre », le chatbot pose quelques questions
(description, durée, intensité, âge, signes d'alerte), puis transmet un résumé à un médecin.
Le chatbot ne pose AUCUN diagnostic : il recueille seulement les informations.

L'état de la conversation est gardé en mémoire (un dict par patient, expire après 30 min).
Limite : si le backend tourne avec plusieurs workers ou redémarre, le dialogue en cours est perdu.
"""
import re
import time

from app.triage import URGENCY_MESSAGES, norm

SESSION_TTL = 30 * 60
STEPS = ["describe", "duration", "severity", "age", "redflags"]
_sessions: dict[int, dict] = {}

QUESTIONS = {
    "fr": {
        "describe": ("Je suis désolé que vous souffriez. Pour mieux comprendre : où se situe exactement votre "
                     "douleur ou votre gêne, et comment la ressentez-vous (brûlure, piqûre, pression, crampes…) ?"),
        "duration": "Depuis combien de temps avez-vous ces symptômes ? (par exemple : 2 heures, 3 jours, 1 semaine)",
        "severity": "Sur une échelle de 1 à 10, quelle est l'intensité ? (1 = très légère, 10 = insupportable)",
        "age": "Quel âge avez-vous (ou quel âge a la personne concernée) ?",
        "redflags": ("Dernière question : avez-vous l'un de ces signes : difficulté à respirer, douleur dans la "
                     "poitrine, perte de connaissance, saignement important, confusion ? (oui / non)"),
    },
    "ar": {
        "describe": ("أنا آسف لأنك تتألم. لأفهم أكثر: أين يوجد الألم أو الإزعاج بالضبط، وكيف تشعر به "
                     "(حرقة، وخز، ضغط، تقلصات...)؟"),
        "duration": "منذ متى تعاني من هذه الأعراض؟ (مثلًا: ساعتان، 3 أيام، أسبوع)",
        "severity": "من 1 إلى 10، ما شدة الألم؟ (1 = خفيف جدًا، 10 = لا يُحتمل)",
        "age": "كم عمرك (أو كم عمر الشخص المعني)؟",
        "redflags": ("سؤال أخير: هل لديك أحد هذه العلامات: صعوبة في التنفس، ألم في الصدر، فقدان الوعي، "
                     "نزيف شديد، تشوش؟ (نعم / لا)"),
    },
}
HINTS = {"fr": "Je n'ai pas bien compris. ", "ar": "لم أفهم جيدًا. "}
CANCELLED = {
    "fr": "D'accord, j'arrête ce questionnaire. Vous pouvez aussi utiliser l'onglet « Symptômes ».",
    "ar": "حسنًا، أوقفت هذه الأسئلة. يمكنك أيضًا استعمال تبويب «Symptômes» (الأعراض).",
}
URGENCY_AR = {
    "urgent": "⚠️ حالتك مصنفة عاجلة. اتصل بالرقم 190 أو توجه إلى المستعجلات دون انتظار رد الطبيب.",
    "within_24h": "تم إرسال طلبك. من المفترض أن يعالجه طبيب خلال 24 ساعة.",
    "routine": "تم إرسال طلبك إلى طبيب. ستجد رده في «Mes consultations».",
}

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
CANCEL_WORDS = [norm(x) for x in ["annuler", "stop", "laisse tomber", "cancel", "الغاء", "إلغاء", "وقف"]]
_NUM_WORDS = {norm(k): v for k, v in {
    "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
    "يومين": 2, "اسبوعين": 2, "أسبوعين": 2, "شهرين": 2, "ساعتين": 2,
    "ثلاثة": 3, "ثلاث": 3, "اربعة": 4, "أربعة": 4, "خمسة": 5, "ستة": 6, "سبعة": 7, "عشرة": 10,
}.items()}
_UNITS = [  # (jours par unité, motif)
    (365, r"\b(an|ans|annee|annees|year|years)\b|سنه|سنة|سنوات|سنين"),
    (30, r"\bmois\b|\bmonths?\b|شهر|اشهر"),
    (7, r"semaine|week|اسبوع|اسابيع"),
    (1, r"\bjours?\b|\bjournees?\b|\bdays?\b|يوم|ايام"),
    (0, r"heure|(?<=\d)h\b|\bh\b|minute|hour|ساعه|ساعة|ساعات|ساعتين|دقيقه|دقيقة|دقائق"),
]


def _prep(text: str) -> str:
    return norm(text.translate(_DIGITS))


def _lang(text: str) -> str:
    return "ar" if any("\u0600" <= ch <= "\u06ff" for ch in text) else "fr"


# ---------------------------------------------------------------- Lecture des réponses
def parse_duration(text: str):
    """Durée en jours (0 = moins d'un jour), ou None si incompréhensible."""
    t = _prep(text)
    if re.search(r"\bhier\b|امس|البارح", t):
        return 1
    if re.search(r"aujourd|ce matin|ce soir|cette nuit|اليوم|الليله|الليلة|هذا الصباح", t):
        return 0
    m = re.search(r"\d+", t)
    n = int(m.group()) if m else next((_NUM_WORDS[w] for w in re.findall(r"\w+", t) if w in _NUM_WORDS), 1)
    for days, pattern in _UNITS:
        if re.search(pattern, t):
            return min(n * days, 3650)
    return min(n, 3650) if m else None


def parse_severity(text: str):
    t = _prep(text)
    m = re.search(r"\d+", t)
    if m:
        return min(max(int(m.group()), 1), 10)
    if re.search(r"insupportable|atroce|terrible|لا يحتمل|لا تحتمل|ما نجمش نتحمل|شديد جدا", t):
        return 10
    if re.search(r"fort|severe|intense|شديد|قوي|كبير", t):
        return 8
    if re.search(r"moyen|modere|متوسط|عادي", t):
        return 5
    if re.search(r"leger|faible|petit|un peu|خفيف|شوي|قليل", t):
        return 3
    return None


def parse_age(text: str):
    t = _prep(text)
    m = re.search(r"\d+", t)
    if not m:
        return None
    if re.search(r"\bmois\b|شهر|اشهر", t):
        return 0  # bébé en mois
    age = int(m.group())
    return age if 0 <= age <= 120 else None


def parse_yes_no(text: str):
    t = _prep(text)
    if re.search(r"\b(oui|ouais|yes|yep)\b|نعم|\bاي\b|ايه|\bاه\b|ايوه|اكيد", t):
        return True  # en cas de doute, on privilégie la sécurité
    if re.search(r"\b(non|no|pas|aucun|rien|jamais)\b|\bلا\b|لأ|ما فماش|ماهوش", t):
        return False
    return None


def _parse(step: str, text: str):
    if step == "describe":
        return text.strip()[:500]
    return {"duration": parse_duration, "severity": parse_severity,
            "age": parse_age, "redflags": parse_yes_no}[step](text)


# Valeur utilisée si le patient n'est pas compris deux fois de suite (le médecin est prévenu dans le résumé)
DEFAULTS = {"duration": 0, "severity": 5, "age": 30, "redflags": False}
UNKNOWN_LABELS = {
    "duration": "durée non précisée",
    "severity": "intensité non précisée (5 par défaut)",
    "age": "âge non précisé (30 par défaut)",
    "redflags": "signes d'alerte : réponse non comprise",
}


# ---------------------------------------------------------------- Session
def is_active(uid: int) -> bool:
    s = _sessions.get(uid)
    if not s:
        return False
    if time.time() - s["ts"] > SESSION_TTL:
        _sessions.pop(uid, None)
        return False
    return True


def cancel(uid: int) -> None:
    _sessions.pop(uid, None)


def start(uid: int, complaint: str) -> str:
    lang = _lang(complaint)
    _sessions[uid] = {"lang": lang, "step": 0, "complaint": complaint.strip()[:300], "ts": time.time(),
                      "retry": False, "answers": {}, "unknown": []}
    return QUESTIONS[lang]["describe"]


def answer(uid: int, text: str):
    """Traite la réponse du patient. Retourne (statut, réponse, infos) :
    statut = ask | cancel | done | red_flag ; infos = None sauf pour done / red_flag."""
    s = _sessions[uid]
    s["ts"] = time.time()
    lang = s["lang"]
    t = norm(text)
    if len(t) < 30 and any(w in t for w in CANCEL_WORDS):
        cancel(uid)
        return "cancel", CANCELLED[lang], None

    step = STEPS[s["step"]]
    value = _parse(step, text)
    if value is None:
        if not s["retry"]:
            s["retry"] = True
            return "ask", HINTS[lang] + QUESTIONS[lang][step], None
        s["unknown"].append(step)
        value = DEFAULTS[step]
    s["answers"][step] = value
    s["retry"] = False
    s["step"] += 1
    if s["step"] < len(STEPS):
        return "ask", QUESTIONS[lang][STEPS[s["step"]]], None

    info = _build_info(s)
    cancel(uid)
    return ("red_flag" if s["answers"]["redflags"] else "done"), "", info


def _build_info(s: dict) -> dict:
    a = s["answers"]
    text = (f"[Recueil guidé dans le chat] Plainte initiale : {s['complaint']}. "
            f"Description : {a['describe']}. "
            f"Signes d'alerte (difficulté à respirer, douleur thoracique, perte de connaissance, saignement, "
            f"confusion) : {'OUI' if a['redflags'] else 'non déclarés'}.")
    if s["unknown"]:
        text += " À vérifier : " + ", ".join(UNKNOWN_LABELS[k] for k in s["unknown"]) + "."
    return {"lang": s["lang"], "symptoms": text[:1500], "duration_days": a["duration"],
            "severity": a["severity"], "age": a["age"], "describe": a["describe"]}


# ---------------------------------------------------------------- Messages finaux
def final_reply(info: dict, urgency: str) -> str:
    if info["lang"] == "ar":
        return (f"شكرًا على هذه التوضيحات. تم إرسال ملخص إلى طبيب في المنصة "
                f"(الشدة {info['severity']}/10، العمر {info['age']}). {URGENCY_AR[urgency]}")
    days = info["duration_days"]
    since = "depuis moins d'un jour" if days == 0 else f"depuis {days} jour(s)"
    return (f"Merci pour ces précisions. J'ai transmis un résumé à un médecin de la plateforme "
            f"(intensité {info['severity']}/10, {since}, âge {info['age']}). {URGENCY_MESSAGES[urgency]}")


def too_many(lang: str) -> str:
    return ("Vous avez déjà envoyé plusieurs demandes récemment. Un médecin les traite : "
            "consultez « Mes consultations »." if lang == "fr" else
            "لقد أرسلت عدة طلبات مؤخرًا. يعالجها طبيب حاليًا: راجع «Mes consultations».")


def failed(lang: str) -> str:
    return ("Je n'ai pas pu transmettre votre demande à un médecin. Utilisez l'onglet « Symptômes » pour l'envoyer."
            if lang == "fr" else
            "لم أتمكن من إرسال طلبك إلى طبيب. استعمل تبويب «Symptômes» (الأعراض) لإرساله.")