"""
db_mock.py — Mock in-memory database for development/testing
Provides the same interface as db.py but stores data in memory
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict
from uuid import uuid4

logger = logging.getLogger(__name__)

# In-memory storage
_patients = {}      # patient_code -> patient record
_sessions = {}      # session_id -> session record
_conversations = {} # (session_id, msg_idx) -> message record
_scores = {}        # (session_id, group) -> score record

# ── Mock seed: per-patient addictions (primary first in each list) ────────────
# PAT-001 = Arjun (alcohol primary, gambling comorbid — common dual presentation)
# PAT-002 = generic drugs patient
# PAT-003 = Karthik (gaming primary, social_media comorbid)
_MOCK_ADDICTIONS: Dict[str, List[dict]] = {
    "PAT-001": [
        {"addiction_type": "alcohol",  "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Primary alcohol use disorder"},
        {"addiction_type": "gambling", "is_primary": False, "severity": "medium", "noted_at": None, "clinical_notes": "Comorbid problem gambling identified at intake"},
    ],
    "PAT-002": [
        {"addiction_type": "drugs",    "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Primary substance use disorder"},
    ],
    "PAT-003": [
        {"addiction_type": "gaming",       "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Primary gaming disorder"},
        {"addiction_type": "social_media", "is_primary": False, "severity": "medium", "noted_at": None, "clinical_notes": "Comorbid social media compulsion identified at intake"},
    ],
}

# ── Mock seed: response routing table (mirrors SQL seed data) ─────────────────
_MOCK_ROUTING: List[dict] = [
    # PRIMARY cravings
    {"patient_addiction": "alcohol",      "detected_intent": "addiction_drugs",        "relationship": "primary",      "severity_override": "high",   "video_key": "addiction_alcohol",      "requires_escalation": False},
    {"patient_addiction": "drugs",        "detected_intent": "addiction_drugs",        "relationship": "primary",      "severity_override": "high",   "video_key": "addiction_drugs",        "requires_escalation": False},
    {"patient_addiction": "gaming",       "detected_intent": "addiction_gaming",       "relationship": "primary",      "severity_override": "high",   "video_key": "addiction_gaming",       "requires_escalation": False},
    {"patient_addiction": "social_media", "detected_intent": "addiction_social_media", "relationship": "primary",      "severity_override": "medium", "video_key": "addiction_social_media", "requires_escalation": False},
    {"patient_addiction": "nicotine",     "detected_intent": "addiction_nicotine",     "relationship": "primary",      "severity_override": "high",   "video_key": "addiction_nicotine",     "requires_escalation": False},
    {"patient_addiction": "smoking",      "detected_intent": "addiction_nicotine",     "relationship": "primary",      "severity_override": "high",   "video_key": "addiction_nicotine",     "requires_escalation": False},
    {"patient_addiction": "gambling",     "detected_intent": "addiction_gambling",     "relationship": "primary",      "severity_override": "high",   "video_key": "addiction_gambling",     "requires_escalation": False},
    # CROSS-HIGH: behavioural → substance
    {"patient_addiction": "gaming",       "detected_intent": "addiction_drugs",        "relationship": "cross_high",   "severity_override": "high",   "video_key": "addiction_drugs",        "requires_escalation": True},
    {"patient_addiction": "social_media", "detected_intent": "addiction_drugs",        "relationship": "cross_high",   "severity_override": "high",   "video_key": "addiction_drugs",        "requires_escalation": True},
    {"patient_addiction": "gambling",     "detected_intent": "addiction_drugs",        "relationship": "cross_high",   "severity_override": "high",   "video_key": "addiction_drugs",        "requires_escalation": True},
    {"patient_addiction": "nicotine",     "detected_intent": "addiction_drugs",        "relationship": "cross_high",   "severity_override": "high",   "video_key": "addiction_drugs",        "requires_escalation": False},
    # CROSS-HIGH: substance → gambling
    {"patient_addiction": "alcohol",      "detected_intent": "addiction_gambling",     "relationship": "cross_high",   "severity_override": "high",   "video_key": "addiction_gambling",     "requires_escalation": True},
    {"patient_addiction": "drugs",        "detected_intent": "addiction_gambling",     "relationship": "cross_high",   "severity_override": "high",   "video_key": "addiction_gambling",     "requires_escalation": True},
    # CROSS-MEDIUM
    {"patient_addiction": "alcohol",      "detected_intent": "addiction_gaming",       "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_gaming",       "requires_escalation": False},
    {"patient_addiction": "alcohol",      "detected_intent": "addiction_social_media", "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_social_media", "requires_escalation": False},
    {"patient_addiction": "alcohol",      "detected_intent": "addiction_nicotine",     "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_nicotine",     "requires_escalation": False},
    {"patient_addiction": "drugs",        "detected_intent": "addiction_gaming",       "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_gaming",       "requires_escalation": False},
    {"patient_addiction": "drugs",        "detected_intent": "addiction_social_media", "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_social_media", "requires_escalation": False},
    {"patient_addiction": "drugs",        "detected_intent": "addiction_nicotine",     "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_nicotine",     "requires_escalation": False},
    {"patient_addiction": "gambling",     "detected_intent": "addiction_gaming",       "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_gaming",       "requires_escalation": False},
    {"patient_addiction": "gaming",       "detected_intent": "addiction_gambling",     "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_gambling",     "requires_escalation": False},
    {"patient_addiction": "nicotine",     "detected_intent": "addiction_gaming",       "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_gaming",       "requires_escalation": False},
    {"patient_addiction": "nicotine",     "detected_intent": "addiction_social_media", "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_social_media", "requires_escalation": False},
    {"patient_addiction": "nicotine",     "detected_intent": "addiction_gambling",     "relationship": "cross_medium", "severity_override": "medium", "video_key": "addiction_gambling",     "requires_escalation": False},
    # SLEEP
    {"patient_addiction": "alcohol",      "detected_intent": "behaviour_sleep",        "relationship": "sleep",        "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "drugs",        "detected_intent": "behaviour_sleep",        "relationship": "sleep",        "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "gaming",       "detected_intent": "behaviour_sleep",        "relationship": "sleep",        "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "social_media", "detected_intent": "behaviour_sleep",        "relationship": "sleep",        "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "nicotine",     "detected_intent": "behaviour_sleep",        "relationship": "sleep",        "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "smoking",      "detected_intent": "behaviour_sleep",        "relationship": "sleep",        "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "gambling",     "detected_intent": "behaviour_sleep",        "relationship": "sleep",        "severity_override": "medium", "video_key": None, "requires_escalation": False},
    # RELAPSE DISCLOSURE (distinct from active craving)
    {"patient_addiction": "alcohol",      "detected_intent": "relapse_disclosure",     "relationship": "relapse",     "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "drugs",        "detected_intent": "relapse_disclosure",     "relationship": "relapse",     "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "gaming",       "detected_intent": "relapse_disclosure",     "relationship": "relapse",     "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "social_media", "detected_intent": "relapse_disclosure",     "relationship": "relapse",     "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "nicotine",     "detected_intent": "relapse_disclosure",     "relationship": "relapse",     "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "smoking",      "detected_intent": "relapse_disclosure",     "relationship": "relapse",     "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "gambling",     "detected_intent": "relapse_disclosure",     "relationship": "relapse",     "severity_override": "medium", "video_key": None, "requires_escalation": False},
    {"patient_addiction": "work",         "detected_intent": "relapse_disclosure",     "relationship": "relapse",     "severity_override": "medium", "video_key": None, "requires_escalation": False},
]

# ── Mock seed: patient records (matches frontend PATIENTS array) ──────────────
_MOCK_PATIENTS: Dict[str, dict] = {
    "PAT-001": {"patient_code": "PAT-001", "display_name": "Arjun",   "first_name": "Arjun",   "programme": "Alcohol Recovery",           "risk_level": "high"},
    "PAT-002": {"patient_code": "PAT-002", "display_name": "Priya",   "first_name": "Priya",   "programme": "Substance Use Disorder",     "risk_level": "medium"},
    "PAT-003": {"patient_code": "PAT-003", "display_name": "Karthik", "first_name": "Karthik", "programme": "Digital Addiction (Gaming)", "risk_level": "low"},
    "PAT-004": {"patient_code": "PAT-004", "display_name": "Divya",   "first_name": "Divya",   "programme": "Trauma & Anxiety",           "risk_level": "high"},
    "PAT-005": {"patient_code": "PAT-005", "display_name": "Rajesh",  "first_name": "Rajesh",  "programme": "Nicotine Cessation",         "risk_level": "low"},
    "PAT-006": {"patient_code": "PAT-006", "display_name": "Ananya",  "first_name": "Ananya",  "programme": "Digital Addiction (Social)", "risk_level": "medium"},
    "PAT-007": {"patient_code": "PAT-007", "display_name": "Suresh",  "first_name": "Suresh",  "programme": "Grief Support",              "risk_level": "medium"},
    "PAT-008": {"patient_code": "PAT-008", "display_name": "Lakshmi", "first_name": "Lakshmi", "programme": "Alcohol Recovery",           "risk_level": "critical"},
    "PAT-009": {"patient_code": "PAT-009", "display_name": "Vikram",  "first_name": "Vikram",  "programme": "Behavioural Addiction",      "risk_level": "low"},
    "PAT-010": {"patient_code": "PAT-010", "display_name": "Meera",   "first_name": "Meera",   "programme": "Substance Use (Discharged)", "risk_level": "low"},
}

# Pre-populate _patients so get_patient() works without ensure_patient() being called first
_patients.update({
    code: {**data, "id": str(uuid4())}
    for code, data in _MOCK_PATIENTS.items()
})

def ensure_patient(patient_code: str,
                   display_name: Optional[str] = None,
                   programme: Optional[str] = None,
                   assigned_to: Optional[str] = None) -> Optional[str]:
    """Mock: return patient ID (UUID-ish)"""
    if patient_code not in _patients:
        patient_id = str(uuid4())
        _patients[patient_code] = {
            "id": patient_id,
            "patient_code": patient_code,
            "display_name": display_name or f"Patient {patient_code}",
            "programme": programme or "General Support",
            "assigned_to": assigned_to,
            "created_at": datetime.now().isoformat()
        }
    return _patients[patient_code]["id"]

def get_patient(patient_code: str) -> Optional[dict]:
    """Mock: return patient by code"""
    if patient_code in _patients:
        return _patients[patient_code]
    return None

def get_patient_sessions(patient_code: str) -> List[dict]:
    """Mock: return all sessions for patient"""
    patient_id = _patients.get(patient_code, {}).get("id")
    if not patient_id:
        return []
    return [s for s in _sessions.values() if s.get("patient_id") == patient_id]

def get_patient_full_history(patient_code: str) -> List[dict]:
    """Mock: return full conversation history for patient"""
    patient_id = _patients.get(patient_code, {}).get("id")
    if not patient_id:
        return []
    
    history = []
    for session_id, session in _sessions.items():
        if session.get("patient_id") == patient_id:
            # Get all messages in this session
            msg_idx = 0
            while (session_id, msg_idx) in _conversations:
                history.append(_conversations[(session_id, msg_idx)])
                msg_idx += 1
    return history

def get_checkin_status(patient_code: str, hours: int = 12) -> dict:
    """Mock: return check-in status"""
    return {
        "has_recent_activity": False,
        "topics_covered": [],
        "continuity_prompt": None
    }


def get_patient_addictions(patient_code: str) -> List[dict]:
    """
    Mock: return ordered list of addiction records for a patient (primary first).
    Falls back to a single record synthesised from _patients if not in seed data.
    """
    if patient_code in _MOCK_ADDICTIONS:
        return _MOCK_ADDICTIONS[patient_code]
    # Graceful fallback: single-addiction from patient store (if set by test code)
    patient = _patients.get(patient_code, {})
    fallback_type = patient.get("addiction_type", "")
    if fallback_type:
        return [{"addiction_type": fallback_type, "is_primary": True, "severity": "high", "noted_at": None, "clinical_notes": None}]
    return []


def get_response_routing_table() -> List[dict]:
    """Mock: return the full routing table (mirrors SQL seed data)."""
    return list(_MOCK_ROUTING)

def get_recent_checkin_activity(patient_code: str, within_hours: int = 12) -> dict:
    """Mock: mimic DB check-in activity summary"""
    # Always return no recent activity in mock mode
    return {
        "has_activity": False,
        "display_name": None,
        "topics_discussed": [],
        "intents_seen": [],
        "last_active": None,
        "was_crisis": False,
        "message_count": 0,
    }

def ensure_session(session_id: str, patient_id: Optional[str] = None,
                   patient_code: Optional[str] = None) -> str:
    """Mock: create or return session"""
    if session_id not in _sessions:
        _sessions[session_id] = {
            "session_id": session_id,
            "patient_id": patient_id,
            "patient_code": patient_code,
            "created_at": datetime.now().isoformat(),
            "continuity_prompt": None,
            "prior_topics": []
        }
    return session_id

def update_session(session_id: str, role: str, message: str,
                   intent: Optional[str] = None, severity: Optional[str] = None,
                   show_resources: bool = False,
                   patient_id: Optional[str] = None,
                   patient_code: Optional[str] = None) -> None:
    """Mock: add message to session"""
    ensure_session(session_id, patient_id, patient_code)
    
    # Find next message index
    msg_idx = 0
    while (session_id, msg_idx) in _conversations:
        msg_idx += 1
    
    _conversations[(session_id, msg_idx)] = {
        "session_id": session_id,
        "role": role,
        "message": message,
        "intent": intent,
        "severity": severity,
        "show_resources": show_resources,
        "timestamp": datetime.now().isoformat()
    }

def get_session(session_id: str) -> dict:
    """Mock: return session"""
    ensure_session(session_id)
    return _sessions[session_id]

def clear_session(session_id: str) -> None:
    """Mock: clear session"""
    if session_id in _sessions:
        del _sessions[session_id]
    # Clear all messages in session
    keys_to_delete = [k for k in _conversations.keys() if k[0] == session_id]
    for k in keys_to_delete:
        del _conversations[k]

def get_session_summary(session_id: str) -> dict:
    """Mock: return session summary"""
    ensure_session(session_id)
    
    messages = []
    msg_idx = 0
    while (session_id, msg_idx) in _conversations:
        messages.append(_conversations[(session_id, msg_idx)])
        msg_idx += 1
    
    return {
        "session_id": session_id,
        "message_count": len(messages),
        "messages": messages
    }

def save_message(session_id: str, role: str, message: str,
                intent: Optional[str] = None,
                severity: Optional[str] = None,
                patient_id: Optional[str] = None,
                patient_code: Optional[str] = None) -> None:
    """Mock: save message (same as update_session)"""
    update_session(session_id, role, message, intent, severity,
                  patient_id=patient_id, patient_code=patient_code)

def log_policy_violation(session_id: str, violation_type: str,
                        details: str, user_message: str,
                        bot_response: str,
                        patient_id: Optional[str] = None) -> None:
    """Mock: log policy violation"""
    logger.warning(f"Policy violation [{violation_type}]: {details}")

def log_crisis_event(session_id: str, severity: str, user_message: str,
                    bot_response: str, intent: str,
                    patient_id: Optional[str] = None,
                    patient_code: Optional[str] = None) -> None:
    """Mock: log crisis event"""
    logger.warning(f"Crisis event [{severity}]: {user_message[:50]}...")

def get_pending_crisis_events() -> List[dict]:
    """Mock: return pending crisis events"""
    return []

def get_policy_violation_summary() -> List[dict]:
    """Mock: return policy violation summary"""
    return []

def get_session_history(session_id: str) -> List[dict]:
    """Mock: return session history"""
    messages = []
    msg_idx = 0
    while (session_id, msg_idx) in _conversations:
        messages.append(_conversations[(session_id, msg_idx)])
        msg_idx += 1
    return messages

def get_all_sessions() -> List[dict]:
    """Mock: return all sessions"""
    return list(_sessions.values())

def get_crisis_sessions() -> List[dict]:
    """Mock: return crisis sessions"""
    return []

def save_patient_score(session_id: str, patient_code: Optional[str],
                      score_group: str, score: int, intent: Optional[str] = None,
                      patient_id: Optional[str] = None) -> None:
    """Mock: save patient score"""
    logger.info(f"Score saved: {score_group}={score}")

def build_checkin_greeting(patient_code: str) -> Optional[dict]:
    """Mock: build check-in greeting"""
    return None

def update_session_meta(session_id: str, key: str, value: any) -> None:
    """Mock: update session metadata"""
    if session_id in _sessions:
        _sessions[session_id][key] = value
