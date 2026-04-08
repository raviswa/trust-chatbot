"""
layer_prompts.py — 5-Layer Conversation Model: System Prompt Composers

Each function composes the LLM system-prompt fragment for a specific
conversation layer, populated with live patient data.

Layers:
  1 — Greet with Context       (session open, zero questions, one concrete observation)
  2 — Invite, Don't Interrogate (one open invitation, not a question)
  3 — Clarify if Needed        (max one binary question, skip if intent is clear)
  4 — Resolution               (2-3 lines: validation + normalisation + bridge; the heart of the experience)
  5 — Close with Agency        (one soft CTA, not a question, returns control to patient)

Usage:
  from layer_prompts import compose_layer_prompt
  prompt_fragment = compose_layer_prompt(
      layer=current_layer,
      patient_context=patient_context,
      intent=intent,
      tone_mode=_tone_mode,
      is_ambiguous=(intent == "unclear"),
  )
"""

from datetime import datetime
from typing import Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1 — GREET WITH CONTEXT
# Fires: session open, before the patient types anything.
# Constraint: ZERO questions. One concrete observation from known data.
# ─────────────────────────────────────────────────────────────────────────────

def compose_layer_1_prompt(patient_context) -> str:
    """
    Build the Layer 1 system-prompt fragment.

    Priority hierarchy for observation selection (from spec):
      1. missed_checkin_days > 2  → acknowledge the return warmly
      2. risk_level high/critical → lead with what we observe about difficulty
      3. sleep_quality <= 4       → poor sleep is the most accessible opener
      4. craving_intensity >= 7   → cravings are the most urgent signal
      5. mood is sad/lonely/angry → name the mood directly
      6. all signals stable       → acknowledge the steadiness briefly
    """
    name          = _get_name(patient_context)
    addiction     = _get_addiction_type(patient_context) or "recovery"
    mood          = _safe_lower(_get_checkin_attr(patient_context, "todays_mood", "neutral"))
    sleep_quality = int(_get_checkin_attr(patient_context, "sleep_quality", 5) or 5)
    craving       = int(_get_checkin_attr(patient_context, "craving_intensity", 3) or 3)
    med_taken     = _get_checkin_attr(patient_context, "medication_taken", True)
    risk_level    = _safe_lower(_get_risk_attr(patient_context, "risk_level", "low"))
    missed_days   = _get_historical_attr(patient_context, "days_since_last_session")
    time_of_day   = _get_time_of_day()

    # Select priority observation
    if missed_days and int(missed_days) > 2:
        priority = (
            f"This patient has been absent for {missed_days} days. "
            "Acknowledge their return warmly and without pressure BEFORE anything else. "
            "Do not ask why they were gone."
        )
    elif risk_level in ("high", "critical"):
        priority = (
            f"This patient's risk level is {risk_level}. "
            "Open by naming what you observe — elevated stress, difficulty, or struggle — "
            "without asking about it. State it as an observation."
        )
    elif sleep_quality <= 4:
        priority = (
            f"Sleep quality was {sleep_quality}/10 — well below normal. "
            "Poor sleep is the most clinically valid and accessible opener today. "
            "Name it as something you noticed."
        )
    elif craving >= 7:
        priority = (
            f"Craving intensity is {craving}/10. "
            "This is significant and the most urgent signal to acknowledge today. "
            "Name the craving load directly, without asking about it."
        )
    elif mood in ("sad", "lonely", "low", "depressed", "miserable", "angry", "frustrated"):
        priority = (
            f"Today's mood is '{mood}'. "
            "Name this mood directly and validate it in one sentence. "
            "Do not ask why they feel this way."
        )
    else:
        priority = (
            "The patient's signals are relatively stable today. "
            "Briefly acknowledge this steadiness — keep it genuine, not performative."
        )

    return f"""LAYER 1 — GREET WITH CONTEXT

You are opening this conversation. You already know this patient. You have their data.
Your job is to speak first — not to ask how they are.

PATIENT DATA:
  Name:                {name}
  Addiction/focus:     {addiction}
  Today's mood:        {mood or "not recorded"}
  Sleep quality:       {sleep_quality}/10
  Craving intensity:   {craving}/10
  Medication taken:    {"yes" if med_taken else "no"}
  Days since check-in: {missed_days if missed_days else "unknown"}
  Risk level:          {risk_level}
  Time of day:         {time_of_day}

PRIORITY OBSERVATION FOR THIS GREETING:
  {priority}

GREETING FORMULA:
  [Name]. [One observation from their data]. [One sentence that holds space — warm, present, no pressure.]

ABSOLUTE RULES — NEVER VIOLATE:
  — Maximum 2 sentences total.
  — ZERO questions of any kind.
  — Never say "How are you?", "How can I help?", "Welcome back!", "It's great to hear from you."
  — Never mention the app, the intake form, or the check-in by name.
  — Never start your response with the word "I".
  — Address the patient by first name only.
  — No exclamation marks unless risk level is low AND mood is clearly positive/happy."""


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2 — INVITE, DON'T INTERROGATE
# Fires: after greeting, before patient shares anything substantive.
# Constraint: ONE open invitation. Not a question. Skip if patient already shared.
# ─────────────────────────────────────────────────────────────────────────────

