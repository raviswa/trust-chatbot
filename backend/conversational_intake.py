"""
conversational_intake.py — Guided Conversational Intake for Trust AI

Replaces the 5-step form UI with a warm, empathetic conversational flow.
Collects the same clinical data as the app screens (onboarding + daily check-in)
through natural dialogue — one question at a time.

INTAKE PHASES (mirrors app screen flow):
  Phase 0 — First contact: empathetic opening, name/greeting
  Phase 1 — Emotional state ("What feels heavy for you lately?")
  Phase 2 — Addiction type ("What are you working to recover from?")
  Phase 3 — Baseline assessment (sleep, stress, cravings, medication)
  Phase 4 — Daily life context (triggers, social support, work status)
  Phase 5 — Physical health + consent (light touch, not a form)
  Phase 6 — Handoff to main chatbot engine (RAG + support loop)

DAILY CHECK-IN (returning users):
  Mirrors the Daily Check-In screen: craving intensity, mood, rest, triggers, meds
"""

from typing import Optional, Dict, Any
import re

# ── Intake state keys stored in session ──────────────────────────────────────

INTAKE_KEY = "intake_state"
CHECKIN_KEY = "checkin_state"

ADDICTION_TYPES = {
    "alcohol": ["alcohol", "drinking", "drink", "drunk", "liquor", "beer", "wine", "whisky"],
    "opioids": ["opioid", "heroin", "fentanyl", "morphine", "codeine", "opiate", "painkiller"],
    "stimulants": ["cocaine", "meth", "amphetamine", "stimulant", "speed", "crystal"],
    "cannabis": ["cannabis", "weed", "marijuana", "ganja", "pot", "thc", "edible"],
    "nicotine": ["nicotine", "cigarette", "smoking", "vaping", "vape", "tobacco"],
    "gaming": ["gaming", "video game", "game", "online game", "screen"],
    "gambling": ["gambling", "betting", "casino", "bet"],
    "social_media": ["social media", "instagram", "tiktok", "scrolling", "phone addiction"],
    "food": ["food", "binge eating", "emotional eating", "overeating"],
    "behavioral": ["behavioral", "behaviour", "shopping", "work addiction", "pornography"],
}

MOOD_SIGNALS = {
    "anger":     ["angry", "anger", "rage", "furious", "irritated", "frustrated"],
    "hunger":    ["hunger", "cravings", "craving", "urge", "wanting"],
    "loneliness":["lonely", "alone", "isolated", "no one", "nobody"],
    "tiredness": ["tired", "exhausted", "fatigue", "no energy", "drained"],
    "distrust":  ["distrust", "suspicious", "can't trust", "paranoid", "doubt"],
    "boredom":   ["bored", "boredom", "nothing to do", "empty", "pointless"],
    "guilt":     ["guilty", "guilt", "ashamed", "shame", "regret", "disappointed in myself"],
    "sadness":   ["sad", "sadness", "depressed", "unhappy", "miserable", "low", "down"],
    "happy":     ["happy", "good", "great", "well", "fine", "okay", "alright"],
}

# ── Intake question definitions ───────────────────────────────────────────────

