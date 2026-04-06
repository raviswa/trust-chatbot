"""
db_postgres.py
─────────────────────────────────────────────────────────────────
PostgreSQL Persistence Layer — drop-in replacement for db_supabase.py

Uses psycopg2 with a thread-safe connection pool.
Identical function signatures to db_supabase.py — to switch, change
one line in db.py: from db_postgres import ...

Configuration via environment variables:
  DATABASE_URL   — Full DSN (takes precedence if set)
                   e.g. postgresql://user:pass@host:5432/dbname
  PG_HOST        — Database host          (default: localhost)
  PG_PORT        — Database port          (default: 5432)
  PG_DB          — Database name          (default: chatbot_db)
  PG_USER        — Database user          (default: chatbot_user)
  PG_PASSWORD    — Database password

Pool sizing:
  PG_POOL_MIN    — Minimum connections    (default: 2)
  PG_POOL_MAX    — Maximum connections    (default: 10)

Schema tables (unchanged from SUPABASE_SCHEMA.sql):
  patients, onboarding_profiles, daily_checkins, sessions, messages,
  risk_assessments, content_engagement, support_networks, crisis_events,
  conversation_metrics, relapse_events, patient_milestones,
  policy_violations, wearable_readings, patient_addictions,
  response_routing, patient_context_vectors
─────────────────────────────────────────────────────────────────
"""

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONNECTION POOL
# ─────────────────────────────────────────────

def _build_dsn() -> str:
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    return (
        f"host={os.getenv('PG_HOST', 'localhost')} "
        f"port={os.getenv('PG_PORT', '5432')} "
        f"dbname={os.getenv('PG_DB', 'chatbot_db')} "
        f"user={os.getenv('PG_USER', 'chatbot_user')} "
        f"password={os.getenv('PG_PASSWORD', '')} "
        f"connect_timeout=10"
    )


_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=int(os.getenv("PG_POOL_MIN", "2")),
            maxconn=int(os.getenv("PG_POOL_MAX", "10")),
            dsn=_build_dsn(),
        )
        # Teach psycopg2 to auto-adapt Python dicts/lists ↔ JSONB
        psycopg2.extras.register_default_jsonb(globally=True)
        logger.info("PostgreSQL connection pool initialised")
    return _pool


@contextmanager
def _conn():
    """Yield a connection from the pool; return it on exit."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def _fetchone(cursor) -> Optional[dict]:
    row = cursor.fetchone()
    return dict(row) if row else None


def _fetchall(cursor) -> List[dict]:
    return [dict(r) for r in cursor.fetchall()]


def _jsonb(value) -> Optional[str]:
    """Serialise a Python value for a JSONB column, None-safe."""
    return json.dumps(value) if value is not None else None


# ─────────────────────────────────────────────
# PATIENT
# ─────────────────────────────────────────────

def ensure_patient(
    patient_code: str,
    display_name: Optional[str] = None,
    programme: Optional[str] = None,
    assigned_to: Optional[str] = None,
) -> Optional[str]:
    """
    Look up a patient by patient_code; create one if absent.
    Returns the patient UUID (patient_id), or None on failure.
    """
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT patient_id FROM patients WHERE patient_code = %s",
                    (patient_code,),
                )
                row = _fetchone(cur)
                if row:
                    return str(row["patient_id"])

                cur.execute(
                    """
                    INSERT INTO patients (patient_code, first_name, created_at, updated_at)
                    VALUES (%s, %s, now(), now())
                    RETURNING patient_id
                    """,
                    (patient_code, display_name),
                )
                row = _fetchone(cur)
                return str(row["patient_id"]) if row else None
    except Exception as exc:
        logger.error(f"ensure_patient failed: {exc}")
        return None


def get_patient(patient_code: str) -> Optional[dict]:
    """Return full patient row by patient_code."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM patients WHERE patient_code = %s",
                    (patient_code,),
                )
                return _fetchone(cur)
    except Exception as exc:
        logger.error(f"get_patient failed: {exc}")
        return None


