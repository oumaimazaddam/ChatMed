import re
import unicodedata

from app import alerts

# Couche ML optionnelle (app/emergency_detector.py). Si absente, seules les règles sont utilisées.
try:
    from app.emergency_detector import check_emergency as _ml_check
except Exception:  # module absent ou modèle non entraîné
    _ml_check = None

ML_ONLY_THRESHOLD = 0.60  # le ML seul déclenche une urgence uniquement s'il est très sûr


def norm(text: str) -> str:
    """Minuscules, sans accents, apostrophes normalisées."""
    text = text.lower().replace("’", "'")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


SELF_HARM = [norm(x) for x in [
    "suicide", "me suicider", "veux mourir", "envie de mourir", "me faire du mal",
    "mettre fin a mes jours", "انتحار", "أريد أن أموت",
]]

EMERGENCY = [norm(x) for x in [
    "douleur thoracique", "douleur dans la poitrine", "mal a la poitrine", "oppression thoracique",
    "difficulte a respirer", "du mal a respirer", "arrive pas a respirer", "ne peux plus respirer",
    "perte de connaissance", "evanoui", "convulsion", "paralysie", "visage qui tombe",
    "difficulte a parler", "saignement abondant", "hemorragie", "vomis du sang", "crache du sang",
    "overdose", "surdose", "avale trop", "empoisonn", "gonflement de la gorge", "gonflement du visage",
    "reaction allergique grave", "chest pain", "can't breathe", "cannot breathe", "heart attack",
    "ألم في الصدر", "صعوبة في التنفس", "ضيق في التنفس", "نزيف حاد", "فقدان الوعي",
]]

# Formulations que la liste ci-dessus rate (ex. « je n'arrive plus à respirer »)
EMERGENCY_REGEX = [re.compile(p) for p in [
    r"arrive (plus|pas|jamais) a respirer",
    r"\b(suffoque|etouffe|etouffement)\b",
    r"serrement .{0,15}poitrine",
    r"poitrine .{0,20}(serre|ecrase|brule)",
    r"(douleur|mal) .{0,30}(bras gauche|machoire)",
    r"(ne|n') ?(repond|reagit) (plus|pas)",
    r"(visage|bouche) .{0,15}(tombe|affaisse|travers)",
    r"\bparle (mal|plus)\b",
    r"vomi\w* (du )?sang",
    r"(saigne|sang).{0,20}(abondan|beaucoup|arrete pas)",
    r"(tout|toute) bleu|levres bleues",
    r"pire douleur",
]]

DIAGNOSIS = [norm(x) for x in [
    "diagnostic", "quelle maladie", "est-ce que j'ai", "est ce que j'ai", "ai-je un", "suis-je malade",
    "que dois-je prendre", "quel medicament dois-je", "quelle dose pour moi", "combien dois-je en prendre",
    "arreter mon traitement", "can you diagnose",
    # demandes de traitement personnel (français)
    "donne-moi un medicament", "donne moi un medicament", "donnez-moi un medicament",
    "que prendre pour", "quoi prendre pour", "quel traitement pour",
    # demandes de traitement personnel (arabe et dialecte tunisien)
    "اعطيني دواء", "اعطني دواء", "ماذا اخذ", "شنو ناخذ", "شنوة ناخذ", "ما الدواء المناسب",
    "اريد دواء", "نحب دواء", "ما هو مرضي", "شنوة مرضي",
]]

NOT_FOUND = ("Je n'ai pas trouvé cette information dans les notices. "
             "Demandez à votre pharmacien ou à votre médecin.")

MESSAGES = {
    "emergency": ("⚠️ Ce que vous décrivez peut être une urgence. Appelez immédiatement le 190 (SAMU) "
                  "ou allez aux urgences les plus proches. Un médecin de la plateforme a été alerté, "
                  "mais ne l'attendez pas."),
    "self_harm": ("Je suis désolé que vous traversiez cela, vous n'êtes pas seul(e). Si vous pensez à vous "
                  "faire du mal, appelez le 190 maintenant ou allez aux urgences, et parlez à une personne "
                  "de confiance. Un médecin de la plateforme a été alerté."),
    "diagnosis": ("Je ne peux pas poser de diagnostic ni conseiller un traitement personnel. "
                  "Utilisez l'onglet « Symptômes » : un médecin recevra un résumé et vous répondra."),
}

URGENCY_MESSAGES = {
    "urgent": "⚠️ Cas marqué URGENT. Appelez le 190 ou allez aux urgences sans attendre la réponse.",
    "within_24h": "Votre demande a été transmise. Un médecin devrait la traiter sous 24 h.",
    "routine": "Votre demande a été transmise à un médecin. Vous verrez sa réponse dans « Mes consultations ».",
}


# Plainte personnelle (« j'ai mal... ») ET demande de solution (« que faire ? ») = demande de soin : pas pour le RAG
COMPLAINT = [norm(x) for x in [
    "j'ai mal", "j'ai un probleme", "j'ai des douleurs", "j'ai de la fievre", "je souffre", "je me sens mal",
    "mal au ventre", "mal a l'estomac", "mal a la tete", "mal de tete", "je tousse", "j'ai la diarrhee",
    "i have a problem", "i have pain", "i have a headache", "my stomach", "i feel sick", "i am sick", "i suffer",
    "عندي مشكل", "عندي وجع", "عندي الم", "عندي حرقة", "نحس", "اعاني", "اشعر", "تعبان", "كرشي", "معدتي", "بطني",
]]
SOLUTION = [norm(x) for x in [
    "solution", "remede", "que faire", "quoi faire", "comment soigner", "comment guerir", "comment traiter",
    "traitement", "soulager", "remedy", "what should i do", "how to treat", "how can i treat", "cure", "relieve",
    "الحل", "شنو نعمل", "شنوة نعمل", "شنو ندير", "كيفاش نعالج", "كيف اعالج", "علاج", "دواء", "ماذا افعل",
]]

