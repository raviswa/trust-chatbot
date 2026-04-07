"""
chatbot_engine.py — Refactored Mental Health Chatbot Engine (Microservices Architecture)

Orchestrates multiple microservices for:
- Context-aware minimal-question conversations
- Intent classification
- Safety-first response generation
- Policy compliance

Architecture:
1. Intent Classifier Service - Classifies user intent
2. Context Manager Service - Tracks patient context vector
3. Response Generator Service - Generates personalized responses
4. Safety Checker Service - Validates safety and policies
"""

import json
import hashlib
import logging
import os
import re
from datetime import datetime
from typing import Optional, Dict, List

from clause_analysis import analyze_recovery_clause, analyze_relationship_clause
from services_pipeline import IntentClassifier, ResponseGenerator, SafetyChecker, PolicyChecker, _init_response_router
from db_comprehensive_update import update_all_tables_from_chatbot_interaction
from patient_context import (
    build_context, format_context_for_prompt, get_opening_line,
    get_current_layer, enforce_5layer_rules, record_video_shown,
    should_show_video, add_layer_awareness_to_system_prompt,
    get_tone_mode,
)
from patient_context import (
    get_or_create_context, update_context_from_turn, clear_context,
    synthesize_patient_context, SubjectiveState, PhysiologicalState, HistoricalContext,
    build_clinical_context_block, get_response_length_instruction, build_enriched_query,
)
from greeting_generator import generate_greeting_message
from video_map import get_video, get_video_for_patient, get_video_for_intents
try:
    from conversational_intake import (
        coerce_profile_flags,
        is_intake_active,
        is_intake_complete,
        should_start_intake,
        handle_intake_turn,
        init_intake,
        restore_intake_from_db,
        INTAKE_QUESTIONS,
        INTAKE_KEY,
    )
except ImportError:
    def coerce_profile_flags(profile):          return profile          # type: ignore[misc]
    def is_intake_active(session):              return False            # type: ignore[misc]
    def is_intake_complete(session):            return False            # type: ignore[misc]
    def should_start_intake(session, count):    return False            # type: ignore[misc]
    def handle_intake_turn(msg, session):       return None             # type: ignore[misc]
    def init_intake(session, is_returning=False): return session        # type: ignore[misc]
    def restore_intake_from_db(session, profile): return False         # type: ignore[misc]
    INTAKE_QUESTIONS = {}                                               # type: ignore[misc]
    INTAKE_KEY = "intake_state"                                         # type: ignore[misc]



# Database — connection priority:
#   1. db_postgres  (direct psycopg2 — when a real PG_HOST / DATABASE_URL is set)
#   2. db_supabase  (Supabase SDK — when SUPABASE_URL + SUPABASE_KEY are present)
#   3. db_mock      (in-memory fallback for offline / CI environments)
logger_startup = logging.getLogger(__name__)

_DB_BACKEND = None  # tracks which backend is active

try:
    from db_postgres import (
        ensure_patient, get_patient, get_patient_sessions,
        get_patient_full_history, get_checkin_status,
        ensure_session, update_session_meta, save_message,
        log_policy_violation, log_crisis_event,
        get_pending_crisis_events, get_policy_violation_summary,
        get_session_history, get_all_sessions, get_crisis_sessions,
        get_conversation_stats, get_top_intents,
        get_latest_daily_checkin, get_latest_wearable_reading, get_historical_context,
        save_context_vector, get_patient_context_vectors, get_context_vector_trends, get_contradiction_patterns,
        get_watched_video_ids, get_patient_onboarding, save_intake_progress,
        get_patient_addictions, get_response_routing_table,
    )
    # Verify the connection is actually reachable before committing to this backend.
    # db_postgres uses a lazy pool, so the import alone never raises even if postgres
    # is unavailable — we must probe it explicitly here.
    import psycopg2 as _psycopg2, os as _os
    _probe_dsn = _os.getenv("DATABASE_URL") or (
        f"host={_os.getenv('PG_HOST','localhost')} "
        f"port={_os.getenv('PG_PORT','5432')} "
        f"dbname={_os.getenv('PG_DB','chatbot_db')} "
        f"user={_os.getenv('PG_USER','chatbot_user')} "
        f"password={_os.getenv('PG_PASSWORD','')} "
        f"connect_timeout=3"
    )
    _probe = _psycopg2.connect(_probe_dsn)
    _probe.close()
    del _probe, _probe_dsn, _psycopg2, _os
    _DB_BACKEND = "postgres"
    logger_startup.info("✓ Using PostgreSQL backend (db_postgres)")
except Exception as _pg_err:
    logger_startup.warning(f"PostgreSQL unavailable ({type(_pg_err).__name__}: {str(_pg_err)[:80]}), trying Supabase backend...")
    try:
        import os as _os
        if not _os.getenv("SUPABASE_URL") or not _os.getenv("SUPABASE_KEY"):
            raise EnvironmentError("SUPABASE_URL / SUPABASE_KEY not set")
        from db_supabase import (
            ensure_patient, get_patient, get_patient_sessions,
            get_patient_full_history, get_checkin_status,
            ensure_session, update_session_meta, save_message,
            log_policy_violation, log_crisis_event,
            get_pending_crisis_events, get_policy_violation_summary,
            get_session_history, get_all_sessions, get_crisis_sessions,
            get_conversation_stats, get_top_intents,
            get_latest_daily_checkin, get_latest_wearable_reading, get_historical_context,
            save_context_vector, get_patient_context_vectors, get_context_vector_trends, get_contradiction_patterns,
            get_watched_video_ids, get_patient_onboarding, save_intake_progress,
            get_patient_addictions, get_response_routing_table,
        )
        # Quick connectivity probe — fetch one row from patients table
        get_patient("__probe__")
        _DB_BACKEND = "supabase"
        del _os
        logger_startup.info("✓ Using Supabase backend (db_supabase)")
    except Exception as _sb_err:
        logger_startup.warning(f"Supabase unavailable ({type(_sb_err).__name__}: {str(_sb_err)[:80]}), falling back to mock database")
        from db_mock import (
            ensure_patient, get_patient, get_patient_sessions,
            get_patient_full_history, get_checkin_status,
            ensure_session, update_session_meta, save_message,
            log_policy_violation, log_crisis_event,
            get_pending_crisis_events, get_policy_violation_summary,
            get_session_history, get_all_sessions, get_crisis_sessions,
            get_patient_addictions, get_response_routing_table,
        )
        _DB_BACKEND = "mock"
        def get_conversation_stats(session_id):
            return {"total_messages": 0, "user_messages": 0, "assistant_messages": 0}
        def get_top_intents(limit=10):
            return []
        def get_latest_daily_checkin(patient_code, within_hours=24):
            return None
        def get_latest_wearable_reading(patient_code, within_hours=48):
            return None
        def get_historical_context(patient_code, days_back=30):
            return {"recurring_themes": [], "recent_intents": [], "crisis_history": False, "last_session_timestamp": None, "days_since_last_session": None, "session_count": 0}
        def save_context_vector(patient_id, patient_code, session_id, context_vector, greeting_text):
            return None
        def get_patient_context_vectors(patient_code, limit=50):
            return []
        def get_context_vector_trends(patient_code, days=30):
            return {"risk_trend": [], "tone_distribution": {}, "theme_distribution": {}, "contradiction_count": 0, "avg_data_freshness": {}, "greetings_generated": 0}
        def get_contradiction_patterns(patient_code=None, limit=100):
            return []
        def get_watched_video_ids(patient_id):
            return set()
        def get_patient_onboarding(patient_code):
            addictions = get_patient_addictions(patient_code)
            if not addictions:
                return None
            primary = next((a for a in addictions if a.get("is_primary")), addictions[0])
            patient = get_patient(patient_code) or {}
            return {
                "name": patient.get("display_name", f"Patient {patient_code}"),
                "addiction_type": primary.get("addiction_type", ""),
                "addictions": addictions,
                "baseline_mood": [],
                "primary_triggers": [],
                "support_network": {},
                "work_status": "",
                "last_intake_phase": 0,
                "intake_consent_given": False,
            }
        def save_intake_progress(patient_code, phase, pct):
            pass

# Import language safety and RAG
try:
    from language_sanitiser import sanitise_response, check_self_stigma
    from rag_pipeline import retrieve, assemble_context, format_citations
    from ethical_policy import (
        check_policy,
        validate_crisis_response,
        POLICY_SUMMARY,
        POLICY_DISCLOSURE_SHORT,
    )
except Exception as e:
    logger_startup.warning(f"Optional modules unavailable: {e}")
    def sanitise_response(text): return text
    def check_self_stigma(text): return None
    def retrieve(query, top_k=5, seen_chunk_ids=None, severity=None): return []  # type: ignore[misc]
    def assemble_context(docs): return ""
    def format_citations(docs): return []
    def check_policy(text): return {"policy_check": "passed"}
    def validate_crisis_response(text): return True
    POLICY_SUMMARY = {"status": "missing"}
    POLICY_DISCLOSURE_SHORT = "Policy information not available"

# Import semantic crisis detector (3-tier: exact → fuzzy → embedding)
try:
    from crisis_detector import get_crisis_detector, CONFIDENCE_INTERCEPT, CONFIDENCE_WARN
    _crisis_detector = get_crisis_detector()
    logger_startup.info("✓ CrisisDetector loaded (3-tier semantic detection active)")
except Exception as _cd_err:
    logger_startup.warning(f"CrisisDetector unavailable: {_cd_err}")
    _crisis_detector = None
    CONFIDENCE_INTERCEPT = 0.72
    CONFIDENCE_WARN = 0.45

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# MICROSERVICES INITIALIZATION
# ────────────────────────────────────────────────────────────────────────────

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_INTENTS_PATH = os.path.join(_BACKEND_DIR, "intents.json")

intent_classifier = IntentClassifier(intents_path=_INTENTS_PATH)
safety_checker = SafetyChecker()
policy_checker = PolicyChecker()
response_generator = ResponseGenerator(intents_path=_INTENTS_PATH)

# Initialise ResponseRouter from DB routing table (falls back to code rules if DB unavailable)
try:
    _routing_rows = get_response_routing_table()
    _init_response_router(_routing_rows)
    logger_startup.info(f"✓ ResponseRouter initialised with {len(_routing_rows)} routing rules")
except Exception as _rr_err:
    logger_startup.warning(f"Could not load routing table ({_rr_err}), using code-based fallback")
    _init_response_router([])

# Session cache for context window and conversation history
_sessions: Dict[str, dict] = {}


# ── CLINICAL HANDSHAKE: Binary feedback protocol (Layer 5) ───────────────────
# Intercepts special feedback tokens in Layer 1.65 before the full LLM pipeline.
# Token contract (sent by FeedbackCard buttons in the frontend):
#   “feedback_thumbsup”          → Stabilize exit (Rule 2)
#   “feedback_pivot_overwhelmed”  → Co-presence Plan B (Rule 3)
#   “feedback_pivot_urge”         → Somatic reset Plan B (Rule 3)
#   “feedback_pivot_stealth”      → Stealth grounding Plan B (Rule 3)
#   “quiet” / “sos”              → Opt-out / final closure (Rule 4)

_FEEDBACK_THUMBSUP_TOKENS: frozenset = frozenset({"feedback_thumbsup", "👍"})
_FEEDBACK_PIVOT_TOKENS: Dict[str, str] = {
    "feedback_pivot_overwhelmed": "overwhelmed",
    "feedback_pivot_urge":        "urge",
    "feedback_pivot_stealth":     "stealth",
    "feedback_pivot_other":       "other",
}
_FEEDBACK_OPTOUT_TOKENS: frozenset = frozenset({"quiet", "sos"})
_MAX_FEEDBACK_PIVOT_RETRIES = 1
_FEEDBACK_ALL_TOKENS: frozenset = frozenset(
    set(_FEEDBACK_THUMBSUP_TOKENS) | set(_FEEDBACK_PIVOT_TOKENS.keys()) | set(_FEEDBACK_OPTOUT_TOKENS)
)

_HANDSHAKE_STABILIZE = (
    "Noted. That tool is now marked as a high-value resource for you.\n\n"
    "Take a ten-second breath to let this feeling of control settle in.\n\n"
    "I'm standing by. If the urge shifts or returns, just type 'Help' or tap a tool below. "
    "Go ahead with your next task when you're ready."
)

_HANDSHAKE_OPTOUT = (
    "Your only job for the next hour is to stay hydrated and notice your breathing. "
    "I am right here if the wave peaks again."
)

_HANDSHAKE_MAX_RETRY_EXIT = (
    "Thank you for telling me this still is not landing. That is not a failure.\n\n"
    "Let's pause the tool loop here. Choose what is safest right now: '\n"
    "Quiet' for a low-pressure check-in, or 'SOS' if you want immediate extra support.\n\n"
    "If you want to continue later, I can switch to a different style (short, practical, or reflective)."
)

_SOS_RESPONSE = (
    "Reaching out to your primary contact now.\n\n"
    "While you wait: press both feet firmly to the floor. Breathe in for four counts, "
    "out for six. You are not alone and this moment will pass.\n\n"
    "UK Crisis Line: 0808 808 8000  •  US: 988 (Suicide & Crisis Lifeline)  •  "
    "Text HOME to 741741 (Crisis Text Line)."
)

_HANDSHAKE_PIVOT: Dict[str, str] = {
    "overwhelmed": (
        "Understood. Let's switch approach. "
        "Let's try Co-Presence instead.\n\n"
        "I'm right here with you. No need to do anything at all. Just breathe.\n\n"
        "You can tap 👍 if this helps, or 👎 for one more pivot. "
        "You can also type 'Quiet' for a five-minute silent frame, or 'SOS' for your primary contact."
    ),
    "urge": (
        "Understood. Let's switch approach. "
        "Let's try a somatic reset instead.\n\n"
        "Splash cold water on your face right now. Hold there for ten seconds. "
        "This activates your dive reflex and slows your heart rate.\n\n"
        "You can tap 👍 if this helps, or 👎 for one more pivot. "
        "You can also type 'Quiet' for a five-minute silent frame, or 'SOS' for your primary contact."
    ),
    "stealth": (
        "Understood. Let's switch approach. "
        "Let's try a stealth grounding exercise instead.\n\n"
        "Close your eyes for three seconds. Name five things you can see, "
        "four you can physically touch, three you can hear. Eyes open. Breathe.\n\n"
        "You can tap 👍 if this helps, or 👎 for one more pivot. "
        "You can also type 'Quiet' for a five-minute silent frame, or 'SOS' for your primary contact."
    ),
    "other": (
        "Thank you for telling me this missed the mark. "
        "Say in your own words what felt off, and I will adapt directly to that.\n\n"
        "A short line is enough, for example: too long, too generic, wrong focus, or not practical now."
    ),
}