def get_patient_onboarding(patient_code: str) -> Optional[dict]:
    """Return the most recent onboarding profile row for a patient."""
    try:
        patient = get_patient(patient_code)
        if not patient:
            return None
        patient_id = patient.get("patient_id")

        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT addiction_type, primary_triggers, baseline_mood,
                           support_network, work_status,
                           last_intake_phase, intake_consent_given
                    FROM   onboarding_profiles
                    WHERE  patient_id = %s
                    ORDER  BY created_at DESC
                    LIMIT  1
                    """,
                    (patient_id,),
                )
                row = _fetchone(cur)

        if row:
            return {
                "addiction_type":     row.get("addiction_type") or "",
                "name":               patient.get("first_name") or patient.get("display_name") or "",
                "primary_triggers":   row.get("primary_triggers") or [],
                "baseline_mood":      row.get("baseline_mood") or [],
                "support_network":    row.get("support_network") or {},
                "work_status":        row.get("work_status") or "",
                "last_intake_phase":  row.get("last_intake_phase") or 0,
                "intake_consent_given": bool(row.get("intake_consent_given")),
            }

        # No onboarding row yet — return minimal record so callers don't break
        return {
            "addiction_type":     "",
            "name":               patient.get("first_name") or "",
            "last_intake_phase":  0,
            "intake_consent_given": False,
        }
    except Exception as exc:
        logger.error(f"get_patient_onboarding failed: {exc}")
        return None


def save_intake_progress(
    patient_code: str,
    phase: int,
    completion_pct: int,
) -> None:
    """
    Persist intake phase progress to onboarding_profiles.
    Updates the most recent row; inserts a placeholder row if none exists.
    """
    try:
        patient = get_patient(patient_code)
        if not patient:
            return
        patient_id = patient["patient_id"]

        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT profile_id FROM onboarding_profiles
                    WHERE  patient_id = %s
                    ORDER  BY created_at DESC
                    LIMIT  1
                    """,
                    (patient_id,),
                )
                row = _fetchone(cur)

                if row:
                    cur.execute(
                        """
                        UPDATE onboarding_profiles
                        SET    last_intake_phase    = %s,
                               intake_completion_pct = %s,
                               updated_at           = now()
                        WHERE  profile_id = %s
                        """,
                        (phase, completion_pct, row["profile_id"]),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO onboarding_profiles
                               (patient_id, last_intake_phase, intake_completion_pct)
                        VALUES (%s, %s, %s)
                        """,
                        (patient_id, phase, completion_pct),
                    )
    except Exception as exc:
        logger.error(f"save_intake_progress failed: {exc}")


def get_patient_addictions(patient_code: str) -> List[dict]:
    """
    Return all active addiction records for a patient, primary first.
    Falls back to onboarding_profiles.addiction_type when the
    patient_addictions table has no rows (backward compat).
    """
    try:
        patient = get_patient(patient_code)
        if not patient:
            return []
        patient_id = patient["patient_id"]

        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT addiction_type, is_primary, severity,
                           noted_at, clinical_notes
                    FROM   patient_addictions
                    WHERE  patient_id = %s
                      AND  is_active  = true
                    ORDER  BY is_primary DESC
                    """,
                    (patient_id,),
                )
                rows = _fetchall(cur)

        if rows:
            return rows

        # Fallback: synthesise from onboarding_profiles
        onboarding = get_patient_onboarding(patient_code)
        if onboarding and onboarding.get("addiction_type"):
            return [{
                "addiction_type": onboarding["addiction_type"],
                "is_primary":     True,
                "severity":       "high",
                "noted_at":       None,
                "clinical_notes": "Migrated from onboarding_profiles.addiction_type",
            }]
        return []
    except Exception as exc:
        logger.error(f"get_patient_addictions failed: {exc}")
        return []


def get_response_routing_table() -> List[dict]:
    """Load the full response_routing table (called once at startup)."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT patient_addiction, detected_intent, relationship,
                           severity_override, video_key, requires_escalation
                    FROM   response_routing
                    WHERE  is_active = true
                    """
                )
                return _fetchall(cur)
    except Exception as exc:
        logger.error(f"get_response_routing_table failed: {exc}")
        return []


def get_patient_sessions(patient_code: str) -> List[dict]:
    """Return all sessions for a patient."""
    try:
        patient = get_patient(patient_code)
        if not patient:
            return []
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM sessions WHERE patient_id = %s ORDER BY started_at DESC",
                    (patient["patient_id"],),
                )
                return _fetchall(cur)
    except Exception as exc:
        logger.error(f"get_patient_sessions failed: {exc}")
        return []


