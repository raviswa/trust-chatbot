"""
db.py
─────────────────────────────────────────────────────────────────
PostgreSQL Persistence Layer
Stores all chat sessions and messages with full patient identity.

Schema:
  patients          — patient registry (one row per patient)
  sessions          — one per browser/app session, linked to patient
  conversations     — every message, linked to both session + patient
  policy_violations — audit log for ethical AI policy breaches
  crisis_events     — dedicated high-priority log for all crisis interactions

Patient identity flow:
  1. Flutter/Next.js app authenticates patient (your auth layer)
  2. App passes patient_code in every /chat request
  3. ensure_patient() looks up or creates the patient row
  4. ensure_session() links session to patient
  5. save_message() stores patient_id on every message row
  6. log_policy_violation() writes to policy_violations on any breach
  7. log_crisis_event() writes to crisis_events on any crisis intent
─────────────────────────────────────────────────────────────────
"""

import os
import logging
from typing import Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

PG_HOST     = os.getenv("PG_HOST",     "localhost")
PG_PORT     = int(os.getenv("PG_PORT", 5432))
PG_DB       = os.getenv("PG_DB",       "chatbot_db")
PG_USER     = os.getenv("PG_USER",     "chatbot_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "your_password")

_conn = None

def get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            dbname=PG_DB, user=PG_USER,
            password=PG_PASSWORD
        )
        _conn.autocommit = False
    return _conn


# ─────────────────────────────────────────────
# PATIENT
# ─────────────────────────────────────────────

def ensure_patient(patient_code: str,
                   display_name: Optional[str] = None,
                   programme:    Optional[str] = None,
                   assigned_to:  Optional[str] = None) -> Optional[str]:
    """
    Looks up a patient by patient_code.
    Creates a new patient row if one doesn't exist.
    Returns the patient UUID (id), or None on failure.

    patient_code = your internal MRN / user ID from your auth system.
    Call this once per session before ensure_session().
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO patients
                    (patient_code, display_name, programme, assigned_to)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (patient_code) DO UPDATE
                    SET display_name = COALESCE(%s, patients.display_name),
                        programme    = COALESCE(%s, patients.programme),
                        assigned_to  = COALESCE(%s, patients.assigned_to)
                RETURNING id
            """, (
                patient_code, display_name, programme, assigned_to,
                display_name, programme, assigned_to
            ))
            row = cur.fetchone()
        conn.commit()
        return str(row[0]) if row else None
    except Exception as e:
        conn.rollback()
        logger.error(f"ensure_patient failed: {e}")
        return None


def get_patient(patient_code: str) -> Optional[dict]:
    """Returns patient record by patient_code."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT id, patient_code, display_name, programme,
                       assigned_to, enrolled_at, is_active
                FROM patients
                WHERE patient_code = %s
            """, (patient_code,))
            row = cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_patient failed: {e}")
        return None


def get_patient_sessions(patient_code: str) -> list:
    """Returns all sessions for a patient — full history across visits."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT s.session_id, s.started_at, s.last_active,
                       s.message_count, s.severity_flags,
                       s.last_topic, s.is_crisis
                FROM sessions s
                JOIN patients p ON p.id = s.patient_id
                WHERE p.patient_code = %s
                ORDER BY s.started_at DESC
            """, (patient_code,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_patient_sessions failed: {e}")
        return []


def get_patient_full_history(patient_code: str, limit: int = 100) -> list:
    """
    Returns complete conversation history for a patient
    across ALL sessions — for clinician review.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT c.session_id, c.role, c.content, c.intent,
                       c.severity, c.citations, c.show_resources,
                       c.created_at
                FROM conversations c
                JOIN patients p ON p.id = c.patient_id
                WHERE p.patient_code = %s
                ORDER BY c.created_at DESC
                LIMIT %s
            """, (patient_code, limit))
            rows = cur.fetchall()
        return [dict(r) for r in reversed(rows)]
    except Exception as e:
        logger.error(f"get_patient_full_history failed: {e}")
        return []