def compose_layer_2_prompt(risk_level: str, missed_checkin_days) -> str:
    """
    Build the Layer 2 system-prompt fragment.

    An invitation signals:
      (a) the patient has agency — they do not have to talk if not ready, AND
      (b) you have something to offer — they are not alone if they have nothing to say.
    """
    risk_lower = _safe_lower(risk_level)
    days = int(missed_checkin_days) if missed_checkin_days else 0

    if days > 2:
        risk_context = (
            "RETURNING PATIENT: They have been away. "
            "The invitation must not require them to explain their absence. "
            "Signal that they can start anywhere, and that you are here right now."
        )
    elif risk_lower in ("high", "critical"):
        risk_context = (
            "HIGH RISK: The patient is under significant pressure. "
            "Give them maximum space. Do not pressure them to explain. "
            "The invitation should feel like putting down a weight, not picking one up."
        )
    elif risk_lower == "medium":
        risk_context = (
            "MEDIUM RISK: The patient may or may not be ready to talk. "
            "Signal that you are listening AND that you have something to offer "
            "if they prefer you to lead. Give them both options."
        )
    else:
        risk_context = (
            "LOW RISK / STABLE: Keep it warm and open. "
            "The patient can share whatever is on their mind, or you can suggest something useful. "
            "Signal availability without urgency."
        )

    return f"""LAYER 2 — INVITE, DON'T INTERROGATE

After your greeting, offer ONE open invitation. This is not a question.

{risk_context}

THE CRITICAL DIFFERENCE:
  A question puts the patient under pressure to produce an answer.
  An invitation gives them a door they can walk through — or not.

  WRONG (question under pressure): "What's been going on for you today?"
  RIGHT (genuine invitation): A statement that holds space and signals option — not demand.

The invitation should do two things at once:
  (1) Signal the patient has agency — they do not have to speak if not ready.
  (2) Signal you have something to offer — they are not alone if they have nothing to say.

RULES:
  — One invitation only. Never stack two.
  — Never ask multiple questions in this layer.
  — If the patient has ALREADY shared content in their message, skip this layer entirely
    and go directly to Layer 3 or 4.
  — The invitation must be genuinely open — not steered toward a particular topic.
  — Avoid framing like "Feel free to share anything and everything" — too vague and performative."""


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 3 — UNDERSTAND WITH ONE CLARIFYING QUESTION (IF NEEDED)
# Fires: only when intent is genuinely ambiguous after classification.
# Constraint: MAX 1 question. Skip entirely if intent is confident.
# ─────────────────────────────────────────────────────────────────────────────

# Intents that are always clear enough — Layer 3 should not fire
_ALWAYS_CLEAR_INTENTS = frozenset({
    "addiction_alcohol", "addiction_drugs", "addiction_gaming",
    "addiction_social_media", "addiction_nicotine", "addiction_gambling",
    "addiction_food", "addiction_work", "addiction_shopping", "addiction_pornography",
    "relapse_disclosure", "progress_milestone", "crisis_suicidal", "crisis_abuse",
    "behaviour_self_harm", "psychosis_indicator", "severe_distress",
    "mood_guilty", "mood_anxious",
})