INTAKE_QUESTIONS = {
    # Phase 0: First contact — empathy + name
    "opening": {
        "phase": 0,
        "question": (
            "Hi there 👋 I'm your Trust AI companion — a safe, private space for your recovery journey.\n\n"
            "I'm glad you're here. To get started, may I ask your name? (You can share a nickname or first name — "
            "whatever feels comfortable.)"
        ),
        "extract": "name",
        "next": "emotional_state"
    },

    # Phase 1: Emotional state
    "emotional_state": {
        "phase": 1,
        "question": (
            "It's really good to meet you, {name}. 🙏\n\n"
            "Recovery is a journey, and every step matters — including this one.\n\n"
            "Before we dive in, I'd love to understand how you're feeling right now. "
            "What feels heaviest for you lately? "
            "(For example: anger, loneliness, guilt, tiredness, cravings — or just tell me in your own words.)"
        ),
        "extract": "mood",
        "next": "addiction_type"
    },

    # Phase 2: Addiction type
    "addiction_type": {
        "phase": 2,
        "question": (
            "Thank you for sharing that, {name}. It takes real courage. 💙\n\n"
            "So I can personalise your support plan, could you tell me — "
            "what are you working to recover from? "
            "(e.g. alcohol, gaming, nicotine, gambling, opioids, or something else entirely — "
            "no judgment here, just want to understand your journey.)"
        ),
        "extract": "addiction_type",
        "next": "sleep_quality"
    },

    # Phase 3a: Baseline — Sleep
    "sleep_quality": {
        "phase": 3,
        "question": (
            "Got it — thank you for being open about that.\n\n"
            "Now let me ask a few quick questions to understand your baseline, "
            "so your recovery plan is as accurate as possible. 📊\n\n"
            "Over the **past week**, how has your **sleep** been? "
            "(Very poor / Poor / Fair / Good / Very good — or describe it in your own words.)"
        ),
        "extract": "sleep_quality",
        "next": "stress_level"
    },

    # Phase 3b: Stress
    "stress_level": {
        "phase": 3,
        "question": (
            "And your **stress level** over the past week — how would you rate it? "
            "(Low / Medium / High — or tell me what's been driving the stress.)"
        ),
        "extract": "stress_level",
        "next": "craving_frequency"
    },

    # Phase 3c: Cravings
    "craving_frequency": {
        "phase": 3,
        "question": (
            "How often have **cravings** been showing up for you lately? "
            "(Rarely / Sometimes / Often / Almost always — or just describe when they tend to hit.)"
        ),
        "extract": "craving_frequency",
        "next": "medication_adherence"
    },

    # Phase 3d: Medication
    "medication_adherence": {
        "phase": 3,
        "question": (
            "Are you currently on any **prescribed medication** as part of your recovery? "
            "(Yes / No — and if yes, have you been able to take it regularly?)\n\n"
            "*(I can't advise on medications — that's for your doctor — "
            "but knowing this helps personalise your support.)*"
        ),
        "extract": "medication_adherence",
        "next": "triggers_exposure"
    },

    # Phase 4a: Triggers
    "triggers_exposure": {
        "phase": 4,
        "question": (
            "Let's talk about **triggers** — the people, places, or situations that make cravings stronger. "
            "Have you been encountering triggers lately? "
            "(Yes / No — and if yes, feel free to share what kinds, so I can tailor your support.)"
        ),
        "extract": "triggers_exposure",
        "next": "social_support"
    },

    # Phase 4b: Social support
    "social_support": {
        "phase": 4,
        "question": (
            "Do you have **social support** around you — friends, family, a sponsor, a support group? "
            "(Yes / No / A little — and how connected do you feel to them right now?)"
        ),
        "extract": "social_support",
        "next": "work_status"
    },

    # Phase 4c: Work/life context
    "work_status": {
        "phase": 4,
        "question": (
            "One last context question — are you currently **working, studying**, or neither right now? "
            "This helps me understand the rhythm of your day and when you might need support most."
        ),
        "extract": "work_status",
        "next": "physical_health"
    },

    # Phase 5: Physical health
    "physical_health": {
        "phase": 5,
        "question": (
            "Almost done, {name} — you're doing great. 🌟\n\n"
            "How is your **physical health** right now, in general? "
            "(Poor / Fair / Good / Excellent — or just tell me how your body is feeling.)"
        ),
        "extract": "physical_health",
        "next": "consent_transition"
    },

    # Phase 5: Consent + transition
    "consent_transition": {
        "phase": 5,
        "question": (
            "Thank you so much for sharing all of that, {name}. It means a lot. 🙏\n\n"
            "Everything you share here is **encrypted and private** — I only use it to "
            "personalise your recovery support and predict when you might need extra help.\n\n"
            "By continuing, you're agreeing to Trust AI using your inputs to build your personalised plan. "
            "Are you happy to continue? (Yes / No)"
        ),
        "extract": "consent",
        "next": "COMPLETE"
    },
}

# ── Daily Check-In questions (for returning users) ────────────────────────────