def get_recent_checkin_activity(patient_code: str,
                                within_hours: int = 12) -> Optional[dict]:
    """
    Fetches a patient's activity from the last N hours.
    Used by the chatbot on session start to generate a
    personalised continuity greeting instead of a cold open.

    Returns dict with:
      has_activity      -- True if any messages in the window
      display_name      -- patient first name if known
      topics_discussed  -- human-readable topic labels
      intents_seen      -- raw intent tags
      last_active       -- timestamp of last message
      was_crisis        -- True if any crisis intent fired
      message_count     -- total messages in the window
    Returns None on DB error.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    p.display_name,
                    COUNT(c.id)                                 AS message_count,
                    MAX(c.created_at)                           AS last_active,
                    ARRAY_AGG(DISTINCT c.intent)
                        FILTER (WHERE c.intent IS NOT NULL
                            AND c.role = 'user'
                            AND c.intent NOT IN (
                                'greeting','farewell','gratitude',
                                'unclear','medication_request','rag_query'
                            ))                                  AS intents_seen,
                    BOOL_OR(c.show_resources)                   AS was_crisis
                FROM conversations c
                JOIN patients p ON p.patient_code = %s
                WHERE c.patient_code  = %s
                  AND c.created_at   >= NOW() - (%s * INTERVAL '1 hour')
                GROUP BY p.display_name
            """, (patient_code, patient_code, within_hours))
            row = cur.fetchone()

        if not row or row["message_count"] == 0:
            return {"has_activity": False, "display_name": None}

        TOPIC_LABELS = {
            "mood_sad":               "low mood",
            "mood_anxious":           "anxiety",
            "mood_angry":             "anger",
            "mood_lonely":            "loneliness",
            "mood_guilty":            "feelings of guilt",
            "behaviour_sleep":        "sleep difficulties",
            "behaviour_eating":       "eating patterns",
            "behaviour_isolation":    "social withdrawal",
            "behaviour_aggression":   "managing anger",
            "behaviour_self_harm":    "self-harm urges",
            "trigger_stress":         "stress",
            "trigger_trauma":         "trauma",
            "trigger_relationship":   "relationship challenges",
            "trigger_grief":          "grief and loss",
            "trigger_financial":      "financial stress",
            "addiction_alcohol":      "alcohol use",
            "addiction_drugs":        "substance use",
            "addiction_gaming":       "gaming habits",
            "addiction_social_media": "social media use",
            "addiction_gambling":     "gambling",
            "addiction_food":         "emotional eating",
            "addiction_work":         "work-life balance",
            "addiction_nicotine":     "smoking and nicotine",
            "addiction_pornography":  "compulsive behaviour",
            "crisis_suicidal":        "difficult thoughts",
            "crisis_abuse":           "safety concerns",
            "severe_distress":        "overwhelming feelings",
            "psychosis_indicator":    "distressing experiences",
        }

        raw_intents   = row["intents_seen"] or []
        topics        = [TOPIC_LABELS.get(i, i.replace("_", " "))
                         for i in raw_intents if i]
        topics_unique = list(dict.fromkeys(topics))

        return {
            "has_activity":     True,
            "display_name":     row["display_name"],
            "topics_discussed": topics_unique,
            "intents_seen":     raw_intents,
            "last_active":      row["last_active"].isoformat() if row["last_active"] else None,
            "message_count":    row["message_count"],
            "was_crisis":       row["was_crisis"] or False,
        }
    except Exception as e:
        logger.error(f"get_recent_checkin_activity failed: {e}")
        return None

# ─────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────

def ensure_session(session_id: str,
                   patient_id:   Optional[str] = None,
                   patient_code: Optional[str] = None):
    """
    Creates a session row linked to a patient if it doesn't exist.
    Updates last_active on every subsequent call.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sessions (session_id, patient_id, patient_code)
                VALUES (%s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE
                    SET last_active  = NOW(),
                        patient_id   = COALESCE(%s, sessions.patient_id),
                        patient_code = COALESCE(%s, sessions.patient_code)
            """, (
                session_id, patient_id, patient_code,
                patient_id, patient_code
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"ensure_session failed: {e}")


