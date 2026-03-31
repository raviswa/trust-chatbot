"""
db_supabase.py
─────────────────────────────────────────────────────────────────
Supabase Persistence Layer

Uses Supabase's PostgreSQL backend via the Python SDK.
Same interface as db.py but with Supabase authentication.

Configuration via environment variables:
  SUPABASE_URL       — Your Supabase project URL
  SUPABASE_KEY       — Your Supabase anon/service API key
  
Get these from: https://app.supabase.com/project/[YOUR_PROJECT]/settings/api

Schema tables (same as original):
  patients          — patient registry (one row per patient)
  sessions          — one per browser/app session, linked to patient
  messages          — every message, linked to both session + patient
  policy_violations — audit log for ethical AI policy breaches
  crisis_events     — dedicated high-priority log for all crisis interactions
─────────────────────────────────────────────────────────────────
"""

import os
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_URL and SUPABASE_KEY environment variables are required.\n"
        "Get them from: https://app.supabase.com/project/[YOUR_PROJECT]/settings/api"
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ─────────────────────────────────────────────
# PATIENT
# ─────────────────────────────────────────────

def ensure_patient(patient_code: str,
                   display_name: Optional[str] = None,
                   programme: Optional[str] = None,
                   assigned_to: Optional[str] = None) -> Optional[str]:
    """
    Looks up a patient by patient_code.
    Creates a new patient row if one doesn't exist.
    Returns the patient UUID (id), or None on failure.
    """
    try:
        # Try to get existing patient
        result = supabase.table("patients").select("id").eq("patient_code", patient_code).execute()
        
        if result.data:
            return str(result.data[0]["id"])
        
        # Create new patient
        new_patient = {
            "patient_code": patient_code,
            "display_name": display_name,
            "programme": programme,
            "assigned_to": assigned_to,
            "created_at": datetime.now().isoformat()
        }
        
        result = supabase.table("patients").insert([new_patient]).execute()
        if result.data:
            return str(result.data[0]["id"])
        
        return None
    except Exception as e:
        logger.error(f"ensure_patient failed: {e}")
        return None


def get_patient(patient_code: str) -> Optional[dict]:
    """Returns patient record by patient_code."""
    try:
        result = supabase.table("patients").select("*").eq("patient_code", patient_code).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"get_patient failed: {e}")
        return None


