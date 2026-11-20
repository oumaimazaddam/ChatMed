import csv
import io
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from datetime import time as dtime
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app import intake, rag, triage
from app.config import CORS_ORIGINS, OLLAMA_URL
from app.db import (AuditLog, Consultation, Message, PatientRecord, SessionLocal, User,
                    engine, get_db, init_db)
from app.security import (audit, check_password, decrypt, encrypt, hash_password, make_token,
                          rate_limit, require_role)

init_db()
app = FastAPI(title="MedAssist")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# CORS : autorise uniquement le front Angular (ng serve) à appeler l'API.
# Ajouté en dernier = traité en premier, donc il répond aussi aux requêtes "preflight" (OPTIONS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,  # on utilise un jeton Bearer, pas de cookies
)


# ---------- Schémas ----------
class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200)
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=72)
    consent: bool


class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=72)


class RecordIn(BaseModel):
    allergies: str = Field("", max_length=1000)
    treatments: str = Field("", max_length=1000)


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class SymptomsIn(BaseModel):
    symptoms: str = Field(min_length=5, max_length=1500)
    duration_days: int = Field(ge=0, le=3650)
    severity: int = Field(ge=1, le=10)
    age: int = Field(ge=0, le=120)
    input_mode: str = Field("text", pattern="^(text|voice)$")  # text = écrit, voice = dictée vocale


class ReplyIn(BaseModel):
    reply: str = Field(min_length=1, max_length=3000)

import logging

log = logging.getLogger("medassist")

# ---------- Santé du système ----------
@app.get("/api/health")
def health():
    status = {"database": False, "ollama": False, "chunks": 0}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status["database"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        status["ollama"] = httpx.get(f"{OLLAMA_URL}/", timeout=3).status_code == 200
    except httpx.HTTPError:
        pass
    try:
        status["chunks"] = rag.col.count()
    except Exception:  # noqa: BLE001
        pass
    return status


# ---------- Authentification ----------
@app.post("/api/auth/register")
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"reg:{request.client.host}", 5, 3600)
    if not data.consent:
        raise HTTPException(400, "Le consentement est obligatoire")
    email = data.email.lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Email déjà utilisé")
    user = User(email=email, full_name=data.full_name, password_hash=hash_password(data.password),
                role="patient")
    db.add(user)
    db.commit()
    db.add(PatientRecord(user_id=user.id, consent=True, consent_at=datetime.now(timezone.utc)))
    db.commit()
    audit(db, user.id, "register")
    return {"token": make_token(user), "role": user.role, "name": user.full_name}