def get_patient_full_history(patient_code: str) -> List[dict]:
    """Return full conversation history for a patient (all messages, chronological)."""
    try:
        patient = get_patient(patient_code)
        if not patient:
            return []
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM messages WHERE patient_id = %s ORDER BY created_at ASC",
                    (patient["patient_id"],),
                )
                return _fetchall(cur)
    except Exception as exc:
        logger.error(f"get_patient_full_history failed: {exc}")
        return []


def get_checkin_status(patient_code: str, hours: int = 12) -> dict:
    """Return check-in status for a patient within the last N hours."""
    try:
        checkin = get_latest_daily_checkin(patient_code, within_hours=hours)
        return {
            "has_recent_activity": checkin is not None,
            "topics_covered":      [],
            "continuity_prompt":   None,
        }
    except Exception as exc:
        logger.error(f"get_checkin_status failed: {exc}")
        return {"has_recent_activity": False, "topics_covered": [], "continuity_prompt": None}


# ─────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────

def ensure_session(
    session_id: str,
    patient_id: Optional[str] = None,
    patient_code: Optional[str] = None,
) -> str:
    """Create or return existing session. Returns session_id."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM sessions WHERE session_id = %s::uuid",
                    (session_id,),
                )
                if cur.fetchone():
                    return session_id

                cur.execute(
                    """
                    INSERT INTO sessions (session_id, patient_id, patient_code, started_at, created_at)
                    VALUES (%s::uuid, %s::uuid, %s, now(), now())
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    (session_id, patient_id, patient_code),
                )
        return session_id
    except Exception as exc:
        logger.error(f"ensure_session failed: {exc}")
        return session_id


def get_session(session_id: str) -> dict:
    """Get session by ID."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM sessions WHERE session_id = %s::uuid",
                    (session_id,),
                )
                row = _fetchone(cur)
                return row if row else {"session_id": session_id}
    except Exception as exc:
        logger.error(f"get_session failed: {exc}")
        return {"session_id": session_id}


def update_session(
    session_id: str,
    role: str,
    message: str,
    intent: Optional[str] = None,
    severity: Optional[str] = None,
    show_resources: bool = False,
    patient_id: Optional[str] = None,
    patient_code: Optional[str] = None,
) -> None:
    """Insert a single message row into the messages table."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO messages
                        (session_id, patient_id, role, content, intent, severity, created_at)
                    VALUES
                        (%s::uuid, %s::uuid, %s, %s, %s, %s, now())
                    """,
                    (session_id, patient_id, role, message, intent, severity),
                )
    except Exception as exc:
        logger.error(f"update_session failed: {exc}")


def update_session_meta(session_id: str, key: str, value) -> None:
    """Update a single column on the sessions row."""
    # Only allow known column names to prevent SQL injection
    _ALLOWED_META_KEYS = {
        "last_intent", "message_count", "peak_risk_level", "crisis_detected",
        "ended_at", "session_type", "conversation_summary", "user_satisfaction_score",
        "escalated_to_human", "escalation_reason", "severity_flags",
    }
    if key not in _ALLOWED_META_KEYS:
        logger.warning(f"update_session_meta: unknown key '{key}' — skipped")
        return
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE sessions SET {key} = %s, updated_at = now() WHERE session_id = %s::uuid",
                    (value, session_id),
                )
    except Exception as exc:
        logger.error(f"update_session_meta failed: {exc}")


def clear_session(session_id: str) -> None:
    """Delete all messages and the session row."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM messages WHERE session_id = %s::uuid", (session_id,)
                )
                cur.execute(
                    "DELETE FROM sessions WHERE session_id = %s::uuid", (session_id,)
                )
    except Exception as exc:
        logger.error(f"clear_session failed: {exc}")


def get_session_summary(session_id: str) -> dict:
    """Return summary info and all messages for a session."""
    messages = get_session_history(session_id)
    return {
        "session_id":    session_id,
        "message_count": len(messages),
        "messages":      messages,
    }