def get_patient_onboarding(patient_code: str) -> Optional[dict]:
    """Returns the most recent onboarding profile row for a patient (includes addiction_type)."""
    try:
        patient = get_patient(patient_code)
        if not patient:
            return None
        patient_id = patient.get("patient_id") or patient.get("id")
        result = (
            supabase.table("onboarding_profiles")
            .select(
                "addiction_type, primary_triggers, baseline_mood, support_network, "
                "work_status, last_intake_phase, intake_consent_given"
            )
            .eq("patient_id", patient_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            row = result.data[0]
            return {
                "addiction_type": row.get("addiction_type") or "",
                "name": patient.get("first_name") or patient.get("display_name") or "",
                "primary_triggers": row.get("primary_triggers") or [],
                "baseline_mood": row.get("baseline_mood") or [],
                "support_network": row.get("support_network") or {},
                "work_status": row.get("work_status") or "",
                "last_intake_phase": row.get("last_intake_phase") or 0,
                "intake_consent_given": bool(row.get("intake_consent_given")),
            }
        # Return at least the patient name even without onboarding row
        return {
            "addiction_type": "",
            "name": patient.get("first_name") or "",
            "last_intake_phase": 0,
            "intake_consent_given": False,
        }
    except Exception as e:
        logger.error(f"get_patient_onboarding failed: {e}")
        return None


def save_intake_progress(patient_code: str, phase: int, completion_pct: int) -> None:
    """
    Persist the patient's intake phase progress to onboarding_profiles so the
    session can resume at the correct question after a reconnect.

    Updates last_intake_phase and intake_completion_pct on the most recent
    onboarding_profiles row for this patient.  Creates a minimal placeholder row
    if no row exists yet (new user filling intake for the first time).
    """
    try:
        patient = get_patient(patient_code)
        if not patient:
            return
        patient_id = patient.get("patient_id") or patient.get("id")

        # Find the most recent profile row to update
        result = (
            supabase.table("onboarding_profiles")
            .select("profile_id")
            .eq("patient_id", patient_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            profile_id = result.data[0].get("profile_id")
            supabase.table("onboarding_profiles").update({
                "last_intake_phase": phase,
                "intake_completion_pct": completion_pct,
                "updated_at": datetime.now().isoformat(),
            }).eq("profile_id", profile_id).execute()
        else:
            # No row yet — insert a minimal placeholder so progress is persisted
            supabase.table("onboarding_profiles").insert({
                "patient_id": patient_id,
                "last_intake_phase": phase,
                "intake_completion_pct": completion_pct,
            }).execute()
    except Exception as e:
        logger.error(f"save_intake_progress failed: {e}")


def get_patient_addictions(patient_code: str) -> List[dict]:
    """
    Return all active addiction records for a patient, primary first.

    Each dict: {addiction_type, is_primary, severity, noted_at, clinical_notes}

    Falls back to the single onboarding_profiles.addiction_type when the
    patient_addictions table has no rows for this patient (backward compat).
    """
    try:
        patient = get_patient(patient_code)
        if not patient:
            return []
        patient_id = patient.get("patient_id") or patient.get("id")

        result = (
            supabase.table("patient_addictions")
            .select("addiction_type, is_primary, severity, noted_at, clinical_notes")
            .eq("patient_id", patient_id)
            .eq("is_active", True)
            .order("is_primary", desc=True)   # primary first
            .execute()
        )
        if result.data:
            return result.data

        # Fallback: synthesise a single-item list from the onboarding profile
        onboarding = get_patient_onboarding(patient_code)
        if onboarding and onboarding.get("addiction_type"):
            return [{
                "addiction_type": onboarding["addiction_type"],
                "is_primary": True,
                "severity": "high",
                "noted_at": None,
                "clinical_notes": "Migrated from onboarding_profiles.addiction_type",
            }]
        return []
    except Exception as e:
        logger.error(f"get_patient_addictions failed: {e}")
        return []


def get_response_routing_table() -> List[dict]:
    """
    Load the full response_routing table into memory (called once at startup).

    Returns list of dicts keyed by (patient_addiction, detected_intent).
    Falls back to [] on error; code-based logic handles the fallback.
    """
    try:
        result = (
            supabase.table("response_routing")
            .select("patient_addiction, detected_intent, relationship, severity_override, video_key, requires_escalation")
            .eq("is_active", True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"get_response_routing_table failed: {e}")
        return []
    """Returns all sessions for a patient."""
    try:
        patient = get_patient(patient_code)
        if not patient:
            return []
        
        result = supabase.table("sessions").select("*").eq("patient_id", patient["id"]).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"get_patient_sessions failed: {e}")
        return []


def get_patient_full_history(patient_code: str) -> List[dict]:
    """Returns full conversation history for a patient."""
    try:
        patient = get_patient(patient_code)
        if not patient:
            return []
        
        # Get all messages for this patient
        result = supabase.table("messages").select("*").eq("patient_id", patient["id"]).order("created_at", desc=False).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"get_patient_full_history failed: {e}")
        return []


def get_checkin_status(patient_code: str, hours: int = 12) -> dict:
    """Returns check-in status for a patient."""
    try:
        patient = get_patient(patient_code)
        if not patient:
            return {
                "has_recent_activity": False,
                "topics_covered": [],
                "continuity_prompt": None
            }
        
        # This would need custom logic to check last N hours
        # For now, return basic structure
        return {
            "has_recent_activity": False,
            "topics_covered": [],
            "continuity_prompt": None
        }
    except Exception as e:
        logger.error(f"get_checkin_status failed: {e}")
        return {}


# ─────────────────────────────────────────────
# SESSION
# ─────────────────────────────────────────────

def ensure_session(session_id: str, patient_id: Optional[str] = None,
                   patient_code: Optional[str] = None) -> str:
    """Create or return existing session."""
    try:
        # Check if session exists
        result = supabase.table("sessions").select("*").eq("session_id", session_id).execute()
        
        if result.data:
            return session_id
        
        # Create new session
        new_session = {
            "session_id": session_id,
            "patient_id": patient_id,
            "patient_code": patient_code,
            "created_at": datetime.now().isoformat()
        }
        
        supabase.table("sessions").insert([new_session]).execute()
        return session_id
    except Exception as e:
        logger.error(f"ensure_session failed: {e}")
        return session_id


def get_session(session_id: str) -> dict:
    """Get session by ID."""
    try:
        result = supabase.table("sessions").select("*").eq("session_id", session_id).execute()
        if result.data:
            return result.data[0]
        return {"session_id": session_id}
    except Exception as e:
        logger.error(f"get_session failed: {e}")
        return {"session_id": session_id}


def update_session(session_id: str, role: str, message: str,
                   intent: Optional[str] = None, severity: Optional[str] = None,
                   show_resources: bool = False,
                   patient_id: Optional[str] = None,
                   patient_code: Optional[str] = None) -> None:
    """Save a message to the conversation."""
    try:
        msg_data = {
            "session_id": session_id,
            "patient_id": patient_id,
            "role": role,
            "content": message,
            "intent": intent,
            "severity": severity
        }
        supabase.table("messages").insert([msg_data]).execute()
    except Exception as e:
        logger.error(f"update_session failed: {e}")


def update_session_meta(session_id: str, key: str, value) -> None:
    """Update session metadata."""
    try:
        supabase.table("sessions").update({key: value}).eq("session_id", session_id).execute()
    except Exception as e:
        logger.error(f"update_session_meta failed: {e}")


def clear_session(session_id: str) -> None:
    """Clear all messages in a session."""
    try:
        supabase.table("messages").delete().eq("session_id", session_id).execute()
        supabase.table("sessions").delete().eq("session_id", session_id).execute()
    except Exception as e:
        logger.error(f"clear_session failed: {e}")


def get_session_summary(session_id: str) -> dict:
    """Get summary of a session."""
    try:
        result = supabase.table("messages").select("*").eq("session_id", session_id).order("created_at", desc=False).execute()
        messages = result.data or []
        
        return {
            "session_id": session_id,
            "message_count": len(messages),
            "messages": messages
        }
    except Exception as e:
        logger.error(f"get_session_summary failed: {e}")
        return {"session_id": session_id, "message_count": 0, "messages": []}


def get_session_history(session_id: str) -> List[dict]:
    """Get full history for a session."""
    try:
        result = supabase.table("messages").select("*").eq("session_id", session_id).order("created_at", desc=False).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"get_session_history failed: {e}")
        return []


# ─────────────────────────────────────────────
# MESSAGES & PERSISTENCE
# ─────────────────────────────────────────────

def save_message(session_id: str, role: str, message: str,
                intent: Optional[str] = None,
                severity: Optional[str] = None,
                patient_id: Optional[str] = None,
                patient_code: Optional[str] = None) -> None:
    """Save a message (alias for update_session)."""
    update_session(session_id, role, message, intent, severity,
                  patient_id=patient_id, patient_code=patient_code)


# ─────────────────────────────────────────────
# POLICY & AUDIT LOGGING
# ─────────────────────────────────────────────

def log_policy_violation(session_id: str, violation_type: str,
                        details: str, user_message: str,
                        bot_response: str,
                        patient_id: Optional[str] = None) -> None:
    """Log a policy violation."""
    try:
        violation = {
            "session_id": session_id,
            "patient_id": patient_id,
            "violation_type": violation_type,
            "details": details,
            "user_message": user_message,
            "bot_response": bot_response,
            "timestamp": datetime.now().isoformat()
        }
        supabase.table("policy_violations").insert([violation]).execute()
        logger.warning(f"Policy violation logged: {violation_type}")
    except Exception as e:
        logger.error(f"log_policy_violation failed: {e}")


def get_policy_violation_summary() -> List[dict]:
    """Get summary of policy violations."""
    try:
        result = supabase.table("policy_violations").select("*").order("timestamp", desc=True).limit(100).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"get_policy_violation_summary failed: {e}")
        return []


# ─────────────────────────────────────────────
# CRISIS TRACKING
# ─────────────────────────────────────────────

def log_crisis_event(session_id: str, severity: str, user_message: str,
                    bot_response: str, intent: str,
                    patient_id: Optional[str] = None,
                    patient_code: Optional[str] = None) -> None:
    """Log a crisis event."""
    try:
        event = {
            "session_id": session_id,
            "patient_id": patient_id,
            "patient_code": patient_code,
            "severity": severity,
            "user_message": user_message,
            "bot_response": bot_response,
            "intent": intent,
            "timestamp": datetime.now().isoformat()
        }
        supabase.table("crisis_events").insert([event]).execute()
        logger.warning(f"Crisis event logged: severity={severity}")
    except Exception as e:
        logger.error(f"log_crisis_event failed: {e}")


def get_pending_crisis_events() -> List[dict]:
    """Get pending crisis events."""
    try:
        result = supabase.table("crisis_events").select("*").eq("acknowledged", False).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"get_pending_crisis_events failed: {e}")
        return []