CHECKIN_QUESTIONS = {
    "checkin_opening": {
        "question": (
            "Hi {name} 👋 Welcome back. Ready for your daily check-in?\n\n"
            "On a scale of **1–10**, how **strong** have your cravings been today? "
            "(1 = barely noticeable, 10 = overwhelming)"
        ),
        "extract": "craving_intensity",
        "next": "checkin_mood"
    },
    "checkin_mood": {
        "question": (
            "And how would you describe your **mood** right now? "
            "(Happy / Neutral / Sad / Angry / Stressed / Lonely — or just tell me.)"
        ),
        "extract": "mood_today",
        "next": "checkin_rest"
    },
    "checkin_rest": {
        "question": (
            "How **rested** do you feel today? "
            "(1 = exhausted, 10 = very well rested)"
        ),
        "extract": "rest_level",
        "next": "checkin_triggers"
    },
    "checkin_triggers": {
        "question": (
            "Have you faced any **triggers** today — "
            "situations, people, or feelings that made cravings stronger? (Yes / No)"
        ),
        "extract": "triggers_today",
        "next": "checkin_medication"
    },
    "checkin_medication": {
        "question": (
            "Have you **missed any medication** today? (Yes / No)\n\n"
            "*(And if there's anything else on your mind today, feel free to share — "
            "I'm here to listen.)*"
        ),
        "extract": "medication_missed",
        "next": "COMPLETE"
    },
}

# ── Intake state management ───────────────────────────────────────────────────

def init_intake(session: dict, is_returning: bool = False) -> dict:
    """Initialise intake state for a new session."""
    if is_returning:
        session[CHECKIN_KEY] = {
            "active": True,
            "current_question": "checkin_opening",
            "collected": {},
            "complete": False,
        }
    else:
        session[INTAKE_KEY] = {
            "active": True,
            "current_question": "opening",
            "phase": 0,
            "collected": {},
            "complete": False,
        }
    return session


def is_intake_active(session: dict) -> bool:
    val = session.get(INTAKE_KEY)
    return bool(val and val.get("active", False))


def is_checkin_active(session: dict) -> bool:
    val = session.get(CHECKIN_KEY)
    return bool(val and val.get("active", False))


def is_intake_complete(session: dict) -> bool:
    val = session.get(INTAKE_KEY)
    return bool(val and val.get("complete", False))


def get_intake_profile(session: dict) -> dict:
    return session.get(INTAKE_KEY, {}).get("collected", {})


def get_checkin_data(session: dict) -> dict:
    return session.get(CHECKIN_KEY, {}).get("collected", {})


# ── Intake phase → first question key mapping ─────────────────────────────────
# Used by restore_intake_from_db to determine where to resume on reconnect.
_PHASE_TO_FIRST_QUESTION: dict = {
    0: "opening",
    1: "emotional_state",
    2: "addiction_type",
    3: "sleep_quality",
    4: "triggers_exposure",
    5: "physical_health",
}


def restore_intake_from_db(session: dict, onboarding_profile: dict) -> bool:
    """
    Restore in-memory intake state from a DB-backed onboarding_profile dict.

    Called on the first message of a reconnected session when last_intake_phase > 0
    and intake_consent_given is False.  Sets INTAKE_KEY so the session resumes
    at the correct question rather than restarting from Phase 0.

    Returns True if the state was restored, False if no action needed.
    """
    phase = onboarding_profile.get("last_intake_phase") or 0
    if phase <= 0 or onboarding_profile.get("intake_consent_given"):
        return False

    resume_q = _PHASE_TO_FIRST_QUESTION.get(phase, "opening")

    # Re-populate collected with whatever the DB already knows so that
    # later questions can still interpolate {name}, etc.
    collected: dict = {}
    if onboarding_profile.get("name"):
        collected["name"] = onboarding_profile["name"]
    if onboarding_profile.get("addiction_type"):
        collected["addiction_type"] = onboarding_profile["addiction_type"]
    if onboarding_profile.get("work_status"):
        collected["work_status"] = onboarding_profile["work_status"]

    session[INTAKE_KEY] = {
        "active": True,
        "current_question": resume_q,
        "phase": phase,
        "collected": collected,
        "complete": False,
        "_show_question": True,      # flag: re-display question before processing next answer
        "_resumed_from_db": True,    # flag: prepend "welcome back" prefix
    }
    return True


