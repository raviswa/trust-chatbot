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
import logging
import re
from datetime import datetime
from typing import Optional, Dict, List

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
from video_map import get_video, get_video_for_patient
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



# Database initialization (same as before - three-tier fallback)
logger_startup = logging.getLogger(__name__)

try:
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
        get_patient_addictions, get_response_routing_table
    )
    logger_startup.info("✓ Using Supabase PostgreSQL backend")
except Exception as e:
    logger_startup.warning(f"Supabase unavailable ({type(e).__name__}: {str(e)[:50]}), trying PostgreSQL...")
    try:
        from db import (
            ensure_patient, get_patient, get_patient_sessions,
            get_patient_full_history, get_checkin_status,
            ensure_session, update_session_meta, save_message,
            log_policy_violation, log_crisis_event,
            get_pending_crisis_events, get_policy_violation_summary,
            get_session_history, get_all_sessions, get_crisis_sessions,
            get_conversation_stats, get_top_intents,
            get_latest_daily_checkin, get_latest_wearable_reading, get_historical_context,
            save_context_vector, get_patient_context_vectors, get_context_vector_trends, get_contradiction_patterns
        )
        def get_watched_video_ids(patient_id):
            return set()  # PostgreSQL fallback — watch history not implemented
        def get_patient_onboarding(patient_code):
            return None  # PostgreSQL fallback — onboarding not implemented
        def save_intake_progress(patient_code, phase, pct):
            pass         # PostgreSQL fallback — intake progress not persisted
        def get_patient_addictions(patient_code):
            return []  # PostgreSQL fallback — addictions table not yet implemented
        def get_response_routing_table():
            return []  # PostgreSQL fallback — routing table not yet implemented
        logger_startup.info("✓ Using PostgreSQL database")
    except Exception as pg_error:
        logger_startup.warning(f"PostgreSQL unavailable ({type(pg_error).__name__}), using mock database for development")
        from db_mock import (
            ensure_patient, get_patient, get_patient_sessions,
            get_patient_full_history, get_checkin_status,
            ensure_session, update_session_meta, save_message,
            log_policy_violation, log_crisis_event,
            get_pending_crisis_events, get_policy_violation_summary,
            get_session_history, get_all_sessions, get_crisis_sessions,
            get_patient_addictions, get_response_routing_table
        )
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
            return None  # Mock — audit not persisted
        def get_patient_context_vectors(patient_code, limit=50):
            return []
        def get_context_vector_trends(patient_code, days=30):
            return {"risk_trend": [], "tone_distribution": {}, "theme_distribution": {}, "contradiction_count": 0, "avg_data_freshness": {}, "greetings_generated": 0}
        def get_contradiction_patterns(patient_code=None, limit=100):
            return []
        def get_watched_video_ids(patient_id):
            return set()  # Mock — no watch history in dev mode
        def get_patient_onboarding(patient_code):
            # Build minimal onboarding payload from seeded mock addictions.
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
                "last_intake_phase": 0,        # fresh — no prior intake in mock mode
                "intake_consent_given": False, # never completed in mock mode
            }
        def save_intake_progress(patient_code, phase, pct):
            pass  # Mock — intake progress not persisted to DB in dev mode

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

