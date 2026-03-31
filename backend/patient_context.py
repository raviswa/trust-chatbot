"""
patient_context.py — Unified Patient Context Module

Consolidates all patient context data modelling, assembly, synthesis, tracking,
and clinical query enrichment into one place.

SECTIONS
========
  §1  DATA MODEL           — Dataclasses for the 4-source PatientContext used by handle_message()
  §2  CONTEXT ASSEMBLY     — build_context(), compute_risk_score(), format_context_for_prompt()
  §3  5-LAYER MODEL        — get_current_layer(), enforce_5layer_rules(), add_layer_awareness_to_system_prompt()
  §4  VIDEO TRACKING       — record_video_shown(), should_show_video()
  §5  MINIMAL-Q TRACKER    — PatientContextVector, in-memory cache, get_or_create_context(), update_context_from_turn()
  §6  CLINICAL SYNTHESIS   — SubjectiveState, PhysiologicalState, HistoricalContext, SynthesizedContextVector,
                             PatientContextSynthesizer, synthesize_patient_context()
                             (implements the Zero-Question clinical principle)
  §7  CLINICAL QUERY BUILDER — CONTEXT_MAP, ADDICTION_DEFAULTS, build_clinical_context_block(),
                             build_enriched_query(), build_topic_filter(), get_response_length_instruction()
                             (answers: "should alcohol & gaming patients get the same sleeplessness response?")
"""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# §1  DATA MODEL
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class OnboardingProfile:
    """Data collected during initial intake"""
    name: str = "Patient"
    addiction_type: str = ""                                  # primary addiction (backward compat)
    addictions: List[dict] = field(default_factory=list)      # full list, primary first
    baseline_mood: List[str] = field(default_factory=list)
    primary_triggers: List[str] = field(default_factory=list)
    support_network: Dict[str, str] = field(default_factory=dict)
    work_status: str = ""


@dataclass
class DailyCheckin:
    """Data from today's check-in"""
    todays_mood: str = "Neutral"
    sleep_quality: int = 5
    craving_intensity: int = 3
    medication_taken: bool = True
    triggers_today: List[str] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class ContentEngagement:
    """Track user interaction with therapeutic content"""
    last_video_watched: Optional[Dict[str, Any]] = None
    content_preferences: List[str] = field(default_factory=list)
    skipped_content: List[str] = field(default_factory=list)
    most_effective_content: List[str] = field(default_factory=list)
    videos_shown_this_session: List[str] = field(default_factory=list)


@dataclass
class RiskAssessment:
    """Computed live risk state"""
    live_risk_score: int = 30
    risk_level: str = "Low"
    key_risk_drivers: List[str] = field(default_factory=list)
    crisis_flag: bool = False


@dataclass
class PatientContext:
    """Complete patient context vector assembled from 4 sources"""
    session_id: str = ""
    patient_id: str = ""

    onboarding: OnboardingProfile = field(default_factory=OnboardingProfile)
    checkin: DailyCheckin = field(default_factory=DailyCheckin)
    content: ContentEngagement = field(default_factory=ContentEngagement)
    risk: RiskAssessment = field(default_factory=RiskAssessment)

    context_assembled_at: str = ""
    is_returning_user: bool = False
    session_message_count: int = 0


# ════════════════════════════════════════════════════════════════════════════
# §2  CONTEXT ASSEMBLY
# ════════════════════════════════════════════════════════════════════════════

def build_context(session: Dict[str, Any]) -> PatientContext:
    """Assemble complete patient context from session dict"""

    intake = session.get("intake_profile", {})
    onboarding = OnboardingProfile(
        name=intake.get("name", "Patient"),
        addiction_type=intake.get("addiction_type", ""),
        addictions=intake.get("addictions", []),
        baseline_mood=intake.get("baseline_mood", []) or [],
        primary_triggers=intake.get("primary_triggers", []) or [],
        support_network=intake.get("support_network", {}) or {},
        work_status=intake.get("work_status", ""),
    )

    checkin_data = session.get("checkin_data", {})
    mood_today = checkin_data.get("mood_today") or session.get("patient_name_mood", "Neutral")
    sleep_quality = checkin_data.get("rest_level") or checkin_data.get("sleep_quality", 5)
    craving = checkin_data.get("craving_intensity", 3)
    meds = checkin_data.get("medication_taken")
    if meds is None:
        meds = not checkin_data.get("medication_missed", False)

    checkin = DailyCheckin(
        todays_mood=mood_today,
        sleep_quality=int(sleep_quality) if sleep_quality else 5,
        craving_intensity=int(craving) if craving else 3,
        medication_taken=meds if isinstance(meds, bool) else True,
        triggers_today=checkin_data.get("triggers_today", []) or [],
        timestamp=checkin_data.get("timestamp", datetime.now().isoformat()),
    )

    content_data = session.get("content_engagement", {})
    content = ContentEngagement(
        last_video_watched=content_data.get("last_video_watched"),
        content_preferences=content_data.get("content_preferences", []) or [],
        skipped_content=content_data.get("skipped_content", []) or [],
        most_effective_content=content_data.get("most_effective_content", []) or [],
        videos_shown_this_session=content_data.get("videos_shown", []) or [],
    )

    risk = compute_risk_score(checkin)

    ctx = PatientContext(
        session_id=session.get("session_id", ""),
        patient_id=session.get("patient_id", ""),
        onboarding=onboarding,
        checkin=checkin,
        content=content,
        risk=risk,
        context_assembled_at=datetime.now().isoformat(),
        is_returning_user=bool(session.get("message_count", 0) > 1),
        session_message_count=session.get("message_count", 0),
    )

    logger.info(f"[{ctx.session_id}] Context: {ctx.onboarding.name} | Risk: {ctx.risk.risk_level} ({ctx.risk.live_risk_score})")
    return ctx


def compute_risk_score(checkin: DailyCheckin) -> RiskAssessment:
    """
    Compute live risk score (0-100) from daily check-in.
    Weighted arithmetic — no ML required.

    Risk levels: Low (0-25), Medium (26-50), High (51-80), Critical (81+)
    """
    score = 0
    drivers = []

    # Sleep quality
    if checkin.sleep_quality < 5:
        impact = int((5 - checkin.sleep_quality) * 5)
        score += impact
        drivers.append(f"sleep -{impact}")
    elif checkin.sleep_quality < 7:
        impact = int((7 - checkin.sleep_quality) * 3)
        score += impact
        drivers.append(f"sleep -{impact}")

    # Craving intensity
    if checkin.craving_intensity > 6:
        impact = int((checkin.craving_intensity - 6) * 5)
        score += impact
        drivers.append(f"cravings +{impact}")
    elif checkin.craving_intensity > 3:
        impact = int((checkin.craving_intensity - 3) * 3)
        score += impact
        drivers.append(f"cravings +{impact}")

    # Mood
    if checkin.todays_mood in ["Sad", "Angry", "Stressed", "Lonely"]:
        score += 20
        drivers.append(f"mood({checkin.todays_mood}) +20")
    elif checkin.todays_mood == "Happy":
        score = max(0, score - 10)
        drivers.append("mood(Happy) -10")

    # Medication adherence
    if not checkin.medication_taken:
        score += 15
        drivers.append("missed_meds +15")

    score = min(100, max(0, score))

    if score < 26:
        risk_level = "Low"
    elif score < 51:
        risk_level = "Medium"
    elif score < 81:
        risk_level = "High"
    else:
        risk_level = "Critical"

    return RiskAssessment(
        live_risk_score=score,
        risk_level=risk_level,
        key_risk_drivers=drivers[:3],
        crisis_flag=False,
    )