_HANDSHAKE_SAFETY_OVERRIDE = (
    "I hear that things feel intense right now. Let's pause the feedback loop and focus on safety first.\n\n"
    "If you feel at risk, type 'SOS' now for immediate crisis support details. "
    "If you can, place both feet on the floor and take one slow breath in, longer breath out."
)


def _handle_feedback_intercept(message: str, session: dict) -> Optional[Dict]:
    """
    Layer 1.65 — Clinical Handshake intercept.

    Returns a ready-to-return response dict when the message is a feedback token,
    or None to let the normal LLM/RAG pipeline continue.

    No questions are asked. No open-ended prompts issued.
    Transitions the patient to Equanimity (Stabilize) or Alternative Action (Re-Route).
    """
    msg_stripped = message.strip()
    msg_lower    = msg_stripped.lower()

    # Safety override: when risk has escalated, feedback loop is suspended and
    # we route to crisis-aware stabilisation language.
    _safety_intents = {
        "crisis_suicidal", "crisis_abuse", "behaviour_self_harm",
        "psychosis_indicator", "severe_distress",
    }
    _risk_escalated = (
        session.get("last_intent") in _safety_intents
        or "high" in session.get("severity_flags", [])
        or "critical" in session.get("severity_flags", [])
    )
    if msg_lower in _FEEDBACK_ALL_TOKENS and _risk_escalated:
        session["pending_feedback_intent"] = None
        session["feedback_pivot_retries"] = 0
        session["awaiting_feedback_after_pivot"] = False
        session["feedback_prompt_suppressed"] = True
        return {
            "response":       _HANDSHAKE_SAFETY_OVERRIDE,
            "intent":         "feedback_safety_override",
            "severity":       "high",
            "show_resources": True,
            "citations":      [],
            "show_score":     False,
            "video":          None,
            "show_feedback":  False,
        }

    # — Rule 2: Thumbs-up → Stabilize exit —
    if msg_lower in _FEEDBACK_THUMBSUP_TOKENS:
        _pending = session.get("pending_feedback_intent")
        if _pending:
            session.setdefault("ineffective_interventions", set()).discard(_pending)
        session["pending_feedback_intent"] = None
        session["feedback_pivot_retries"] = 0
        session["awaiting_feedback_after_pivot"] = False
        session["feedback_prompt_suppressed"] = False
        return {
            "response":       _HANDSHAKE_STABILIZE,
            "intent":         "feedback_thumbsup",
            "severity":       "low",
            "show_resources": False,
            "citations":      [],
            "show_score":     False,
            "video":          None,
            "show_feedback":  False,
        }

    # — Rule 3: Pivot selection → Re-Route exit with Plan B tool —
    if msg_lower in _FEEDBACK_PIVOT_TOKENS:
        _pending = session.get("pending_feedback_intent")
        if _pending:
            session.setdefault("ineffective_interventions", set()).add(_pending)

        retries = int(session.get("feedback_pivot_retries", 0))
        if retries >= _MAX_FEEDBACK_PIVOT_RETRIES:
            session["pending_feedback_intent"] = None
            session["feedback_pivot_retries"] = 0
            session["awaiting_feedback_after_pivot"] = False
            session["feedback_prompt_suppressed"] = True
            return {
                "response":       _HANDSHAKE_MAX_RETRY_EXIT,
                "intent":         "feedback_loop_exit",
                "severity":       "low",
                "show_resources": False,
                "citations":      [],
                "show_score":     False,
                "video":          None,
                "show_feedback":  False,
            }

        pivot_type = _FEEDBACK_PIVOT_TOKENS[msg_lower]
        session["feedback_pivot_retries"] = retries + 1
        session["awaiting_feedback_after_pivot"] = pivot_type != "other"
        session["awaiting_feedback_free_text"] = pivot_type == "other"
        return {
            "response":       _HANDSHAKE_PIVOT[pivot_type],
            "intent":         f"feedback_pivot_{pivot_type}",
            "severity":       "low",
            "show_resources": False,
            "citations":      [],
            "show_score":     False,
            "video":          None,
            # Allow one additional thumbs-up/down check after first pivot,
            # except the explicit free-text branch.
            "show_feedback":  pivot_type != "other",
        }

    # — Rule 4: Opt-out / final closure —
    if msg_lower == "sos":
        session["pending_feedback_intent"] = None
        session["feedback_pivot_retries"] = 0
        session["awaiting_feedback_after_pivot"] = False
        session["awaiting_feedback_free_text"] = False
        session["feedback_prompt_suppressed"] = True
        return {
            "response":       _SOS_RESPONSE,
            "intent":         "feedback_sos",
            "severity":       "high",
            "show_resources": True,
            "citations":      [],
            "show_score":     False,
            "video":          None,
            "show_feedback":  False,
        }

    if msg_lower == "quiet":
        session["pending_feedback_intent"] = None
        session["feedback_pivot_retries"] = 0
        session["awaiting_feedback_after_pivot"] = False
        session["awaiting_feedback_free_text"] = False
        session["feedback_prompt_suppressed"] = True
        return {
            "response":       _HANDSHAKE_OPTOUT,
            "intent":         "feedback_optout",
            "severity":       "low",
            "show_resources": False,
            "citations":      [],
            "show_score":     False,
            "video":          None,
            "show_feedback":  False,
        }

    return None


def get_session(session_id: str) -> Dict:
    """Get or create session."""
    if session_id not in _sessions:
        _sessions[session_id] = {
            "history": [],
            "started_at": datetime.now().isoformat(),
            "last_intent": None,
            "severity_flags": [],
            "message_count": 0,
            "last_question_asked": False,
            "seen_chunk_ids": set(),  # RAG deduplication: tracks chunks shown this session
            "pending_feedback_intent": None,  # Clinical Handshake: last delivered intervention intent
            "feedback_pivot_retries": 0,      # Max retries for thumbs-down pivot loop
            "awaiting_feedback_after_pivot": False,
            "awaiting_feedback_free_text": False,
            "feedback_prompt_suppressed": False,
            "ineffective_interventions": set(),
            "last_relationship_mentions": [],
        }
    return _sessions[session_id]


def _intent_name_to_display(intent: str) -> str:
    """Convert intent tag to readable topic label."""
    labels = {
        "mood_sad": "feelings of sadness",
        "mood_anxious": "anxiety",
        "mood_angry": "anger and frustration",
        "mood_lonely": "loneliness",
        "mood_guilty": "feelings of guilt",
        "behaviour_sleep": "sleep difficulties",
        "behaviour_eating": "eating patterns",
        "trigger_trauma": "trauma",
        "trigger_stress": "stress management",
        "trigger_relationship": "relationship challenges",
        "trigger_grief": "grief and loss",
        "trigger_financial": "financial stress",
        "addiction_drugs": "substance use",
        "addiction_alcohol": "alcohol use",
        "addiction_nicotine": "nicotine use",
        "addiction_gaming": "gaming habits",
        "addiction_social_media": "social media use",
        "addiction_gambling": "gambling urges",
        "addiction_food": "compulsive eating",
        "addiction_work": "overworking",
        "addiction_shopping": "compulsive shopping",
        "addiction_pornography": "compulsive sexual content use",
    }
    return labels.get(intent, "what you shared earlier")


_ADDICTION_TYPE_TO_INTENT: Dict[str, str] = {
    "alcohol":      "addiction_alcohol",
    "drugs":        "addiction_drugs",
    "gaming":       "addiction_gaming",
    "social_media": "addiction_social_media",
    "nicotine":     "addiction_nicotine",
    "smoking":      "addiction_nicotine",
    "gambling":     "addiction_gambling",
    "work":         "addiction_work",
    "food":         "addiction_food",
    "eating":       "addiction_food",
    "sex":          "addiction_pornography",
    "porn":         "addiction_pornography",
    "pornography":  "addiction_pornography",
    "shopping":     "addiction_shopping",
}

_ADDICTION_INTENTS: frozenset = frozenset({
    "addiction_alcohol",
    "addiction_drugs",
    "addiction_gaming",
    "addiction_social_media",
    "addiction_nicotine",
    "addiction_gambling",
    "addiction_food",
    "addiction_work",
    "addiction_shopping",
    "addiction_pornography",
})

_ADDICTION_OVERRIDE_PATTERNS: Dict[str, tuple[str, ...]] = {
    "addiction_alcohol": (
        "drinking", "drink", "alcohol", "alcoholic", "beer", "wine", "whiskey",
        "drunk", "sober", "sobriety", "rehab", "detox", "bottle", "binge drinking",
        "blackout", "quit drinking", "problem with alcohol", "worried about my drinking",
        # lapse / relapse / recovery timeline language
        "make it a week", "didn't make it a week", "did not make it a week",
        "did not even make it", "didn't even make it", "make it through the week",
        "back to drinking", "started drinking again", "relapsed on alcohol",
        "fell off the wagon", "back to square one",
    ),
    "addiction_gaming": (
        "gaming", "game all night", "cannot stop gaming", "can't stop gaming",
        "gamer", "skip meals to game", "instead of sleeping", "lost relationships because of gaming",
    ),
    "addiction_social_media": (
        "social media", "scrolling", "instagram", "tiktok", "notifications",
        "followers", "likes", "phone down", "screen time", "fomo",
    ),
    "addiction_nicotine": (
        "nicotine", "smoking", "smoke", "cigarette", "cigarettes", "vape", "vaping",
        "pack a day", "quit smoking", "nicotine patches",
    ),
    "addiction_gambling": (
        "gambling", "gamble", "betting", "bets", "casino", "sports betting",
        "chasing losses", "win back what i lost", "borrowed money to gamble",
    ),
    "addiction_food": (
        "binge eat", "food is my addiction", "eat compulsively", "eat in secret",
        "out of control around food", "emotional eating", "junk food", "comfort eating",
    ),
    "addiction_work": (
        "workaholic", "cannot stop working", "can't stop working", "work 16 hours",
        "guilty when i'm not working", "guilty when i am not working", "rest feels like laziness",
        "switch off from work", "my identity is tied to my work",
        # overworking / compulsive work language
        "overworking", "overwork", "quit overworking", "stop overworking",
        "cannot stop overworking", "can't stop overworking", "hide my overworking",
        "working too much", "work too much", "addicted to work", "addicted to working",
        "work addiction", "cannot switch off", "can't switch off",
        "working all the time", "work all the time",
    ),
    "addiction_shopping": (
        "shopping addiction", "shop online", "online shopping", "buy things i don't need",
        "hide purchases", "retail therapy", "spent all my money shopping",
        # standalone and behavioural shopping markers
        "quit shopping", "stop shopping", "cannot stop shopping", "can't stop shopping",
        "hide my shopping", "shopping from my partner", "shopping every",
        "shopping problem", "compulsive shopping", "shopping habit",
        "hide shopping", "shopping is my", "addicted to shopping",
        "i shop", "i hide my shopping", "lie about how often i shop",
        "shopping is the only", "shopping is how", "shopping is what",
    ),
    "addiction_pornography": (
        "porn", "pornography", "watching porn", "compulsive pornography",
        "porn use", "porn has replaced real intimacy",
    ),
    "addiction_drugs": (
        # daily-use / frequency questions
        "use every day", "use every night", "use every week", "using every day",
        "using every night", "using every week", "use daily", "using daily",
        "bad to use", "is it bad to use", "okay to use", "is it okay to use",
        "safe to use", "is it safe to use", "harmful to use", "is it harmful",
        "how much is too much", "using too much", "using too often",
        "is it normal to use", "keep using", "cannot stop using", "can't stop using",
        "cut down on", "my substance use", "dependent on", "dependency on",
        # cannabis / weed
        "weed", "marijuana", "cannabis", "joint", "blunt", "edible",
        # functional use and rationalization
        "helps me feel normal", "helps me function", "need it to function",
        "get through the day", "make it through the day", "can't function without",
        "only thing that helps", "only thing that works for me",
        "helps with my pain", "helps with my chronic", "helps with chronic pain",
        "helps me cope", "it helps me", "need it to get through",
        # minimization / normalization about substance
        "not a real drug", "isn't a real drug", "it's natural", "it's legal in",
        "only at parties", "only when i party", "social thing not", "do it at parties",
        "prescribed so it", "it's prescribed", "my doctor gave", "doctor prescribed",
        "just pills", "just taking pills", "only pills",
        # identity / dependency language
        "can't imagine life without", "life without it", "life without the",
        # shame / disclosure reluctance
        "embarrassed to tell", "embarrassed about my use", "ashamed to admit",
        "too ashamed to tell", "too embarrassed to",
        # recovery pressure from others
        "expects me to be fixed", "expects me to be better", "expects me to be clean",
        "recovery is taking longer", "taking longer than they",
        # sleep + substance dependency
        "help sleeping", "can only sleep", "help with sleeping", "help me sleep",
        "take to sleep", "need something to sleep", "pills to sleep",
        # using-pills / stop-using phrasing (template-generated permutation patterns)
        "using pills", "quit using", "stop using", "using the pills",
        "taking pills", "taking the pills", "pill every day",
        "hide my using", "hide my drug", "hide my substance",
        "part of me wants to stop", "cannot cope without it", "can't cope without it",
        "promises i would stop", "promised i would stop", "feel like a failure",
        # lapse / recovery-specific language (alcohol or drug context)
        "make it a week", "didn't make it a week", "did not make it a week",
        "make it through the week", "couldn't make it a week", "did not even make it",
        "relapsed again", "slipped again", "back to using", "using again",
    ),
}

_SOFT_OVERRIDE_INTENTS: frozenset = frozenset({
    "unclear",
    "rag_query",
    "greeting",
    "venting",
    "mood_anxious",
    "mood_angry",
    "mood_guilty",
    "mood_sad",
    "trigger_stress",
    "trigger_financial",
    "behaviour_eating",
    "behaviour_fatigue",  # LLM maps functional-use substance language to fatigue; allow override
    "medication_request",
    "trigger_trauma",   # LLM occasionally misclassifies substance questions as trauma
})

_RELATIONSHIP_SOFT_OVERRIDE_INTENTS: frozenset = frozenset({
    "greeting", "unclear", "rag_query",
    "behaviour_fatigue", "behaviour_sleep",
    "mood_anxious", "mood_angry", "mood_guilty", "mood_sad",
    "trigger_stress",
})

_DISCLOSURE_ACTION_TERMS: tuple[str, ...] = (
    "tell", "share", "say", "open up", "discuss", "mention", "bring up", "talk to",
)