def get_crisis_sessions() -> List[dict]:
    """Get all sessions with crisis events."""
    try:
        result = supabase.table("crisis_events").select("session_id", count="exact").execute()
        return result.data or []
    except Exception as e:
        logger.error(f"get_crisis_sessions failed: {e}")
        return []


# ─────────────────────────────────────────────
# ADMIN & ANALYTICS
# ─────────────────────────────────────────────

def get_all_sessions() -> List[dict]:
    """Get all sessions."""
    try:
        result = supabase.table("sessions").select("*").order("created_at", desc=True).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"get_all_sessions failed: {e}")
        return []


def get_conversation_stats(session_id: str) -> dict:
    """Get conversation statistics."""
    try:
        result = supabase.table("messages").select("*").eq("session_id", session_id).execute()
        msgs = result.data or []
        
        user_msgs = [m for m in msgs if m.get("role") == "user"]
        asst_msgs = [m for m in msgs if m.get("role") == "assistant"]
        
        return {
            "total_messages": len(messages),
            "user_messages": len(user_msgs),
            "assistant_messages": len(asst_msgs)
        }
    except Exception as e:
        logger.error(f"get_conversation_stats failed: {e}")
        return {}


def get_top_intents(limit: int = 10) -> List[dict]:
    """Get top intents across all sessions."""
    try:
        result = supabase.table("messages").select("intent").execute()
        msgs = result.data or []
        
        intent_counts = {}
        for msg in msgs:
            intent = msg.get("intent")
            if intent:
                intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        sorted_intents = sorted(intent_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"intent": i[0], "count": i[1]} for i in sorted_intents[:limit]]
    except Exception as e:
        logger.error(f"get_top_intents failed: {e}")
        return []