# ── Boolean flag normaliser ───────────────────────────────────────────────────
# All keys listed below are boolean-intent fields used by CLINICAL_SAFETY_OVERRIDES
# in patient_context.py.  The intake extractor (_extract_yes_no) and mobile-app DB
# records both return "yes"/"no" strings for these fields.
# • "no" is truthy in Python — leaving it as a string causes overrides to fire
#   incorrectly for patients who answered no.
# • keys absent from the profile dict are falsy (None) — correct, no action needed.
# This function normalises the strings to proper booleans at both write points:
#   1. Inside _build_completion_response (conversational intake path)
#   2. At the DB-load site in chatbot_engine.py (mobile-app / Supabase path)

_BOOLEAN_FLAG_FIELDS: frozenset = frozenset({
    # Clinical safety override flags
    "uses_substance_for_sleep",
    "family_member_uses",
    "suicide_attempt_history",
    "trauma_history",
    "avoidant_coping",
    "high_impulsivity",
    "cognitive_impairment",
    "bipolar_or_psychosis_history",
    # Intake yes/no fields (used elsewhere in the pipeline)
    "medication_adherence",
    "triggers_exposure",
    "social_support",
    "consent",
    "triggers_today",
    "medication_missed",
})

_YES_STRINGS: frozenset = frozenset({"yes", "yeah", "yep", "yup", "true", "1"})
_NO_STRINGS:  frozenset = frozenset({"no", "nope", "nah", "false", "0"})


def coerce_profile_flags(profile: dict) -> dict:
    """
    Return a copy of *profile* where every key in _BOOLEAN_FLAG_FIELDS whose
    current value is a yes/no string is converted to a proper Python bool.

    "yes" / "yeah" / "true" / "1"  →  True
    "no"  / "nope" / "false" / "0" →  False
    booleans, None, or other values →  unchanged

    This must be called at every point where a dict is written to
    session["intake_profile"] so that downstream flag checks
    (profile_flags.get("uses_substance_for_sleep") etc.) behave correctly.
    """
    result = dict(profile)
    for key in _BOOLEAN_FLAG_FIELDS:
        val = result.get(key)
        if isinstance(val, bool):
            continue  # already a boolean
        if isinstance(val, str):
            normalised = val.strip().lower()
            if normalised in _YES_STRINGS:
                result[key] = True
            elif normalised in _NO_STRINGS:
                result[key] = False
            # otherwise leave as-is (e.g. a free-text answer)
    return result

def _extract_name(text: str) -> Optional[str]:
    """Extract a first name / nickname from a response."""
    text = text.strip()
    # Words that are common English words, not names — prevent false positives
    _NON_NAMES = {
        "yes", "no", "hi", "hey", "hello", "sure", "okay", "ok",
        "my", "me", "i", "it", "its", "just", "the", "a", "an",
        "good", "bad", "fine", "not", "well", "so", "oh", "um",
        "friend", "friends", "need", "some", "beer", "help",
    }
    # "My name is X", "I'm X", "Call me X", "It's X"
    for pat in [
        r"(?:my name is|i'm|i am|call me|it's|its|just)\s+([A-Za-z]+)",
        r"^([A-Za-z]{2,20})$",  # bare single word
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).capitalize()
            if name.lower() not in _NON_NAMES:
                return name
    # Only try first-word-before-comma/space when the text is a short, likely-name reply
    # (5 words or fewer) to avoid extracting nouns from full sentences
    if len(text.split()) <= 5:
        m = re.search(r"^([A-Za-z]{2,20})[,\s]", text, re.IGNORECASE)
        if m:
            name = m.group(1).capitalize()
            if name.lower() not in _NON_NAMES:
                return name
    return None


def _extract_mood(text: str) -> Optional[str]:
    l = text.lower()
    for mood, keywords in MOOD_SIGNALS.items():
        if any(k in l for k in keywords):
            return mood
    return "mixed"


def _extract_addiction_type(text: str) -> Optional[str]:
    l = text.lower()
    for addiction, keywords in ADDICTION_TYPES.items():
        if any(k in l for k in keywords):
            return addiction
    return "other"