def format_context_for_prompt(ctx: PatientContext) -> str:
    """Format patient context as concise text block for LLM system prompt"""
    lines = []
    lines.append("=== PATIENT CONTEXT ===")
    lines.append(f"Patient: {ctx.onboarding.name}")
    lines.append(f"Recovery focus: {ctx.onboarding.addiction_type or 'Not specified'}")

    if ctx.onboarding.baseline_mood:
        lines.append(f"Known emotional patterns: {', '.join(ctx.onboarding.baseline_mood)}")
    if ctx.onboarding.primary_triggers:
        lines.append(f"Key triggers: {', '.join(ctx.onboarding.primary_triggers)}")
    if ctx.onboarding.support_network:
        support_str = ", ".join([f"{k}: {v}" for k, v in ctx.onboarding.support_network.items()])
        lines.append(f"Support network: {support_str}")

    lines += [
        "",
        "=== TODAY'S STATE ===",
        f"Mood: {ctx.checkin.todays_mood}",
        f"Sleep quality: {ctx.checkin.sleep_quality}/10",
        f"Craving intensity: {ctx.checkin.craving_intensity}/10",
        f"Medication taken: {'Yes' if ctx.checkin.medication_taken else 'No'}",
    ]
    if ctx.checkin.triggers_today:
        lines.append(f"Triggers today: {', '.join(ctx.checkin.triggers_today)}")

    lines += [
        "",
        "=== RISK ASSESSMENT ===",
        f"Live risk score: {ctx.risk.live_risk_score}/100",
        f"Risk level: {ctx.risk.risk_level}",
    ]
    if ctx.risk.key_risk_drivers:
        lines.append(f"Risk drivers: {', '.join(ctx.risk.key_risk_drivers)}")

    lines.append("")
    tone = get_tone_mode(ctx.risk.risk_level, ctx.checkin.todays_mood)
    lines.append(f"ACTIVE TONE MODE: {tone['label']}")
    lines.append(tone["directive"])

    if ctx.content.most_effective_content:
        lines.append(f"\nMost helpful content: {', '.join(ctx.content.most_effective_content[:2])}")
    if ctx.content.last_video_watched:
        v = ctx.content.last_video_watched
        lines.append(f"Last viewed: {v.get('title', 'Unknown')} ({v.get('completion_pct', 0)}% complete)")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════════
# §2b  TONE ENGINE — Slide 7: 6 Distinct Tone Modes
#       Tone is determined by risk_level × todays_mood combination.
#       Risk level takes priority at the extremes (Critical/High);
#       mood modulates tone at Medium/Low.
# ════════════════════════════════════════════════════════════════════════════

# Mood keyword sets for matching against free-text mood values
_GUILT_MOODS:    frozenset = frozenset({"guilty", "guilt", "ashamed", "shame", "embarrassed", "humiliated"})
_LONELY_SAD_MOODS: frozenset = frozenset({"lonely", "alone", "isolated", "sad", "sadness", "grief", "depressed", "miserable", "low"})
_ANXIOUS_MOODS:  frozenset = frozenset({"anxious", "anxiety", "stressed", "stress", "nervous", "worried", "overwhelmed", "panicked", "panic"})

# The 6 tone modes from Slide 7 — each carries a short label and a full LLM directive
_TONE_MODES: Dict[str, Dict[str, str]] = {
    # 1 ── Warm / Energising ─────────────────────────────────────────────────
    # Low risk + positive or neutral mood.
    # Recovery progress is real — meet the patient in that energy.
    "warm_energising": {
        "label": "Warm / Energising",
        "directive": (
            "TONE — WARM AND ENERGISING: "
            "Affirm the patient's progress and build momentum. "
            "Celebrate small wins without minimising ongoing struggle. "
            "Use forward-facing, encouraging language. "
            "Energy is available here — meet it and amplify it gently."
        ),
    },
    # 2 ── Calm / Grounding ──────────────────────────────────────────────────
    # Medium risk, or stressed/anxious mood at any risk.
    # The patient needs steadiness before they can receive support.
    "calm_grounding": {
        "label": "Calm / Grounding",
        "directive": (
            "TONE — CALM AND GROUNDING: "
            "Validate the patient's feelings explicitly before offering any guidance. "
            "Use slow, steady language — no urgency, no rapid transitions. "
            "One idea at a time. "
            "Anchor the patient in the present moment before introducing any coping tool."
        ),
    },
    # 3 ── Direct / Immediate ────────────────────────────────────────────────
    # High risk (any mood). Speed and clarity matter more than warmth.
    "direct_immediate": {
        "label": "Direct / Immediate",
        "directive": (
            "TONE — DIRECT AND IMMEDIATE: "
            "No preamble. No pleasantries. Lead immediately with the most important stabilising statement. "
            "Offer exactly one concrete action. "
            "Skip elaboration — this patient needs a clear next step right now, not explanation. "
            "Brevity is clinical care at this risk level."
        ),
    },
    # 4 ── Quiet / Stabilising ───────────────────────────────────────────────
    # Critical risk (any mood). De-escalation is the only goal.
    "quiet_stabilising": {
        "label": "Quiet / Stabilising",
        "directive": (
            "TONE — QUIET AND STABILISING: "
            "Extremely short sentences only. "
            "Offer a single breathing anchor — nothing else. "
            "No clinical language. No questions of any kind. No new information. "
            "Stay entirely in the present moment. "
            "Do not escalate, explain, or add content. Hold the patient here."
        ),
    },
    # 5 ── Non-judgmental / Compassionate ────────────────────────────────────
    # Any risk level when guilt or shame is the dominant mood.
    # Shame forecloses on tools — compassion must come first.
    "nonjudgmental_compassionate": {
        "label": "Non-judgmental / Compassionate",
        "directive": (
            "TONE — NON-JUDGMENTAL AND COMPASSIONATE: "
            "Guilt or shame is present — do not probe or ask 'why'. "
            "Separate the person from the behaviour explicitly early in the response. "
            "Warmth and acceptance must come before any tool or suggestion. "
            "No performance pressure. No expectations. "
            "Say clearly: this does not define who you are."
        ),
    },
    # 6 ── Warm / Present ────────────────────────────────────────────────────
    # Low or medium risk when loneliness, sadness, or grief is dominant.
    # The antidote to disconnection is felt presence, not solutions.
    "warm_present": {
        "label": "Warm / Present",
        "directive": (
            "TONE — WARM AND PRESENT: "
            "Loneliness, sadness, or grief is present — presence matters more than problem-solving. "
            "Reflect what the patient has said before responding. "
            "Do not jump to coping tools or solutions. "
            "Affirm explicitly that they are not alone. "
            "Keep the exchange unhurried. The most important thing right now is that they feel heard."
        ),
    },
}