intent_classifier = IntentClassifier(intents_path="intents.json")
safety_checker = SafetyChecker()
policy_checker = PolicyChecker()
response_generator = ResponseGenerator(intents_path="intents.json")

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
        "addiction_gaming": "gaming habits",
        "addiction_social_media": "social media use",
    }
    return labels.get(intent, "what you shared earlier")


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
                logger.warning(f"Could not persist intake start: {_ipe}")
            _first_q = INTAKE_QUESTIONS.get("opening", {})
            logger.info(f"[{session_id}] Starting intake (new user)")
            return {
                "response":        _first_q.get("question", ""),
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

    # ── LAYER 2: INTENT CLASSIFICATION ───────────────────────────────────

    # Extract addiction_type early so the classifier can resolve generic craving language
    # (e.g. "craving is so strong") to the correct addiction-specific intent.
    _early_addiction_type = (
        (session.get("intake_profile") or {}).get("addiction_type") or ""
    ).lower().strip() or None

    if not _semantic_crisis_override:
        intent = intent_classifier.classify(message, addiction_type=_early_addiction_type)
    intent_metadata = intent_classifier.get_intent_metadata(intent)
    if not _semantic_crisis_override:
        severity = intent_metadata["severity"]

    logger.info(f"[{session_id}] Classified intent: {intent} (severity: {severity})")

    # Update session with intent
    session["last_intent"] = intent
    if severity not in session["severity_flags"]:
        session["severity_flags"].append(severity)

    # ── LAYER 3: CONTEXT EXTRACTION & MANAGEMENT ─────────────────────────

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

Core guidelines:
- Respect the patient's autonomy and recovery journey
- Use the context above to personalize your response
- Match the TONE directive above
- Never ask generic questions like "how are you"
- Reference specific context from the patient's profile when appropriate
- For High/Critical risk: Be direct, skip pleasantries, focus on stabilization
- THIS IS LAYER {current_layer} OF THE 5-LAYER CONVERSATION MODEL — FOLLOW THE RULES ABOVE STRICTLY
- {response_length_instruction}
"""
    
    # Get base response from response generator
    # Extract addictions list (primary + comorbid) for ResponseRouter
    addictions_list = patient_context.onboarding.addictions or []

    response_text, response_meta = response_generator.generate(
        intent=intent,
        user_message=message,
        context_vector=context,
        addiction_type=addiction_type,  # Pass patient addiction type for differentiated responses
        addictions=addictions_list,     # Full list enables comorbidity detection
        system_prompt=system_prompt,    # Pass context-aware prompt
        profile_flags=profile_flags,    # Pass flags so psychosis/bipolar guard fires on template responses
    )
    
    # Try RAG for general queries and high/critical severity turns.
    # RAG is suppressed when a semantic crisis INTERCEPT is active — the crisis
    # template is the authoritative response and RAG could dilute or contradict it.
    # For high/critical severity (WARN-level or intent-classified), we still run
    # RAG with a lowered score threshold so evidence-based grounding is included.
    _rag_intents = {"rag_query"}
    _run_rag = (
        not _semantic_crisis_override
        and (intent in _rag_intents or severity in {"high", "critical"})
    )
    if _run_rag:
        try:
            enriched_query = build_enriched_query(message, intent, addiction_type)
            retrieved_docs = retrieve(
                enriched_query,
                top_k=3,
                seen_chunk_ids=session["seen_chunk_ids"],
                severity=severity,      # lowers threshold for high/critical turns
            )
            if retrieved_docs:
                rag_context = assemble_context(retrieved_docs)
                response_text = f"{response_text}\n\n{rag_context}"
                response_meta["citations"] = format_citations(retrieved_docs)
        except Exception as e:
            logger.warning(f"RAG failed (non-critical): {e}")
    
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
    
    # Track content for Layer 4 (video) and future recommendations
    if response_meta.get("video_shown"):
        video = response_meta.get("video_shown")
        record_video_shown(session, {
            "title": video.get("title"),
            "intent": intent,
            "url": video.get("url"),
            "completion_pct": 0
        })
    
    # ── LAYER 5: RESPONSE VALIDATION ─────────────────────────────────────
    
    # Validate response safety
    is_valid, error_msg = safety_checker.validate_response(response_text, intent)
    if not is_valid:
        logger.error(f"Response validation failed: {error_msg}")
        response_text = "Thank you for sharing. I want to make sure I give you appropriate support. This requires a mental health professional to discuss further."
    
    # Check policy compliance
    compliant, policy_violation = policy_checker.check_policy_compliance(response_text, intent)
    if not compliant:
        logger.error(f"Policy violation: {policy_violation}")
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
    
    # ── PERSISTENCE LAYER: COMPREHENSIVE DATABASE UPDATE ────────────────
    
    try:
        base_risk_score = (
            patient_context.current_risk_score
            if patient_context and hasattr(patient_context, 'current_risk_score')
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
                    "craving_intensity": persisted_risk_score,
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
    
    # ── BUILD RESPONSE OBJECT ────────────────────────────────────────────
    
    # Retrieve video for this intent — skip videos already seen by this patient
    watched_video_ids = set()
    try:
        if patient_id:
            watched_video_ids = get_watched_video_ids(patient_id)
    except Exception as _ve:
        logger.warning(f"Could not fetch video watch history: {_ve}")
    video = get_video_for_patient(intent, watched_video_ids)

    # When the patient has a known addiction type, select the most clinically
    # relevant video:
    #   PRIMARY craving  → patient's own specific addiction video
    #   CROSS  craving   → video for the thing they're currently craving
    #                       (most immediately relevant education)
    #   Non-addiction intent with craving keywords → patient's primary video
    if addiction_type:
        _addtype = addiction_type.lower().strip().replace(" ", "_").replace("-", "_")

        # addiction_type → video MAP key (alcohol gets specific video, not generic drugs)
        _PRIMARY_VIDEO: Dict[str, str] = {
            "alcohol":      "addiction_alcohol",
            "drugs":        "addiction_drugs",
            "gaming":       "addiction_gaming",
            "social_media": "addiction_social_media",
            "nicotine":     "addiction_nicotine",
            "smoking":      "addiction_nicotine",
            "gambling":     "addiction_gambling",
            "work":         "addiction_work",
        }
        # Which intent is each addiction_type's primary craving
        _PRIMARY_INTENT_VIDEO: Dict[str, str] = {
            "alcohol":      "addiction_drugs",
            "drugs":        "addiction_drugs",
            "gaming":       "addiction_gaming",
            "social_media": "addiction_social_media",
            "nicotine":     "addiction_nicotine",
            "smoking":      "addiction_nicotine",
            "gambling":     "addiction_gambling",
        }
        # All addiction-craving intents and their video keys
        _ADDICTION_INTENT_VIDEO: Dict[str, str] = {
            "addiction_drugs":        "addiction_drugs",
            "addiction_gaming":       "addiction_gaming",
            "addiction_social_media": "addiction_social_media",
            "addiction_nicotine":     "addiction_nicotine",
            "addiction_gambling":     "addiction_gambling",
            "addiction_work":         "addiction_work",
        }
        # Keywords that signal a craving message for each addiction_type
        _CRAVING_KEYWORDS: Dict[str, List[str]] = {
            "alcohol":      ["beer", "wine", "vodka", "drink", "alcohol", "whiskey", "rum", "gin", "spirits", "pub", "bar"],
            "drugs":        ["drug", "substance", "cocaine", "heroin", "meth", "pills", "using", "relapse"],
            "gaming":       ["game", "gaming", "play", "console", "controller", "stream", "online"],
            "social_media": ["instagram", "twitter", "tiktok", "scroll", "feed", "social media", "refresh", "notifications"],
            "nicotine":     ["smoke", "smoking", "cigarette", "vape", "vaping", "nicotine", "fag"],
            "smoking":      ["smoke", "smoking", "cigarette", "vape", "vaping", "nicotine", "fag"],
            "gambling":     ["bet", "betting", "casino", "gamble", "gambling", "poker", "slot", "wager", "flutter", "lottery"],
        }

        _primary_video_key = _PRIMARY_VIDEO.get(_addtype)
        _primary_intent    = _PRIMARY_INTENT_VIDEO.get(_addtype)
        _msg_lower         = message.lower()

        if _primary_video_key and intent in _ADDICTION_INTENT_VIDEO:
            if intent == _primary_intent:
                # PRIMARY craving — use patient's own specific video
                # (e.g. alcohol patient craving alcohol → addiction_alcohol video, not generic)
                _chosen_key = _primary_video_key
            else:
                # CROSS-addiction craving — use video for what they're craving right now
                _chosen_key = _ADDICTION_INTENT_VIDEO[intent]
            _chosen_video = get_video_for_patient(_chosen_key, watched_video_ids)
            if _chosen_video:
                video = _chosen_video

        elif _primary_video_key:
            # Intent is not an addiction intent — show patient's primary video only
            # if the message contains recognisable craving signals
            if any(kw in _msg_lower for kw in _CRAVING_KEYWORDS.get(_addtype, [])):
                _pv = get_video_for_patient(_primary_video_key, watched_video_ids)
                if _pv:
                    video = _pv

    return {
        "response": response_text,
        "intent": intent,
        "severity": severity,
        "show_resources": response_meta.get("show_resources", False),
        "resource_links": safety_checker.get_resource_links(intent) if response_meta.get("show_resources") else {},
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
    from pydantic import BaseModel

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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class ChatRequest(BaseModel):
        message: str
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
        # These MUST be called before handle_message() to ensure FK constraints pass
        try:
            ensure_patient(patient_code=patient_code)
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