_DISCLOSURE_SIGNAL_PATTERNS: tuple[str, ...] = (
    r"\bnot\s+aware\b",
    r"\bunaware\b",
    r"\b(?:doesn'?t|does\s+not|dont|don't|do\s+not)\s+know\b",
    r"\b(?:haven'?t|have\s+not|didn'?t|did\s+not|never)\s+(?:told|disclosed|mentioned|shared|informed)\b",
    r"\bnot\s+(?:told|informed)\b",
    r"\b(?:hide|hiding|hidden)\b",
    r"\bkeeping\s+(?:it|this)\s+from\b",
    r"\bsecret\b",
    r"\b(?:yet\s+to\s+)?disclos(?:e|ed|ing)\b",
)

_RELATIONSHIP_REACTION_PATTERNS: tuple[str, ...] = (
    r"\bhates?\b",
    r"\b(?:doesn'?t|does\s+not|dont|don't|do\s+not)\s+like\b",
    r"\bangry\b",
    r"\bupset\b",
    r"\bmad\b",
    r"\bjudg(?:e|ing|ed)\b",
    r"\bdisapprov(?:e|es|ing|ed)\b",
    r"\bcriticis(?:e|es|ing|ed)\b",
    r"\bcriticiz(?:e|es|ing|ed)\b",
)

_RESOLUTION_SKIP_INTENTS: frozenset = frozenset({
    "crisis_suicidal", "crisis_abuse", "behaviour_self_harm",
    "medication_request", "psychosis_indicator",
    "greeting", "farewell", "gratitude", "intake",
    "feedback_thumbsup", "feedback_optout", "feedback_sos",
    "feedback_pivot_overwhelmed", "feedback_pivot_urge", "feedback_pivot_stealth",
})


def _stable_pick(options: List[str], seed: str) -> str:
    """Deterministic variant selection to keep responses varied but reproducible."""
    if not options:
        return ""
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(options)
    return options[idx]


def _override_addiction_intent_from_message(message: str, classified_intent: str) -> Optional[str]:
    """Promote clear addiction disclosures that otherwise collapse into mood/stress intents."""
    if classified_intent in _ADDICTION_INTENTS and classified_intent != "addiction_drugs":
        return None
    if classified_intent not in _SOFT_OVERRIDE_INTENTS and classified_intent != "addiction_drugs":
        return None

    msg_lc = (message or "").lower()
    for intent, markers in _ADDICTION_OVERRIDE_PATTERNS.items():
        if classified_intent == "addiction_drugs" and intent == "addiction_drugs":
            continue
        if any(marker in msg_lc for marker in markers):
            if classified_intent == "addiction_drugs" and intent == classified_intent:
                continue
            return intent
    return None


def _override_disclosure_question_intent_from_message(message: str, classified_intent: str) -> Optional[str]:
    """Reroute relational disclosure questions away from greeting to therapeutic flow."""
    if classified_intent not in _RELATIONSHIP_SOFT_OVERRIDE_INTENTS:
        return None

    msg_lc = (message or "").lower().strip()
    if not msg_lc:
        return None

    relationship_analysis = analyze_relationship_clause(message)
    if not relationship_analysis.has_relationship:
        return None

    if _is_relationship_disclosure_question(message):
        return "trigger_relationship"

    # Relationship-impact questions can be misclassified as fatigue/stress.
    relationship_impact_patterns = (
        r"\bhow\s+will\b",
        r"\bwhat\s+will\b",
        r"\bwill\s+(?:my\s+)?\w+\s+(?:see|react|respond|feel|take|think|say|do)\b",
    )
    relationship_impact_verbs = ("see", "react", "respond", "feel", "take", "think", "say", "do")
    if (
        "?" in msg_lc
        and relationship_analysis.has_relationship
        and any(re.search(p, msg_lc) for p in relationship_impact_patterns)
        and any(v in msg_lc for v in relationship_impact_verbs)
    ):
        return "trigger_relationship"

    # Backup trigger when the sentence is a direct question about disclosure.
    if "?" in msg_lc and any(t in msg_lc for t in _DISCLOSURE_ACTION_TERMS):
        return "trigger_relationship"

    return None


def _override_relationship_disclosure_statement_intent_from_message(
    message: str,
    classified_intent: str,
) -> Optional[str]:
    """Reroute relationship disclosure statements away from greeting fallback.

    Handles first-pass statements such as:
    - "my partner is not aware"
    - "my dad doesn't know"
    - "I haven't told my wife"
    """
    if classified_intent not in _RELATIONSHIP_SOFT_OVERRIDE_INTENTS:
        return None

    msg_lc = (message or "").lower().strip()
    if not msg_lc:
        return None

    relationship_analysis = analyze_relationship_clause(message)
    if not relationship_analysis.has_relationship:
        return None

    # Generalized relationship reroute: secrecy/conflict/concern/support statements
    # should stay in relationship therapeutic flow even when the base classifier
    # drifts to greeting/unclear/rag_query.
    if relationship_analysis.tone in {"secrecy", "conflict", "concern", "support"}:
        return "trigger_relationship"
    if any(re.search(pattern, msg_lc) for pattern in _DISCLOSURE_SIGNAL_PATTERNS):
        return "trigger_relationship"

    return None


def _override_relationship_continuity_intent_from_message(
    message: str,
    classified_intent: str,
    last_intent: Optional[str],
    last_secondary_intents: Optional[List[str]],
    pending_feedback_intent: Optional[str],
    awaiting_feedback_free_text: bool,
) -> Optional[str]:
    """Keep relationship disclosure follow-ups in therapeutic flow instead of greeting fallback.

    Handles short pronoun/secrecy follow-ups such as "he is not aware of this"
    when the prior turn was already relationship-focused.
    """
    if classified_intent not in _RELATIONSHIP_SOFT_OVERRIDE_INTENTS:
        return None

    msg_lc = (message or "").lower().strip()
    if not msg_lc:
        return None

    previous_intents = {last_intent} | set(last_secondary_intents or [])
    relationship_context_active = (
        "trigger_relationship" in previous_intents
        or pending_feedback_intent == "trigger_relationship"
    )
    if not relationship_context_active and not awaiting_feedback_free_text:
        return None

    relationship_analysis = analyze_relationship_clause(message)
    has_pronoun_reference = bool(re.search(r"\b(he|she|they|him|her|them)\b", msg_lc))
    has_disclosure_signal = any(re.search(pattern, msg_lc) for pattern in _DISCLOSURE_SIGNAL_PATTERNS)
    has_reaction_signal = any(re.search(pattern, msg_lc) for pattern in _RELATIONSHIP_REACTION_PATTERNS)

    # Continuity with explicit relationship mention.
    if relationship_analysis.has_relationship and (
        has_disclosure_signal
        or has_reaction_signal
        or "?" in msg_lc
        or relationship_analysis.tone in {"secrecy", "conflict", "support", "concern"}
    ):
        return "trigger_relationship"

    # Continuity with pronoun-only follow-up after relationship turn.
    if has_pronoun_reference and (has_disclosure_signal or has_reaction_signal):
        return "trigger_relationship"

    return None


def _override_feedback_clarification_intent(
    classified_intent: str,
    clarification_intent: Optional[str],
) -> Optional[str]:
    """Generalized post-feedback clarification routing.

    When a patient picks "Something else" and then clarifies what was missing,
    preserve continuity by keeping the response anchored to the intervention that
    was just being evaluated. This avoids drifting into generic fallback intents.
    """
    if not clarification_intent:
        return None

    # Allow continuity override only when the classifier landed in generic/soft
    # buckets that commonly absorb short clarification turns.
    _clarification_soft_intents = {
        "greeting", "unclear", "rag_query",
        "behaviour_fatigue", "behaviour_sleep",
        "mood_anxious", "trigger_stress",
    }
    if classified_intent in _clarification_soft_intents:
        return clarification_intent
    return None


def _is_relationship_disclosure_question(message: str) -> bool:
    """Detect relational disclosure questions such as 'why should I tell my father?' (including common typos)."""
    msg_lc = (message or "").lower().strip()
    if not msg_lc:
        return False

    disclosure_question_patterns = (
        r"\b(?:why\s+should|should|how\s+do|can|do\s+i\s+have\s+to)\s+i\s+(?:tell|say|share|open\s+up|discuss|mention|bring\s+up)\b",
        r"\bhow\s+do\s+i\s+talk\s+to\b",
        r"\bshould\s+we\s+(?:tell|share|say|discuss|mention|bring\s+up)\b",
    )
    if any(re.search(p, msg_lc) for p in disclosure_question_patterns):
        return True

    # Backup trigger when the sentence is a direct disclosure question with relationship mention.
    if "?" in msg_lc and any(t in msg_lc for t in _DISCLOSURE_ACTION_TERMS):
        return True
    return False


def _normalize_secondary_intents(primary_intent: str, secondary_intents: List[str]) -> List[str]:
    """Keep patient-visible secondary intents unique and drop generic substance tags when a specific addiction is present."""
    cleaned: List[str] = []
    seen = set()
    all_intents = [primary_intent] + list(secondary_intents or [])
    has_specific_addiction = any(
        intent in _ADDICTION_INTENTS and intent != "addiction_drugs"
        for intent in all_intents
    )

    for intent in secondary_intents or []:
        if not intent or intent == primary_intent or intent in seen:
            continue
        if has_specific_addiction and intent == "addiction_drugs":
            continue
        seen.add(intent)
        cleaned.append(intent)
    return cleaned


_URGE_MARKERS: tuple[str, ...] = (
    "craving", "urge", "want to drink", "want to use",
    "feel like drinking", "feel like using", "tempted",
    "about to", "need a drink", "need to use", "need a hit",
    "pull toward", "can't resist", "cannot resist",
    "can't stop myself", "cannot stop myself", "going to relapse",
    "i could use a drink", "i could use", "on the verge",
)


def _has_urge_language(message: str) -> bool:
    """Return True when the message explicitly describes a craving or urge."""
    msg_lc = (message or "").lower()
    return any(m in msg_lc for m in _URGE_MARKERS)


def _extract_relationship_mentions(message: str) -> List[str]:
    """Extract explicit social-circle references so responses can mirror them back precisely."""
    return analyze_relationship_clause(message).mentions


def _format_relationship_phrase(relationships: List[str]) -> str:
    if not relationships:
        return ""
    if len(relationships) == 1:
        return f"your {relationships[0]}"
    if len(relationships) == 2:
        return f"your {relationships[0]} and {relationships[1]}"
    return f"your {', '.join(relationships[:-1])}, and {relationships[-1]}"


def _relationship_verb(relationships: List[str]) -> str:
    return "is" if len(relationships) == 1 else "are"


def _relationship_do_verb(relationships: List[str]) -> str:
    return "does" if len(relationships) == 1 else "do"


def _detect_relationship_tone(message: str) -> Optional[str]:
    """Infer the stance around a mentioned relationship from common verb/adjective patterns."""
    analysis = analyze_relationship_clause(message)
    return analysis.tone if analysis.has_relationship else None