def get_watched_video_ids(patient_id: str) -> set:
    """
    Returns the set of video_ids (content_id) that have already been shown
    to this patient across all their sessions.

    Used by the video recommendation engine to avoid repeating videos.

    Args:
        patient_id: The patient's UUID from the patients table.

    Returns:
        A set of video_id strings. Empty set on failure or no history.
    """
    try:
        result = (
            supabase.table("content_engagement")
            .select("content_id")
            .eq("patient_id", patient_id)
            .eq("content_type", "video")
            .execute()
        )
        return {
            row["content_id"]
            for row in (result.data or [])
            if row.get("content_id")
        }
    except Exception as e:
        logger.error(f"get_watched_video_ids failed: {e}")
        return set()


def save_patient_score(session_id: str, patient_code: Optional[str],
                      score_group: str, score: int, intent: Optional[str] = None,
                      patient_id: Optional[str] = None) -> None:
    """Save patient score."""
    try:
        score_record = {
            "session_id": session_id,
            "patient_id": patient_id,
            "patient_code": patient_code,
            "score_group": score_group,
            "score": score,
            "intent": intent,
            "timestamp": datetime.now().isoformat()
        }
        supabase.table("scores").insert([score_record]).execute()
        logger.info(f"Score saved: {score_group}={score}")
    except Exception as e:
        logger.error(f"save_patient_score failed: {e}")


def build_checkin_greeting(patient_code: str) -> Optional[dict]:
    """Build check-in greeting based on recent history."""
    # This would require more complex logic
    return None


def get_latest_daily_checkin(patient_code: str, within_hours: int = 24) -> Optional[dict]:
    """Return the most recent daily check-in for a patient within the given hour window."""
    try:
        from datetime import timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).isoformat()
        patient = get_patient(patient_code)
        if not patient:
            return None
        result = (
            supabase.table("daily_checkins")
            .select("*")
            .eq("patient_id", patient["patient_id"])
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"get_latest_daily_checkin failed: {e}")
        return None