def get_tone_mode(risk_level: str, todays_mood: str) -> Dict[str, str]:
    """
    Return the Slide 7 tone mode dict for the given risk_level × mood combination.

    Priority order (most clinically specific first):
      1. Critical risk  →  Quiet / Stabilising          (mood irrelevant)
      2. High risk      →  Direct / Immediate            (mood irrelevant)
      3. Any risk + guilt/shame mood  →  Non-judgmental / Compassionate
      4. Any risk + lonely/sad mood   →  Warm / Present
      5. Medium + anxious/stressed    →  Calm / Grounding
      6. Low + positive/neutral       →  Warm / Energising
      7. Default (medium / unknown)   →  Calm / Grounding
    """
    mood_lower = (todays_mood or "").lower().strip()
    risk_lower = (risk_level or "").lower()

    # Risk-level extremes always win
    if risk_lower == "critical":
        return _TONE_MODES["quiet_stabilising"]
    if risk_lower == "high":
        return _TONE_MODES["direct_immediate"]

    # Mood-specific overrides (medium and low risk)
    if any(m in mood_lower for m in _GUILT_MOODS):
        return _TONE_MODES["nonjudgmental_compassionate"]
    if any(m in mood_lower for m in _LONELY_SAD_MOODS):
        return _TONE_MODES["warm_present"]
    if any(m in mood_lower for m in _ANXIOUS_MOODS):
        return _TONE_MODES["calm_grounding"]

    if risk_lower == "low":
        return _TONE_MODES["warm_energising"]

    return _TONE_MODES["calm_grounding"]  # default for medium / unknown


def get_tone_for_risk_level(risk_level: str) -> str:
    """Return tone label for the given risk level (mood-neutral fallback)."""
    return get_tone_mode(risk_level, "")["label"]


def get_opening_line(ctx: PatientContext) -> str:
    """Generate context-aware opening (never generic 'how are you')"""
    name = ctx.onboarding.name
    mood = ctx.checkin.todays_mood
    sleep = ctx.checkin.sleep_quality
    craving = ctx.checkin.craving_intensity

    if ctx.risk.risk_level == "Critical":
        return (
            f"Hi {name}. I'm concerned about how you're doing right now. "
            f"Let's focus on getting you stable. I'm here."
        )
    elif ctx.risk.risk_level == "High":
        if sleep < 5:
            return (
                f"Hi {name}. I see sleep has been rough — that makes everything harder. "
                f"Let's talk about what's weighing on you."
            )
        elif craving > 7:
            return (
                f"Hi {name}. Cravings are high today, and that's significant. "
                f"I'm here to help you work through this."
            )
        else:
            return f"Hi {name}. {mood} day — I'm here to support you through it."
    elif ctx.risk.risk_level == "Medium":
        if sleep < 6:
            return (
                f"Hi {name}. Last night was rough on sleep. "
                f"That can make the day feel extra heavy. What's on your mind?"
            )
        else:
            return (
                f"Hi {name}. Feeling {mood.lower()} today. "
                f"Recovery has ups and downs — I'm here for both. What's happening?"
            )
    else:
        return f"Hi {name}. Good to see you. You're doing well. What's on your mind today?"


# ════════════════════════════════════════════════════════════════════════════
# §3  5-LAYER CONVERSATION MODEL
# ════════════════════════════════════════════════════════════════════════════

def get_current_layer(message_count: int) -> int:
    """
    Map message count → 5-layer stage.

    Layer 1: Opening (msg 0)   — Greet with context, zero questions
    Layer 2: Invitation (msg 1) — One open prompt, listen
    Layer 3: Clarify (msg 2)   — Ask 1 question if needed
    Layer 4: Response (msg 3+) — Text + video (2-3 lines)
    Layer 5: Closure (msg 4+)  — Soft CTA
    """
    if message_count <= 0:
        return 1
    elif message_count == 1:
        return 2
    elif message_count == 2:
        return 3
    elif message_count == 3:
        return 4
    else:
        return 5


def enforce_5layer_rules(response_text: str, current_layer: int, last_question_asked: bool) -> tuple:
    """
    Enforce 5-layer model rules on generated response text.
    Returns (modified_response_text, compliance_notes).
    """
    notes = []

    if current_layer == 1:
        if "?" in response_text:
            response_text = re.sub(r'\s*\?+\s*$', '', response_text)
            response_text = re.sub(r'(\w)\?', r'\1.', response_text)
            notes.append("Layer 1: Removed questions (greeting should have zero questions)")

    elif current_layer == 2:
        if response_text.count("?") > 1:
            parts = response_text.split("?")
            response_text = parts[0] + "?" + " ".join(parts[1:]).replace("?", ".")
            notes.append("Layer 2: Limited to one question (invitation)")

    elif current_layer == 5:
        if response_text.rstrip().endswith("?"):
            response_text = response_text.rstrip()[:-1] + "."
            notes.append("Layer 5: Changed ending question to statement (soft CTA required)")

    return response_text, notes


def add_layer_awareness_to_system_prompt(ctx: PatientContext, current_layer: int) -> str:
    """Return layer-specific guidance string for injection into the LLM system prompt."""
    layer_guidance = {
        1: """LAYER 1 - GREETING WITH CONTEXT (First message only)
CRITICAL RULES:
- Greet with patient name and specific check-in data (mood, sleep, cravings)
- Never ask "how are you" or generic questions
- Zero questions in this response
- Build empathy using what you already know
- Set the tone based on risk level""",

        2: """LAYER 2 - INVITE, DON'T INTERROGATE (Second message)
CRITICAL RULES:
- One open invitation maximum (e.g., "Tell me what's happening")
- Listen, don't ask multiple questions
- Acknowledge emotions with markers (I hear you, that sounds tough)
- Zero interrogation questions
- Match the tone from Layer 1""",

        3: """LAYER 3 - CLARIFY IF AMBIGUOUS (Third message)
CRITICAL RULES:
- Ask max 1 targeted clarifying question if intent is unclear
- Skip the question if you understand the issue
- If patient describes multiple issues, pick the most urgent one
- Use NLP-based confidence: if confident > 80%, don't ask""",

        4: """LAYER 4 - TEXT + VIDEO RESPONSE (Fourth message onwards)
CRITICAL RULES:
- Keep response to 2-3 lines max
- Validate the user's experience first
- Then offer concrete support (tools, practices, next steps)
- Video will be included separately in response object
- One brief soft prompt or no prompt at all""",

        5: """LAYER 5 - CLOSE WITH AGENCY (Fifth message onwards)
CRITICAL RULES:
- End with soft CTA: a tool, practice, or opt-out
- NOT another question
- Examples: "You could try...", "Next time consider...", "No pressure to..."
- Let the user decide next steps (agency matters)
- Affirm their strength""",
    }
    return layer_guidance.get(current_layer, "")


# ════════════════════════════════════════════════════════════════════════════
# §4  VIDEO TRACKING
# ════════════════════════════════════════════════════════════════════════════

def record_video_shown(session: dict, video_data: dict) -> None:
    """Record video shown to patient (prevent Layer 4 repetition)."""
    if "content_engagement" not in session:
        session["content_engagement"] = {"videos_shown": []}

    videos = session["content_engagement"].get("videos_shown", [])
    videos.append(video_data.get("title", "Unknown"))
    session["content_engagement"]["videos_shown"] = videos[-5:]

    session["content_engagement"]["last_video_watched"] = {
        "title": video_data.get("title"),
        "intent": video_data.get("intent"),
        "watched_at": datetime.now().isoformat(),
        "completion_pct": video_data.get("completion_pct", 0),
    }


def should_show_video(session: dict, intent: str) -> bool:
    """
    Check if video should be shown (Layer 4 rule: avoid repetition).
    Returns False if 3+ videos shown this session or same intent repeated.
    """
    videos = session.get("content_engagement", {}).get("videos_shown", [])
    if len(videos) >= 3:
        return False
    if session.get("last_intent") == intent and len(videos) > 0:
        return False
    return True


# ════════════════════════════════════════════════════════════════════════════
# §5  MINIMAL-QUESTION CONTEXT TRACKER
#     Implements "WHAT THE CHATBOT ALREADY KNOWS" — avoids redundant questions
# ════════════════════════════════════════════════════════════════════════════