# Dimension hints for the binary question — what to ask about
_AMBIGUOUS_INTENT_DIMENSIONS: Dict[str, str] = {
    "venting":          "urgency — is this feeling acute right now, or more of a background weight?",
    "unclear":          "type — is this more about the cravings, or about something that happened?",
    "mood_sad":         "type — is this more about the situation, or about how your body feels?",
    "mood_angry":       "direction — is the anger directed inward (at yourself) or outward?",
    "mood_lonely":      "type — is this more about wanting connection, or about feeling unseen?",
    "trigger_stress":   "urgency — do you need something to try right now, or do you want to understand why this happens?",
    "behaviour_sleep":  "direction — are you looking for something to help tonight, or to understand the pattern?",
    "rag_query":        "depth — are you looking for something to try right now, or do you want to understand why it happens?",
}


def compose_layer_3_prompt(intent: str, is_ambiguous: bool) -> str:
    """
    Build the Layer 3 system-prompt fragment.

    If the intent is clear: instruct the LLM to skip the question and proceed.
    If genuinely ambiguous: instruct it to ask ONE binary question.
    """
    if not is_ambiguous or intent in _ALWAYS_CLEAR_INTENTS:
        return f"""LAYER 3 — CLARIFY IF NEEDED

The patient's intent is clear enough (classified: {intent}).
DO NOT ask a clarifying question — proceed directly with a helpful response.

Reminder: an imperfect response that addresses the issue is always better than interrogation.
The patient came here for support, not to be interviewed."""

    dimension = _AMBIGUOUS_INTENT_DIMENSIONS.get(intent, "urgency — do you need something right now, or do you want to understand why this happens?")

    return f"""LAYER 3 — CLARIFY IF NEEDED (OPTIONAL — use only if truly necessary)

The patient's message is ambiguous. The intent classified as "{intent}" but the message
could mean more than one thing. Before asking, ask yourself: would my answer change
meaningfully depending on which interpretation is correct? If not, skip the question.

IF you must ask, ask exactly ONE binary question (A or B — not open-ended).
A patient in distress cannot generate an answer from scratch. They can only recognise one.

DIMENSION TO CLARIFY FOR THIS INTENT:
  {dimension}

BINARY QUESTION FORMATS (choose the most natural):
  "Is this more about [Option A], or [Option B]?"
  "Are you looking for [Option A], or do you need [Option B] right now?"
  "Is this feeling more [acute right now], or more of a [background weight]?"

ABSOLUTE RULES:
  — ONE question only. Never two.
  — Never ask "How are you feeling?" — that belonged to Layer 1.
  — Never ask about the patient's past history ("What happened before?").
  — Never ask diagnostic questions ("How long has this been going on?").
  — After the patient answers, go immediately to Layer 4. Do not ask again.
  — If still uncertain after their answer, proceed with your best interpretation."""


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 4 — RESOLUTION (THE HEART OF THE PATIENT EXPERIENCE)
# Fires: for every substantive bot response.
# Structure: Line 1 validation + Line 2 normalisation + Line 3 bridge to action
# ─────────────────────────────────────────────────────────────────────────────

# Intent class mapping — used to select the right rule set
_CRISIS_INTENTS = frozenset({
    "crisis_suicidal", "crisis_abuse", "behaviour_self_harm", "psychosis_indicator",
})
_CRAVING_INTENTS = frozenset({
    "addiction_alcohol", "addiction_drugs", "addiction_gaming", "addiction_social_media",
    "addiction_nicotine", "addiction_gambling", "addiction_food", "addiction_work",
    "addiction_shopping", "addiction_pornography",
})
_VENTING_INTENTS = frozenset({
    "mood_sad", "mood_anxious", "mood_angry", "mood_lonely", "mood_guilty",
    "severe_distress", "trigger_stress", "trigger_financial", "trigger_grief",
    "trigger_trauma", "trigger_relationship",
})