def _detect_resolution_focus(
    intent: str,
    addiction_type: Optional[str],
    retrieved_docs: List[Dict],
    user_message: str,
) -> Dict[str, str]:
    """
    Derive an intervention focus from retrieved PDF chunks + message context.
    Returns a small descriptor used by both text generation and video hinting.
    """
    recovery_analysis = analyze_recovery_clause(user_message)
    relationship_analysis = analyze_relationship_clause(user_message)
    disclosure_question = _is_relationship_disclosure_question(user_message)

    def _primary_hint_from_profile(default: str = intent) -> str:
        return _ADDICTION_TYPE_TO_INTENT.get(
            (addiction_type or "").lower().replace("-", "_").replace(" ", "_"),
            default,
        )

    if intent == "trigger_relationship":
        # Generalized relationship focus selection for BOTH first-pass and feedback
        # clarification turns. This avoids falling back to generic cycle phrasing.
        if relationship_analysis.tone == "secrecy":
            return {
                "key": "disclosure_readiness",
                "phrase": "deciding what to share, why it may help, and how to do it safely at your pace",
                "video_hint_intent": _primary_hint_from_profile("trigger_relationship"),
            }
        if relationship_analysis.tone == "conflict":
            return {
                "key": "relationship_friction",
                "phrase": "staying grounded when other people's reactions feel sharp, disapproving, or hard to absorb",
                "video_hint_intent": _primary_hint_from_profile("trigger_relationship"),
            }
        if disclosure_question or relationship_analysis.has_relationship:
            return {
                "key": "connection_accountability",
                "phrase": "weighing why disclosure can help recovery while protecting your boundaries and timing",
                "video_hint_intent": _primary_hint_from_profile("trigger_relationship"),
            }

    def _theme_video_hint() -> str:
        if intent in _ADDICTION_INTENTS and intent != "addiction_drugs":
            return intent
        return _ADDICTION_TYPE_TO_INTENT.get(
            (addiction_type or "").lower().replace("-", "_").replace(" ", "_"),
            intent,
        )

    explicit_by_intent = {
        "behaviour_sleep": ("sleep_reset", "resetting your sleep and nervous system rhythm", "behaviour_sleep"),
        "behaviour_fatigue": ("sleep_reset", "repairing sleep pressure and energy rhythm", "behaviour_sleep"),
        "mood_anxious": ("grounding", "grounding your body before your mind spirals", "mood_anxious"),
        "trigger_stress": ("stress_reset", "down-shifting stress before it turns into urges", "trigger_stress"),
        "mood_guilty": ("shame_relief", "reducing shame while keeping accountability", "mood_guilty"),
        "trigger_trauma": ("trauma_grounding", "stabilizing your body when trauma activation spikes", "trigger_trauma"),
        "relapse_disclosure": ("reset_after_lapse", "recovering quickly after a slip without self-attack", "addiction_drugs"),
    }
    if recovery_analysis.theme == "shame":
        return {
            "key": "shame_relief",
            "phrase": "softening shame enough to make the next honest, workable choice",
            "video_hint_intent": _theme_video_hint() or intent,
        }
    if recovery_analysis.theme == "pressure":
        return {
            "key": "boundary_protection",
            "phrase": "staying steady when pressure, scrutiny, or demands start tightening the nervous system",
            "video_hint_intent": _theme_video_hint() or intent,
        }
    if recovery_analysis.theme == "change_readiness":
        return {
            "key": "change_commitment",
            "phrase": "turning the part of you that wants change into one concrete next step",
            "video_hint_intent": _theme_video_hint() or intent,
        }
    if intent in explicit_by_intent:
        key, phrase, video_hint_intent = explicit_by_intent[intent]
        return {"key": key, "phrase": phrase, "video_hint_intent": video_hint_intent}

    msg_lc = (user_message or "").lower()
    if intent in _ADDICTION_INTENTS:
        addiction_hint = intent
        if intent == "addiction_drugs":
            addiction_hint = _ADDICTION_TYPE_TO_INTENT.get(
                (addiction_type or "").lower().replace("-", "_").replace(" ", "_"),
                intent,
            )
        relationship_analysis = analyze_relationship_clause(user_message)
        relationships = relationship_analysis.mentions
        relationship_tone = relationship_analysis.tone
        sleep_markers = ["sleep", "morning", "insomnia", "awake", "wake up", "tired"]
        cope_markers = ["unwind", "edge off", "after work", "long day", "cope", "stress"]
        money_markers = ["money", "debt", "bills", "rent", "borrowed", "lost a lot", "losses"]
        compare_markers = ["compare", "likes", "followers", "fomo", "notifications", "validation", "scrolling"]
        work_markers = ["productive", "working", "work", "rest", "busy", "worthless", "weekends"]
        intimacy_markers = ["porn", "pornography", "intimacy", "sexual", "shame", "secret"]
        food_markers = ["binge", "food", "eat", "eating", "junk food", "comfort eating", "emotional eating"]
        shopping_markers = ["shopping", "buy", "purchases", "cart", "spending", "orders", "online shopping"]
        gaming_markers = ["game", "gaming", "ranked", "loot", "stream", "late night", "all night"]

        if relationships and relationship_tone == "secrecy":
            return {
                "key": "disclosure_readiness",
                "phrase": "carrying this while others don't yet know, and what, if anything, feels right to share",
                "video_hint_intent": addiction_hint,
            }
        if relationships and relationship_tone == "conflict":
            return {
                "key": "relationship_friction",
                "phrase": "staying grounded when other people's reactions feel sharp, disapproving, or hard to absorb",
                "video_hint_intent": addiction_hint,
            }
        if recovery_analysis.theme == "lapse":
            return {
                "key": "reset_after_lapse",
                "phrase": "recovering quickly after a slip without turning one moment into a longer spiral",
                "video_hint_intent": addiction_hint,
            }
        if recovery_analysis.theme == "shame":
            return {
                "key": "shame_relief",
                "phrase": "softening shame enough to make the next honest, workable choice",
                "video_hint_intent": addiction_hint,
            }
        if recovery_analysis.theme == "pressure":
            return {
                "key": "boundary_protection",
                "phrase": "staying steady when pressure, scrutiny, or demands start tightening the nervous system",
                "video_hint_intent": addiction_hint,
            }
        if recovery_analysis.theme == "change_readiness":
            return {
                "key": "change_commitment",
                "phrase": "turning the part of you that wants change into one concrete next step",
                "video_hint_intent": addiction_hint,
            }
        if relationships:
            return {
                "key": "connection_accountability",
                "phrase": "using supportive accountability instead of defensive coping",
                "video_hint_intent": addiction_hint,
            }
        if intent == "addiction_social_media" and any(m in msg_lc for m in compare_markers):
            return {
                "key": "comparison_detox",
                "phrase": "loosening the comparison and validation loop before it snowballs",
                "video_hint_intent": "addiction_social_media",
            }
        if intent == "addiction_gambling" and any(m in msg_lc for m in money_markers):
            return {
                "key": "loss_chasing_interrupt",
                "phrase": "interrupting the urge to chase losses before it compounds harm",
                "video_hint_intent": "addiction_gambling",
            }
        if intent == "addiction_work" and any(m in msg_lc for m in work_markers):
            return {
                "key": "permission_to_pause",
                "phrase": "separating self-worth from constant output so your system can downshift",
                "video_hint_intent": "addiction_work",
            }
        if intent == "addiction_pornography" and any(m in msg_lc for m in intimacy_markers):
            return {
                "key": "shame_and_intimacy_reset",
                "phrase": "reducing shame while rebuilding safer regulation and intimacy",
                "video_hint_intent": "addiction_pornography",
            }
        if intent == "addiction_food" and any(m in msg_lc for m in food_markers):
            return {
                "key": "emotion_to_eating_bridge",
                "phrase": "slowing the jump from emotional pain to automatic eating",
                "video_hint_intent": "addiction_food",
            }
        if intent == "addiction_shopping" and any(m in msg_lc for m in shopping_markers):
            return {
                "key": "urge_spend_pause",
                "phrase": "creating a pause between emotional urgency and spending",
                "video_hint_intent": "addiction_shopping",
            }
        if intent == "addiction_gaming" and any(m in msg_lc for m in gaming_markers):
            return {
                "key": "screen_compulsion_reset",
                "phrase": "breaking the dissociation and reward loop that keeps pulling you back in",
                "video_hint_intent": "addiction_gaming",
            }
        daily_use_markers = [
            "every day", "every night", "every week", "daily",
            "bad to use", "okay to use", "is it bad", "is it harmful",
            "how much is too much", "using too much", "using too often",
            "is it normal", "is it okay to use", "safe to use",
        ]
        if any(m in msg_lc for m in daily_use_markers):
            return {
                "key": "habit_awareness",
                "phrase": "understanding how daily use gradually reshapes tolerance and what that pattern means for recovery",
                "video_hint_intent": addiction_hint,
            }
        if any(m in msg_lc for m in sleep_markers):
            return {
                "key": "sleep_reset",
                "phrase": "resetting your sleep and nervous system rhythm",
                "video_hint_intent": "behaviour_sleep",
            }
        if any(m in msg_lc for m in cope_markers):
            return {
                "key": "stress_to_urge_bridge",
                "phrase": "interrupting the stress to substance loop early",
                "video_hint_intent": addiction_hint,
            }
        return {
            "key": "urge_regulation",
            "phrase": "urge regulation in the first 15 to 20 minutes",
            "video_hint_intent": addiction_hint,
        }

    doc_text = " ".join((d.get("text", "")[:700] for d in retrieved_docs)).lower()
    doc_tags = " ".join(
        " ".join(d.get("topic_tags", []) or [])
        for d in retrieved_docs
    ).lower()
    signal_text = f"{user_message.lower()} {doc_text} {doc_tags}"

    # Message-first: prevent retrieved doc topic-tags from contaminating focus for substance-use questions
    _msg_only = user_message.lower()
    _substance_words = ["use", "using", "drink", "drinking", "smoke", "smoking", "substance"]
    _daily_context = [
        "every day", "daily", "every night", "every week", "bad to", "okay to",
        "safe to", "is it harmful", "how much", "too much", "too often", "is it normal",
    ]
    if any(sw in _msg_only for sw in _substance_words) and any(dw in _msg_only for dw in _daily_context):
        _hint = _ADDICTION_TYPE_TO_INTENT.get(
            (addiction_type or "").lower().replace("-", "_").replace(" ", "_"),
            "addiction_drugs",
        )
        return {
            "key": "habit_awareness",
            "phrase": "understanding how daily use gradually reshapes tolerance and what that pattern means for recovery",
            "video_hint_intent": _hint or "addiction_drugs",
        }

    if any(k in signal_text for k in ["urge surfing", "craving", "delay", "halt", "relapse prevention"]):
        hint = _ADDICTION_TYPE_TO_INTENT.get((addiction_type or "").lower().replace("-", "_").replace(" ", "_"), "addiction_drugs")
        return {
            "key": "urge_regulation",
            "phrase": "urge regulation in the first 15 to 20 minutes",
            "video_hint_intent": hint,
        }
    if any(k in signal_text for k in ["rem", "insomnia", "sleep hygiene", "blue light", "sleep architecture"]):
        return {
            "key": "sleep_reset",
            "phrase": "resetting your sleep and nervous system rhythm",
            "video_hint_intent": "behaviour_sleep",
        }
    if any(k in signal_text for k in ["grounding", "breathing", "nervous system", "panic", "anxiety"]):
        return {
            "key": "grounding",
            "phrase": "grounding your body before your mind spirals",
            "video_hint_intent": "mood_anxious",
        }
    if any(k in signal_text for k in ["guilt", "shame", "self compassion", "self-compassion"]):
        return {
            "key": "shame_relief",
            "phrase": "reducing shame while keeping accountability",
            "video_hint_intent": "mood_guilty",
        }
    if any(k in signal_text for k in ["trauma", "flashback", "hypervigil", "assault"]):
        return {
            "key": "trauma_grounding",
            "phrase": "stabilizing your body when trauma activation spikes",
            "video_hint_intent": "trigger_trauma",
        }

    hint = _ADDICTION_TYPE_TO_INTENT.get((addiction_type or "").lower().replace("-", "_").replace(" ", "_"), intent)
    return {
        "key": "stabilise_and_choose",
        "phrase": "slowing the cycle so choice comes back online",
        "video_hint_intent": hint or intent,
    }


def _build_resolution_active_intents(
    intent: str,
    secondary_intents: List[str],
    addiction_type: Optional[str],
    patient_context,
    focus_hint_intent: Optional[str],
) -> List[str]:
    """Add patient-state hints to make video matching tighter and context-aware."""
    active: List[str] = [intent]

    def _add(tag: Optional[str]) -> None:
        if tag and tag not in active:
            active.append(tag)

    _add(focus_hint_intent)

    if patient_context and patient_context.checkin:
        if getattr(patient_context.checkin, "sleep_quality", 5) <= 4:
            _add("behaviour_sleep")
        if getattr(patient_context.checkin, "craving_intensity", 3) >= 7:
            _add(_ADDICTION_TYPE_TO_INTENT.get((addiction_type or "").lower().replace("-", "_").replace(" ", "_")))

        mood_today = (getattr(patient_context.checkin, "todays_mood", "") or "").lower()
        if mood_today in {"anxious", "stressed", "stress", "nervous", "panic", "panicking"}:
            _add("mood_anxious")
        elif mood_today in {"sad", "depressed", "low"}:
            _add("mood_sad")
        elif mood_today in {"angry", "frustrated", "irritated"}:
            _add("mood_angry")

        trigger_map = {
            "stress": "trigger_stress",
            "financial": "trigger_financial",
            "money": "trigger_financial",
            "relationship": "trigger_relationship",
            "partner": "trigger_relationship",
            "grief": "trigger_grief",
            "loss": "trigger_grief",
            "trauma": "trigger_trauma",
        }
        for t in getattr(patient_context.checkin, "triggers_today", []) or []:
            tl = str(t).lower()
            for key, mapped in trigger_map.items():
                if key in tl:
                    _add(mapped)

    for sec in secondary_intents:
        _add(sec)

    _add(_ADDICTION_TYPE_TO_INTENT.get((addiction_type or "").lower().replace("-", "_").replace(" ", "_")))
    return active


