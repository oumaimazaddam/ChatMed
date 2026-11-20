"""
app/alerts.py - Enregistrement et lecture des alertes d'urgence (PostgreSQL)

Variable d'environnement :
    DATABASE_URL=postgresql://medassist:MOT_DE_PASSE@localhost:5432/medassist
"""
import logging
import os

import psycopg2
import psycopg2.extras

log = logging.getLogger("medassist.alerts")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://medassist:password@localhost:5432/medassist")

# CHAQUE instruction SQL est un élément séparé de la liste (psycopg2 = 1 instruction par execute)
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS emergency_alerts (
        id          SERIAL PRIMARY KEY,
        user_id     INTEGER,
        message     TEXT NOT NULL,
        probability REAL,
        reason      TEXT,
        status      VARCHAR(20) DEFAULT 'new',
        kind        VARCHAR(20),
        source      VARCHAR(20) DEFAULT 'chat',
        handled_by  INTEGER,
        handled_at  TIMESTAMP,
        created_at  TIMESTAMP DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_alerts_status ON emergency_alerts (status, created_at DESC)",
]

_schema_ready = False


def _connect():
    return psycopg2.connect(DATABASE_URL)


def ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _connect() as conn, conn.cursor() as cur:
        for stmt in SCHEMA_STATEMENTS:
            cur.execute(stmt)
    _schema_ready = True


def save_alert(user_id, message: str, kind: str, source: str = "chat", probability=None) -> bool:
    """Enregistre une alerte. Retourne True seulement si elle est bien écrite en base."""
    try:
        ensure_schema()
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO emergency_alerts (user_id, message, kind, source, reason, probability) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, message, kind, source, kind, probability),
            )
        return True
    except Exception:
        log.exception("Échec de l'enregistrement de l'alerte d'urgence (user_id=%s, kind=%s)", user_id, kind)
        return False