def _extract_scale(text: str, low_words: list, high_words: list) -> str:
    """Extract a quality descriptor from a scale response."""
    l = text.lower()
    for w in high_words:
        if w in l:
            return "high"
    for w in low_words:
        if w in l:
            return "low"
    # Try to extract a numeric value
    m = re.search(r"\b([1-9]|10)\b", text)
    if m:
        val = int(m.group(1))
        if val <= 3:
            return "low"
        elif val <= 6:
            return "medium"
        else:
            return "high"
    return "medium"


def _extract_yes_no(text: str) -> Optional[str]:
    l = text.lower()
    if any(w in l for w in ["yes", "yeah", "yep", "yup", "sure", "definitely", "absolutely", "correct"]):
        return "yes"
    if any(w in l for w in ["no", "nope", "not", "nah", "never", "haven't", "don't"]):
        return "no"
    return "yes"  # default to yes if ambiguous


def _extract_field(field: str, text: str) -> Any:
    """Route extraction to the right extractor."""
    if field == "name":
        return _extract_name(text)
    elif field == "mood":
        return _extract_mood(text)
    elif field == "addiction_type":
        return _extract_addiction_type(text)
    elif field in ("medication_adherence", "triggers_exposure", "social_support", "consent"):
        return _extract_yes_no(text)
    elif field == "sleep_quality":
        return _extract_scale(text,
            ["very poor", "poor", "bad", "terrible"],
            ["very good", "excellent", "great", "wonderful"])
    elif field == "stress_level":
        return _extract_scale(text, ["low", "calm", "relaxed"], ["high", "very stressed", "extreme"])
    elif field == "craving_frequency":
        return _extract_scale(text, ["rarely", "seldom", "almost never"], ["often", "always", "constantly"])
    elif field == "work_status":
        l = text.lower()
        if any(w in l for w in ["work", "working", "job", "employed", "office"]):
            return "working"
        elif any(w in l for w in ["student", "studying", "college", "school", "university"]):
            return "student"
        return "not working"
    elif field == "physical_health":
        return _extract_scale(text, ["poor", "bad", "sick", "unwell"], ["excellent", "great", "very good"])
    elif field == "craving_intensity":
        m = re.search(r"\b([1-9]|10)\b", text)
        return int(m.group(1)) if m else 5
    elif field == "mood_today":
        return _extract_mood(text)
    elif field == "rest_level":
        m = re.search(r"\b([1-9]|10)\b", text)
        return int(m.group(1)) if m else 5
    elif field == "triggers_today":
        return _extract_yes_no(text)
    elif field == "medication_missed":
        return _extract_yes_no(text)
    return text.strip()


# ── Main intake handler ───────────────────────────────────────────────────────

def handle_intake_turn(user_input: str, session: dict) -> Optional[dict]:
    """
    Called by chatbot_engine before normal message handling.
    Returns a response dict if intake is active, else None (pass to main engine).

    Response dict: { "response": str, "intent": "intake", "severity": "low",
                     "show_resources": False, "citations": [],
                     "intake_complete": bool, "intake_profile": dict }
    """
    state = session.get(INTAKE_KEY)
    if not state or not state.get("active"):
        return None

    current_q_key = state["current_question"]
    q_def = INTAKE_QUESTIONS.get(current_q_key)
    if not q_def:
        # Shouldn't happen — mark complete and hand off
        state["active"] = False
        state["complete"] = True
        return None

    collected = state.get("collected", {})

    # Extract field from user's answer to the PREVIOUS question
    field = q_def.get("extract")
    if field and user_input.strip():
        extracted = _extract_field(field, user_input)
        if extracted:
            collected[field] = extracted
        state["collected"] = collected

    # Determine next question
    next_q_key = q_def.get("next", "COMPLETE")

    if next_q_key == "COMPLETE":
        state["active"] = False
        state["complete"] = True
        return _build_completion_response(collected, session)

    # Advance to next question
    next_q_def = INTAKE_QUESTIONS.get(next_q_key)
    state["current_question"] = next_q_key
    state["phase"] = next_q_def.get("phase", state["phase"])

    # Skip questions whose fields are already pre-populated (e.g. from the
    # patient's first message or from a pre-loaded onboarding profile).
    _skip_limit = len(INTAKE_QUESTIONS)  # safety cap to prevent infinite loop
    while _skip_limit > 0:
        _skip_field = next_q_def.get("extract")
        if _skip_field and _skip_field in collected and collected[_skip_field]:
            # Field already known — advance without asking the question
            _next_of_next = next_q_def.get("next", "COMPLETE")
            if _next_of_next == "COMPLETE":
                state["active"] = False
                state["complete"] = True
                return _build_completion_response(collected, session)
            next_q_key = _next_of_next
            next_q_def = INTAKE_QUESTIONS.get(next_q_key, {})
            state["current_question"] = next_q_key
            state["phase"] = next_q_def.get("phase", state["phase"])
            _skip_limit -= 1
        else:
            break

    # Format question with collected data
    name = collected.get("name", "there")
    question_text = next_q_def["question"].format(name=name)

    return {
        "response": question_text,
        "intent": "intake",
        "severity": "low",
        "show_resources": False,
        "citations": [],
        "intake_complete": False,
        "intake_profile": coerce_profile_flags(collected),
        "intake_phase": next_q_def.get("phase", 0),
    }