@app.post("/api/auth/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(f"login:{request.client.host}", 8, 60)
    user = db.query(User).filter_by(email=data.email.lower()).first()
    if not user or not check_password(data.password, user.password_hash):
        audit(db, user.id if user else None, "login_failed", f"ip:{request.client.host}")
        raise HTTPException(401, "Identifiants incorrects")
    audit(db, user.id, "login")
    return {"token": make_token(user), "role": user.role, "name": user.full_name}


# ---------- Dossier patient ----------
@app.get("/api/me/record")
def get_record(user: User = Depends(require_role("patient")), db: Session = Depends(get_db)):
    r = db.get(PatientRecord, user.id)
    return {"allergies": decrypt(r.allergies_enc), "treatments": decrypt(r.treatments_enc)}


@app.put("/api/me/record")
def put_record(data: RecordIn, user: User = Depends(require_role("patient")),
               db: Session = Depends(get_db)):
    r = db.get(PatientRecord, user.id)
    r.allergies_enc = encrypt(data.allergies)
    r.treatments_enc = encrypt(data.treatments)
    db.commit()
    audit(db, user.id, "update_record")
    return {"ok": True}


# ---------- Chat RAG (streaming) ----------
def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def save_alert(user_id: int, message: str, kind: str = "emergency") -> bool:
    try:
        with SessionLocal() as db:  # ou ta manière habituelle d'ouvrir la session
            db.execute(
                text("INSERT INTO emergency_alerts (user_id, message, kind, status, source, created_at) "
                     "VALUES (:uid, :msg, :kind, 'pending', 'chat', NOW())"),
                {"uid": user_id, "msg": message, "kind": kind},
            )
            db.commit()
        return True
    except Exception:
        log.exception("Échec de l'enregistrement de l'alerte (user_id=%s, kind=%s)", user_id, kind)
        return False


def save_chat(uid: int, question: str, answer: str, sources: list):
    with SessionLocal() as db:
        db.add_all([
            Message(patient_id=uid, role="user", content_enc=encrypt(question)),
            Message(patient_id=uid, role="assistant", content_enc=encrypt(answer),
                    sources=json.dumps(sources, ensure_ascii=False)),
        ])
        db.commit()


@app.post("/api/chat")
async def chat(data: ChatIn, user: User = Depends(require_role("patient"))):
    rate_limit(f"chat:{user.id}", 10, 60)
    q, uid = data.question.strip(), user.id

    async def alert_and_reply(text: str, kind: str, lang_hint: str) -> str:
        alerted = True
        try:
            await run_in_threadpool(save_alert, uid, text, kind)
        except Exception:  # noqa: BLE001
            alerted = False
            log.exception("Échec de l'enregistrement de l'alerte d'urgence")
        return triage.reply_for(kind, lang_hint, alerted=alerted)

    async def safe_save_chat(reply: str):
        try:
            await run_in_threadpool(save_chat, uid, q, reply, [])
        except Exception:  # noqa: BLE001
            log.exception("Échec de la sauvegarde du chat")

    async def finish_intake(info: dict) -> str:
        try:
            rate_limit(f"consult:{uid}", 5, 3600)
            payload = SymptomsIn(symptoms=info["symptoms"], duration_days=info["duration_days"],
                                 severity=info["severity"], age=info["age"], input_mode="text")
            result = await run_in_threadpool(make_consultation_from_chat, uid, payload)
            return intake.final_reply(info, result["urgency"])
        except HTTPException:
            return intake.too_many(info["lang"])
        except Exception:  # noqa: BLE001
            log.exception("Échec de la création de la consultation depuis le chat")
            return intake.failed(info["lang"])

    async def gen():
        try:
            kind = await run_in_threadpool(triage.classify_message, q)

            # 1) Urgence ou idées suicidaires : toujours prioritaire, même pendant le dialogue guidé
            if kind in ("emergency", "self_harm"):
                intake.cancel(uid)
                reply = await alert_and_reply(q, kind, q)
                yield sse("token", {"t": reply})
                await safe_save_chat(reply)
                yield sse("done", {})
                return

            # 2) Dialogue guidé en cours : le message est la réponse à la question précédente
            if intake.is_active(uid):
                status, reply, info = intake.answer(uid, q)
                if status == "red_flag":
                    reply = await alert_and_reply(info["symptoms"], "emergency", info["describe"])
                elif status == "done":
                    reply = await finish_intake(info)
                yield sse("token", {"t": reply})
                await safe_save_chat(reply)
                yield sse("done", {})
                return

            # 3) Le patient décrit un symptôme : on démarre le dialogue guidé
            if triage.is_complaint(q) and not triage.is_explicit_diagnosis_request(q):
                reply = intake.start(uid, q)
                yield sse("token", {"t": reply})
                await safe_save_chat(reply)
                yield sse("done", {})
                return

            # 4) Demande explicite de diagnostic ou de médicament : refus poli
            if kind == "diagnosis":
                reply = triage.reply_for("diagnosis", q)
                await safe_save_chat(reply)
                yield sse("token", {"t": reply})
                yield sse("done", {})
                return

            # 5) Question sur un médicament : RAG
            chunks = await run_in_threadpool(rag.retrieve, q)
            if not rag.is_confident(chunks):
                reply = triage.reply_for("not_found", q)
                await run_in_threadpool(save_chat, uid, q, reply, [])
                yield sse("token", {"t": reply})
                yield sse("done", {})
                return

            messages = rag.build_messages(q, chunks)
            answer = ""
            try:
                async for tok in rag.stream_answer(messages):
                    answer += tok
                    yield sse("token", {"t": tok})
            except rag.LanguageDrift:
                yield sse("reset", {})
                answer = await rag.answer_once(messages, rag.detect_language(q))
                yield sse("token", {"t": answer})
            sources = [{"drug": d, "ref": r} for d, r in sorted({(c["drug"], c["ref"]) for c in chunks})]
            yield sse("sources", sources)
            await run_in_threadpool(save_chat, uid, q, answer, sources)
            yield sse("done", {})
        except (httpx.HTTPError, OSError):
            yield sse("error", {"t": "Le service d'IA est indisponible. Réessayez plus tard "
                                     "ou envoyez vos symptômes à un médecin."})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/chat/history")
def history(user: User = Depends(require_role("patient")), db: Session = Depends(get_db)):
    rows = db.query(Message).filter_by(patient_id=user.id).order_by(Message.id.desc()).limit(20).all()
    return [{"role": m.role, "text": decrypt(m.content_enc), "sources": json.loads(m.sources)}
            for m in reversed(rows)]


# ---------- Consultations (patient) ----------
def make_consultation(db: Session, user: User, data: SymptomsIn) -> dict:
    urgency, reasons = triage.triage_symptoms(data.symptoms, data.severity, data.duration_days, data.age)
    rec = db.get(PatientRecord, user.id)
    try:
        short = rag.reformulate(data.symptoms)
    except httpx.HTTPError:
        short = "(reformulation indisponible)"
    why = "; ".join(reasons) or "aucun signe d'alerte détecté"
    mode_label = ("dictée vocale transcrite automatiquement (peut contenir des erreurs de transcription)"
                  if data.input_mode == "voice" else "texte écrit par le patient")
    summary = (
        f"Texte du patient : {data.symptoms}\n"
        f"Mode de saisie : {mode_label}\n"
        f"Reformulation IA (à vérifier) : {short}\n"
        f"Durée : {data.duration_days} jour(s) | Intensité : {data.severity}/10 | Âge : {data.age}\n"
        f"Allergies déclarées : {decrypt(rec.allergies_enc) or 'non renseigné'}\n"
        f"Traitements déclarés : {decrypt(rec.treatments_enc) or 'non renseigné'}\n"
        f"Urgence (règles fixes) : {urgency} ({why})"
    )
    c = Consultation(patient_id=user.id, urgency=urgency, summary_enc=encrypt(summary))
    db.add(c)
    db.commit()
    audit(db, user.id, "create_consultation", f"consultation:{c.id}")
    return {"id": c.id, "urgency": urgency, "message": triage.URGENCY_MESSAGES[urgency]}


def make_consultation_from_chat(uid: int, data: SymptomsIn) -> dict:
    with SessionLocal() as db:
        return make_consultation(db, db.get(User, uid), data)


@app.post("/api/consultations")
def create_consultation(data: SymptomsIn, user: User = Depends(require_role("patient")),
                        db: Session = Depends(get_db)):
    rate_limit(f"consult:{user.id}", 5, 3600)
    return make_consultation(db, user, data)


@app.get("/api/consultations/mine")
def my_consultations(user: User = Depends(require_role("patient")), db: Session = Depends(get_db)):
    rows = (db.query(Consultation).filter_by(patient_id=user.id)
            .order_by(Consultation.created_at.desc()).all())
    return [{"id": c.id, "urgency": c.urgency, "status": c.status,
             "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
             "reply": decrypt(c.doctor_reply_enc)} for c in rows]


# ---------- Médecin ----------
def is_chat_alert(summary: str) -> bool:
    """Vrai si la consultation vient de la détection d'urgence du chat."""
    return summary.startswith("ALERTE (chat")


@app.get("/api/doctor/consultations")
def doctor_list(user: User = Depends(require_role("doctor")), db: Session = Depends(get_db)):
    order = {"urgent": 0, "within_24h": 1, "routine": 2}
    rows = db.query(Consultation).filter_by(status="pending").all()
    out = []
    for c in rows:
        patient = db.get(User, c.patient_id)
        summary = decrypt(c.summary_enc)
        audit(db, user.id, "doctor_view_consultation", f"consultation:{c.id}")
        out.append({"id": c.id, "urgency": c.urgency, "patient": patient.full_name,
                    "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
                    "summary": summary,
                    "is_alert": is_chat_alert(summary),
                    "alert_type": "self_harm" if "idées suicidaires" in summary else
                                  ("emergency" if is_chat_alert(summary) else None)})
    # alertes du chat d'abord, puis par urgence, puis les plus anciennes
    out.sort(key=lambda x: (not x["is_alert"], order.get(x["urgency"], 3), x["created_at"]))
    return out


@app.post("/api/doctor/consultations/{cid}/reply")
def doctor_reply(cid: int, data: ReplyIn, user: User = Depends(require_role("doctor")),
                 db: Session = Depends(get_db)):
    c = db.get(Consultation, cid)
    if not c:
        raise HTTPException(404, "Consultation introuvable")
    c.doctor_reply_enc = encrypt(data.reply)
    c.status = "answered"
    c.doctor_id = user.id
    c.answered_at = datetime.now(timezone.utc)
    db.commit()
    audit(db, user.id, "doctor_reply", f"consultation:{cid}")
    return {"ok": True}


# ---------- Admin ----------
# Actions de routine : toujours enregistrées en base, mais masquées dans la vue de l'admin
ROUTINE_ACTIONS = ("login", "register", "doctor_view_dashboard", "doctor_view_history")


def audit_query(db: Session, action: str, search: str):
    q = db.query(AuditLog).filter(AuditLog.action.not_in(ROUTINE_ACTIONS))
    if action:
        q = q.filter(AuditLog.action == action)
    if search.strip():
        like = f"%{search.strip()}%"
        ids = [u.id for u in db.query(User).filter(or_(User.full_name.ilike(like), User.email.ilike(like))).all()]
        q = q.filter(AuditLog.user_id.in_(ids)) if ids else q.filter(AuditLog.id < 0)
    return q


def users_by_id(db: Session, rows) -> dict:
    ids = {r.user_id for r in rows if r.user_id}
    if not ids:
        return {}
    return {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()}


@app.get("/api/admin/audit")
def audit_log(action: str = "", search: str = "", limit: int = 50, offset: int = 0,
              user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    q = audit_query(db, action, search)
    total = q.count()
    rows = (q.order_by(AuditLog.id.desc()).offset(max(offset, 0))
            .limit(min(max(limit, 1), 200)).all())
    users = users_by_id(db, rows)
    actions = [a for (a,) in db.query(AuditLog.action).filter(AuditLog.action.not_in(ROUTINE_ACTIONS))
               .distinct().order_by(AuditLog.action).all()]
    return {
        "total": total,
        "actions": actions,
        "items": [{
            "id": a.id,
            "time": fmt_date(a.created_at),
            "user_id": a.user_id,
            "user": users[a.user_id].full_name if a.user_id in users else "—",
            "role": users[a.user_id].role if a.user_id in users else "",
            "action": a.action,
            "target": a.target,
        } for a in rows],
    }


def safe_cell(value) -> str:
    """Évite l'injection de formules quand le CSV est ouvert dans Excel ou LibreOffice."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


@app.get("/api/admin/audit/export")
def audit_export(action: str = "", search: str = "",
                 user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = audit_query(db, action, search).order_by(AuditLog.id.desc()).limit(5000).all()
    users = users_by_id(db, rows)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "utilisateur_id", "nom", "role", "action", "cible"])
    for a in rows:
        u = users.get(a.user_id)
        writer.writerow([fmt_date(a.created_at), a.user_id or "", safe_cell(u.full_name if u else ""),
                         u.role if u else "", a.action, safe_cell(a.target)])
    audit(db, user.id, "admin_export_audit", f"{len(rows)} lignes")
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="audit.csv"'})


# ---------- Tableaux de bord ----------
def aware(dt: datetime) -> datetime:
    """Rend une date comparable (PostgreSQL renvoie des dates avec fuseau, SQLite sans)."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def minutes_between(start: datetime, end: datetime) -> float:
    return (aware(end) - aware(start)).total_seconds() / 60


def fmt_date(dt: datetime) -> str:
    return aware(dt).strftime("%Y-%m-%d %H:%M")


@app.get("/api/patient/dashboard")
def patient_dashboard(user: User = Depends(require_role("patient")), db: Session = Depends(get_db)):
    rows = (db.query(Consultation).filter_by(patient_id=user.id)
            .order_by(Consultation.created_at.desc()).all())
    rec = db.get(PatientRecord, user.id)
    questions = (db.query(func.count(Message.id))
                 .filter(Message.patient_id == user.id, Message.role == "user").scalar() or 0)
    return {
        "name": user.full_name,
        "total": len(rows),
        "pending": sum(1 for c in rows if c.status == "pending"),
        "answered": sum(1 for c in rows if c.status == "answered"),
        "urgent_pending": sum(1 for c in rows if c.status == "pending" and c.urgency == "urgent"),
        "questions": questions,
        "record": {"allergies": bool(decrypt(rec.allergies_enc)),
                   "treatments": bool(decrypt(rec.treatments_enc))},
        "recent": [{"id": c.id, "urgency": c.urgency, "status": c.status,
                    "created_at": fmt_date(c.created_at),
                    "reply": decrypt(c.doctor_reply_enc)[:160]} for c in rows[:3]],
    }


@app.get("/api/doctor/dashboard")
def doctor_dashboard(user: User = Depends(require_role("doctor")), db: Session = Depends(get_db)):
    moment = datetime.now(timezone.utc)
    order = {"urgent": 0, "within_24h": 1, "routine": 2}
    pending = db.query(Consultation).filter_by(status="pending").all()
    pending.sort(key=lambda c: (order.get(c.urgency, 3), aware(c.created_at)))
    mine = (db.query(Consultation).filter_by(doctor_id=user.id, status="answered")
            .order_by(Consultation.answered_at.desc()).all())
    times = [minutes_between(c.created_at, c.answered_at) for c in mine if c.answered_at]

    next_cases = []
    for c in pending[:3]:
        patient = db.get(User, c.patient_id)
        next_cases.append({"id": c.id, "urgency": c.urgency, "patient": patient.full_name,
                           "created_at": fmt_date(c.created_at),
                           "is_alert": is_chat_alert(decrypt(c.summary_enc)),
                           "waiting_minutes": round(minutes_between(c.created_at, moment))})
    recent = []
    for c in mine[:5]:
        patient = db.get(User, c.patient_id)
        recent.append({"id": c.id, "patient": patient.full_name, "urgency": c.urgency,
                       "answered_at": fmt_date(c.answered_at),
                       "reply": decrypt(c.doctor_reply_enc)[:140]})
    audit(db, user.id, "doctor_view_dashboard")

    oldest = min(pending, key=lambda c: aware(c.created_at)) if pending else None
    return {
        "pending_total": len(pending),
        "pending_urgent": sum(1 for c in pending if c.urgency == "urgent"),
        "pending_24h": sum(1 for c in pending if c.urgency == "within_24h"),
        "pending_routine": sum(1 for c in pending if c.urgency == "routine"),
        "pending_alerts": sum(1 for c in pending if is_chat_alert(decrypt(c.summary_enc))),
        "answered_total": len(mine),
        "answered_today": sum(1 for c in mine
                              if c.answered_at and aware(c.answered_at).date() == moment.date()),
        "avg_response_minutes": round(sum(times) / len(times)) if times else None,
        "oldest_pending_minutes": round(minutes_between(oldest.created_at, moment)) if oldest else None,
        "next_cases": next_cases,
        "recent": recent,
    }


@app.get("/api/doctor/history")
def doctor_history(user: User = Depends(require_role("doctor")), db: Session = Depends(get_db)):
    rows = (db.query(Consultation).filter_by(doctor_id=user.id, status="answered")
            .order_by(Consultation.answered_at.desc()).limit(50).all())
    out = []
    for c in rows:
        patient = db.get(User, c.patient_id)
        out.append({"id": c.id, "patient": patient.full_name, "urgency": c.urgency,
                    "created_at": fmt_date(c.created_at),
                    "answered_at": fmt_date(c.answered_at) if c.answered_at else "",
                    "summary": decrypt(c.summary_enc), "reply": decrypt(c.doctor_reply_enc)})
    audit(db, user.id, "doctor_view_history", f"{len(rows)} cas")
    return out


class DoctorIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200)
    full_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=72)