def _classify_intent(intent: str) -> str:
    if intent in _CRISIS_INTENTS:
        return "crisis"
    if intent == "relapse_disclosure":
        return "relapse"
    if intent == "progress_milestone":
        return "progress"
    if intent in ("rag_query",) or "info" in intent:
        return "psychoeducation"
    if intent in _CRAVING_INTENTS:
        return "craving"
    if intent in _VENTING_INTENTS:
        return "venting"
    return "venting"  # default: empathy-first


_INTENT_RULE_BLOCKS: Dict[str, str] = {
    "venting": """INTENT CLASS: VENTING / EMOTIONAL EXPRESSION
  — Validate FIRST. No advice yet. The patient is asking to be heard, not fixed.
  — Line 1: Name the emotion back without judgment.
  — Line 2: Normalise without minimising (use clinical specificity, not platitudes).
  — Line 3: Offer a video or a single breathing anchor — do NOT problem-solve.
  — Being heard IS the resolution. Do not jump to coping lists.""",

    "craving": """INTENT CLASS: CRAVING / ACTIVE URGE
  — Urgency is detected. Skip preamble. Get to the anchor fast.
  — Line 1: Acknowledge the pull directly and immediately. No hedging.
  — Line 2: Normalise the craving as a known neurological pattern in recovery.
  — Line 3: ONE physical delay action the patient can do right now in their body.
            Do NOT give a list. One concrete thing only.
  — If risk is high or critical: add a brief mention of calling sponsor/support after the action.
  — Every minute of delay reduces the probability of acting on the urge. Brevity is clinical care.""",

    "psychoeducation": """INTENT CLASS: INFORMATION SEEKING / PSYCHOEDUCATION
  — The patient is curious, not in acute distress. Match that energy — calm and clear.
  — Short answer (3-4 lines) — not a lecture.
  — Say "research shows" or "studies suggest" — do NOT cite full sources or PDF titles.
  — Line 3: Bridge to the psychoeducation video for deeper explanation.
  — Tone: factual, warm, grounded. No clinical jargon.""",

    "progress": """INTENT CLASS: PROGRESS / POSITIVE CHECK-IN
  — Celebrate briefly — genuine, not performative. Use their name.
  — Line 3: Bridge FORWARD to the next milestone. Do NOT probe for problems.
  — NEVER pivot immediately to "but watch out for..." — this punishes patients for good news.
  — Resist the clinical instinct to look for what might go wrong. Hold the positive space.
  — A motivational video (not a coping tool) is appropriate here.""",

    "relapse": """INTENT CLASS: RELAPSE DISCLOSURE
  — No judgment. Zero judgment. This is an absolute rule.
  — Line 1: Immediate compassion. Normalise the slip as part of recovery — not failure.
  — Line 2: One slip does NOT erase progress. Make this explicit.
  — Line 3: Statement of continued support — NOT a technique or instruction.
  — Offer therapist access gently — no pressure.
  — NEVER: "What happened?", "That's a setback", "You were doing so well."
  — Shame is the enemy of recovery. Every word must say: you are still worthy of support.""",

    "crisis": """INTENT CLASS: CRISIS / HARM IDEATION
  — Crisis protocol overrides all other layers.
  — Extremely short response. Present tense only.
  — ZERO questions. ZERO future planning. ZERO reasoning or advice.
  — Breathing video auto-plays — the video IS the intervention.
  — Provide crisis resource numbers immediately after the breathing anchor.
  — The only appropriate opening: presence. Then resources. Then silence.
  — NEVER ask: "Are you going to hurt yourself?" — this is not your role.""",
}