def handle_checkin_turn(user_input: str, session: dict) -> Optional[dict]:
    """
    Same as handle_intake_turn but for daily check-in (returning users).
    """
    state = session.get(CHECKIN_KEY)
    if not state or not state.get("active"):
        return None

    current_q_key = state["current_question"]
    q_def = CHECKIN_QUESTIONS.get(current_q_key)
    if not q_def:
        state["active"] = False
        state["complete"] = True
        return None

    collected = state.get("collected", {})

    field = q_def.get("extract")
    if field and user_input.strip():
        extracted = _extract_field(field, user_input)
        if extracted:
            collected[field] = extracted
        state["collected"] = collected

    next_q_key = q_def.get("next", "COMPLETE")

    if next_q_key == "COMPLETE":
        state["active"] = False
        state["complete"] = True
        return _build_checkin_completion_response(collected, session)

    next_q_def = CHECKIN_QUESTIONS.get(next_q_key)
    state["current_question"] = next_q_key

    name = session.get("patient_name") or collected.get("name", "")
    name_str = f", {name}" if name else ""
    question_text = next_q_def["question"].format(name=name_str)

    return {
        "response": question_text,
        "intent": "daily_checkin",
        "severity": "low",
        "show_resources": False,
        "citations": [],
        "checkin_complete": False,
        "checkin_data": collected,
    }


# ── Completion responses ──────────────────────────────────────────────────────

def _build_completion_response(collected: dict, session: dict) -> dict:
    name = collected.get("name", "")
    addiction = collected.get("addiction_type", "your recovery journey")
    addiction_label = addiction.replace("_", " ") if addiction != "other" else "your recovery journey"
    mood = collected.get("mood", "")
    stress = collected.get("stress_level", "medium")
    cravings = collected.get("craving_frequency", "medium")

    # Build personalised summary + segue
    severity = "medium"
    risk_note = ""
    if stress == "high" and cravings == "high":
        severity = "high"
        risk_note = (
            "Based on what you've shared — high stress and frequent cravings — "
            "your AI risk score is being set to **medium-high**. "
            "I'll make sure to check in on you more regularly. "
        )
    elif stress == "low" and cravings == "low":
        severity = "low"
        risk_note = (
            "Your baseline looks relatively stable — that's a great starting point. "
        )

    mood_note = f"I hear that you've been feeling **{mood}** lately. " if mood and mood != "mixed" else ""

    response = (
        f"Thank you for completing your profile, {name}! 🎉\n\n"
        f"{mood_note}"
        f"Your personalised recovery plan for **{addiction_label}** is now active. "
        f"{risk_note}\n\n"
        "**What happens next:**\n"
        "• Your AI risk score will update daily based on our check-ins\n"
        "• I'll surface personalised content and coping tools for you\n"
        "• Your care team (if assigned) can see your risk trends\n\n"
        "I'm here whenever you need to talk — about cravings, triggers, emotions, or anything at all. "
        f"What's on your mind right now, {name}?"
    )

    return {
        "response": response,
        "intent": "intake_complete",
        "severity": severity,
        "show_resources": False,
        "citations": [],
        "intake_complete": True,
        "intake_profile": coerce_profile_flags(collected),
    }