# ----- Versions arabes des messages de sécurité -----
NOT_FOUND_AR = "لم أجد هذه المعلومة في النشرات الطبية. اسأل الصيدلي أو الطبيب."
MESSAGES_AR = {
    "emergency": ("⚠️ ما تصفه قد يكون حالة طارئة. اتصل فورًا بالرقم 190 (الإسعاف) أو توجه إلى أقرب مستعجلات. "
                  "تم تنبيه طبيب في المنصة، لكن لا تنتظره."),
    "self_harm": ("أنا آسف لأنك تمر بهذا، لست وحدك. إذا كنت تفكر في إيذاء نفسك، اتصل بالرقم 190 الآن "
                  "أو توجه إلى المستعجلات، وتحدث مع شخص تثق به. تم تنبيه طبيب في المنصة."),
    "diagnosis": ("لا أستطيع تشخيص الحالة أو اقتراح علاج شخصي. استخدم تبويب «Symptômes» (الأعراض) "
                  "وسيصلك رد من طبيب بعد اطلاعه على ملخصك."),
}

# Variantes SANS la phrase « un médecin a été alerté » : utilisées si l'enregistrement de l'alerte échoue,
# pour ne jamais promettre une alerte qui n'existe pas.
MESSAGES_NO_ALERT = {k: v.split(" Un médecin")[0] for k, v in MESSAGES.items()}
MESSAGES_AR_NO_ALERT = {k: v.split(" تم تنبيه")[0] for k, v in MESSAGES_AR.items()}

# Toutes les réponses fixes possibles (utile pour classer les réponses dans le tableau de bord admin)
REPLY_SETS = {
    "not_found": {NOT_FOUND, NOT_FOUND_AR},
    "diagnosis": {MESSAGES["diagnosis"], MESSAGES_AR["diagnosis"]},
    "emergency": {MESSAGES["emergency"], MESSAGES["self_harm"], MESSAGES_AR["emergency"], MESSAGES_AR["self_harm"],
                  MESSAGES_NO_ALERT["emergency"], MESSAGES_NO_ALERT["self_harm"],
                  MESSAGES_AR_NO_ALERT["emergency"], MESSAGES_AR_NO_ALERT["self_harm"]},
}


def reply_for(kind: str, question: str, alerted: bool = True) -> str:
    """Message de sécurité dans la langue de la question (arabe ou français).
    alerted=False : variante sans promesse d'alerte (si l'enregistrement a échoué)."""
    arabic = any("\u0600" <= ch <= "\u06ff" for ch in question)
    if kind == "not_found":
        return NOT_FOUND_AR if arabic else NOT_FOUND
    if arabic:
        return (MESSAGES_AR if alerted else MESSAGES_AR_NO_ALERT)[kind]
    return (MESSAGES if alerted else MESSAGES_NO_ALERT)[kind]


def classify_message(text: str, use_ml: bool = True) -> str:
    """Retourne : self_harm | emergency | diagnosis | ok."""
    t = norm(text)
    if any(p in t for p in SELF_HARM):
        return "self_harm"
    if any(p in t for p in EMERGENCY) or any(rx.search(t) for rx in EMERGENCY_REGEX):
        return "emergency"
    if use_ml and _ml_check is not None:
        try:
            if _ml_check(text)["probability"] >= ML_ONLY_THRESHOLD:
                return "emergency"
        except Exception:
            pass  # le ML ne doit jamais bloquer le chat
    if any(p in t for p in DIAGNOSIS):
        return "diagnosis"
    if any(p in t for p in COMPLAINT) and any(p in t for p in SOLUTION):
        return "diagnosis"
    return "ok"

def is_complaint(text: str) -> bool:
    """Vrai si le message est une plainte personnelle (« j'ai mal », « عندي الم »...)."""
    t = norm(text)
    return any(p in t for p in COMPLAINT)


def is_explicit_diagnosis_request(text: str) -> bool:
    """Vrai si le patient demande un diagnostic ou un médicament (« quelle maladie ? »...)."""
    t = norm(text)
    return any(p in t for p in DIAGNOSIS)


def check_and_alert(user_id, text: str, source: str = "chat"):
    kind = classify_message(text)
    if kind == "ok":
        return kind, None
    if kind in ("emergency", "self_harm"):
        alerted = alerts.save_alert(user_id, text, kind, source)
        if not alerted:
            log.warning("Alerte %s NON enregistrée pour user_id=%s", kind, user_id)
        return kind, reply_for(kind, text, alerted=alerted)
    return kind, reply_for(kind, text)


def triage_symptoms(text: str, severity: int, duration_days: int, age: int):
    """Retourne (urgence, raisons). Règles de départ, à faire valider par un médecin."""
    if classify_message(text) in ("emergency", "self_harm"):
        return "urgent", ["signe d'alerte dans la description"]
    if severity >= 8:
        return "urgent", ["intensité très élevée"]
    reasons = []
    if severity >= 5:
        reasons.append("intensité modérée à forte")
    if duration_days >= 7:
        reasons.append("symptômes persistants (7 jours ou plus)")
    if age < 3 or age >= 75:
        reasons.append("âge à risque")
    return ("within_24h", reasons) if reasons else ("routine", [])