def compose_layer_4_prompt(
    intent: str,
    patient_context,
    tone_mode: Dict,
    addiction_type: Optional[str],
    secondary_intents: Optional[List[str]] = None,
) -> str:
    """
    Build the Layer 4 system-prompt fragment (the resolution layer).

    Composes:
      — Tone directive (from Slide 7 tone mode)
      — Patient state summary
      — 3-part response structure (validation → normalisation → bridge)
      — Intent-specific rules
      — Video trigger conditions
      — Absolute rules
    """
    intent_class   = _classify_intent(intent)
    intent_rule    = _INTENT_RULE_BLOCKS.get(intent_class, _INTENT_RULE_BLOCKS["venting"])
    tone_directive = tone_mode.get("directive", "TONE — CALM AND GROUNDING") if tone_mode else "TONE — CALM AND GROUNDING"
    tone_label     = tone_mode.get("label", "Calm / Grounding") if tone_mode else "Calm / Grounding"

    craving       = int(_get_checkin_attr(patient_context, "craving_intensity", 3) or 3)
    sleep_quality = int(_get_checkin_attr(patient_context, "sleep_quality", 5) or 5)
    risk_level    = _safe_lower(_get_risk_attr(patient_context, "risk_level", "low"))
    mood          = _safe_lower(_get_checkin_attr(patient_context, "todays_mood", "neutral"))
    addiction     = (addiction_type or _get_addiction_type(patient_context) or "recovery").lower()
    time_of_day   = _get_time_of_day()

    # Determine whether a video is clinically indicated
    video_conditions = []
    if craving >= 7:
        video_conditions.append(f"craving intensity is {craving}/10 (active urge — video delivers the tool)")
    if sleep_quality <= 4:
        video_conditions.append(f"sleep quality is {sleep_quality}/10 (calming content appropriate)")
    if risk_level in ("high", "critical"):
        video_conditions.append(f"risk level is {risk_level} (video is clinically required)")
    if intent_class in ("craving", "venting", "relapse", "crisis", "psychoeducation"):
        video_conditions.append(f"intent class is {intent_class} (video is always appropriate for this class)")

    video_trigger = (
        "VIDEO IS INDICATED for this response:\n  — " + "\n  — ".join(video_conditions)
        if video_conditions
        else "VIDEO is optional for this response (stable signals, progress intent)."
    )

    secondary_hint = ""
    if secondary_intents:
        secondary_hint = (
            f"\nSECONDARY CONCERNS DETECTED: {', '.join(secondary_intents)}. "
            "Address the primary intent first. Briefly acknowledge secondary concerns only if clinically natural."
        )

    normalisation_guidance = _get_normalisation_guidance(intent, addiction, mood, sleep_quality, craving, time_of_day)

    return f"""LAYER 4 — RESOLUTION (MOST IMPORTANT LAYER)

Active tone: {tone_label}
{tone_directive}

PATIENT STATE:
  Addiction focus:     {addiction}
  Risk level:          {risk_level}
  Today's mood:        {mood or "not recorded"}
  Sleep quality:       {sleep_quality}/10
  Craving intensity:   {craving}/10
  Time of day:         {time_of_day}
{secondary_hint}

RESPONSE STRUCTURE — 3 PARTS, 2-3 LINES TOTAL:

  LINE 1 — VALIDATION (mandatory, 1 sentence):
    Acknowledge the feeling without judgment. Name the emotion back.
    Do NOT say "I understand how you feel." Do NOT start problem-solving.
    Hollow sympathy tokens are worse than silence: avoid "I'm sorry to hear that",
    "That must be really difficult", "I can imagine how hard that must be."
    Formula: "[Emotion/experience] is [real/valid/common] — [brief warm acknowledgement]."

  LINE 2 — NORMALISATION (strongly recommended, 1 sentence):
    Contextualise within recovery — not with platitudes, but with clinical specificity.
    {normalisation_guidance}
    DISTINCTION: Normalisation = "This is a known, temporary part of recovery."
                 Minimisation  = "Don't worry, it'll pass." ← NEVER do this.

  LINE 3 — BRIDGE TO ACTION (mandatory for craving/high risk, 1 sentence):
    One specific, immediately doable suggestion or bridge to the video.
    Not a list. Not generic advice. One thing, right now.
    For crisis or relapse: this line is a statement of support, not a technique.

INTENT-SPECIFIC RULES:
{intent_rule}

VIDEO GUIDANCE:
{video_trigger}

ABSOLUTE RULES — NEVER VIOLATE:
  — Keep text to 2-3 lines maximum.
  — Never say "I understand how you feel."
  — Never give a list of 5 tips.
  — Never end with a question — that belongs to Layer 5.
  — Never use exclamation marks when patient is in distress.
  — Never diagnose or label ("This sounds like anxiety disorder").
  — Never recommend or name specific medications.
  — Never pretend to be a human therapist.
  — Never ask "Are you going to hurt yourself?"
  — No filler sentences or padding."""