def get_session_history(session_id: str) -> List[dict]:
    """Return all messages for a session in chronological order."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM messages WHERE session_id = %s::uuid ORDER BY created_at ASC",
                    (session_id,),
                )
                return _fetchall(cur)
    except Exception as exc:
        logger.error(f"get_session_history failed: {exc}")
        return []


# ─────────────────────────────────────────────
# MESSAGES & PERSISTENCE
# ─────────────────────────────────────────────

def save_message(
    session_id: str,
    role: str,
    message: str,
    intent: Optional[str] = None,
    severity: Optional[str] = None,
    patient_id: Optional[str] = None,
    patient_code: Optional[str] = None,
) -> None:
    """Save a message (alias for update_session)."""
    update_session(
        session_id, role, message, intent, severity,
        patient_id=patient_id, patient_code=patient_code,
    )


# ─────────────────────────────────────────────
# POLICY & AUDIT LOGGING
# ─────────────────────────────────────────────

def log_policy_violation(
    session_id: str,
    violation_type: str,
    details: str,
    user_message: str,
    bot_response: str,
    patient_id: Optional[str] = None,
) -> None:
    """Log a policy violation."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO policy_violations
                        (session_id, patient_id, violation_type, details,
                         user_message, bot_response, detected_at)
                    VALUES
                        (%s::uuid, %s::uuid, %s, %s, %s, %s, now())
                    """,
                    (session_id, patient_id, violation_type, details,
                     user_message, bot_response),
                )
        logger.warning(f"Policy violation logged: {violation_type}")
    except Exception as exc:
        logger.error(f"log_policy_violation failed: {exc}")


def get_policy_violation_summary() -> List[dict]:
    """Return the most recent 100 policy violations."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM policy_violations ORDER BY detected_at DESC LIMIT 100"
                )
                return _fetchall(cur)
    except Exception as exc:
        logger.error(f"get_policy_violation_summary failed: {exc}")
        return []


# ─────────────────────────────────────────────
# CRISIS TRACKING
# ─────────────────────────────────────────────

def log_crisis_event(
    session_id: str,
    severity: str,
    user_message: str,
    bot_response: str,
    intent: str,
    patient_id: Optional[str] = None,
    patient_code: Optional[str] = None,
) -> None:
    """Log a crisis event."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO crisis_events
                        (session_id, patient_id, severity_level, disclosure_text,
                         bot_response_text, crisis_type, detected_at)
                    VALUES
                        (%s::uuid, %s::uuid, %s, %s, %s, %s, now())
                    """,
                    (session_id, patient_id, severity, user_message,
                     bot_response, intent),
                )
        logger.warning(f"Crisis event logged: severity={severity}")
    except Exception as exc:
        logger.error(f"log_crisis_event failed: {exc}")


def get_pending_crisis_events() -> List[dict]:
    """Return unacknowledged crisis events."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM crisis_events WHERE acknowledged = false ORDER BY detected_at DESC"
                )
                return _fetchall(cur)
    except Exception as exc:
        logger.error(f"get_pending_crisis_events failed: {exc}")
        return []


def get_crisis_sessions() -> List[dict]:
    """Return sessions that had a crisis event."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT DISTINCT session_id FROM crisis_events ORDER BY session_id"
                )
                return _fetchall(cur)
    except Exception as exc:
        logger.error(f"get_crisis_sessions failed: {exc}")
        return []


# ─────────────────────────────────────────────
# ADMIN & ANALYTICS
# ─────────────────────────────────────────────