def _compose_dynamic_resolution(
    intent: str,
    user_message: str,
    patient_context,
    focus: Dict[str, str],
    selected_video: Optional[Dict],
    session_message_count: int,
    prior_relationships: Optional[List[str]] = None,
) -> Dict:
    """
    Build the slide-4 compliant resolution payload:
      - 2-3 lines of warm validation
      - one line introducing the precisely matched therapeutic video.
    """
    msg_lc = (user_message or "").lower()
    mood = (getattr(patient_context.checkin, "todays_mood", "") or "").lower() if patient_context else ""
    craving = int(getattr(patient_context.checkin, "craving_intensity", 3) or 3) if patient_context else 3
    sleep_quality = int(getattr(patient_context.checkin, "sleep_quality", 5) or 5) if patient_context else 5
    risk_level = (getattr(patient_context.risk, "risk_level", "") or "").lower() if patient_context else ""
    relationship_analysis = analyze_relationship_clause(user_message)
    relationships = relationship_analysis.mentions
    if not relationships:
        msg_lc_for_pronoun = (user_message or "").lower()
        has_pronoun_reference = bool(re.search(r"\b(he|she|they|him|her|them)\b", msg_lc_for_pronoun))
        if has_pronoun_reference and prior_relationships:
            relationships = list(prior_relationships)
    relationship_phrase = _format_relationship_phrase(relationships)
    relationship_verb = _relationship_verb(relationships)
    relationship_do_verb = _relationship_do_verb(relationships)
    relationship_tone = relationship_analysis.tone
    recovery_analysis = analyze_recovery_clause(user_message)
    disclosure_question = _is_relationship_disclosure_question(user_message)
    onboarding_addiction = (
        (getattr(getattr(patient_context, "onboarding", None), "addiction_type", "") or "")
        if patient_context else ""
    ).lower()

    frame = "general"
    if recovery_analysis.theme == "lapse" or intent == "relapse_disclosure":
        frame = "reset"
    elif recovery_analysis.theme == "shame":
        frame = "shame"
    elif recovery_analysis.theme == "pressure":
        frame = "pressure"
    elif recovery_analysis.theme == "change_readiness":
        frame = "change"
    elif intent == "trigger_relationship" and disclosure_question:
        frame = "change"
    elif focus.get("key") == "habit_awareness":
        frame = "habit"
    elif craving >= 7:
        frame = "urge"
    elif intent in _ADDICTION_INTENTS and _has_urge_language(user_message):
        frame = "urge"
    elif intent in {"mood_anxious", "trigger_stress"} or mood in {"anxious", "stressed", "panic", "nervous"}:
        frame = "anxious"
    elif intent in {"behaviour_sleep", "behaviour_fatigue"} or sleep_quality <= 4 or "morning" in msg_lc:
        frame = "fatigue"
    elif intent in {"mood_guilty", "mood_sad", "severe_distress"}:
        frame = "heavy_emotion"

    line1_options = {
        "urge": [
            "What you are feeling right now is a common recovery moment, and it makes sense that it feels intense.",
            "This kind of pull can feel urgent, and that does not mean you are weak or failing.",
            "You are not broken for feeling this urge; this is a known nervous-system pattern in recovery.",
        ],
        "anxious": [
            "Given what your system is carrying, this level of anxiety is understandable.",
            "It makes sense that your body feels on alert right now; that reaction is human, not a flaw.",
            "Anxiety can surge fast in recovery contexts, and what you are feeling is a valid response.",
        ],
        "fatigue": [
            "Feeling this drained in your situation is understandable and clinically common.",
            "Your exhaustion makes sense, especially when sleep and stress are both under strain.",
            "This level of morning depletion is a known recovery signal, not a personal failure.",
        ],
        "heavy_emotion": [
            "The weight you are carrying comes through clearly, and your reaction is deeply understandable.",
            "What you are describing is emotionally heavy, and it makes sense it feels hard to hold alone.",
            "These feelings are painful but valid, and naming them is already a meaningful step.",
        ],
        "reset": [
            "A slip can set off fear and self-attack quickly, and that does not mean the whole recovery effort is gone.",
            "Moments like this can feel discouraging, but one painful turn does not erase the work you have already done.",
            "After a slip, the nervous system often swings hard into panic or shame; that reaction is common, and it can be steadied.",
        ],
        "shame": [
            "Shame can get loud fast in recovery, and what you are feeling is painful without meaning you are beyond help.",
            "Feeling ashamed does not mean you have failed; it means this matters to you and it hurts.",
            "That self-critical weight is real, and it deserves care rather than more punishment.",
        ],
        "pressure": [
            "Pressure can make the whole system tense up quickly, especially when recovery already feels exposed.",
            "It makes sense that being pushed or watched would make this feel heavier, not easier.",
            "When outside pressure builds, the body often shifts into defense before it can think clearly.",
        ],
        "change": [
            "The part of you that wants something different matters, and it is worth taking seriously.",
            "Wanting change is meaningful; it is often the point where choice starts to come back online.",
            "The wish to do this differently is important, even if the path still feels hard.",
        ],
        "general": [
            "What you are feeling right now makes sense in context.",
            "Your response is understandable, given the pressure your system is under.",
            "There is nothing abnormal about this reaction in recovery.",
        ],
        "habit": [
            "Asking whether daily use is harmful is one of the most honest and important questions in recovery.",
            "Daily use is worth examining without judgment, and you are already doing that by asking.",
            "That question about your daily use deserves a real answer, not just reassurance.",
        ],
    }

    state_markers: List[str] = []
    if craving >= 7:
        state_markers.append("high craving load")
    if sleep_quality <= 4:
        state_markers.append("sleep depletion")
    if mood in {"anxious", "stressed", "panic", "nervous", "sad", "lonely", "angry", "guilty"}:
        state_markers.append(f"{mood} mood state")
    if risk_level in {"high", "critical"}:
        state_markers.append(f"{risk_level} risk window")

    if relationship_phrase and disclosure_question and relationship_tone == "secrecy":
        line2 = (
            f"Asking this about {relationship_phrase} shows thoughtful judgment; you do not have to share everything at once, "
            f"and careful, paced disclosure can still reduce isolation and build safer support."
        )
    elif relationship_phrase and disclosure_question:
        line2 = (
            f"Asking why to tell {relationship_phrase} is a meaningful recovery question; selective honesty can lower secrecy stress, "
            f"improve support, and help urges feel less private and overwhelming."
        )
    elif relationship_phrase and relationship_tone == "secrecy":
        line2 = (
            f"Carrying this while {relationship_phrase} {relationship_do_verb} not yet know about it can add a quiet weight of its own; "
            f"holding it alone has its own kind of pressure, and you do not have to figure out what to say to them today."
        )
    elif relationship_phrase and relationship_tone == "conflict":
        line2 = (
            f"When {relationship_phrase} {relationship_verb} reacting strongly to this, shame, defensiveness, or pressure can spike quickly; "
            f"that reaction is understandable, and it can still be met without turning against yourself."
        )
    elif relationship_phrase and relationship_tone == "support":
        line2 = (
            f"When {relationship_phrase} {relationship_verb} trying to help, even care can bring pressure or mixed feelings; "
            f"that does not mean you are doing recovery the wrong way."
        )
    elif relationship_phrase and recovery_analysis.theme == "pressure":
        line2 = (
            f"When {relationship_phrase} {relationship_verb} part of this and the pressure keeps building, the nervous system can go straight into defense or shutdown; "
            f"slowing that pattern down can help you stay honest without feeling cornered."
        )
    elif recovery_analysis.theme == "lapse":
        line2 = (
            "What matters most now is the next stabilizing move rather than turning this into proof that you cannot recover; "
            "a fast, honest reset is more protective than self-punishment."
        )
    elif recovery_analysis.theme == "shame":
        line2 = (
            "When shame takes over, it narrows options and pushes people toward hiding or giving up; "
            "making a little room around that feeling can help choice come back online."
        )
    elif recovery_analysis.theme == "pressure":
        line2 = (
            "When pressure or scrutiny starts closing in, the mind often shifts toward defense, escape, or shutdown; "
            "slowing that pattern down helps you respond instead of just react."
        )
    elif recovery_analysis.theme == "change_readiness":
        line2 = (
            "That part of you that wants to stop or do this differently is clinically important; "
            "it often helps to translate that momentum into one small next step while it is available."
        )
    elif focus.get("key") == "habit_awareness":
        line2 = (
            "Daily use gradually reshapes the brain's reward system, lowering your baseline comfort and making use feel necessary rather than chosen; "
            "that shift is gradual, reversible, and worth recognizing early."
        )
    elif relationship_phrase and state_markers:
        state_phrase = ", ".join(state_markers[:2])
        line2 = (
            f"When {relationship_phrase} {relationship_verb} part of this and {state_phrase} is already in the room, the mind often reaches for fast relief; that pattern is deeply human and still workable."
        )
    elif relationship_phrase:
        line2 = (
            f"When {relationship_phrase} {relationship_verb} part of this, it makes sense that your system would react quickly; closeness and concern can stir a lot at once, and that does not mean you are failing."
        )
    elif state_markers:
        state_phrase = ", ".join(state_markers[:2])
        line2 = (
            f"When {state_phrase} overlap, the mind looks for fast relief; that pattern is expected, and it can be worked with safely."
        )
    else:
        line2 = "Your system is trying to protect you quickly; that survival pattern is understandable and changeable."

    video_title = (selected_video or {}).get("title", "a short therapeutic video")
    line3 = (
        f"I am matching you with {video_title} so the next few minutes focus on {focus.get('phrase', 'a practical regulation skill')} while you stay grounded."
    )

    seed = (
        f"{intent}|{user_message}|{session_message_count}|{focus.get('key','')}|"
        f"{mood}|{sleep_quality}|{craving}|{risk_level}|{onboarding_addiction}"
    )
    line1 = _stable_pick(line1_options.get(frame, line1_options["general"]), seed)

    lines = [line1, line2, line3]
    return {
        "text": "\n".join(lines),
        "lines": lines,
        "focus": focus.get("key", "stabilise_and_choose"),
        "focus_phrase": focus.get("phrase", "stabilization"),
        "video_match_reason": {
            "focus_hint": focus.get("video_hint_intent"),
            "active_state": {
                "mood": mood or "unknown",
                "sleep_quality": sleep_quality,
                "craving_intensity": craving,
                "risk_level": risk_level or "unknown",
            },
        },
        "relationships": relationships,
    }


def get_context_aware_greeting(session: Dict, patient_context) -> str:
    """
    Generate a context-aware opening greeting (never generic "how are you").
    
    Used after intake/check-in completion to open the main conversation.
    Incorporates patient name, current mood/risk level, and personalization.
    
    Args:
        session: The session dict
        patient_context: PatientContext object
        
    Returns:
        str: Personalized greeting string
    """
    return get_opening_line(patient_context)


# ────────────────────────────────────────────────────────────────────────────
# MAIN MESSAGE HANDLER - 6-LAYER SAFETY ARCHITECTURE
# ────────────────────────────────────────────────────────────────────────────