def update_session_meta(session_id:   str,
                        last_topic:   Optional[str] = None,
                        last_topic_tag: Optional[str] = None,
                        severity:     Optional[str] = None,
                        is_crisis:    bool = False,
                        crisis_intent: Optional[str] = None,
                        role:         Optional[str] = None,
                        intent:       Optional[str] = None):
    """
    Updates session metadata after each message.
    Tracks per-role message counts, intents seen, and crisis timestamps.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sessions SET
                    last_active         = NOW(),
                    message_count       = message_count + 1,
                    user_message_count  = user_message_count  + CASE WHEN %s = 'user'      THEN 1 ELSE 0 END,
                    bot_message_count   = bot_message_count   + CASE WHEN %s = 'assistant' THEN 1 ELSE 0 END,
                    last_topic          = COALESCE(%s, last_topic),
                    last_topic_tag      = COALESCE(%s, last_topic_tag),
                    is_crisis           = is_crisis OR %s,
                    crisis_intent       = CASE WHEN %s IS NOT NULL THEN %s ELSE crisis_intent END,
                    crisis_at           = CASE WHEN %s AND crisis_at IS NULL THEN NOW() ELSE crisis_at END,
                    severity_flags      = CASE
                        WHEN %s IS NOT NULL
                         AND NOT (severity_flags @> ARRAY[%s::TEXT])
                        THEN severity_flags || ARRAY[%s::TEXT]
                        ELSE severity_flags
                    END,
                    intents_seen        = CASE
                        WHEN %s IS NOT NULL
                         AND NOT (intents_seen @> ARRAY[%s::TEXT])
                        THEN intents_seen || ARRAY[%s::TEXT]
                        ELSE intents_seen
                    END
                WHERE session_id = %s
            """, (
                role, role,
                last_topic,
                last_topic_tag,
                is_crisis,
                crisis_intent, crisis_intent,
                is_crisis,
                severity, severity, severity,
                intent, intent, intent,
                session_id
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"update_session_meta failed: {e}")


# ─────────────────────────────────────────────
# MESSAGES
# ─────────────────────────────────────────────

def save_message(session_id:      str,
                 role:            str,
                 content:         str,
                 intent:          Optional[str]  = None,
                 severity:        Optional[str]  = None,
                 citations:       Optional[list] = None,
                 show_resources:  bool           = False,
                 patient_id:      Optional[str]  = None,
                 patient_code:    Optional[str]  = None,
                 has_rag_context: bool           = False,
                 policy_checked:      bool       = False,
                 policy_violation:    bool       = False,
                 policy_violation_type: Optional[str] = None) -> Optional[str]:
    """
    Persists a single message with full patient identity and policy audit fields.
    patient_id and patient_code are denormalised onto every row for fast
    per-patient queries without joins.
    Returns the conversation UUID so callers can reference it in other tables.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO conversations
                    (session_id, role, content, intent,
                     severity, citations, show_resources,
                     patient_id, patient_code,
                     has_rag_context,
                     policy_checked, policy_violation, policy_violation_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                session_id, role, content, intent,
                severity, citations or [], show_resources,
                patient_id, patient_code,
                has_rag_context,
                policy_checked, policy_violation, policy_violation_type
            ))
            row = cur.fetchone()
        conn.commit()
        return str(row[0]) if row else None
    except Exception as e:
        conn.rollback()
        logger.error(f"save_message failed: {e}")
        return None


# ─────────────────────────────────────────────
# PATIENT SCORES
# ─────────────────────────────────────────────

def save_patient_score(session_id: str, patient_code: str,
                       score_group: str, score: int,
                       intent: Optional[str] = None,
                       patient_id: Optional[str] = None):
    """
    Saves a 0-10 score for a patient for a given score group.
    Called once per session per group — never overwritten.
    score_group: mood / addiction / triggers / sleep
    score: 0 (worst) to 10 (best)
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO patient_scores
                    (session_id, patient_id, patient_code,
                     score_group, score, intent_at_time)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id, score_group) DO NOTHING
            """, (session_id, patient_id, patient_code,
                  score_group, score, intent))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"save_patient_score failed: {e}")


def get_session_scores(session_id: str) -> dict:
    """
    Returns all scores captured in this session as a dict.
    e.g. {"mood": 4, "addiction": 7, "sleep": 5}
    Used to check which score groups have already been captured.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT score_group, score
                FROM patient_scores
                WHERE session_id = %s
            """, (session_id,))
            return {row[0]: row[1] for row in cur.fetchall()}
    except Exception as e:
        logger.error(f"get_session_scores failed: {e}")
        return {}


def get_patient_score_history(patient_code: str, score_group: str,
                               limit: int = 10) -> list:
    """
    Returns score history for a patient/group — for trend charts.
    Returns list of {score, scored_at} dicts ordered oldest first.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT score, scored_at
                FROM patient_scores
                WHERE patient_code = %s
                  AND score_group  = %s
                ORDER BY scored_at DESC
                LIMIT %s
            """, (patient_code, score_group, limit))
            rows = cur.fetchall()
        return [dict(r) for r in reversed(rows)]
    except Exception as e:
        logger.error(f"get_patient_score_history failed: {e}")
        return []


def log_policy_violation(session_id:       str,
                         violation_type:    str,
                         intent_at_time:    Optional[str] = None,
                         original_response: Optional[str] = None,
                         safe_response:     Optional[str] = None,
                         pattern_matched:   Optional[str] = None,
                         patient_id:        Optional[str] = None,
                         patient_code:      Optional[str] = None,
                         conversation_id:   Optional[str] = None):
    """
    Writes a row to policy_violations for every ethical AI policy breach.
    Required for EU AI Act Annex III compliance and clinical governance.
    Call this whenever check_policy() returns violation=True.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO policy_violations
                    (session_id, patient_id, patient_code, conversation_id,
                     violation_type, intent_at_time,
                     original_response, safe_response_used, pattern_matched)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session_id, patient_id, patient_code, conversation_id,
                violation_type, intent_at_time,
                (original_response or "")[:1000],   # truncate for storage
                (safe_response     or "")[:1000],
                (pattern_matched   or "")[:200]
            ))
        conn.commit()
        logger.info(f"Policy violation logged | type={violation_type} | session={session_id}")
    except Exception as e:
        conn.rollback()
        logger.error(f"log_policy_violation failed: {e}")