def get_all_sessions() -> List[dict]:
    """Return all sessions, most recent first."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM sessions ORDER BY started_at DESC")
                return _fetchall(cur)
    except Exception as exc:
        logger.error(f"get_all_sessions failed: {exc}")
        return []


def get_conversation_stats(session_id: str) -> dict:
    """Return message counts for a session."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*)                                       AS total_messages,
                        COUNT(*) FILTER (WHERE role = 'user')         AS user_messages,
                        COUNT(*) FILTER (WHERE role = 'assistant')    AS assistant_messages
                    FROM messages
                    WHERE session_id = %s::uuid
                    """,
                    (session_id,),
                )
                row = _fetchone(cur)
                return row if row else {
                    "total_messages": 0, "user_messages": 0, "assistant_messages": 0
                }
    except Exception as exc:
        logger.error(f"get_conversation_stats failed: {exc}")
        return {"total_messages": 0, "user_messages": 0, "assistant_messages": 0}


def get_top_intents(limit: int = 10) -> List[dict]:
    """Return the most frequent intents across all messages."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT intent, COUNT(*) AS count
                    FROM   messages
                    WHERE  intent IS NOT NULL
                    GROUP  BY intent
                    ORDER  BY count DESC
                    LIMIT  %s
                    """,
                    (limit,),
                )
                return _fetchall(cur)
    except Exception as exc:
        logger.error(f"get_top_intents failed: {exc}")
        return []


def get_watched_video_ids(patient_id: str) -> set:
    """
    Return the set of video content_ids already shown to this patient,
    used by the video recommendation engine to avoid repeats.
    """
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content_id
                    FROM   content_engagement
                    WHERE  patient_id    = %s::uuid
                      AND  content_type  = 'video'
                      AND  content_id   IS NOT NULL
                    """,
                    (patient_id,),
                )
                return {row[0] for row in cur.fetchall()}
    except Exception as exc:
        logger.error(f"get_watched_video_ids failed: {exc}")
        return set()


def save_patient_score(
    session_id: str,
    patient_code: Optional[str],
    score_group: str,
    score: int,
    intent: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> None:
    """Save a patient score record."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scores
                        (session_id, patient_id, patient_code, score_group, score, intent, created_at)
                    VALUES
                        (%s::uuid, %s::uuid, %s, %s, %s, %s, now())
                    """,
                    (session_id, patient_id, patient_code, score_group, score, intent),
                )
        logger.info(f"Score saved: {score_group}={score}")
    except Exception as exc:
        logger.error(f"save_patient_score failed: {exc}")


def build_checkin_greeting(patient_code: str) -> Optional[dict]:
    """Build check-in greeting based on recent history (stub — extended by patient_context)."""
    return None


def get_latest_daily_checkin(
    patient_code: str,
    within_hours: int = 24,
) -> Optional[dict]:
    """Return the most recent daily check-in within the given hour window."""
    try:
        patient = get_patient(patient_code)
        if not patient:
            return None
        cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)

        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM   daily_checkins
                    WHERE  patient_id  = %s::uuid
                      AND  created_at >= %s
                    ORDER  BY created_at DESC
                    LIMIT  1
                    """,
                    (patient["patient_id"], cutoff),
                )
                return _fetchone(cur)
    except Exception as exc:
        logger.error(f"get_latest_daily_checkin failed: {exc}")
        return None


def get_latest_wearable_reading(
    patient_code: str,
    within_hours: int = 48,
) -> Optional[dict]:
    """
    Return the most recent wearable reading within the given hour window.
    Maps schema column names to the field names expected by PatientContextSynthesis.
    """
    try:
        patient = get_patient(patient_code)
        if not patient:
            return None
        cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)

        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM   wearable_readings
                    WHERE  patient_id  = %s::uuid
                      AND  created_at >= %s
                    ORDER  BY created_at DESC
                    LIMIT  1
                    """,
                    (patient["patient_id"], cutoff),
                )
                row = _fetchone(cur)

        if not row:
            return None

        return {
            "heart_rate":            row.get("hr_bpm"),
            "hrv":                   row.get("hrv_ms"),
            "sleep_hours":           row.get("sleep_hours"),
            "steps_today":           row.get("steps_today"),
            "stress_score":          row.get("physiological_stress_score"),
            "spo2":                  row.get("spo2_pct"),
            "personal_anomaly_flag": row.get("personal_anomaly_flag", False),
            "anomaly_detail":        row.get("personal_anomaly_detail"),
            "wearable_timestamp":    row.get("created_at"),
            "hours_ago":             None,
        }
    except Exception as exc:
        logger.debug(f"get_latest_wearable_reading: {exc}")
        return None