def handle_message(
    message: str,
    session_id: str,
    patient_id: str,
    patient_code: str,
) -> Dict:
    """
    Main message handler with multi-layer safety and context awareness.
    
    ARCHITECTURE (6 Layers):
    
    Layer 0: Input Validation
    - Check message is valid and non-empty
    - Extract patient context
    
    Layer 1: Safety Checks
    - Detect crisis indicators
    - Check for medication requests
    - Validate policy compliance
    
    Layer 2: Intent Classification
    - Classify user intent using microservice
    - Get intent metadata (severity, category)
    
    Layer 3: Context Extraction & Management
    - Extract information from message
    - Update patient context vector
    - Determine relevant questions (minimal-question model)
    
    Layer 4: Response Generation
    - Generate response using response generator service
    - Incorporate minimal-question logic
    - Add context-aware personalization
    
    Layer 5: Response Validation
    - Validate response safety
    - Check policy compliance
    - Sanitize and finalize response
    
    Returns:
        Dict with keys: response, intent, severity, resources, session_id, metadata
    """
    
    # ── LAYER 0: INPUT VALIDATION ────────────────────────────────────────
    
    logger.info(f"[{session_id}] Processing message from {patient_code}")
    
    session = get_session(session_id)
    session["message_count"] += 1
    
    # Store patient identifiers in session if not already present
    if "session_id" not in session:
        session["session_id"] = session_id
    if "patient_id" not in session:
        session["patient_id"] = patient_id

    # Pre-load onboarding profile (addiction_type etc.) from DB on first message
    # This ensures context-aware responses even without conversational intake
    if session["message_count"] == 1 and not session.get("intake_profile"):
        try:
            onboarding = get_patient_onboarding(patient_code)
            if onboarding:
                # Also load the full addictions list (primary + comorbid)
                addictions_list = get_patient_addictions(patient_code)
                if addictions_list:
                    onboarding["addictions"] = addictions_list
                session["intake_profile"] = coerce_profile_flags(onboarding)
                logger.info(
                    f"[{session_id}] Loaded onboarding profile: addiction_type={onboarding.get('addiction_type')}, "
                    f"addictions={[a['addiction_type'] for a in addictions_list]}"
                )
                # Restore partial intake so patient can resume mid-flow after reconnect.
                # Fires only when last_intake_phase > 0 and consent was never given.
                _lp = onboarding.get("last_intake_phase", 0)
                if _lp > 0 and not onboarding.get("intake_consent_given"):
                    if restore_intake_from_db(session, onboarding):
                        logger.info(
                            f"[{session_id}] Restored partial intake from DB: "
                            f"phase={_lp}, resuming at '{session[INTAKE_KEY]['current_question']}'"
                        )
        except Exception as _ob_err:
            logger.warning(f"Could not pre-load onboarding profile: {_ob_err}")

    # Build patient context vector (assembles data from 4 sources)
    patient_context = build_context(session)
    
    if not message or not message.strip():
        return {
            "response": "I'm here to listen. Please share what's on your mind.",
            "intent": "unclear",
            "severity": "low",
            "session_id": session_id,
            "show_resources": False,
            "timestamp": datetime.now().isoformat(),
        }
    
    message = message.strip()

    _awaiting_feedback_free_text = bool(session.get("awaiting_feedback_free_text"))
    _feedback_clarification_intent = None
    if _awaiting_feedback_free_text and message.lower() not in _FEEDBACK_ALL_TOKENS:
        _feedback_clarification_intent = session.get("pending_feedback_intent")

    # Time-out path: if the patient does not answer feedback after a pivot and
    # sends a normal chat message, stop re-prompting feedback in this session.
    if (
        session.get("awaiting_feedback_after_pivot")
        and message.lower() not in _FEEDBACK_ALL_TOKENS
    ):
        session["awaiting_feedback_after_pivot"] = False
        session["pending_feedback_intent"] = None
        session["feedback_prompt_suppressed"] = True
        session["feedback_pivot_retries"] = 0

    # Free-text feedback clarification branch (feedback_pivot_other): consume
    # the very next non-token message as problem-specific clarification.
    if _awaiting_feedback_free_text and message.lower() not in _FEEDBACK_ALL_TOKENS:
        session["awaiting_feedback_free_text"] = False
        # This clarification turn is consumed immediately; avoid stale carry-over.
        session["pending_feedback_intent"] = None
    
    # Ensure patient context exists
    context = get_or_create_context(session_id, patient_id, patient_code)
    
    # ── LAYER 1: SAFETY CHECKS ───────────────────────────────────────────
    
    is_safe, safety_violation = safety_checker.check_safety(message, "user_input")
    
    if not is_safe:
        logger.error(f"Safety violation detected: {safety_violation}")
        return {
            "response": "I'm sorry, I encountered an issue. Please try again or contact support.",
            "intent": "error",
            "severity": "high",
            "session_id": session_id,
            "show_resources": False,
            "timestamp": datetime.now().isoformat(),
        }
    
    # ── LAYER 1.5: SEMANTIC CRISIS GATE ─────────────────────────────────
    # Three-tier detection (exact → fuzzy → embedding cosine similarity).
    # Runs BEFORE intent classification so oblique crisis phrases are caught
    # before they fall through to the RAG/LLM pipeline.
    #
    # Severity / confidence → action
    # ─────────────────────────────────────────────────────────────────────
    #  confidence >= CONFIDENCE_INTERCEPT (0.72)
    #        Override intent; skip RAG + LLM; return crisis template.
    #  confidence >= CONFIDENCE_WARN (0.45, < 0.72)
    #        Continue normal flow but inject a safety-context note into the
    #        system prompt so the LLM responds with appropriate care.
    # ─────────────────────────────────────────────────────────────────────

    _semantic_crisis_override = False   # True → skip RAG, use crisis template
    _potential_crisis_context = ""      # Injected into system_prompt when warn-level

    if _crisis_detector is not None:
        _cr = _crisis_detector.detect(message)
        if _cr.confidence >= CONFIDENCE_INTERCEPT:
            logger.warning(
                "[%s] Semantic crisis INTERCEPT [%s]: %s confidence=%.2f — overriding intent",
                session_id, _cr.method, _cr.category, _cr.confidence,
            )
            # Override intent and severity; skip the LLM/RAG path entirely
            intent = _cr.category
            severity = _cr.severity
            _semantic_crisis_override = True

        elif _cr.confidence >= CONFIDENCE_WARN:
            logger.warning(
                "[%s] Semantic crisis WARN [%s]: %s confidence=%.2f — injecting safety context",
                session_id, _cr.method, _cr.category, _cr.confidence,
            )
            _potential_crisis_context = (
                "\n\n⚠ SAFETY NOTE: The patient's message shows possible signs of "
                f"{_cr.category.replace('_', ' ')} (confidence {_cr.confidence:.0%}). "
                "Respond with extra care and empathy. Do NOT dismiss or minimise feelings. "
                "Gently offer crisis resources if relevant without being alarmist."
            )

    # ── LAYER 1.6: CONVERSATIONAL INTAKE ROUTING ─────────────────────────
    # Intake turns are handled entirely within conversational_intake.py and
    # bypass the LLM/RAG pipeline.  Crisis intercepts always take priority
    # (patient safety > intake flow), so this block is gated on NOT
    # _semantic_crisis_override.

    if not _semantic_crisis_override:
        _intake_state = session.get(INTAKE_KEY, {})

        # Sub-case A: intake was just restored from DB (reconnect) OR just
        # started fresh.  We need to display the current question to the
        # patient before processing any of their input as an answer.
        if _intake_state.get("active") and _intake_state.pop("_show_question", False):
            _prefix = (
                "Welcome back! Let's pick up where you left off. 🙌\n\n"
                if _intake_state.pop("_resumed_from_db", False)
                else ""
            )
            _q_key  = _intake_state.get("current_question", "opening")
            _q_def  = INTAKE_QUESTIONS.get(_q_key, {})
            _name   = _intake_state.get("collected", {}).get("name", "there")
            _q_text = _q_def.get("question", "").format(name=_name)
            logger.info(f"[{session_id}] Intake resume display: question='{_q_key}'")
            return {
                "response":        _prefix + _q_text,
                "intent":          "intake",
                "severity":        "low",
                "show_resources":  False,
                "citations":       [],
                "intake_complete": False,
                "intake_profile":  coerce_profile_flags(_intake_state.get("collected", {})),
                "intake_phase":    _q_def.get("phase", 0),
                "session_id":      session_id,
                "timestamp":       datetime.now().isoformat(),
                "show_score":      False,
                "video":           None,
            }

        # Sub-case B: intake already in-progress — patient is answering a question.
        if is_intake_active(session):
            _ir = handle_intake_turn(message, session)
            if _ir is not None:
                _phase = _ir.get("intake_phase", 0)
                try:
                    save_intake_progress(patient_code, _phase, min(100, _phase * 20))
                except Exception as _ipe:
                    logger.warning(f"Could not persist intake progress: {_ipe}")
                if _ir.get("intake_complete"):
                    session["intake_profile"] = coerce_profile_flags(
                        _ir.get("intake_profile", {})
                    )
                    logger.info(f"[{session_id}] Intake complete — profile stored in session")
                return {
                    **_ir,
                    "session_id": session_id,
                    "timestamp":  datetime.now().isoformat(),
                    "show_score": False,
                    "video":      None,
                    "citations":  _ir.get("citations", []),
                }

        # Sub-case C: first message from a patient who has never done intake.
        elif should_start_intake(session, session["message_count"]):
            init_intake(session, is_returning=False)
            try:
                save_intake_progress(patient_code, 0, 0)
            except Exception as _ipe:
                logger.warning(f"Could not persist intake progress: {_ipe}")

            # Pre-populate mood / addiction_type if the user's first message already
            # contains that information (e.g. "I need a beer" → alcohol; "I feel angry")
            _intake_state = session.get(INTAKE_KEY, {})
            _collected = _intake_state.get("collected", {})
            try:
                from conversational_intake import _extract_mood, _extract_addiction_type
                _pre_mood = _extract_mood(message)
                _pre_addiction = _extract_addiction_type(message)
                if _pre_mood and _pre_mood != "mixed":
                    _collected["mood"] = _pre_mood
                if _pre_addiction and _pre_addiction != "other":
                    _collected["addiction_type"] = _pre_addiction
                _intake_state["collected"] = _collected
            except Exception:
                pass

            # Acknowledge the user's opening message in the intake greeting so their
            # words are not ignored before jumping to name collection.
            _first_q_text = INTAKE_QUESTIONS.get("opening", {}).get("question", "")
            if message and len(message.split()) >= 3:
                _ack = (
                    "I hear you — thank you for reaching out. 🙏\n\n"
                    + _first_q_text
                )
            else:
                _ack = _first_q_text

            logger.info(f"[{session_id}] Starting intake (new user, pre-populated: {list(_collected.keys())})")
            return {
                "response":        _ack,
                "intent":          "intake",
                "severity":        "low",
                "show_resources":  False,
                "citations":       [],
                "intake_complete": False,
                "intake_profile":  {},
                "intake_phase":    0,
                "session_id":      session_id,
                "timestamp":       datetime.now().isoformat(),
                "show_score":      False,
                "video":           None,
            }

    # ── LAYER 1.65: CLINICAL HANDSHAKE FEEDBACK INTERCEPT ────────────────
    # Intercepts binary feedback tokens (👍 / pivot choices / "quiet" / "sos")
    # before the full LLM/RAG pipeline and returns the Clinical Handshake immediately.
    # Crisis intercepts always have priority, so this gates on NOT _semantic_crisis_override.
    if not _semantic_crisis_override:
        _feedback_result = _handle_feedback_intercept(message, session)
        if _feedback_result is not None:
            logger.info(
                "[%s] Clinical Handshake intercept: intent=%s",
                session_id, _feedback_result.get("intent"),
            )
            return {
                **_feedback_result,
                "session_id": session_id,
                "timestamp":  datetime.now().isoformat(),
            }

    # ── LAYER 2: INTENT CLASSIFICATION ───────────────────────────────────

    # Extract addiction_type early so the classifier can resolve generic craving language
    # (e.g. "craving is so strong") to the correct addiction-specific intent.
    _early_addiction_type = (
        (session.get("intake_profile") or {}).get("addiction_type") or ""
    ).lower().strip() or None

    if not _semantic_crisis_override:
        intent, _secondary_intents = intent_classifier.classify_multi(message, addiction_type=_early_addiction_type)
    else:
        _secondary_intents: List[str] = []

    _addiction_override_intent = None
    _relationship_statement_override_intent = None
    _feedback_clarification_override_intent = None
    _relationship_continuity_override_intent = None
    _disclosure_question_override_intent = None
    if not _semantic_crisis_override:
        _previous_intent = session.get("last_intent")
        _previous_secondary = session.get("last_secondary_intents") or []

        _addiction_override_intent = _override_addiction_intent_from_message(message, intent)
        if _addiction_override_intent:
            if intent and intent != _addiction_override_intent and intent not in _secondary_intents:
                _secondary_intents = [intent] + _secondary_intents
            intent = _addiction_override_intent

        _feedback_clarification_override_intent = _override_feedback_clarification_intent(
            intent,
            _feedback_clarification_intent,
        )
        if _feedback_clarification_override_intent:
            if intent and intent != _feedback_clarification_override_intent and intent not in _secondary_intents:
                _secondary_intents = [intent] + _secondary_intents
            intent = _feedback_clarification_override_intent

        _relationship_statement_override_intent = _override_relationship_disclosure_statement_intent_from_message(
            message,
            intent,
        )
        if _relationship_statement_override_intent:
            if intent and intent != _relationship_statement_override_intent and intent not in _secondary_intents:
                _secondary_intents = [intent] + _secondary_intents
            intent = _relationship_statement_override_intent

        _relationship_continuity_override_intent = _override_relationship_continuity_intent_from_message(
            message,
            intent,
            _previous_intent,
            _previous_secondary,
            session.get("pending_feedback_intent"),
            _awaiting_feedback_free_text,
        )
        if _relationship_continuity_override_intent:
            if intent and intent != _relationship_continuity_override_intent and intent not in _secondary_intents:
                _secondary_intents = [intent] + _secondary_intents
            intent = _relationship_continuity_override_intent

        _disclosure_question_override_intent = _override_disclosure_question_intent_from_message(message, intent)
        if _disclosure_question_override_intent:
            if intent and intent != _disclosure_question_override_intent and intent not in _secondary_intents:
                _secondary_intents = [intent] + _secondary_intents
            intent = _disclosure_question_override_intent

        _secondary_intents = _normalize_secondary_intents(intent, _secondary_intents)

    intent_metadata = intent_classifier.get_intent_metadata(intent)
    if not _semantic_crisis_override:
        severity = intent_metadata["severity"]

    logger.info(f"[{session_id}] Classified intent: {intent} (severity: {severity})"
                + (f" | secondary: {_secondary_intents}" if _secondary_intents else ""))

    # Update session with intent
    session["last_intent"] = intent
    session["last_secondary_intents"] = _secondary_intents
    if severity not in session["severity_flags"]:
        session["severity_flags"].append(severity)

    # Extract context from user message
    update_context_from_turn(session_id, message, intent, intent_metadata)

    # Determine minimal questions to ask (if appropriate)
    next_questions = context.determine_questions_to_ask_next()
    should_ask_question = (
        len(next_questions) > 0
        and session["message_count"] >= 2
        and not session["last_question_asked"]
        and severity in {"low", "medium"}  # Don't ask during crises
        and not _semantic_crisis_override   # Never ask during semantic crisis intercept
    )

    # ── LAYER 4: RESPONSE GENERATION WITH 5-LAYER MODEL ──────────────────
    
    # Determine current 5-layer stage
    current_layer = get_current_layer(session["message_count"])
    
    # Build LLM system prompt with patient context injection
    # This ensures every response is tailored to the patient's current state and risk level
    patient_context_block = format_context_for_prompt(patient_context)
    layer_guidance = add_layer_awareness_to_system_prompt(patient_context, current_layer)

    # Extract addiction type and profile flags for clinical context differentiation
    addiction_type = (patient_context.onboarding.addiction_type or "").lower() or None
    profile_flags = session.get("intake_profile", {})

    # Build addiction×intent clinical context block (differentiates alcohol vs gaming for same symptom)
    clinical_context_block = build_clinical_context_block(addiction_type, intent, profile_flags)
    response_length_instruction = get_response_length_instruction(profile_flags)

    # Secondary-intent context hint — injected into system prompt so the LLM
    # can acknowledge co-present concerns in a single coherent response.
    _secondary_hint = (
        f"\nCo-present concerns detected in this message: {', '.join(_secondary_intents)}. "
        "Address the primary concern first, then briefly acknowledge the secondary concern(s) "
        "if clinically appropriate — do not let the secondary overshadow the primary."
        if _secondary_intents else ""
    )

    _ineffective = session.get("ineffective_interventions") or set()
    _intervention_hint = (
        "\nThe patient signalled that the previous strategy for this intervention did not help. "
        "Do not repeat the same coping instruction; provide a different concrete approach."
        if intent in _ineffective else ""
    )

    # Resolve active tone mode (Slide 7: 6 modes, driven by risk_level × todays_mood)
    _tone_mode = get_tone_mode(
        patient_context.risk.risk_level,
        patient_context.checkin.todays_mood,
    )

    system_prompt = f"""You are a mental health support chatbot specialising in recovery and peer support.
Active tone mode: {_tone_mode['label']} — apply this strictly throughout your response.

{patient_context_block}

{layer_guidance}
{clinical_context_block}
{_potential_crisis_context}
{_secondary_hint}
{_intervention_hint}

Core guidelines:
- Respect the patient's autonomy and recovery journey
- Use the context above to personalize your response
- Match the TONE directive above
- Never ask generic questions like "how are you"
- Reference specific context from the patient's profile when appropriate
- For High/Critical risk: Be direct, skip pleasantries, focus on stabilization
- THIS IS LAYER {current_layer} OF THE 5-LAYER CONVERSATION MODEL — FOLLOW THE RULES ABOVE STRICTLY
- RESPONSE FORMAT (mandatory): {response_length_instruction}
"""
    
    # ── PRE-LLM RAG RETRIEVAL ─────────────────────────────────────────────
    # Retrieve relevant evidence-based content and inject it into the system
    # prompt BEFORE the LLM generates a response, so the model synthesises the
    # information naturally into a 1-2 sentence empathetic reply.
    # Raw chunks are NEVER appended to the final response shown to the patient.
    _run_rag = not _semantic_crisis_override
    _rag_citations = []
    _retrieved_docs: List[Dict] = []
    if _run_rag:
        try:
            enriched_query = build_enriched_query(message, intent, addiction_type)
            retrieved_docs = retrieve(
                enriched_query,
                top_k=3,
                seen_chunk_ids=session["seen_chunk_ids"],
                severity=severity,
            )
            if retrieved_docs:
                _retrieved_docs = retrieved_docs
                rag_context = assemble_context(retrieved_docs)
                _rag_citations = format_citations(retrieved_docs)
                # Augment the system prompt with the retrieved evidence so the LLM
                # synthesises a concise, patient-friendly response — not a dump of PDF text.
                system_prompt += (
                    f"\n\nEVIDENCE CONTEXT (internal use only — do NOT quote or cite sources):\n"
                    f"Use the following clinical evidence to inform your response. "
                    f"Synthesise it into 1-2 warm, patient-friendly sentences. "
                    f"Never reproduce the text verbatim. Never mention PDF titles, page numbers, or sources.\n\n"
                    f"{rag_context}"
                )
        except Exception as e:
            logger.warning(f"RAG failed (non-critical): {e}")

    # Get base response from response generator
    # Extract addictions list (primary + comorbid) for ResponseRouter
    addictions_list = patient_context.onboarding.addictions or []

    response_text, response_meta = response_generator.generate(
        intent=intent,
        user_message=message,
        context_vector=context,
        addiction_type=addiction_type,  # Pass patient addiction type for differentiated responses
        addictions=addictions_list,     # Full list enables comorbidity detection
        system_prompt=system_prompt,    # Pass context-aware prompt (now includes RAG evidence)
        profile_flags=profile_flags,    # Pass flags so psychosis/bipolar guard fires on template responses
    )

    if _rag_citations:
        response_meta["citations"] = _rag_citations

    # ── GREETING PERSONALISATION ──────────────────────────────────────────────
    # When a known patient says hello, override the generic template with the
    # wearable-/checkin-aware greeting (same logic as /checkin-status endpoint).
    # _greeting_is_validated: set True when GreetingGenerator succeeds so the
    # downstream ethical_policy check is skipped (greeting content is pre-validated).
    _greeting_is_validated = False
    if intent == "greeting" and patient_code and patient_code != "UNKNOWN":
        try:
            _subj_data = get_latest_daily_checkin(patient_code, within_hours=48)
            _phys_data = get_latest_wearable_reading(patient_code, within_hours=48)
            _hist_data = get_historical_context(patient_code, days_back=30)
            _patient_rec = get_patient(patient_code)
            _pname = (
                (_patient_rec.get("first_name") or _patient_rec.get("display_name") or "there")
                if _patient_rec else "there"
            )
            _subj = None
            if _subj_data:
                from datetime import timezone
                from dateutil import parser as dateparser
                _emo = _subj_data.get("emotional_state") or _subj_data.get("todays_mood") or "neutral"
                _g_hours = None
                if _subj_data.get("created_at"):
                    try:
                        _created = dateparser.parse(_subj_data["created_at"])
                        if _created.tzinfo is None:
                            _created = _created.replace(tzinfo=timezone.utc)
                        _g_hours = (datetime.now(timezone.utc) - _created).total_seconds() / 3600
                    except Exception:
                        pass
                _subj = SubjectiveState(
                    emotional_state=_emo,
                    craving_intensity=_subj_data.get("craving_intensity", 5),
                    sleep_quality=_subj_data.get("sleep_quality", 5),
                    medication_taken=_subj_data.get("medication_taken", True),
                    triggers_today=_subj_data.get("triggers_today") or [],
                    checkin_timestamp=_subj_data.get("checkin_timestamp") or _subj_data.get("created_at"),
                    hours_ago=_g_hours,
                )
            _phys = None
            if _phys_data:
                _phys = PhysiologicalState(
                    heart_rate=_phys_data.get("heart_rate"),
                    hrv=_phys_data.get("hrv"),
                    sleep_hours=_phys_data.get("sleep_hours"),
                    steps_today=_phys_data.get("steps_today"),
                    stress_score=_phys_data.get("stress_score"),
                    spo2=_phys_data.get("spo2"),
                    personal_anomaly_flag=_phys_data.get("personal_anomaly_flag", False),
                    anomaly_detail=_phys_data.get("anomaly_detail"),
                    wearable_timestamp=_phys_data.get("wearable_timestamp"),
                    hours_ago=_phys_data.get("hours_ago"),
                )
            _hist = HistoricalContext(
                session_count=_hist_data.get("session_count", 0) if _hist_data else 0,
                days_since_last_session=_hist_data.get("days_since_last_session") if _hist_data else None,
                recurring_themes=_hist_data.get("recurring_themes", []) if _hist_data else [],
                crisis_history=bool(_hist_data.get("crisis_history", False)) if _hist_data else False,
            )
            _gctx = synthesize_patient_context(
                subjective=_subj, physiological=_phys,
                historical=_hist, patient_name=_pname,
            )
            _greeting_result = generate_greeting_message(_gctx, include_sources=False)
            response_text = _greeting_result["greeting"]
            _greeting_is_validated = True
            logger.info(f"[{session_id}] Personalized greeting generated for {patient_code} (risk={_greeting_result.get('risk_score')})")
        except Exception as _ge:
            logger.warning(f"[{session_id}] Personalized greeting failed, using generic: {_ge}")


    # Enforce 5-layer rules on response
    response_text, layer_notes = enforce_5layer_rules(
        response_text, 
        current_layer, 
        session.get("last_question_asked", False)
    )
    if layer_notes:
        logger.info(f"[{session_id}] 5-Layer enforcement: {'; '.join(layer_notes)}")
    
    # Add minimal question if appropriate (Layer 3 only)
    if current_layer == 3 and should_ask_question and next_questions:
        question_obj = next_questions[0]
        response_text = response_text + f"\n\n{question_obj['text']}"
        context.mark_question_asked(question_obj["id"])
        session["last_question_asked"] = True
        response_meta["minimal_question_id"] = question_obj["id"]
    else:
        session["last_question_asked"] = False
    
    # Track content for Layer 4 (video) — handled after video selection below.

    # ── LAYER 5: RESPONSE VALIDATION ─────────────────────────────────────
    
    # Validate response safety
    is_valid, error_msg = safety_checker.validate_response(response_text, intent)
    if not is_valid:
        logger.error(f"Response validation failed: {error_msg}")
        # For crisis intents the fallback MUST include crisis resources so the
        # downstream PolicyChecker (which also requires crisis keywords) does not
        # cascade into the cold "I apologize" response.
        if intent in {"crisis_suicidal", "crisis_abuse", "behaviour_self_harm"}:
            response_text = (
                "I'm really concerned about you right now. "
                "Please call emergency services (911 / 999 / 112) or a crisis helpline immediately. "
                "You deserve immediate support, and help is available right now."
            )
        else:
            response_text = "Thank you for sharing. I want to make sure I give you appropriate support. This requires a mental health professional to discuss further."
    
    # Check policy compliance — use the full ethical_policy module which catches
    # medication names, dosages, diagnosis claims, and identity violations.
    # services_pipeline.PolicyChecker is used as a fast pre-filter only.
    # Skip for pre-validated GreetingGenerator output (which may mention clinical
    # observations like "missed medication dose" that are safe in context).
    if _greeting_is_validated:
        compliant = True
        policy_violation = None
    else:
        _ep_result = check_policy(response_text, intent=intent, session_id=session_id)
        if _ep_result.violation:
            logger.error(
                f"[{session_id}] Policy violation ({_ep_result.violation_type}): "
                f"intent={intent}"
            )
            response_text = _ep_result.safe_response
            compliant = False
            policy_violation = {
                "rule": _ep_result.violation_type,
                "severity": "high",
                "message": f"Ethical policy violation: {_ep_result.violation_type}",
            }
        else:
            # Secondary check for crisis-resource presence on crisis intents
            compliant, policy_violation = policy_checker.check_policy_compliance(response_text, intent)
            if not compliant:
                logger.error(f"[{session_id}] Policy violation (crisis resources): {policy_violation}")
                response_text = "I apologize, but I need to provide a more appropriate response. Please contact a mental health professional for guidance on this topic."
    
    # Sanitize response (language safety, person-first language, etc.)
    try:
        response_text = sanitise_response(response_text)
    except Exception as e:
        logger.warning(f"Sanitization failed: {e}")
    
    # Check for self-stigma and reframe if needed
    try:
        stigma_reframe = check_self_stigma(message)
        if stigma_reframe:
            response_text = stigma_reframe + " " + response_text
    except Exception as e:
        logger.warning(f"Stigma check failed: {e}")

    # ── LAYER 4 RESOLUTION COMPOSER: TEXT (2-3 lines) + ONE PRECISE VIDEO ──
    # Slide 4 requirement:
    #   - text holds space with warm validation
    #   - one tightly matched video delivers the intervention
    # Video selection is driven by active intents + current patient state.
    _safety_video_skip = {
        "crisis_suicidal", "crisis_abuse", "behaviour_self_harm",
        "severe_distress", "psychosis_indicator", "medication_request",
    }
    _active_intents_base = [intent] + [
        s for s in _secondary_intents if s not in _safety_video_skip
    ]
    _focus = _detect_resolution_focus(
        intent=intent,
        addiction_type=addiction_type,
        retrieved_docs=_retrieved_docs,
        user_message=message,
    )
    if _awaiting_feedback_free_text and intent == "trigger_relationship":
        _focus = {
            "key": "disclosure_readiness",
            "phrase": "deciding what to share, why it may help, and how to do it safely at your pace",
            "video_hint_intent": _ADDICTION_TYPE_TO_INTENT.get(
                (addiction_type or "").lower().replace("-", "_").replace(" ", "_"),
                "trigger_relationship",
            ),
        }
    _active_intents = _build_resolution_active_intents(
        intent=intent,
        secondary_intents=_active_intents_base[1:],
        addiction_type=addiction_type,
        patient_context=patient_context,
        focus_hint_intent=_focus.get("video_hint_intent"),
    )

    watched_video_ids = set()
    try:
        if patient_id:
            watched_video_ids = get_watched_video_ids(patient_id)
    except Exception as _ve:
        logger.warning(f"Could not fetch video watch history: {_ve}")

    _focus_video_intent = _focus.get("video_hint_intent")
    video = get_video_for_patient(_focus_video_intent, watched_video_ids) if _focus_video_intent else None
    if not video:
        video = get_video_for_intents(_active_intents, watched_video_ids)
    if video:
        video = {**video, "active_intents": _active_intents}

    if intent not in _RESOLUTION_SKIP_INTENTS and not _semantic_crisis_override:
        resolution_payload = _compose_dynamic_resolution(
            intent=intent,
            user_message=message,
            patient_context=patient_context,
            focus=_focus,
            selected_video=video,
            session_message_count=session.get("message_count", 0),
            prior_relationships=session.get("last_relationship_mentions", []),
        )
        _resolution_text = resolution_payload.get("text", "").strip()
        if _resolution_text:
            _res_ok, _res_err = safety_checker.validate_response(_resolution_text, intent)
            if _res_ok:
                response_text = _resolution_text
                response_meta["resolution"] = resolution_payload
                # Feedback should be shown for any response that delivers a
                # structured therapeutic resolution, regardless of intent label.
                response_meta["show_feedback"] = True
            else:
                logger.warning(
                    f"[{session_id}] Resolution text rejected by safety validator: {_res_err}"
                )
    
    # ── PERSISTENCE LAYER: COMPREHENSIVE DATABASE UPDATE ────────────────
    
    try:
        base_risk_score = (
            patient_context.risk.live_risk_score
            if patient_context
            else None
        )
        persisted_risk_score = base_risk_score
        if intent == "relapse_disclosure":
            # Relapse disclosure should increase persisted risk tracking,
            # even when immediate crisis language is absent.
            if base_risk_score is None:
                persisted_risk_score = 70
            else:
                persisted_risk_score = min(100, int(base_risk_score) + 15)

        # Prepare checkin data if extractable from this interaction
        checkin_data = None
        if intent in ["mood_sad", "mood_anxious", "mood_angry", "mood_lonely", "mood_guilty", "behaviour_sleep", "relapse_disclosure"]:
            # Extract basic health data from context if available
            if patient_context:
                checkin_data = {
                    "mood": intent.replace("mood_", "") if intent.startswith("mood_") else None,
                    # craving_intensity is 0-10; patient_context.checkin.craving_intensity
                    # holds the value extracted during intake (defaults to 3 if unknown).
                    # Do NOT substitute persisted_risk_score (0-100 scale) here.
                    "craving_intensity": patient_context.checkin.craving_intensity,
                    "trigger_exposure_flag": "trigger_stress" in intent or "trigger_" in intent,
                    "relapse_disclosed": intent == "relapse_disclosure",
                }
        
        # Determine if crisis was detected
        crisis_detected = severity in ["high", "critical"] and intent != "relapse_disclosure"
        crisis_details = None
        if crisis_detected:
            crisis_details = {
                "type": intent if intent not in ["unclear", "error"] else "unspecified",
                "severity": severity,
                "escalation_status": "pending_review" if severity == "critical" else "identified",
            }
        
        # Call comprehensive update function to update ALL relevant tables
        db_update_results = update_all_tables_from_chatbot_interaction(
            patient_id=patient_id,
            patient_code=patient_code,
            session_id=session_id,
            user_message=message,
            bot_response=response_text,
            intent=intent,
            severity=severity,
            checkin_data=checkin_data,
            risk_score=persisted_risk_score,
            policy_violations=[policy_violation] if not compliant else None,
            crisis_detected=crisis_detected,
            crisis_details=crisis_details,
            video_shown=response_meta.get("video_shown"),
            current_layer=current_layer,
            response_tone=response_meta.get("tone"),
            response_latency_ms=response_meta.get("latency_ms"),
            rag_sources=response_meta.get("citations") if response_meta.get("rag_context_used") else None,
        )
        
        logger.info(f"[{session_id}] Comprehensive DB update completed: {db_update_results}")
        
    except Exception as db_error:
        logger.error(f"Comprehensive database update failed (non-critical): {db_error}")
        # Fall back to basic save_message if comprehensive update fails
        try:
            save_message(
                session_id=session_id,
                role="user",
                message=message,
                intent=intent,
                severity=severity,
                patient_id=patient_id,
                patient_code=patient_code,
            )
            save_message(
                session_id=session_id,
                role="assistant",
                message=response_text,
                intent=intent,
                severity=severity,
                patient_id=patient_id,
                patient_code=patient_code,
            )
            logger.info(f"[{session_id}] Fallback to basic save_message completed")
        except Exception as fallback_error:
            logger.error(f"Even fallback persistence failed: {fallback_error}")
    
    # Update session history (in-memory)
    session["history"].append({
        "role": "user",
        "content": message,
        "intent": intent,
        "timestamp": datetime.now().isoformat()
    })
    session["history"].append({
        "role": "assistant",
        "content": response_text,
        "intent": intent,
        "severity": severity,
        "timestamp": datetime.now().isoformat()
    })

    _latest_relationships = analyze_relationship_clause(message).mentions
    if _latest_relationships:
        session["last_relationship_mentions"] = _latest_relationships
    
    # ── BUILD RESPONSE OBJECT ────────────────────────────────────────────
    if video:
        # Persist watch history so this video is never repeated.
        record_video_shown(session, {
            "title": video.get("title"),
            "intent": intent,
            "url": video.get("url"),
            "completion_pct": 0,
        })
        try:
            # Write only the content_engagement row — all other tables were already
            # written in the persistence block above. A second full update would
            # create duplicate message/session/risk_assessment records.
            from db_comprehensive_update import ComprehensiveDatabaseUpdater as _Updater, _supabase_client as _supa_cli
            if patient_id and _supa_cli:
                _Updater(_supa_cli)._update_content_engagement_table(
                    patient_id=patient_id,
                    session_id=session_id,
                    video_shown=video,
                    intent=intent,
                )
        except Exception as _ve:
            logger.warning(f"[{session_id}] content_engagement write failed (non-critical): {_ve}")

    # Tag session with the last intervention intent so downstream tooling can
    # correlate a Clinical Handshake 👍/👎 response back to the tool that was served.
    if response_meta.get("show_feedback"):
        _ineffective_set = session.get("ineffective_interventions") or set()
        # Do not re-prompt feedback for interventions already marked ineffective,
        # or when feedback has been suppressed by timeout/safety.
        if (
            intent in _ineffective_set
            or session.get("feedback_prompt_suppressed")
            or severity in {"high", "critical"}
        ):
            response_meta["show_feedback"] = False

    if response_meta.get("show_feedback"):
        session["pending_feedback_intent"] = intent
        session["feedback_pivot_retries"] = 0
        session["awaiting_feedback_after_pivot"] = False

    return {
        "response": response_text,
        "intent": intent,
        "secondary_intents": _secondary_intents,
        "severity": severity,
        "show_resources": response_meta.get("show_resources", False),
        "resource_links": safety_checker.get_resource_links(intent) if response_meta.get("show_resources") else {},
        "show_feedback": response_meta.get("show_feedback", False),
        "resolution": response_meta.get("resolution"),
        "video": video,
        "session_id": session_id,
        "patient_code": patient_code,
        "patient_id": patient_id,
        "message_number": session["message_count"],
        "context_summary": context.get_relevant_context_summary(),
        "has_minimal_question": "minimal_question_id" in response_meta,
        "timestamp": datetime.now().isoformat(),
        "current_layer": current_layer,
        "metadata": {
            "intent_category": intent_metadata.get("category"),
            "requires_follow_up": intent_metadata.get("requires_follow_up"),
            "citations": response_meta.get("citations", []),
            "5layer_stage": f"Layer {current_layer} of 5-layer conversation model",
            "risk_level": patient_context.risk.risk_level,
            "risk_score": patient_context.risk.live_risk_score,
        }
    }


