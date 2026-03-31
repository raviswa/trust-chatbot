"""
db.py — Compatibility shim: re-exports all functions from db_supabase.py
"""
from db_supabase import (
    ensure_patient,
    get_patient,
    get_patient_sessions,
    get_patient_full_history,
    ensure_session,
    update_session_meta,
    save_message,
    log_policy_violation,
    log_crisis_event,
    get_pending_crisis_events,
    get_policy_violation_summary,
    get_session_history,
    get_all_sessions,
    get_crisis_sessions,
    get_conversation_stats,
    get_top_intents,
)