def get_historical_context(patient_code: str, days_back: int = 30) -> dict:
    """Return aggregated historical context for a patient over the past N days."""
    default = {
        "recurring_themes":      [],
        "recent_intents":        [],
        "crisis_history":        False,
        "last_session_timestamp": None,
        "days_since_last_session": None,
        "session_count":         0,
    }
    try:
        patient = get_patient(patient_code)
        if not patient:
            return default
        patient_id = patient["patient_id"]
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT session_id, started_at, last_intent, crisis_detected
                    FROM   sessions
                    WHERE  patient_id  = %s::uuid
                      AND  started_at >= %s
                    ORDER  BY started_at DESC
                    """,
                    (patient_id, cutoff),
                )
                sessions = _fetchall(cur)

        if not sessions:
            return default

        last_ts = sessions[0].get("started_at")
        days_since: Optional[int] = None
        if last_ts:
            try:
                if isinstance(last_ts, str):
                    from dateutil import parser as dateparser
                    last_ts_dt = dateparser.parse(last_ts)
                    if last_ts_dt.tzinfo is None:
                        last_ts_dt = last_ts_dt.replace(tzinfo=timezone.utc)
                else:
                    last_ts_dt = last_ts
                    if last_ts_dt.tzinfo is None:
                        last_ts_dt = last_ts_dt.replace(tzinfo=timezone.utc)
                days_since = (datetime.now(timezone.utc) - last_ts_dt).days
            except Exception:
                pass

        return {
            "recurring_themes":       [],
            "recent_intents":         [s["last_intent"] for s in sessions if s.get("last_intent")][:10],
            "crisis_history":         any(s.get("crisis_detected") for s in sessions),
            "last_session_timestamp": str(last_ts) if last_ts else None,
            "days_since_last_session": days_since,
            "session_count":          len(sessions),
        }
    except Exception as exc:
        logger.error(f"get_historical_context failed: {exc}")
        return default


def save_context_vector(
    patient_id: str,
    patient_code: str,
    session_id: str,
    context_vector: dict,
    greeting_text: str,
) -> None:
    """Save a patient context vector snapshot to the audit table."""
    try:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO patient_context_vectors
                        (patient_id, patient_code, session_id,
                         context_vector, greeting_text, created_at)
                    VALUES
                        (%s::uuid, %s, %s::uuid, %s, %s, now())
                    """,
                    (patient_id, patient_code, session_id,
                     json.dumps(context_vector), greeting_text),
                )
    except Exception as exc:
        logger.debug(f"save_context_vector failed (table may not exist): {exc}")


def get_patient_context_vectors(patient_code: str, limit: int = 50) -> List[dict]:
    """Retrieve stored context vectors for a patient."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM   patient_context_vectors
                    WHERE  patient_code = %s
                    ORDER  BY created_at DESC
                    LIMIT  %s
                    """,
                    (patient_code, limit),
                )
                return _fetchall(cur)
    except Exception as exc:
        logger.debug(f"get_patient_context_vectors failed: {exc}")
        return []


def get_context_vector_trends(patient_code: str, days: int = 30) -> dict:
    """Return trend data derived from stored context vectors."""
    try:
        vectors = get_patient_context_vectors(patient_code, limit=days * 2)
        return {
            "risk_trend":         [],
            "tone_distribution":  {},
            "theme_distribution": {},
            "contradiction_count": 0,
            "avg_data_freshness": {},
            "greetings_generated": len(vectors),
        }
    except Exception as exc:
        logger.error(f"get_context_vector_trends failed: {exc}")
        return {
            "risk_trend": [], "tone_distribution": {}, "theme_distribution": {},
            "contradiction_count": 0, "avg_data_freshness": {}, "greetings_generated": 0,
        }


def get_contradiction_patterns(
    patient_code: Optional[str] = None,
    limit: int = 100,
) -> List[dict]:
    """Return contradiction patterns from stored context vectors."""
    try:
        with _conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if patient_code:
                    cur.execute(
                        """
                        SELECT patient_code, context_vector, created_at
                        FROM   patient_context_vectors
                        WHERE  patient_code = %s
                        ORDER  BY created_at DESC
                        LIMIT  %s
                        """,
                        (patient_code, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT patient_code, context_vector, created_at
                        FROM   patient_context_vectors
                        ORDER  BY created_at DESC
                        LIMIT  %s
                        """,
                        (limit,),
                    )
                return _fetchall(cur)
    except Exception as exc:
        logger.debug(f"get_contradiction_patterns failed: {exc}")
        return []