def log_crisis_event(session_id:     str,
                     crisis_type:    str,
                     trigger_message: str,
                     bot_response:   str,
                     patient_id:     Optional[str] = None,
                     patient_code:   Optional[str] = None,
                     conversation_id: Optional[str] = None):
    """
    Writes a row to crisis_events for every crisis interaction.
    Every row is follow_up_status='pending' until a clinician reviews it.
    Call this whenever a crisis_suicidal, crisis_abuse, or
    behaviour_self_harm intent fires.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO crisis_events
                    (session_id, patient_id, patient_code, conversation_id,
                     crisis_type, trigger_message, bot_response,
                     severity, follow_up_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'critical', 'pending')
            """, (
                session_id, patient_id, patient_code, conversation_id,
                crisis_type, trigger_message[:2000], bot_response[:2000]
            ))
        conn.commit()
        logger.warning(f"CRISIS EVENT logged | type={crisis_type} | session={session_id} | patient={patient_code}")
    except Exception as e:
        conn.rollback()
        logger.error(f"log_crisis_event failed: {e}")


# ─────────────────────────────────────────────
# SESSION CONTINUITY — 12-HOUR CHECK-IN STATUS
# ─────────────────────────────────────────────

# Intent tags that count as a clinical check-in
CHECKIN_INTENT_GROUPS = {
    "mood":      ["mood_sad","mood_anxious","mood_angry","mood_lonely","mood_guilty"],
    "sleep":     ["behaviour_sleep","behaviour_eating","behaviour_isolation","behaviour_aggression"],
    "addiction": ["addiction_alcohol","addiction_drugs","addiction_gaming","addiction_social_media",
                  "addiction_gambling","addiction_food","addiction_work","addiction_shopping",
                  "addiction_nicotine","addiction_pornography"],
    "triggers":  ["trigger_stress","trigger_trauma","trigger_relationship",
                  "trigger_grief","trigger_financial"],
}

# Human-readable labels for each intent tag
INTENT_LABELS = {
    "mood_sad":              "low mood",
    "mood_anxious":          "anxiety",
    "mood_angry":            "anger",
    "mood_lonely":           "loneliness",
    "mood_guilty":           "guilt",
    "behaviour_sleep":       "sleep difficulties",
    "behaviour_eating":      "eating patterns",
    "behaviour_isolation":   "social withdrawal",
    "behaviour_aggression":  "managing anger",
    "addiction_alcohol":     "alcohol use",
    "addiction_drugs":       "substance use",
    "addiction_gaming":      "gaming habits",
    "addiction_social_media":"social media use",
    "addiction_gambling":    "gambling",
    "addiction_food":        "emotional eating",
    "addiction_work":        "work-life balance",
    "addiction_shopping":    "compulsive shopping",
    "addiction_nicotine":    "nicotine use",
    "addiction_pornography": "compulsive behaviour",
    "trigger_stress":        "stress",
    "trigger_trauma":        "trauma",
    "trigger_relationship":  "relationship challenges",
    "trigger_grief":         "grief and loss",
    "trigger_financial":     "financial stress",
}