# ────────────────────────────────────────────────────────────────────────────
# SESSION MANAGEMENT
# ────────────────────────────────────────────────────────────────────────────

def get_session_summary(session_id: str) -> Dict:
    """Get summary of a session."""
    session = get_session(session_id)
    context = _get_context_if_exists(session_id)
    
    return {
        "session_id": session_id,
        "started_at": session["started_at"],
        "message_count": session["message_count"],
        "last_intent": session.get("last_intent"),
        "severity_flags": session["severity_flags"],
        "context_summary": context.get_relevant_context_summary() if context else "No context tracked",
    }


def _get_context_if_exists(session_id: str):
    """Get context if it exists in cache (helper)."""
    from patient_context import _context_cache
    return _context_cache.get(session_id)


def end_session(session_id: str) -> Dict:
    """End a session and clean up context."""
    summary = get_session_summary(session_id)
    _sessions.pop(session_id, None)
    clear_context(session_id)
    logger.info(f"Session {session_id} ended. Message count: {summary['message_count']}")
    return summary


# ────────────────────────────────────────────────────────────────────────────
# ANALYTICS & MONITORING
# ────────────────────────────────────────────────────────────────────────────

def get_session_stats(session_id: str) -> Dict:
    """Get detailed session statistics."""
    session = get_session(session_id)
    context = _get_context_if_exists(session_id)
    
    intents_used = {}
    for msg in session["history"]:
        if "intent" in msg:
            intent = msg["intent"]
            intents_used[intent] = intents_used.get(intent, 0) + 1
    
    return {
        "session_id": session_id,
        "total_turns": session["message_count"],
        "intents_detected": intents_used,
        "severity_progression": session["severity_flags"],
        "context_awareness": context.to_dict() if context else None,
        "session_duration_seconds": (
            (datetime.fromisoformat(session["history"][-1]["timestamp"]) -
             datetime.fromisoformat(session["history"][0]["timestamp"])).total_seconds()
            if session["history"] else 0
        ),
    }