# Délais cibles de réponse (en minutes) selon l'urgence
SLA_MINUTES = {"urgent": 30, "within_24h": 24 * 60, "routine": 72 * 60}


@app.get("/api/admin/dashboard")
def admin_dashboard(days: int = 7, user: User = Depends(require_role("admin")),
                    db: Session = Depends(get_db)):
    days = 30 if days >= 30 else 7
    moment = datetime.now(timezone.utc)
    today = moment.date()

    roles = {r: n for r, n in db.query(User.role, func.count(User.id)).group_by(User.role).all()}
    consultations = db.query(Consultation).all()
    statuses = Counter(c.status for c in consultations)
    urgencies = Counter(c.urgency for c in consultations)
    questions = db.query(func.count(Message.id)).filter(Message.role == "user").scalar() or 0
    alerts = db.query(func.count(AuditLog.id)).filter(AuditLog.action == "emergency_alert").scalar() or 0
    failed_logins = (db.query(func.count(AuditLog.id))
                     .filter(AuditLog.action == "login_failed",
                             AuditLog.created_at >= moment - timedelta(hours=24)).scalar() or 0)

    # Activité sur la période choisie
    start = datetime.combine(today - timedelta(days=days - 1), dtime.min, tzinfo=timezone.utc)
    q_times = [t for (t,) in db.query(Message.created_at)
               .filter(Message.role == "user", Message.created_at >= start).all()]
    c_times = [c.created_at for c in consultations if aware(c.created_at) >= start]
    daily = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        daily.append({"date": d.strftime("%d/%m"),
                      "questions": sum(1 for t in q_times if aware(t).date() == d),
                      "consultations": sum(1 for t in c_times if aware(t).date() == d)})

    # Respect des délais (SLA) et cas en retard (sans nom de patient : l'admin n'est pas soignant)
    sla, overdue = {}, []
    for u, target in SLA_MINUTES.items():
        done = [c for c in consultations if c.urgency == u and c.status == "answered" and c.answered_at]
        late = [c for c in consultations if c.urgency == u and c.status == "pending"
                and minutes_between(c.created_at, moment) > target]
        sla[u] = {"target_minutes": target, "answered": len(done),
                  "on_time": sum(1 for c in done if minutes_between(c.created_at, c.answered_at) <= target),
                  "overdue_pending": len(late)}
        overdue += [{"id": c.id, "urgency": u, "target_minutes": target,
                     "waiting_minutes": round(minutes_between(c.created_at, moment))} for c in late]
    overdue.sort(key=lambda x: x["waiting_minutes"] - x["target_minutes"], reverse=True)

    answered = [c for c in consultations if c.status == "answered" and c.answered_at]
    times = [minutes_between(c.created_at, c.answered_at) for c in answered]

    # Qualité de l'IA : on classe les 2000 dernières réponses du chat
    quality = {"answered": 0, "not_found": 0, "diagnosis": 0, "emergency": 0, "other": 0}
    drug_counts = Counter()
    recent_ai = (db.query(Message).filter(Message.role == "assistant")
                 .order_by(Message.id.desc()).limit(2000).all())
    for m in recent_ai:
        sources = json.loads(m.sources or "[]")
        if sources:
            quality["answered"] += 1
            for drug in {s.get("drug") for s in sources if s.get("drug")}:
                drug_counts[drug] += 1
            continue
        reply = decrypt(m.content_enc)
        if reply in triage.REPLY_SETS["not_found"]:
            quality["not_found"] += 1
        elif reply in triage.REPLY_SETS["diagnosis"]:
            quality["diagnosis"] += 1
        elif reply in triage.REPLY_SETS["emergency"]:
            quality["emergency"] += 1
        else:
            quality["other"] += 1
    total_ai = sum(quality.values())
    quality["answered_rate"] = round(100 * quality["answered"] / total_ai) if total_ai else None

    # Charge de travail des médecins
    workload = []
    for d in db.query(User).filter_by(role="doctor").order_by(User.full_name).all():
        mine = [c for c in answered if c.doctor_id == d.id]
        mt = [minutes_between(c.created_at, c.answered_at) for c in mine]
        workload.append({
            "name": d.full_name, "answered_total": len(mine),
            "answered_7d": sum(1 for c in mine if aware(c.answered_at) >= moment - timedelta(days=7)),
            "avg_minutes": round(sum(mt) / len(mt)) if mt else None,
        })

    top = (db.query(AuditLog.action, func.count(AuditLog.id))
           .filter(AuditLog.action.not_in(ROUTINE_ACTIONS)).group_by(AuditLog.action)
           .order_by(func.count(AuditLog.id).desc()).limit(6).all())

    return {
        "period_days": days,
        "patients": roles.get("patient", 0),
        "doctors": roles.get("doctor", 0),
        "admins": roles.get("admin", 0),
        "consultations_total": len(consultations),
        "consultations_pending": statuses.get("pending", 0),
        "consultations_answered": statuses.get("answered", 0),
        "urgency": {"urgent": urgencies.get("urgent", 0), "within_24h": urgencies.get("within_24h", 0),
                    "routine": urgencies.get("routine", 0)},
        "questions_total": questions,
        "emergency_alerts": alerts,
        "failed_logins_24h": failed_logins,
        "avg_response_minutes": round(sum(times) / len(times)) if times else None,
        "sla": sla,
        "overdue_total": len(overdue),
        "overdue_cases": overdue[:5],
        "ai_quality": quality,
        "top_drugs": [{"drug": d, "count": n} for d, n in drug_counts.most_common(6)],
        "doctors_workload": workload,
        "daily": daily,
        "top_actions": [{"action": a, "count": n} for a, n in top],
        "system": health(),
    }