# All checkin intents flattened
ALL_CHECKIN_INTENTS = [i for group in CHECKIN_INTENT_GROUPS.values() for i in group]


def get_checkin_status(patient_code: str, hours: int = 12) -> dict:
    """
    Checks whether a patient has had any clinical check-in activity
    in the last N hours (default 12).

    Returns a dict with:
      has_recent_activity  — bool
      topics_covered       — list of human-readable topic labels
      topic_groups         — which groups were covered (mood/sleep/addiction/triggers)
      intent_tags          — raw intent tags found
      last_seen            — ISO timestamp of most recent message
      last_session_id      — session_id of most recent session
      hours_since_checkin  — float, hours since last activity (None if no activity)
      continuity_prompt    — pre-built prompt string for chatbot_engine to use
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:

            # Get all user messages with checkin intents in last N hours
            cur.execute("""
                SELECT c.intent, c.created_at, c.session_id
                FROM conversations c
                WHERE c.patient_code   = %s
                  AND c.role           = 'user'
                  AND c.intent         = ANY(%s)
                  AND c.created_at    >= NOW() - (%s * INTERVAL '1 hour')
                ORDER BY c.created_at DESC
            """, (patient_code, ALL_CHECKIN_INTENTS, hours))
            rows = cur.fetchall()

            # Get patient display name
            cur.execute(
                "SELECT display_name FROM patients WHERE patient_code = %s",
                (patient_code,)
            )
            patient_row = cur.fetchone()
            display_name = patient_row["display_name"] if patient_row else None

            # Get last activity time regardless of intent
            cur.execute("""
                SELECT MAX(c.created_at) AS last_active, c.session_id
                FROM conversations c
                WHERE c.patient_code = %s
                GROUP BY c.session_id
                ORDER BY last_active DESC
                LIMIT 1
            """, (patient_code,))
            last_row = cur.fetchone()

        if not rows:
            return {
                "has_recent_activity":  False,
                "topics_covered":       [],
                "topic_groups":         [],
                "intent_tags":          [],
                "last_seen":            last_row["last_active"].isoformat() if last_row else None,
                "last_session_id":      last_row["session_id"] if last_row else None,
                "hours_since_checkin":  None,
                "display_name":         display_name,
                "continuity_prompt":    None,
            }

        # Deduplicate intents seen
        seen_intents = list(dict.fromkeys(r["intent"] for r in rows))
        last_active  = rows[0]["created_at"]
        last_session = rows[0]["session_id"]

        import datetime as dt
        hours_ago = (dt.datetime.now(last_active.tzinfo) - last_active).total_seconds() / 3600

        # Map intents to labels and groups
        topics   = [INTENT_LABELS.get(i, i) for i in seen_intents]
        groups   = []
        for group_name, group_intents in CHECKIN_INTENT_GROUPS.items():
            if any(i in group_intents for i in seen_intents):
                groups.append(group_name)

        # Build continuity prompt for chatbot_engine
        topic_str = ", ".join(topics)
        time_str  = (
            f"{int(hours_ago)} hour{'s' if int(hours_ago) != 1 else ''} ago"
            if hours_ago >= 1
            else f"{int(hours_ago * 60)} minutes ago"
        )
        name_str = display_name or "there"
        continuity_prompt = (
            f"CONTINUITY CONTEXT: The patient last checked in {time_str}. "
            f"Topics already discussed in that session: {topic_str}. "
            f"Open with a warm greeting referencing these topics and ask if they are "
            f"still a concern today, or if something new has come up. "
            f"Do not repeat advice already given — build on it."
        )

        return {
            "has_recent_activity":  True,
            "topics_covered":       topics,
            "topic_groups":         groups,
            "intent_tags":          seen_intents,
            "last_seen":            last_active.isoformat(),
            "last_session_id":      last_session,
            "hours_since_checkin":  round(hours_ago, 1),
            "display_name":         display_name,
            "continuity_prompt":    continuity_prompt,
        }

    except Exception as e:
        logger.error(f"get_checkin_status failed: {e}")
        return {
            "has_recent_activity":  False,
            "topics_covered":       [],
            "topic_groups":         [],
            "intent_tags":          [],
            "last_seen":            None,
            "last_session_id":      None,
            "hours_since_checkin":  None,
            "display_name":         None,
            "continuity_prompt":    None,
        }


def get_pending_crisis_events() -> list:
    """Returns all unreviewed crisis events — primary clinical worklist."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT ce.id, ce.patient_code, ce.crisis_type,
                       ce.trigger_message, ce.bot_response,
                       ce.detected_at, ce.follow_up_status,
                       p.display_name, p.assigned_clinician, p.programme
                FROM crisis_events ce
                LEFT JOIN patients p ON p.id = ce.patient_id
                WHERE ce.follow_up_status = 'pending'
                ORDER BY ce.detected_at DESC
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_pending_crisis_events failed: {e}")
        return []