# Keep original function names for backward compatibility
def classify_intent(text: str) -> str:
    """Backward compatibility wrapper."""
    return intent_classifier.classify(text)


# ── FastAPI wrapper ──────────────────────────────────────────────────────────
try:
    from contextlib import asynccontextmanager
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field

    # ── Daily data refresh scheduler ─────────────────────────────────────────
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from daily_data_refresh import run_daily_refresh

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Seed today's data on startup (skips gracefully if already present)
            try:
                run_daily_refresh()
            except Exception as _e:
                logger_startup.warning(f"Startup daily refresh failed: {_e}")

            scheduler = BackgroundScheduler()
            scheduler.add_job(run_daily_refresh, CronTrigger(hour=0, minute=0), id="daily_refresh")
            scheduler.start()
            logger_startup.info("✓ Daily data refresh scheduler started (runs at midnight UTC)")
            yield
            scheduler.shutdown(wait=False)
            logger_startup.info("Daily data refresh scheduler stopped")

    except ImportError as _sched_err:
        logger_startup.warning(f"APScheduler not available ({_sched_err}) — daily refresh disabled. Run: pip install apscheduler")

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            yield

    app = FastAPI(title="Trust AI Chatbot API", version="2.0.0", lifespan=lifespan)
    _allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    _frontend_url = os.getenv("FRONTEND_URL", "").strip()
    if _frontend_url and _frontend_url not in _allowed_origins:
        _allowed_origins.append(_frontend_url)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    class ChatRequest(BaseModel):
        message: str = Field(..., max_length=2000)
        session_id: str
        patient_id: Optional[str] = None
        patient_code: Optional[str] = None

    class SessionRequest(BaseModel):
        session_id: str

    @app.post("/chat")
    async def chat(req: ChatRequest):
        """Chat endpoint (main conversation loop)."""
        patient_id = req.patient_id or f"user_{req.session_id}"
        patient_code = req.patient_code or "UNKNOWN"
        
        # ── CRITICAL: Initialize patient and session in database ──────────────
        # ensure_patient() returns the real UUID — capture it so every subsequent
        # DB call (messages, sessions, content_engagement, ...) uses a valid UUID
        # and not the fallback "user_{session_id}" placeholder string.
        try:
            real_uuid = ensure_patient(patient_code=patient_code)
            if real_uuid:
                patient_id = real_uuid
            ensure_session(session_id=req.session_id, 
                          patient_id=patient_id, 
                          patient_code=patient_code)
        except Exception as e:
            logger.error(f"Failed to initialize patient/session: {e}")
            # Continue anyway - messages will be saved in-memory but not to DB
        
        result = handle_message(
            message=req.message,
            session_id=req.session_id,
            patient_id=patient_id,
            patient_code=patient_code,
        )
        return {"status": "ok", **result}

    @app.post("/session/clear")
    async def session_clear(req: SessionRequest):
        summary = end_session(req.session_id)
        return {"status": "cleared", "session_id": req.session_id, "summary": summary}

    @app.get("/session/{session_id}/summary")
    async def session_summary(session_id: str):
        try:
            summary = get_session_summary(session_id)
            return {"status": "ok", **summary}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/session/{session_id}/stats")
    async def session_stats(session_id: str):
        try:
            stats = get_session_stats(session_id)
            return {"status": "ok", **stats}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/")
    async def root():
        return {
            "service": "Trust AI Chatbot API",
            "version": "2.0.0",
            "status": "running",
            "note": "The chatbot UI is on port 3000. API docs at /docs"
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "timestamp": datetime.now().isoformat()}

    @app.get("/documents")
    async def documents():
        try:
            from rag_pipeline import get_document_list
            return {"documents": get_document_list()}
        except Exception:
            return {"documents": []}

    @app.get("/policy")
    async def policy():
        return POLICY_SUMMARY

    @app.get("/policy/disclosure")
    async def policy_disclosure():
        return {"disclosure": POLICY_DISCLOSURE_SHORT}

    @app.get("/patient/{patient_code}")
    async def patient_profile(patient_code: str):
        return get_patient(patient_code) or {"error": "Patient not found"}

    @app.get("/patient/{patient_code}/sessions")
    async def patient_sessions(patient_code: str):
        return {"sessions": get_patient_sessions(patient_code)}

    @app.get("/patient/{patient_code}/history")
    async def patient_history(patient_code: str):
        return {"history": get_patient_full_history(patient_code)}

    # ── NEW: GREETING CONTEXT ENDPOINTS ──────────────────────────────────────
    
    @app.get("/patient/{patient_code}/checkin-status")
    async def get_patient_checkin_context(patient_code: str, hours: int = 240):
        """
        Get synthesized patient context for greeting generation.
        
        Returns: greeting message, tone, risk score, and data freshness info.
        
        Query params:
          hours: Look back this many hours for recent data (default 240 = 10 days)
        """
        try:
            # Fetch from all three data sources
            subjective_data = get_latest_daily_checkin(patient_code, within_hours=hours)
            physiological_data = get_latest_wearable_reading(patient_code, within_hours=min(hours, 48))
            historical_data = get_historical_context(patient_code, days_back=max(1, hours // 24))
            
            # Convert to domain objects
            subjective = None
            if subjective_data:
                # Map DB column names to domain field names
                emotional_state = (
                    subjective_data.get("emotional_state")
                    or subjective_data.get("todays_mood")
                    or "neutral"
                ).lower()
                # Calculate hours_ago from created_at if not present
                hours_ago = subjective_data.get("hours_ago")
                if hours_ago is None and subjective_data.get("created_at"):
                    try:
                        from datetime import timezone
                        from dateutil import parser as dateparser
                        created = dateparser.parse(subjective_data["created_at"])
                        if created.tzinfo is None:
                            created = created.replace(tzinfo=timezone.utc)
                        hours_ago = (datetime.now(timezone.utc) - created).total_seconds() / 3600
                    except Exception:
                        pass
                subjective = SubjectiveState(
                    emotional_state=emotional_state,
                    craving_intensity=subjective_data.get("craving_intensity", 5),
                    sleep_quality=subjective_data.get("sleep_quality", 5),
                    medication_taken=subjective_data.get("medication_taken", True),
                    triggers_today=subjective_data.get("triggers_today") or [],
                    checkin_timestamp=subjective_data.get("checkin_timestamp") or subjective_data.get("created_at"),
                    hours_ago=hours_ago,
                )
            
            physiological = None
            if physiological_data:
                physiological = PhysiologicalState(
                    heart_rate=physiological_data.get("heart_rate"),
                    hrv=physiological_data.get("hrv"),
                    sleep_hours=physiological_data.get("sleep_hours"),
                    steps_today=physiological_data.get("steps_today"),
                    stress_score=physiological_data.get("stress_score"),
                    spo2=physiological_data.get("spo2"),
                    personal_anomaly_flag=physiological_data.get("personal_anomaly_flag", False),
                    anomaly_detail=physiological_data.get("anomaly_detail"),
                    wearable_timestamp=physiological_data.get("wearable_timestamp"),
                    hours_ago=physiological_data.get("hours_ago"),
                )
            
            historical = None
            if historical_data:
                historical = HistoricalContext(
                    recurring_themes=historical_data.get("recurring_themes", []),
                    recent_intents=historical_data.get("recent_intents", []),
                    crisis_history=historical_data.get("crisis_history", False),
                    last_session_timestamp=historical_data.get("last_session_timestamp"),
                    days_since_last_session=historical_data.get("days_since_last_session"),
                    session_count=historical_data.get("session_count", 0),
                )
            
            # Get patient name
            patient = get_patient(patient_code)
            patient_name = (
                patient.get("first_name") or patient.get("display_name") or "there"
            ) if patient else "there"
            
            # Synthesize context
            context = synthesize_patient_context(
                subjective=subjective,
                physiological=physiological,
                historical=historical,
                patient_name=patient_name
            )
            
            # Generate greeting
            greeting_result = generate_greeting_message(context, include_sources=False)
            
            # Persist context vector to audit table (non-blocking)
            patient_id = patient.get("patient_id") or patient.get("id") if patient else None
            if patient_id:
                try:
                    audit_context = {
                        "dominant_theme": context.dominant_theme,
                        "emotional_anchor": context.emotional_anchor,
                        "tone_directive": greeting_result["tone"],
                        "subjective_risk_score": context.subjective_risk_score,
                        "objective_risk_score": context.objective_risk_score,
                        "clinical_risk_score": greeting_result["risk_score"],
                        "contradiction_detected": context.contradiction_detected,
                        "contradiction_type": context.contradiction_type,
                        "layers": greeting_result.get("layers", {}),
                        "subjective_state": {
                            "emotional_state": context.subjective.emotional_state,
                            "craving_intensity": context.subjective.craving_intensity,
                            "sleep_quality": context.subjective.sleep_quality,
                        },
                        "physiological_state": {
                            "heart_rate": context.physiological.heart_rate if context.physiological else None,
                            "stress_score": context.physiological.stress_score if context.physiological else None,
                        },
                        "historical_context": {
                            "recurring_themes": context.historical.recurring_themes,
                            "session_count": context.historical.session_count,
                        },
                        "data_freshness": {
                            "subjective_hours_ago": context.subjective.hours_ago if context.subjective else None,
                            "physiological_hours_ago": context.physiological.hours_ago if context.physiological else None,
                            "historical_hours_ago": context.historical.days_since_last_session * 24 if context.historical.days_since_last_session else None,
                        }
                    }
                    
                    save_context_vector(patient_id, patient_code, "unknown", audit_context, greeting_result["greeting"])
                except Exception as audit_e:
                    logger.warning(f"Audit save failed (non-blocking): {audit_e}")
            
            # Return formatted response
            return {
                "status": "ok",
                "has_recent_activity": context.is_returning_user,
                "topics_covered": context.historical.recurring_themes,
                "hours_since_checkin": context.subjective.hours_ago,
                "greeting": greeting_result["greeting"],
                "tone": greeting_result["tone"],
                "risk_score": greeting_result["risk_score"],
                "dominant_theme": greeting_result["dominant_theme"],
                "data_freshness": greeting_result["data_freshness"],
                "layers": greeting_result["layers"],
            }
        except Exception as e:
            logger.error(f"get_patient_checkin_context failed: {e}")
            return {
                "status": "error",
                "has_recent_activity": False,
                "topics_covered": [],
                "greeting": f"Hi there, I'm here to listen and support you. What's on your mind today?",
                "error": str(e)
            }
    
    @app.post("/patient/{patient_code}/set-continuity")
    async def set_continuity_flag(patient_code: str, req: dict = None):
        """
        Record that continuity greeting was used.
        This flag helps the backend understand the greeting context was applied.
        """
        try:
            session_id = req.get("session_id") if isinstance(req, dict) else None
            
            # Update session metadata to flag that continuity greeting was applied
            if session_id:
                update_session_meta(session_id, {
                    "continuity_greeting_shown": True,
                    "continuity_at": datetime.now().isoformat()
                })
            
            return {"status": "ok", "message": "Continuity flag set"}
        except Exception as e:
            logger.error(f"set_continuity_flag failed: {e}")
            return {"status": "error"}
    
    @app.get("/admin/sessions")
    async def admin_sessions():
        return {"sessions": get_all_sessions()}

    @app.get("/admin/crisis")
    async def admin_crisis():
        return {"crisis_sessions": get_crisis_sessions()}

    @app.get("/admin/crisis/pending")
    async def admin_crisis_pending():
        return {"pending_crisis_events": get_pending_crisis_events()}

    @app.get("/admin/stats")
    async def admin_stats():
        return {"stats": get_conversation_stats()}

    @app.get("/admin/intents")
    async def admin_intents():
        return {"top_intents": get_top_intents()}

    @app.get("/admin/context-vectors/{patient_code}")
    async def admin_context_vectors(patient_code: str, limit: int = 50):
        """
        Retrieve context vector history for a patient.
        Clinical review of greeting synthesis decisions.
        """
        try:
            vectors = get_patient_context_vectors(patient_code, limit=limit)
            return {
                "status": "ok",
                "patient_code": patient_code,
                "count": len(vectors),
                "vectors": vectors
            }
        except Exception as e:
            logger.error(f"admin_context_vectors failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @app.get("/admin/context-trends/{patient_code}")
    async def admin_context_trends(patient_code: str, days: int = 30):
        """
        Analyze trends in synthesis decisions over time.
        Used for identifying patterns and clinical insights.
        """
        try:
            trends = get_context_vector_trends(patient_code, days=days)
            return {
                "status": "ok",
                "patient_code": patient_code,
                "days": days,
                "trends": trends
            }
        except Exception as e:
            logger.error(f"admin_context_trends failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @app.get("/admin/contradictions")
    async def admin_contradictions(patient_code: Optional[str] = None, limit: int = 100):
        """
        Retrieve all contradictions detected during synthesis.
        All patients if no patient_code, filtered to one patient otherwise.
        Used to identify patients needing clinical review.
        """
        try:
            contradictions = get_contradiction_patterns(patient_code, limit=limit)
            return {
                "status": "ok",
                "scope": f"patient:{patient_code}" if patient_code else "all_patients",
                "count": len(contradictions),
                "contradictions": contradictions
            }
        except Exception as e:
            logger.error(f"admin_contradictions failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

except ImportError:
    # FastAPI is optional (e.g., when running unit tests without HTTP server)
    pass
