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
# PAT-001 = Arjun Rao       UC 1.1  Alcohol primary          — late-night loneliness, Bengaluru
# PAT-002 = Emily Carter    UC 1.2  Alcohol primary          — after-work stress, New York
# PAT-003 = Rohan Sharma    UC 2.1  Gaming primary           — study-break procrastination, Delhi
# PAT-004 = Oliver Thompson UC 2.2  Gaming primary           — late-night one-more-game, London
# PAT-005 = Priya Nair      UC 3.1  Drugs primary            — emotional pain at night, Mumbai
# PAT-006 = Jordan Reyes    UC 3.2  Drugs primary            — anger after argument, Los Angeles
# PAT-007 = Karthik Reddy   UC 4.1  Nicotine primary         — stressed work-break, Bengaluru
# PAT-008 = Ishan Rao       UC 5.1  Alcohol + Behavioral     — festival pressure, Bengaluru
# PAT-009 = Sneha Patil     UC 5.2  Alcohol + Nicotine + Behavioral — setback shame, Bengaluru
# PAT-010 = Alex Chen       UC 5.3  Alcohol + Gaming         — slip after 3 weeks, Toronto
# PAT-011 = Taylor Brooks   UC 5.4  Alcohol + Social Media   — inner conflict before going out, New York
# PAT-012 = Aravind Reddy   UC 6.1  Social Media primary     — morning scroll habit, Hyderabad
# PAT-013 = Sophia Martinez UC 6.2  Social Media primary     — excitement posting urge, Los Angeles
_MOCK_ADDICTIONS: Dict[str, List[dict]] = {
    "PAT-001": [
        {"addiction_type": "alcohol",      "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Primary alcohol use disorder; daily drinking to cope with loneliness; craving 6–7/10"},
    ],
    "PAT-002": [
        {"addiction_type": "alcohol",      "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Primary alcohol use disorder; after-work stress drinking; craving 7–8/10; stress 8/10"},
    ],
    "PAT-003": [
        {"addiction_type": "gaming",       "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Primary gaming disorder; study-break procrastination gaming; craving 7–8/10; student triggers during exam periods"},
    ],
    "PAT-004": [
        {"addiction_type": "gaming",       "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Primary gaming disorder; late-night one-more-game pattern; craving 8–9/10; sleep severely impacted"},
    ],
    "PAT-005": [
        {"addiction_type": "drugs",        "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Primary substance use disorder; nighttime emotional distress craving; post-breakup isolation; craving 7–8/10"},
    ],
    "PAT-006": [
        {"addiction_type": "drugs",        "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Primary substance use disorder; anger/argument trigger pattern; craving spikes after emotional conflict; craving 8–9/10"},
    ],
    "PAT-007": [
        {"addiction_type": "nicotine",     "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Primary nicotine dependence; stress-triggered work-break smoking; craving 7–8/10; deadline pressure trigger"},
    ],
    "PAT-008": [
        {"addiction_type": "alcohol",      "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Alcohol primary; multi-addiction pattern; social/festival pressure trigger; craving 8–9/10"},
        {"addiction_type": "behavioral",   "is_primary": False, "severity": "medium", "noted_at": None, "clinical_notes": "Comorbid behavioural compulsion (noted at intake); can include nicotine"},
    ],
    "PAT-009": [
        {"addiction_type": "alcohol",      "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Alcohol primary; 12-day recovery streak broken by missed check-in; all-or-nothing thinking pattern"},
        {"addiction_type": "nicotine",     "is_primary": False, "severity": "medium", "noted_at": None, "clinical_notes": "Comorbid nicotine dependence"},
        {"addiction_type": "behavioral",   "is_primary": False, "severity": "medium", "noted_at": None, "clinical_notes": "Comorbid behavioural compulsion"},
    ],
    "PAT-010": [
        {"addiction_type": "alcohol",      "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Alcohol primary; 3-week recovery streak; slipped once; shame and 'what's the point' thinking; craving 7/10"},
        {"addiction_type": "gaming",       "is_primary": False, "severity": "medium", "noted_at": None, "clinical_notes": "Comorbid gaming disorder (noted at intake)"},
    ],
    "PAT-011": [
        {"addiction_type": "alcohol",      "is_primary": True,  "severity": "high",   "noted_at": None, "clinical_notes": "Alcohol primary; early recovery; social situation trigger — going out with friends who drink; craving 8/10"},
        {"addiction_type": "social_media", "is_primary": False, "severity": "medium", "noted_at": None, "clinical_notes": "Comorbid social media/internet overuse (noted at intake)"},
    ],
    "PAT-012": [
        {"addiction_type": "social_media", "is_primary": True,  "severity": "medium", "noted_at": None, "clinical_notes": "Primary social media compulsion; morning phone-scrolling habit on waking; craving 7–8/10; mood impacted after use"},
    ],
    "PAT-013": [
        {"addiction_type": "social_media", "is_primary": True,  "severity": "medium", "noted_at": None, "clinical_notes": "Primary social media compulsion; reward-seeking/posting urge triggered by positive events; craving 8/10"},
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
    # UC 1.1 — Alcohol, Indian
    "PAT-001": {"patient_code": "PAT-001", "display_name": "Arjun",   "first_name": "Arjun",   "last_name": "Rao",       "programme": "Alcohol Recovery",                   "risk_level": "high",   "risk_score": 78, "age": 28, "occupation": "IT Professional",          "city": "Bengaluru",    "country": "India"},
    # UC 1.2 — Alcohol, Global
    "PAT-002": {"patient_code": "PAT-002", "display_name": "Emily",   "first_name": "Emily",   "last_name": "Carter",    "programme": "Alcohol Recovery",                   "risk_level": "high",   "risk_score": 82, "age": 34, "occupation": "Marketing Executive",      "city": "New York",     "country": "United States"},
    # UC 2.1 — Gaming, Indian
    "PAT-003": {"patient_code": "PAT-003", "display_name": "Rohan",   "first_name": "Rohan",   "last_name": "Sharma",    "programme": "Gaming Addiction Recovery",           "risk_level": "high",   "risk_score": 76, "age": 19, "occupation": "Engineering Student",      "city": "Delhi",        "country": "India"},
    # UC 2.2 — Gaming, Global
    "PAT-004": {"patient_code": "PAT-004", "display_name": "Oliver",  "first_name": "Oliver",  "last_name": "Thompson",  "programme": "Gaming Addiction Recovery",           "risk_level": "high",   "risk_score": 79, "age": 17, "occupation": "Student (A-levels)",       "city": "London",       "country": "United Kingdom"},
    # UC 3.1 — Substance Use, Indian
    "PAT-005": {"patient_code": "PAT-005", "display_name": "Priya",   "first_name": "Priya",   "last_name": "Nair",      "programme": "Substance Use Disorder",             "risk_level": "high",   "risk_score": 80, "age": 26, "occupation": "Software Engineer",        "city": "Mumbai",       "country": "India"},
    # UC 3.2 — Substance Use, Global
    "PAT-006": {"patient_code": "PAT-006", "display_name": "Jordan",  "first_name": "Jordan",  "last_name": "Reyes",     "programme": "Substance Use Disorder",             "risk_level": "high",   "risk_score": 83, "age": 31, "occupation": "Graphic Designer (Freelance)", "city": "Los Angeles", "country": "United States"},
    # UC 4.1 — Nicotine, Indian
    "PAT-007": {"patient_code": "PAT-007", "display_name": "Karthik", "first_name": "Karthik", "last_name": "Reddy",     "programme": "Nicotine Cessation",                 "risk_level": "high",   "risk_score": 74, "age": 29, "occupation": "Software Engineer",        "city": "Bengaluru",    "country": "India"},
    # UC 5.1 — Agnostic, Indian
    "PAT-008": {"patient_code": "PAT-008", "display_name": "Ishan",   "first_name": "Ishan",   "last_name": "Rao",       "programme": "Multi-Addiction Recovery",            "risk_level": "high",   "risk_score": 78, "age": 25, "occupation": "Marketing Executive",      "city": "Bengaluru",    "country": "India"},
    # UC 5.2 — Agnostic, Indian
    "PAT-009": {"patient_code": "PAT-009", "display_name": "Sneha",   "first_name": "Sneha",   "last_name": "Patil",     "programme": "Multi-Addiction Recovery",            "risk_level": "high",   "risk_score": 75, "age": 27, "occupation": "Data Analyst",             "city": "Bengaluru",    "country": "India"},
    # UC 5.3 — Agnostic, Global
    "PAT-010": {"patient_code": "PAT-010", "display_name": "Alex",    "first_name": "Alex",    "last_name": "Chen",      "programme": "Alcohol Recovery (with Gaming)",      "risk_level": "high",   "risk_score": 77, "age": 33, "occupation": "Software Developer",       "city": "Toronto",      "country": "Canada"},
    # UC 5.4 — Agnostic, Global
    "PAT-011": {"patient_code": "PAT-011", "display_name": "Taylor",  "first_name": "Taylor",  "last_name": "Brooks",    "programme": "Alcohol Recovery (with Behavioural)", "risk_level": "high",   "risk_score": 76, "age": 29, "occupation": "Photographer (Freelance)", "city": "New York",     "country": "United States"},
    # UC 6.1 — Social Media, Indian
    "PAT-012": {"patient_code": "PAT-012", "display_name": "Aravind", "first_name": "Aravind", "last_name": "Reddy",     "programme": "Digital Addiction (Social Media)",    "risk_level": "medium", "risk_score": 68, "age": 21, "occupation": "Engineering Student",      "city": "Hyderabad",    "country": "India"},
    # UC 6.2 — Social Media, Global
    "PAT-013": {"patient_code": "PAT-013", "display_name": "Sophia",  "first_name": "Sophia",  "last_name": "Martinez",  "programme": "Digital Addiction (Social Media)",    "risk_level": "medium", "risk_score": 66, "age": 27, "occupation": "Content Creator (Freelance)", "city": "Los Angeles", "country": "United States"},
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