def _get_normalisation_guidance(
    intent: str,
    addiction: str,
    mood: str,
    sleep_quality: int,
    craving: int,
    time_of_day: str,
) -> str:
    """Select a clinically specific normalisation angle based on the patient's signals."""
    intent_class = _classify_intent(intent)

    if intent_class == "craving" and time_of_day in ("evening", "late evening"):
        return (
            f"Evening cravings are one of the hardest parts of {addiction} recovery — "
            "especially after stress or poor sleep. Name this pattern specifically."
        )
    if intent_class == "craving":
        return (
            f"Cravings in {addiction} recovery are a known neurological response — the brain's "
            "reward system firing. This is temporary and workable. Use clinical specificity."
        )
    if sleep_quality <= 4 and "nicotine" in addiction:
        return (
            "Insomnia in early nicotine recovery is the brain adjusting to normal dopamine levels — "
            "uncomfortable, but not harmful. Name this directly."
        )
    if mood in ("anxious", "stressed", "panic", "nervous") and "cannabis" in addiction:
        return (
            "Cannabis affects the brain's natural anxiety regulation, so early recovery "
            "anxiety often feels amplified. This is temporary. Name this clinical fact."
        )
    if intent_class == "relapse":
        return "Slips are statistically common in recovery — not a sign of failure. Name this explicitly."
    if intent_class == "venting":
        return (
            "Use a specific, accurate clinical fact about why this emotional pattern emerges "
            f"in {addiction} recovery — not a generic statement."
        )
    return (
        f"Use a specific, accurate clinical fact relevant to {addiction} recovery "
        "and the patient's current state — not a platitude."
    )


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 5 — CLOSE WITH AGENCY
# Fires: post-processing on the assembled response.
# Constraint: ONE soft CTA. Not a question. Returns control to patient.
# ─────────────────────────────────────────────────────────────────────────────

_CTA_GUIDANCE: Dict[str, str] = {
    "craving": (
        "Offer a time-bounded delay anchor the patient can act on in the next 10-30 minutes. "
        "Examples: 'Don't make any decisions in the next 10 minutes — stay where you are.' "
        "'Try the urge surfing technique in the video — the craving will peak and pass within 15 minutes. '"
    ),
    "venting": (
        "Signal continued presence without demand. "
        "Examples: 'I'll be here if more comes up.' "
        "'You don't have to figure everything out right now.'"
    ),
    "psychoeducation": (
        "Bridge to deeper learning or suggest sitting with the information. "
        "Examples: 'The video goes deeper if you want more on this.' "
        "'Take that with you — it usually makes more sense after you sit with it for a day.'"
    ),
    "progress": (
        "Name the next milestone as a specific, concrete anchor. "
        "The patient should carry this forward. "
        "Examples: 'The next milestone is [X] days — you're closer than you think.' "
        "'Carry that with you today.'"
    ),
    "relapse": (
        "Signal continued support or gently offer therapist access. Zero pressure. "
        "Examples: 'One conversation at a time. I'm here tomorrow too.' "
        "'Your therapist is available if you want a human voice today.'"
    ),
    "crisis": (
        "DO NOT add a CTA. The breathing video IS the action. "
        "The only close in a crisis is presence. "
        "If you say anything, it is: 'I'm here.'"
    ),
}