@app.get("/api/admin/users")
def admin_users(user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = db.query(User).order_by(User.id).all()
    last_login = {uid: t for uid, t in db.query(AuditLog.user_id, func.max(AuditLog.created_at))
                  .filter(AuditLog.action == "login").group_by(AuditLog.user_id).all()}
    return [{"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role,
             "created_at": fmt_date(u.created_at),
             "last_login": fmt_date(last_login[u.id]) if u.id in last_login else ""} for u in rows]


@app.post("/api/admin/doctors")
def create_doctor(data: DoctorIn, user: User = Depends(require_role("admin")),
                  db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Email déjà utilisé")
    doctor = User(email=email, full_name=data.full_name, password_hash=hash_password(data.password),
                  role="doctor")
    db.add(doctor)
    db.commit()
    audit(db, user.id, "admin_create_doctor", f"user:{doctor.id}")
    return {"id": doctor.id, "email": doctor.email}


@app.delete("/api/admin/users/{uid}")
def delete_user(uid: int, user: User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    if uid == user.id:
        raise HTTPException(400, "Vous ne pouvez pas supprimer votre propre compte")
    target = db.get(User, uid)
    if not target:
        raise HTTPException(404, "Utilisateur introuvable")
    if target.role == "admin" and db.query(func.count(User.id)).filter(User.role == "admin").scalar() <= 1:
        raise HTTPException(400, "Impossible de supprimer le dernier administrateur")

    role = target.role
    if role == "patient":  # droit à l'effacement : toutes les données du patient sont supprimées
        db.query(Message).filter(Message.patient_id == uid).delete(synchronize_session=False)
        db.query(Consultation).filter(Consultation.patient_id == uid).delete(synchronize_session=False)
        db.query(PatientRecord).filter(PatientRecord.user_id == uid).delete(synchronize_session=False)
    elif role == "doctor":  # les consultations traitées sont conservées, sans médecin associé
        db.query(Consultation).filter(Consultation.doctor_id == uid).update(
            {Consultation.doctor_id: None}, synchronize_session=False)
    db.delete(target)
    db.commit()
    audit(db, user.id, "admin_delete_user", f"user:{uid} ({role})")  # le journal conserve la trace
    return {"ok": True}


# ---------- Interface web (application Angular compilée) ----------
DIST = Path("frontend/dist/frontend/browser").resolve()


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Route inconnue")
    index = DIST / "index.html"
    if not index.is_file():
        raise HTTPException(404, "Interface non compilée : lance « npm run build » dans le dossier frontend/")
    file = (DIST / path).resolve()
    if path and file.is_file() and DIST in file.parents:  
        return FileResponse(file)
    return FileResponse(index)  