def _build_checkin_completion_response(collected: dict, session: dict) -> dict:
    name = session.get("patient_name", "")
    name_str = f", {name}" if name else ""

    craving = collected.get("craving_intensity", 5)
    mood = collected.get("mood_today", "")
    rest = collected.get("rest_level", 5)
    has_triggers = collected.get("triggers_today") == "yes"
    missed_meds = collected.get("medication_missed") == "yes"

    # Risk assessment
    risk_score = 0
    if isinstance(craving, int):
        risk_score += craving
    if mood in ("angry", "sadness", "guilt", "loneliness"):
        risk_score += 3
    if has_triggers:
        risk_score += 2
    if missed_meds:
        risk_score += 2
    if isinstance(rest, int) and rest < 4:
        risk_score += 2

    severity = "low"
    risk_label = "Low"
    support_msg = "You're doing well today. Keep up the consistency! 💪"

    if risk_score >= 12:
        severity = "high"
        risk_label = "High"
        support_msg = (
            "I'm noticing a few risk signals today{name_str}. "
            "High cravings, low rest, and triggers together can make things harder. "
            "Let's try a **calming breathing exercise** right now — would that help?"
        ).format(name_str=name_str)
    elif risk_score >= 7:
        severity = "medium"
        risk_label = "Medium"
        support_msg = (
            f"Today looks moderately challenging{name_str}. "
            "Your cravings and mood suggest you could use some extra support. "
            "Would you like a coping tip, or would you rather just talk?"
        )

    response = (
        f"Check-in complete{name_str}! 📋\n\n"
        f"**Today's Risk Level: {risk_label}**\n\n"
        f"{support_msg}\n\n"
        "I'm here — what would be most helpful right now?"
    )

    return {
        "response": response,
        "intent": "checkin_complete",
        "severity": severity,
        "show_resources": severity == "high",
        "citations": [],
        "checkin_complete": True,
        "checkin_data": collected,
        "risk_score": risk_score,
    }


# ── Helper: should we start intake? ──────────────────────────────────────────

def should_start_intake(session: dict, message_count: int) -> bool:
    """Return True if we should initiate intake on this session's first message.

    message_count is the *already-incremented* session counter (>= 1 when called
    from handle_message).  We gate on <= 1 so we fire on the very first turn.
    intake_consent_given in intake_profile is the DB-backed completion guard —
    prevents re-starting intake for patients who already finished it in a prior
    session and whose profile was pre-loaded by the onboarding fetch.

    Skips intake entirely when the patient's name and addiction_type are already
    known from the pre-loaded onboarding profile — avoids duplicate greetings and
    asking for information the system already has.
    """
    profile = session.get("intake_profile", {})
    # Profile is sufficiently populated — intake would only ask redundant questions
    if profile.get("name") and profile.get("addiction_type"):
        return False
    return (
        message_count <= 1
        and not is_intake_active(session)
        and not is_intake_complete(session)
        and not profile.get("intake_consent_given")
    )


def should_start_checkin(session: dict, message_count: int, is_returning: bool) -> bool:
    """Return True if we should initiate daily check-in."""
    checkin_state = session.get(CHECKIN_KEY, {})
    return (
        is_returning
        and message_count == 0
        and not checkin_state.get("active", False)
        and not checkin_state.get("complete", False)
    )


def get_first_intake_question(session: dict) -> dict:
    """Returns the very first intake message to send (before user says anything)."""
    q_def = INTAKE_QUESTIONS["opening"]
    return {
        "response": q_def["question"],
        "intent": "intake",
        "severity": "low",
        "show_resources": False,
        "citations": [],
        "intake_complete": False,
        "intake_profile": {},
        "intake_phase": 0,
    }


def get_first_checkin_question(session: dict) -> dict:
    """Returns the daily check-in opening message."""
    name = session.get("patient_name", "")
    name_str = name if name else "there"
    q_def = CHECKIN_QUESTIONS["checkin_opening"]
    return {
        "response": q_def["question"].format(name=name_str),
        "intent": "daily_checkin",
        "severity": "low",
        "show_resources": False,
        "citations": [],
        "checkin_complete": False,
        "checkin_data": {},
    }