class PatientContextVector:
    """
    In-session tracker of discovered patient facts.
    Enables minimal-question conversations by recording what is already known.
    """

    def __init__(self, patient_id: str, patient_code: str):
        self.patient_id = patient_id
        self.patient_code = patient_code

        self.demographics = {
            "age": None, "gender": None, "location": None, "occupation": None,
        }

        self.mental_health_profile = {
            "diagnosed_conditions": set(),
            "current_medications": set(),
            "previous_treatments": set(),
            "family_history": None,
            "trauma_history": None,
        }

        self.current_state = {
            "primary_concerns": set(),
            "mood_level": None,
            "severity_flags": set(),
            "coping_mechanisms": set(),
            "support_system": None,
            "last_updated": None,
        }

        self.conversation_history = {
            "total_sessions": 0,
            "total_messages": 0,
            "last_session_date": None,
            "recurring_themes": {},
            "previous_crises": [],
        }

        self.questions_asked: Set[str] = set()

        self.preferences = {
            "preferred_tone": "supportive",
            "response_length": "moderate",
            "languages": ["English"],
            "avoid_topics": set(),
        }

        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def extract_from_conversation(self, user_message: str, intent: str, metadata: Dict = None):
        """Extract and update context from a user message and detected intent."""
        msg = user_message.lower()

        condition_keywords = {
            "depression": ["depressed", "depression"],
            "anxiety": ["anxious", "anxiety", "stressed"],
            "ptsd": ["ptsd", "trauma", "flashbacks"],
            "bipolar": ["bipolar", "manic"],
            "schizophrenia": ["schizophrenia", "psychosis"],
            "ocd": ["ocd", "obsessive"],
            "eating_disorder": ["eating disorder", "anorexia", "bulimia"],
        }
        for condition, keywords in condition_keywords.items():
            if any(k in msg for k in keywords):
                self.mental_health_profile["diagnosed_conditions"].add(condition)

        coping_keywords = {
            "exercise":       ["exercise", "running", "gym", "workout", "jogging"],
            "journaling":     ["journal", "journaling", "writing", "write down"],
            "meditation":     ["meditation", "meditate", "mindfulness"],
            "medication":     ["medication", "pills", "tablets"],
            "therapy":        ["therapy", "therapist", "counselor", "counseling"],
            "social_support": ["talk to friends", "talk to family", "friends", "family"],
        }
        for mechanism, keywords in coping_keywords.items():
            if any(k in msg for k in keywords):
                self.current_state["coping_mechanisms"].add(mechanism)

        if intent and intent not in {"greeting", "farewell", "gratitude"}:
            category = intent.split("_")[0] if "_" in intent else intent
            if category not in {"rag", "error"}:
                self.current_state["primary_concerns"].add(category)

        if metadata and metadata.get("severity"):
            severity_mapping = {"critical": "critical", "high": "high", "medium": "medium"}
            self.current_state["mood_level"] = severity_mapping.get(
                metadata["severity"], self.current_state["mood_level"]
            )

        self.updated_at = datetime.now().isoformat()

    def has_been_asked(self, question_id: str) -> bool:
        return question_id in self.questions_asked

    def mark_question_asked(self, question_id: str):
        self.questions_asked.add(question_id)
        self.updated_at = datetime.now().isoformat()

    def get_relevant_context_summary(self) -> str:
        parts = []
        if self.mental_health_profile["diagnosed_conditions"]:
            parts.append(f"Known conditions: {', '.join(self.mental_health_profile['diagnosed_conditions'])}")
        if self.current_state["primary_concerns"]:
            parts.append(f"Current concerns: {', '.join(self.current_state['primary_concerns'])}")
        if self.current_state["coping_mechanisms"]:
            parts.append(f"Uses coping: {', '.join(self.current_state['coping_mechanisms'])}")
        if self.conversation_history["recurring_themes"]:
            top = sorted(
                self.conversation_history["recurring_themes"].keys(),
                key=lambda x: self.conversation_history["recurring_themes"][x],
                reverse=True
            )[:3]
            parts.append(f"Recurring themes: {', '.join(top)}")
        return " | ".join(parts) if parts else "New patient - minimal context"

    def determine_questions_to_ask_next(self) -> List[Dict]:
        """Return at most 2 highest-priority minimal questions not yet asked."""
        questions = []

        if not self.demographics["age"]:
            questions.append({"id": "ask_age", "text": "To better support you, could you share your age range?", "priority": 10, "category": "demographics"})
        if not self.demographics["occupation"]:
            questions.append({"id": "ask_occupation", "text": "What's your work situation like (student/employed/other)?", "priority": 8, "category": "demographics"})
        if not self.current_state["support_system"] and not self.has_been_asked("ask_support_system"):
            questions.append({"id": "ask_support_system", "text": "Do you have people in your life you can talk to about what you're going through?", "priority": 15, "category": "support"})
        if not self.mental_health_profile["previous_treatments"] and not self.has_been_asked("ask_previous_help"):
            questions.append({"id": "ask_previous_help", "text": "Have you worked with a therapist or counselor before?", "priority": 12, "category": "history"})
        if (self.current_state["primary_concerns"]
                and not self.mental_health_profile["current_medications"]
                and not self.has_been_asked("ask_current_meds")):
            questions.append({"id": "ask_current_meds", "text": "Are you currently taking any medications?", "priority": 11, "category": "health"})
        if "mood_sad" in self.current_state["primary_concerns"] and not self.has_been_asked("ask_sleep_quality"):
            questions.append({"id": "ask_sleep_quality", "text": "How has your sleep been?", "priority": 9, "category": "behavior"})
        if ("trigger_trauma" in str(self.current_state["primary_concerns"])
                and not self.mental_health_profile["trauma_history"]
                and not self.has_been_asked("ask_trauma_support")):
            questions.append({"id": "ask_trauma_support", "text": "Have you received any support specifically for trauma-related experiences?", "priority": 14, "category": "treatment"})

        questions.sort(key=lambda x: x["priority"], reverse=True)
        return questions[:2]

    def to_dict(self) -> Dict:
        return {
            "patient_id": self.patient_id,
            "patient_code": self.patient_code,
            "demographics": dict(self.demographics),
            "mental_health_profile": {k: list(v) if isinstance(v, set) else v for k, v in self.mental_health_profile.items()},
            "current_state": {k: list(v) if isinstance(v, set) else v for k, v in self.current_state.items()},
            "conversation_history": self.conversation_history,
            "questions_asked": list(self.questions_asked),
            "preferences": {k: list(v) if isinstance(v, set) else v for k, v in self.preferences.items()},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# In-memory context cache keyed by session_id
_context_cache: Dict[str, PatientContextVector] = {}


def get_or_create_context(session_id: str, patient_id: str, patient_code: str) -> PatientContextVector:
    """Get or create PatientContextVector for a session."""
    if session_id not in _context_cache:
        _context_cache[session_id] = PatientContextVector(patient_id, patient_code)
    return _context_cache[session_id]


def update_context_from_turn(session_id: str, user_message: str, intent: str, metadata: Dict = None):
    """Extract context information from a conversation turn."""
    if session_id in _context_cache:
        _context_cache[session_id].extract_from_conversation(user_message, intent, metadata)
        logger.debug(f"Context updated for {session_id}: {_context_cache[session_id].get_relevant_context_summary()}")


def clear_context(session_id: str):
    """Remove context cache entry for a session."""
    _context_cache.pop(session_id, None)


# ════════════════════════════════════════════════════════════════════════════
# §6  CLINICAL SYNTHESIS ENGINE
#     Zero-Question principle: know the patient before they speak
#     Priority 1: Subjective (check-in) → Priority 2: Physiological (wearables)
#     → Priority 3: Historical (session history)
# ════════════════════════════════════════════════════════════════════════════

class EmotionalState(str, Enum):
    HAPPY       = "happy"
    NEUTRAL     = "neutral"
    SAD         = "sad"
    ANGRY       = "angry"
    STRESSED    = "stressed"
    LONELY      = "lonely"
    GUILTY      = "guilty"
    ANXIOUS     = "anxious"
    HOPEFUL     = "hopeful"
    OVERWHELMED = "overwhelmed"


class PhysiologicalThreat(str, Enum):
    LOW_HRV      = "low_hrv"
    ELEVATED_HR  = "elevated_hr"
    POOR_SLEEP   = "poor_sleep"
    HIGH_STRESS  = "high_stress"
    LOW_ACTIVITY = "low_activity"
    ANOMALY      = "anomaly"
    NONE         = "none"


class ToneDirective(str, Enum):
    CALM_GROUNDING = "calm_grounding"
    VALIDATING     = "validating"
    CELEBRATORY    = "celebratory"
    CURIOUS        = "curious"
    SUPPORTIVE     = "supportive"
    CRISIS_SAFE    = "crisis_safe"


@dataclass
class SubjectiveState:
    """From daily_checkins table — patient's own report"""
    emotional_state: str = "neutral"
    craving_intensity: int = 5
    sleep_quality: int = 5
    medication_taken: bool = True
    triggers_today: List[str] = field(default_factory=list)
    checkin_timestamp: Optional[str] = None
    hours_ago: Optional[float] = None

    def is_recent(self, hours_threshold: float = 12) -> bool:
        return self.hours_ago is not None and self.hours_ago <= hours_threshold


@dataclass
class PhysiologicalState:
    """From wearable_readings table — objective health metrics"""
    heart_rate: Optional[int] = None
    hrv: Optional[int] = None
    sleep_hours: Optional[float] = None
    steps_today: Optional[int] = None
    stress_score: Optional[float] = None
    spo2: Optional[int] = None
    personal_anomaly_flag: bool = False
    anomaly_detail: Optional[str] = None
    wearable_timestamp: Optional[str] = None
    hours_ago: Optional[float] = None

    def identify_threats(self) -> List[PhysiologicalThreat]:
        threats = []
        if self.hrv is not None and self.hrv < 20:
            threats.append(PhysiologicalThreat.LOW_HRV)
        if self.heart_rate is not None and self.heart_rate > 85:
            threats.append(PhysiologicalThreat.ELEVATED_HR)
        if self.sleep_hours is not None and self.sleep_hours < 5:
            threats.append(PhysiologicalThreat.POOR_SLEEP)
        if self.stress_score is not None and self.stress_score > 0.7:
            threats.append(PhysiologicalThreat.HIGH_STRESS)
        if self.steps_today is not None and self.steps_today < 3000:
            threats.append(PhysiologicalThreat.LOW_ACTIVITY)
        if self.personal_anomaly_flag:
            threats.append(PhysiologicalThreat.ANOMALY)
        return threats if threats else [PhysiologicalThreat.NONE]

    def is_recent(self, hours_threshold: float = 24) -> bool:
        return self.hours_ago is not None and self.hours_ago <= hours_threshold


@dataclass
class HistoricalContext:
    """From conversations table — recurring themes and patterns"""
    recurring_themes: List[str] = field(default_factory=list)
    recent_intents: List[str] = field(default_factory=list)
    crisis_history: bool = False
    last_session_timestamp: Optional[str] = None
    days_since_last_session: Optional[float] = None
    session_count: int = 0


@dataclass
class SynthesizedContextVector:
    """Unified patient context for greeting generation"""
    patient_name: str = "there"
    subjective: SubjectiveState = field(default_factory=SubjectiveState)
    physiological: PhysiologicalState = field(default_factory=PhysiologicalState)
    historical: HistoricalContext = field(default_factory=HistoricalContext)

    dominant_theme: str = ""
    emotional_anchor: str = ""
    physiological_threats: List[PhysiologicalThreat] = field(default_factory=list)
    contradiction_detected: bool = False
    contradiction_type: Optional[str] = None

    tone_directive: ToneDirective = ToneDirective.SUPPORTIVE

    subjective_risk_score: int = 30
    objective_risk_score: int = 30
    clinical_risk_score: int = 30

    is_returning_user: bool = False
    all_data_recent: bool = False

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class PatientContextSynthesizer:
    """
    Synthesizes multi-source clinical data into a unified SynthesizedContextVector.

    Core philosophy:
    1. Patient's subjective reality is primary (therapeutic alliance)
    2. Wearables inform tone and silent risk adjustment
    3. History adds continuity and memory
    4. Contradictions are bridged, not corrected
    """

    def synthesize(
        self,
        subjective: Optional[SubjectiveState] = None,
        physiological: Optional[PhysiologicalState] = None,
        historical: Optional[HistoricalContext] = None,
        patient_name: str = "there",
    ) -> SynthesizedContextVector:
        ctx = SynthesizedContextVector(patient_name=patient_name)
        ctx.subjective = subjective or SubjectiveState()
        ctx.physiological = physiological or PhysiologicalState()
        ctx.historical = historical or HistoricalContext()

        ctx.is_returning_user = ctx.subjective.is_recent() or ctx.physiological.is_recent()
        ctx.all_data_recent = ctx.subjective.is_recent() and ctx.physiological.is_recent()

        ctx.physiological_threats = ctx.physiological.identify_threats()

        contradiction = self._detect_contradiction(ctx.subjective, ctx.physiological)
        if contradiction:
            ctx.contradiction_detected = True
            ctx.contradiction_type = contradiction

        ctx.dominant_theme = self._establish_dominant_theme(ctx.subjective, ctx.physiological, ctx.historical)
        ctx.emotional_anchor = self._extract_emotional_anchor(ctx.subjective)

        ctx.subjective_risk_score = self._calculate_subjective_risk(ctx.subjective)
        ctx.objective_risk_score = self._calculate_objective_risk(ctx.physiological)
        ctx.clinical_risk_score = self._calculate_clinical_risk(
            ctx.subjective_risk_score, ctx.objective_risk_score, contradiction
        )
        ctx.tone_directive = self._determine_tone(ctx)
        return ctx

    def _detect_contradiction(self, subjective: SubjectiveState, physiological: PhysiologicalState) -> Optional[str]:
        if not subjective.is_recent() or not physiological.is_recent():
            return None
        if subjective.sleep_quality >= 7 and physiological.sleep_hours is not None and physiological.sleep_hours < 5:
            return "patient_felt_rested_but_objectively_poor"
        if subjective.craving_intensity <= 3 and physiological.stress_score is not None and physiological.stress_score > 0.8:
            return "patient_calm_but_physiologically_stressed"
        return None

    def _establish_dominant_theme(self, subjective: SubjectiveState, physiological: PhysiologicalState, historical: HistoricalContext) -> str:
        if subjective.is_recent():
            if subjective.emotional_state in ["stressed", "anxious", "overwhelmed"]:
                return f"emotional_distress:{subjective.emotional_state}"
            if subjective.emotional_state in ["sad", "lonely", "guilty"]:
                return f"mood:{subjective.emotional_state}"
            if subjective.craving_intensity >= 7:
                return f"high_craving:{subjective.craving_intensity}"
            if subjective.sleep_quality <= 3:
                return "poor_sleep"
            if not subjective.medication_taken:
                return "medication_missed"

        threats = physiological.identify_threats()
        if PhysiologicalThreat.LOW_HRV in threats:
            return "physiological_stress:low_hrv"
        if PhysiologicalThreat.HIGH_STRESS in threats:
            return "physiological_stress:high"
        if PhysiologicalThreat.POOR_SLEEP in threats:
            return "poor_sleep_objective"
        if PhysiologicalThreat.ANOMALY in threats:
            return f"anomaly:{physiological.anomaly_detail or 'detected'}"

        if historical.recurring_themes:
            return f"recurring_theme:{historical.recurring_themes[0]}"

        return "general_check_in"

    def _extract_emotional_anchor(self, subjective: SubjectiveState) -> str:
        if not subjective.is_recent():
            return ""
        return {
            "stressed":    "feeling stressed and overwhelmed",
            "anxious":     "feeling anxious or worried",
            "sad":         "feeling down or sad",
            "lonely":      "feeling isolated or lonely",
            "angry":       "feeling frustrated or angry",
            "guilty":      "carrying feelings of guilt",
            "overwhelmed": "feeling like too much is happening",
        }.get(subjective.emotional_state, "")

    def _calculate_subjective_risk(self, subjective: SubjectiveState) -> int:
        if not subjective.is_recent():
            return 30
        score = {
            "happy": 5, "neutral": 15, "hopeful": 10, "anxious": 40,
            "stressed": 50, "overwhelmed": 60, "angry": 45, "sad": 35,
            "lonely": 30, "guilty": 40,
        }.get(subjective.emotional_state, 30)
        if subjective.craving_intensity > 7:
            score += 20
        elif subjective.craving_intensity > 5:
            score += 10
        if subjective.sleep_quality < 3:
            score += 15
        if not subjective.medication_taken:
            score += 10
        if subjective.triggers_today:
            score += 5 * len(subjective.triggers_today)
        return min(score, 100)

    def _calculate_objective_risk(self, physiological: PhysiologicalState) -> int:
        if not physiological.is_recent():
            return 30
        score = 20
        if physiological.hrv is not None:
            if physiological.hrv < 20:    score += 40
            elif physiological.hrv < 35:  score += 25
            elif physiological.hrv < 50:  score += 10
        if physiological.heart_rate is not None:
            if physiological.heart_rate > 95: score += 20
            elif physiological.heart_rate > 80: score += 10
        if physiological.stress_score is not None:
            score += int(physiological.stress_score * 40)
        if physiological.sleep_hours is not None:
            if physiological.sleep_hours < 5: score += 25
            elif physiological.sleep_hours < 6: score += 15
        if physiological.steps_today is not None and physiological.steps_today < 3000:
            score += 10
        if physiological.personal_anomaly_flag:
            score += 15
        return min(score, 100)

    def _calculate_clinical_risk(self, subjective_score: int, objective_score: int, contradiction_type: Optional[str]) -> int:
        clinical = int(subjective_score * 0.7 + objective_score * 0.3)
        if contradiction_type == "patient_felt_rested_but_objectively_poor":
            clinical = int(clinical * 0.8 + objective_score * 0.2)
        elif contradiction_type == "patient_calm_but_physiologically_stressed":
            clinical = min(int(clinical * 1.1), 100)
        return clinical

    def _determine_tone(self, ctx: SynthesizedContextVector) -> ToneDirective:
        if "override_to_crisis" in ctx.dominant_theme:
            return ToneDirective.CRISIS_SAFE
        if (PhysiologicalThreat.HIGH_STRESS in ctx.physiological_threats or
                PhysiologicalThreat.LOW_HRV in ctx.physiological_threats):
            return ToneDirective.CALM_GROUNDING
        if ctx.emotional_anchor:
            return ToneDirective.VALIDATING
        if "general_check_in" in ctx.dominant_theme:
            return ToneDirective.CURIOUS
        return ToneDirective.SUPPORTIVE


_synthesizer = PatientContextSynthesizer()


def synthesize_patient_context(
    subjective: Optional[SubjectiveState] = None,
    physiological: Optional[PhysiologicalState] = None,
    historical: Optional[HistoricalContext] = None,
    patient_name: str = "there",
) -> SynthesizedContextVector:
    """Main entry point for context synthesis."""
    return _synthesizer.synthesize(subjective=subjective, physiological=physiological,
                                   historical=historical, patient_name=patient_name)


# ════════════════════════════════════════════════════════════════════════════
# §7  CLINICAL CONTEXT QUERY BUILDER
#     Answers: "Should an alcohol patient and a gaming patient get the
#               same response for sleeplessness?"  → Absolutely not.
#
#     Enriches every RAG query and LLM system prompt with:
#       • Addiction × symptom specific clinical context
#       • Safety overrides from patient profile flags
#       • Addiction-biased topic tags for Qdrant retrieval
# ════════════════════════════════════════════════════════════════════════════

# ── Addiction × Symptom → Clinical Context ───────────────────────────────────

CONTEXT_MAP: Dict[Tuple[str, str], Dict] = {

    # SLEEP
    ("alcohol", "behaviour_sleep"): {
        "enriched_query": "alcohol withdrawal insomnia sleep disruption REM suppression recovery",
        "extra_tags":     ["alcohol", "treatment"],
        "clinical_context": (
            "This patient has alcohol use disorder. Their sleep issues are likely caused by "
            "alcohol's suppression of REM sleep and potential withdrawal effects. "
            "Recommend sleep hygiene for AUD recovery. "
            "NEVER suggest relaxation with alcohol, sedatives, or anything that could validate "
            "substance use as a sleep aid."
        ),
        "avoid_topics": ["sedatives", "sleep_medication"],
    },
    ("gaming", "behaviour_sleep"): {
        "enriched_query": "gaming screen time blue light sleep disruption dopamine bedtime routine digital detox",
        "extra_tags":     ["behaviour", "mood"],
        "clinical_context": (
            "This patient has a gaming addiction. Their sleep issues are likely driven by "
            "screen exposure before bed, dopamine dysregulation from gameplay, and irregular "
            "sleep schedules. Focus on screen-free wind-down routines and bedtime structure."
        ),
        "avoid_topics": [],
    },
    ("nicotine", "behaviour_sleep"): {
        "enriched_query": "nicotine withdrawal sleep disturbance insomnia smoking cessation",
        "extra_tags":     ["addiction"],
        "clinical_context": (
            "This patient is recovering from nicotine addiction. Nicotine withdrawal commonly "
            "causes insomnia and vivid dreams, typically peaking in the first 1-2 weeks. "
            "Reassure that sleep disruption is temporary and part of recovery."
        ),
        "avoid_topics": [],
    },
    ("opioids", "behaviour_sleep"): {
        "enriched_query": "opioid withdrawal insomnia restless legs sleep disruption detox",
        "extra_tags":     ["drugs", "addiction", "treatment"],
        "clinical_context": (
            "This patient is in opioid recovery. Sleep disturbance is a hallmark opioid "
            "withdrawal symptom. Refer to clinical team for assessment. Do NOT suggest "
            "any substances or supplements without medical guidance."
        ),
        "avoid_topics": ["sedatives"],
    },
    ("cannabis", "behaviour_sleep"): {
        "enriched_query": "cannabis withdrawal insomnia sleep disruption THC abstinence vivid dreams",
        "extra_tags":     ["addiction", "behaviour"],
        "clinical_context": (
            "This patient is recovering from cannabis use. Cannabis suppresses REM sleep; "
            "cessation causes a REM rebound with vivid dreams and disrupted sleep for 2-6 weeks. "
            "Normalise this as part of recovery."
        ),
        "avoid_topics": [],
    },

    # ANXIETY
    ("alcohol", "mood_anxious"): {
        "enriched_query": "alcohol anxiety bidirectional relationship self-medication withdrawal anxiety",
        "extra_tags":     ["alcohol", "mood"],
        "clinical_context": (
            "This patient has alcohol use disorder and anxiety. These are often bidirectional: "
            "alcohol is used to self-medicate anxiety, but worsens it over time. "
            "Avoid suggesting any 'relaxation' techniques that might be misinterpreted. "
            "Focus on grounding and breathing exercises."
        ),
        "avoid_topics": [],
    },
    ("gaming", "mood_anxious"): {
        "enriched_query": "gaming anxiety social anxiety avoidance digital escapism",
        "extra_tags":     ["behaviour", "mood"],
        "clinical_context": (
            "Gaming addiction often co-occurs with social anxiety — gaming becomes an escape "
            "from real-world anxiety. Responses should avoid pushing immediate social engagement. "
            "Focus on in-the-moment grounding first."
        ),
        "avoid_topics": [],
    },
    ("cannabis", "mood_anxious"): {
        "enriched_query": "cannabis anxiety THC anxiety paradoxical effect paranoia withdrawal",
        "extra_tags":     ["addiction", "mood"],
        "clinical_context": (
            "Cannabis can both cause and worsen anxiety, especially high-THC strains. "
            "This patient may be experiencing cannabis-induced anxiety or withdrawal anxiety. "
            "Validate and normalise — this is very common in cannabis recovery."
        ),
        "avoid_topics": [],
    },

    # LONELINESS
    ("alcohol", "mood_lonely"): {
        "enriched_query": "alcohol social isolation loneliness recovery peer support AA community",
        "extra_tags":     ["alcohol", "mood"],
        "clinical_context": (
            "Loneliness is a major relapse trigger for alcohol use disorder. "
            "Peer support (AA, SMART Recovery) is clinically significant here. "
            "If family_member_uses is true, do NOT suggest 'reach out to family'."
        ),
        "avoid_topics": [],
    },
    ("gaming", "mood_lonely"): {
        "enriched_query": "gaming addiction social isolation online vs real connection loneliness",
        "extra_tags":     ["behaviour", "mood"],
        "clinical_context": (
            "For gaming addiction, loneliness is often both a cause and consequence. "
            "Online social connections may feel more real than offline ones. "
            "Gently validate the importance of connection without dismissing online friendships. "
            "Bridge toward real-world social activity gradually."
        ),
        "avoid_topics": [],
    },
    ("social_media", "mood_lonely"): {
        "enriched_query": "social media loneliness comparison FOMO passive scrolling real connection",
        "extra_tags":     ["behaviour", "mood"],
        "clinical_context": (
            "Social media addiction paradoxically increases loneliness. "
            "Passive consumption (scrolling) worsens loneliness; active engagement helps less. "
            "Focus on reducing passive use and encouraging real-world connection."
        ),
        "avoid_topics": [],
    },

    # GUILT
    ("alcohol", "mood_guilty"): {
        "enriched_query": "alcohol guilt shame recovery self-compassion relapse normalisation",
        "extra_tags":     ["alcohol", "mood"],
        "clinical_context": (
            "Guilt and shame are extremely common in alcohol use disorder and are major "
            "relapse drivers. The clinical priority is de-shaming. "
            "Responses must NEVER reinforce guilt. Use non-judgmental, compassionate language. "
            "Normalise the slip — it does not erase progress."
        ),
        "avoid_topics": [],
    },
    ("gambling", "mood_guilty"): {
        "enriched_query": "gambling guilt shame financial harm family impact recovery",
        "extra_tags":     ["gambling", "mood"],
        "clinical_context": (
            "Gambling guilt often includes financial harm to family, which intensifies shame. "
            "Acknowledge the weight without amplifying it. Focus on what the patient can "
            "do right now, not what has been lost."
        ),
        "avoid_topics": [],
    },

    # CRAVINGS
    ("alcohol", "addiction_alcohol"): {
        "enriched_query": "alcohol craving urge surfing HALT technique delay response triggers",
        "extra_tags":     ["alcohol", "addiction", "treatment"],
        "clinical_context": (
            "Active alcohol craving. Clinical priority: urge surfing and delay response. "
            "The craving will peak and pass — typically 15-30 minutes. "
            "Offer a concrete immediate action: breathing, cold water, walk."
        ),
        "avoid_topics": [],
    },
    ("gaming", "addiction_gaming"): {
        "enriched_query": "gaming urge screen-free timer delay technique boredom tolerance",
        "extra_tags":     ["behaviour", "treatment"],
        "clinical_context": (
            "Gaming craving. Trigger is likely boredom, stress escape, or social isolation. "
            "Delay technique: suggest a timed 20-minute alternative activity before deciding. "
            "Do not lecture — meet the patient where they are."
        ),
        "avoid_topics": [],
    },
    ("nicotine", "addiction_nicotine"): {
        "enriched_query": "nicotine craving urge duration 3-minute rule distraction technique",
        "extra_tags":     ["addiction", "treatment"],
        "clinical_context": (
            "Nicotine craving typically peaks at 3-5 minutes then fades. "
            "The 3-minute rule: distract for 3 minutes and the urge will pass. "
            "Suggest a physical distraction — walk, water, chewing gum."
        ),
        "avoid_topics": [],
    },

    # SADNESS
    ("alcohol", "mood_sad"): {
        "enriched_query": "alcohol depression comorbidity dual diagnosis sadness recovery emotional regulation",
        "extra_tags":     ["alcohol", "mood"],
        "clinical_context": (
            "Depression and alcohol use disorder have very high comorbidity. "
            "Alcohol is a depressant — current use worsens sadness. "
            "Validate the feeling without giving clinical advice. "
            "If sadness is persistent, recommend clinical support."
        ),
        "avoid_topics": [],
    },
    ("gaming", "mood_sad"): {
        "enriched_query": "gaming depression escapism emotional numbing sadness real world avoidance",
        "extra_tags":     ["behaviour", "mood"],
        "clinical_context": (
            "For gaming addiction, sadness often drives escapism into gaming. "
            "Address the sadness directly — don't just target the gaming behaviour. "
            "Validate the emotional pain before suggesting behavioural change."
        ),
        "avoid_topics": [],
    },

    # STRESS / TRIGGERS
    ("alcohol", "trigger_stress"): {
        "enriched_query": "alcohol stress trigger HALT high-risk situation relapse prevention",
        "extra_tags":     ["alcohol", "treatment"],
        "clinical_context": (
            "Stress is a top relapse trigger for alcohol use disorder. "
            "HALT framework: is the patient Hungry, Angry, Lonely, or Tired? "
            "Provide an immediate coping tool — do not just validate."
        ),
        "avoid_topics": [],
    },
    ("gambling", "trigger_stress"): {
        "enriched_query": "gambling stress trigger financial anxiety escape betting urge",
        "extra_tags":     ["gambling", "mood"],
        "clinical_context": (
            "Financial stress is both a trigger and consequence of gambling disorder. "
            "Be careful not to reinforce the idea that gambling could 'solve' financial stress. "
            "Focus on grounding before problem-solving."
        ),
        "avoid_topics": [],
    },
}


# ── Default enrichment per addiction type (when no specific pair exists) ─────

ADDICTION_DEFAULTS: Dict[str, Dict] = {
    "alcohol": {
        "extra_tags":     ["alcohol", "addiction"],
        "clinical_context": (
            "Patient has alcohol use disorder. All responses must avoid any language that "
            "normalises or minimises alcohol use. Prioritise AUD-specific content."
        ),
    },
    "gaming": {
        "extra_tags":     ["behaviour", "gaming"],
        "clinical_context": (
            "Patient has a gaming addiction (behavioural addiction). Focus on behavioural "
            "strategies, screen management, and real-world engagement."
        ),
    },
    "nicotine": {
        "extra_tags":     ["addiction"],
        "clinical_context": (
            "Patient is recovering from nicotine/tobacco addiction. "
            "Acknowledge cravings are intense but short-lived."
        ),
    },
    "opioids": {
        "extra_tags":     ["drugs", "addiction", "treatment"],
        "clinical_context": (
            "Patient is in opioid recovery. Responses must be especially careful around "
            "any mention of pain management or medication. Always defer to clinical team."
        ),
    },
    "cannabis": {
        "extra_tags":     ["addiction", "behaviour"],
        "clinical_context": (
            "Patient is recovering from cannabis use disorder. "
            "Normalise withdrawal symptoms — they are temporary and well-documented."
        ),
    },
    "gambling": {
        "extra_tags":     ["gambling", "behaviour"],
        "clinical_context": (
            "Patient has gambling disorder. Financial shame and impulsivity are common. "
            "Never suggest financial problem-solving as a coping mechanism."
        ),
    },
    "social_media": {
        "extra_tags":     ["behaviour", "social_media"],
        "clinical_context": (
            "Patient has social media addiction. Passive scrolling worsens mood. "
            "Focus on intentional use and real-world connection."
        ),
    },
    "behavioral": {
        "extra_tags":     ["behaviour"],
        "clinical_context": (
            "Patient has a behavioural addiction. Focus on habit replacement and "
            "identifying the underlying emotional need the behaviour is meeting."
        ),
    },
}


# ── Clinical safety overrides (fire from patient profile flags, not intent) ──

CLINICAL_SAFETY_OVERRIDES = {
    "uses_substance_for_sleep": (
        "CRITICAL: This patient uses substances to aid sleep. "
        "NEVER suggest any sedating technique, supplement, or substance as a sleep aid. "
        "Only recommend evidence-based behavioural sleep strategies (CBT-I, sleep hygiene)."
    ),
    "family_member_uses": (
        "CRITICAL: A family member of this patient also uses substances. "
        "NEVER suggest 'talk to your family' or 'lean on family' as a coping strategy. "
        "Focus on peer support, sponsor, or professional support instead."
    ),
    "suicide_attempt_history": (
        "IMPORTANT: This patient has a history of suicide attempts. "
        "Apply extra caution with any language around hopelessness or worthlessness. "
        "At any sign of distress, bridge to crisis resources earlier than you normally would."
    ),
    "trauma_history": (
        "IMPORTANT: This patient has trauma history. "
        "Use trauma-informed language throughout. Never ask 'what happened' or probe for details. "
        "Let the patient lead disclosure at their own pace."
    ),
    "avoidant_coping": (
        "NOTE: This patient uses avoidant coping strategies. "
        "Do NOT suggest taking a break, stepping away, or distracting as primary responses. "
        "Gently encourage facing feelings rather than avoiding them."
    ),
    "high_impulsivity": (
        "NOTE: This patient has high impulsivity. "
        "Prioritise the delay response technique — encourage them to wait 15-20 minutes "
        "before acting on any urge. Short, direct instructions work best."
    ),
    "cognitive_impairment": (
        "NOTE: This patient has cognitive impairment. "
        "Keep responses shorter, simpler, and more concrete than usual. "
        "Avoid abstract concepts or long explanations. One idea at a time."
    ),
    "bipolar_or_psychosis_history": (
        "CRITICAL — PSYCHOSIS/BIPOLAR HISTORY: This patient has a history of bipolar disorder or psychosis. "
        "Apply ALL of the following language rules without exception:\n"
        "  1. NO metaphors or similes of any kind (not 'cravings are like waves', not 'grief is love', "
        "not 'ride the urge', not 'your brain is rewiring'). \n"
        "  2. Literal and concrete language only. Name the feeling or action directly. \n"
        "  3. No open-ended or abstract prompts (not 'I wonder...', not 'What does that feel like for you?'). \n"
        "  4. Short, simple sentences. One idea per sentence. \n"
        "  5. End every response with a single, specific, concrete action (e.g. 'Drink a glass of water now.' "
        "or 'Take three slow breaths.') — never a question or an abstract invitation."
    ),
}


# ── Public API ────────────────────────────────────────────────────────────────

def build_enriched_query(
    user_input: str,
    intent: Optional[str],
    addiction_type: Optional[str],
    checkin_data: Optional[Dict] = None,
) -> str:
    """Return an enriched query string for embedding (blends user text with clinical context)."""
    if not addiction_type:
        return user_input
    key = (addiction_type, intent) if intent else None
    ctx = CONTEXT_MAP.get(key) if key else None
    if ctx and ctx.get("enriched_query"):
        return f"{user_input} {ctx['enriched_query']}"
    return user_input


def build_topic_filter(
    intent: Optional[str],
    addiction_type: Optional[str],
    base_tags: Optional[List[str]] = None,
) -> List[str]:
    """Return combined topic tags for Qdrant filtering."""
    tags = set(base_tags or [])
    if addiction_type and addiction_type in ADDICTION_DEFAULTS:
        tags.update(ADDICTION_DEFAULTS[addiction_type]["extra_tags"])
    key = (addiction_type, intent) if addiction_type and intent else None
    if key and key in CONTEXT_MAP:
        tags.update(CONTEXT_MAP[key].get("extra_tags", []))
    return list(tags)


def build_clinical_context_block(
    addiction_type: Optional[str],
    intent: Optional[str],
    profile_flags: Optional[Dict] = None,
) -> str:
    """
    Return a clinical context block for injection into the LLM system prompt.
    Combines addiction×intent context with patient safety override flags.
    """
    lines = []

    key = (addiction_type, intent) if addiction_type and intent else None
    if key and key in CONTEXT_MAP:
        lines.append(CONTEXT_MAP[key]["clinical_context"])
    elif addiction_type and addiction_type in ADDICTION_DEFAULTS:
        lines.append(ADDICTION_DEFAULTS[addiction_type]["clinical_context"])

    if profile_flags:
        for flag, override_text in CLINICAL_SAFETY_OVERRIDES.items():
            if profile_flags.get(flag):
                lines.append(override_text)

    if not lines:
        return ""

    return "\nCLINICAL CONTEXT (follow strictly):\n" + "\n".join(f"- {l}" for l in lines)


def get_response_length_instruction(profile_flags: Optional[Dict] = None) -> str:
    """Return a response-length instruction tailored to patient profile flags."""
    if not profile_flags:
        return "Keep responses to 2-3 sentences."
    if profile_flags.get("bipolar_or_psychosis_history"):
        return (
            "Keep responses to 1-2 short sentences per idea. "
            "Use only literal, concrete words. "
            "No metaphors, no comparisons, no figurative language. "
            "End with one specific action the patient can do right now."
        )
    if profile_flags.get("cognitive_impairment"):
        return "Keep responses to 1-2 short sentences maximum. Use simple words. One idea only."
    if profile_flags.get("high_impulsivity"):
        return "Keep responses to 2 sentences. Be direct. Give one concrete action immediately."
    return "Keep responses to 2-3 sentences."