def get_latest_wearable_reading(patient_code: str, within_hours: int = 48) -> Optional[dict]:
    """Return the most recent wearable reading for a patient within the given hour window.
    Maps schema column names to the field names expected by PatientContextSynthesis."""
    try:
        from datetime import timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=within_hours)).isoformat()
        patient = get_patient(patient_code)
        if not patient:
            return None
        result = (
            supabase.table("wearable_readings")
            .select("*")
            .eq("patient_id", patient["patient_id"])
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        row = result.data[0]
        # Map schema columns → synthesis engine field names
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
            "hours_ago":             None,  # calculated downstream if needed
        }
    except Exception as e:
        logger.debug(f"get_latest_wearable_reading: {e}")
        return None


def get_historical_context(patient_code: str, days_back: int = 30) -> dict:
    """Return aggregated historical context for a patient over the past N days."""
    default = {
        "recurring_themes": [],
        "recent_intents": [],
        "crisis_history": False,
        "last_session_timestamp": None,
        "days_since_last_session": None,
        "session_count": 0,
    }
    try:
        from datetime import timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        patient = get_patient(patient_code)
        if not patient:
            return default
        patient_id = patient["patient_id"]

        sessions = (
            supabase.table("sessions")
            .select("session_id, started_at, last_intent, crisis_detected")
            .eq("patient_id", patient_id)
            .gte("started_at", cutoff)
            .order("started_at", desc=True)
            .execute()
        ).data or []

        if not sessions:
            return default

        last_session = sessions[0]
        last_ts = last_session.get("started_at")
        days_since = None
        if last_ts:
            from dateutil import parser as dateparser
            try:
                delta = datetime.now(timezone.utc) - dateparser.parse(last_ts)
                days_since = delta.days
            except Exception:
                pass

        crisis_history = any(s.get("crisis_detected") for s in sessions)
        recent_intents = [s["last_intent"] for s in sessions if s.get("last_intent")]

        return {
            "recurring_themes": [],
            "recent_intents": recent_intents[:10],
            "crisis_history": crisis_history,
            "last_session_timestamp": last_ts,
            "days_since_last_session": days_since,
            "session_count": len(sessions),
        }
    except Exception as e:
        logger.error(f"get_historical_context failed: {e}")
        return default


def save_context_vector(patient_id: str, patient_code: str, session_id: str,
                        context_vector: dict, greeting_text: str) -> None:
    """Save a patient context vector snapshot to the audit table."""
    try:
        supabase.table("patient_context_vectors").insert({
            "patient_id": patient_id,
            "patient_code": patient_code,
            "session_id": session_id,
            "context_vector": context_vector,
            "greeting_text": greeting_text,
            "created_at": datetime.now().isoformat(),
        }).execute()
    except Exception as e:
        logger.debug(f"save_context_vector failed (table may not exist): {e}")


def get_patient_context_vectors(patient_code: str, limit: int = 50) -> List[dict]:
    """Retrieve stored context vectors for a patient."""
    try:
        result = (
            supabase.table("patient_context_vectors")
            .select("*")
            .eq("patient_code", patient_code)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.debug(f"get_patient_context_vectors failed: {e}")
        return []


def get_context_vector_trends(patient_code: str, days: int = 30) -> dict:
    """Return trend data derived from stored context vectors."""
    try:
        vectors = get_patient_context_vectors(patient_code, limit=days * 2)
        return {
            "risk_trend": [],
            "tone_distribution": {},
            "theme_distribution": {},
            "contradiction_count": 0,
            "avg_data_freshness": {},
            "greetings_generated": len(vectors),
        }
    except Exception as e:
        logger.error(f"get_context_vector_trends failed: {e}")
        return {"risk_trend": [], "tone_distribution": {}, "theme_distribution": {},
                "contradiction_count": 0, "avg_data_freshness": {}, "greetings_generated": 0}


def get_contradiction_patterns(patient_code: Optional[str] = None, limit: int = 100) -> List[dict]:
    """Return contradiction patterns from stored context vectors."""
    try:
        query = supabase.table("patient_context_vectors").select("patient_code, context_vector, created_at")
        if patient_code:
            query = query.eq("patient_code", patient_code)
        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.debug(f"get_contradiction_patterns failed: {e}")
        return []