def get_policy_violation_summary() -> list:
    """Returns policy violation counts by type — for compliance reporting."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT violation_type,
                       COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE reviewed_at IS NULL) AS unreviewed,
                       MAX(detected_at) AS last_seen
                FROM policy_violations
                GROUP BY violation_type
                ORDER BY total DESC
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_policy_violation_summary failed: {e}")
        return []


def get_session_history(session_id: str, limit: int = 20) -> list:
    """Returns last N messages for a session. Used for in-context history."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT role, content, intent, severity, created_at
                FROM conversations
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (session_id, limit))
            rows = cur.fetchall()
        return [dict(r) for r in reversed(rows)]
    except Exception as e:
        logger.error(f"get_session_history failed: {e}")
        return []


# ─────────────────────────────────────────────
# ADMIN QUERIES
# ─────────────────────────────────────────────

def get_all_sessions(limit: int = 50) -> list:
    """Returns recent sessions with patient identity — for admin dashboard."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT s.session_id, s.patient_code,
                       p.display_name, p.programme, p.assigned_to,
                       s.started_at, s.last_active,
                       s.message_count, s.severity_flags,
                       s.last_topic, s.is_crisis
                FROM sessions s
                LEFT JOIN patients p ON p.id = s.patient_id
                ORDER BY s.last_active DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_all_sessions failed: {e}")
        return []


def get_crisis_sessions() -> list:
    """Returns all crisis sessions with patient identity — for urgent review."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT s.session_id, s.patient_code,
                       p.display_name, p.programme, p.assigned_to,
                       s.started_at, s.last_active, s.severity_flags,
                       c.content AS crisis_message,
                       c.intent  AS crisis_intent,
                       c.created_at AS crisis_at
                FROM sessions s
                JOIN patients p ON p.id = s.patient_id
                JOIN conversations c ON c.session_id = s.session_id
                WHERE s.is_crisis = TRUE
                  AND c.intent IN (
                      'crisis_suicidal','crisis_abuse','behaviour_self_harm'
                  )
                ORDER BY c.created_at DESC
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_crisis_sessions failed: {e}")
        return []


def get_conversation_stats() -> dict:
    """Returns aggregate stats across all five tables."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(DISTINCT s.session_id)                         AS total_sessions,
                    COUNT(DISTINCT s.patient_id)                         AS total_patients,
                    COUNT(c.id)                                          AS total_messages,
                    COUNT(c.id) FILTER (WHERE c.role='user')             AS user_messages,
                    SUM(CASE WHEN s.is_crisis THEN 1 ELSE 0 END)         AS crisis_sessions,
                    COUNT(c.id) FILTER (WHERE c.policy_violation = TRUE) AS policy_violations
                FROM sessions s
                LEFT JOIN conversations c ON c.session_id = s.session_id
            """)
            row = cur.fetchone()
            # crisis_events pending count
            cur.execute("""
                SELECT COUNT(*) FROM crisis_events WHERE follow_up_status = 'pending'
            """)
            pending = cur.fetchone()[0]
        return {
            "total_sessions":          row[0],
            "total_patients":          row[1],
            "total_messages":          row[2],
            "user_messages":           row[3],
            "crisis_sessions":         row[4],
            "policy_violations_total": row[5],
            "crisis_events_pending":   pending
        }
    except Exception as e:
        logger.error(f"get_conversation_stats failed: {e}")
        return {}


def get_top_intents(limit: int = 10) -> list:
    """Returns most common intents across all patients."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT intent, COUNT(*) as count
                FROM conversations
                WHERE role = 'user'
                  AND intent IS NOT NULL
                  AND intent NOT IN ('greeting','farewell','gratitude','unclear')
                GROUP BY intent
                ORDER BY count DESC
                LIMIT %s
            """, (limit,))
            return [{"intent": r[0], "count": r[1]} for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_top_intents failed: {e}")
        return []