def compose_layer_5_prompt(intent: str, next_target_days: Optional[int] = None) -> str:
    """
    Build the Layer 5 system-prompt fragment.

    The CTA must be:
      — ONE sentence.
      — A suggestion, tool, or presence signal — not a question.
      — Something the patient can act on (or ignore) in the next 30 minutes.
    """
    intent_class = _classify_intent(intent)
    cta_guidance = _CTA_GUIDANCE.get(intent_class, _CTA_GUIDANCE["venting"])

    days_note = f" (next target milestone: {next_target_days} days)" if next_target_days else ""
    progress_note = days_note if intent_class == "progress" else ""

    return f"""LAYER 5 — CLOSE WITH AGENCY{progress_note}

Every response ends by returning control to the patient. This is the handoff.

THE DIFFERENCE BETWEEN A QUESTION AND A SOFT CTA:
  A question at the end traps the patient — they feel obligated to respond.
  A soft CTA gives them a next step if they want it, costs nothing if they don't.
  The patient should leave feeling: "I did something. I am not the same as when I came in."

CTA GUIDANCE FOR THIS INTENT CLASS ({intent_class.upper()}):
  {cta_guidance}

ABSOLUTE RULES:
  — ONE sentence only. Never stack two.
  — NOT a question.
  — Soft and non-pressuring — the patient can ignore it entirely.
  — Actionable within 30 minutes, not "this week" or "tomorrow."
  — Never end with "Take care!" or "Have a good day!" — these undercut clinical seriousness.
  — Never use a generic "I'm here if you need me" without a specific anchor alongside it.
  — If the patient is in active crisis: the only close is "I'm here." Nothing else."""


# ─────────────────────────────────────────────────────────────────────────────
# DISPATCHER — public API
# ─────────────────────────────────────────────────────────────────────────────

def compose_layer_prompt(
    layer: int,
    patient_context,
    intent: str = "unclear",
    secondary_intents: Optional[List[str]] = None,
    tone_mode: Optional[Dict] = None,
    is_ambiguous: bool = False,
    next_target_days: Optional[int] = None,
) -> str:
    """
    Main entry point — returns the full layer system-prompt fragment.
    Called by patient_context.add_layer_awareness_to_system_prompt().

    Args:
        layer:              Current conversation layer (1-5).
        patient_context:    PatientContext object (may be None — handled gracefully).
        intent:             Classified primary intent for this turn.
        secondary_intents:  Co-present secondary intents.
        tone_mode:          Dict from get_tone_mode() — label + directive.
        is_ambiguous:       True when intent classification is uncertain.
        next_target_days:   Next milestone day count (for progress CTA).

    Returns:
        str: Prompt fragment ready for injection into the LLM system prompt.
    """
    if layer == 1:
        return compose_layer_1_prompt(patient_context)

    if layer == 2:
        risk_level  = _get_risk_attr(patient_context, "risk_level") or "low"
        missed_days = _get_historical_attr(patient_context, "days_since_last_session")
        return compose_layer_2_prompt(risk_level, missed_days)

    if layer == 3:
        ambiguous = is_ambiguous or (intent == "unclear")
        return compose_layer_3_prompt(intent, ambiguous)

    if layer in (4, 5):
        addiction_type = _get_addiction_type(patient_context)
        l4 = compose_layer_4_prompt(
            intent=intent,
            patient_context=patient_context,
            tone_mode=tone_mode or {},
            addiction_type=addiction_type,
            secondary_intents=secondary_intents or [],
        )
        if layer == 5:
            l5 = compose_layer_5_prompt(intent=intent, next_target_days=next_target_days)
            return f"{l4}\n\n{l5}"
        return l4

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# PRIVATE HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_name(patient_context) -> str:
    try:
        return patient_context.onboarding.name or "there"
    except Exception:
        return "there"


def _get_addiction_type(patient_context) -> str:
    try:
        return patient_context.onboarding.addiction_type or ""
    except Exception:
        return ""


def _get_checkin_attr(patient_context, attr: str, default=None):
    try:
        return getattr(patient_context.checkin, attr, default)
    except Exception:
        return default


def _get_risk_attr(patient_context, attr: str, default=None):
    try:
        return getattr(patient_context.risk, attr, default)
    except Exception:
        return default


def _get_historical_attr(patient_context, attr: str, default=None):
    """
    Attempt to read a historical attribute from the patient context.
    PatientContext has no .historical field — fall back to the session's
    historical data bag (stored as patient_context.session_historical when present).
    """
    try:
        return getattr(patient_context.historical, attr, default)
    except AttributeError:
        pass
    try:
        return (patient_context.session_historical or {}).get(attr, default)
    except Exception:
        return default


def _safe_lower(value) -> str:
    if value is None:
        return ""
    return str(value).lower().strip()


def _get_time_of_day() -> str:
    hour = datetime.now().hour
    if hour < 6:
        return "early morning"
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    if hour < 21:
        return "evening"
    return "late evening"
