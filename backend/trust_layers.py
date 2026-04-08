"""
TRUST AI — 5-layer conversation model (prompts + orchestration helpers).
Layers are composed into the system prompt and post-processing as documented.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import ollama

from db import get_checkin_status, get_patient, get_session_scores
from video_map import get_video

logger = logging.getLogger(__name__)

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

# ── Layer 1–2 combined generation (session open) ─────────────────────────────

LAYER_12_SYSTEM = """You are TRUST AI opening a recovery support chat.
Output EXACTLY two short paragraphs separated by a blank line.

PARAGRAPH 1 — LAYER 1 (GREET WITH CONTEXT):
- Address the patient by FIRST NAME only.
- Reference exactly ONE concrete observation from the patient context below (prioritise: missed check-in > risk > sleep > cravings > mood > stability).
- Maximum 2 sentences. Do NOT ask any question. Do NOT start with "I".
- Never say: "How are you?", "How can I help?", "Welcome back!", "It's great to hear from you."
- Never reference the intake form or app by name.
- No exclamation marks unless risk is low and mood is positive.

PARAGRAPH 2 — LAYER 2 (INVITE, DON'T INTERROGATE):
- ONE invitation only — not a question (no question mark). Give agency.
- Match risk: low = gentle open door; medium = offer to share or hear a suggestion; high = permission to go slow; returning after silence = no need to catch up on everything.
- Maximum 2 sentences.

If CONTINUITY NOTE is present, weave prior topics naturally without interrogating."""

# ── Layer 3 ─────────────────────────────────────────────────────────────────

LAYER_3_SYSTEM = """You are clarifying an ambiguous message in mental health chat.
Ask EXACTLY ONE short, targeted question. Prefer a binary choice (A or B).
No diagnostic questions. No "How are you feeling?"
Reply with ONLY the question, nothing else."""

# ── Layer 4 (injected into RAG system prompt) ─────────────────────────────────

LAYER_4_RESOLUTION_BLOCK = """
TRUST LAYER 4 — RESOLUTION (mandatory style for this reply):
- Keep the TEXT portion to 2–3 short lines: (1) validation naming the emotion without hollow phrases
  (never say "I understand how you feel"); (2) optional normalisation using retrieved context —
  not minimisation; (3) one bridge to action or to the video — not a bulleted list.
- Do not end the text with a question (closing is Layer 5).
- Let an attached video do detailed psychoeducation when one is offered.
- Never recommend or name medications. Do not diagnose.
- Match tone to risk: high craving = direct, immediate, one physical action.
"""

# ── Layer 5 ─────────────────────────────────────────────────────────────────

LAYER_5_SYSTEM = """You add ONE closing sentence to a therapeutic chat reply.
Rules:
- A soft CTA or suggestion — NOT a question (no question mark).
- One sentence only. Specific, not generic.
- Never: "Take care!", "Have a good day!", vague "I'm here if you need me" alone.
- For crisis-style content, output exactly: I'm here.

Output ONLY the closing sentence (or the exact crisis line above). No quotes."""

# ── Ambiguous phrases (Layer 3) ────────────────────────────────────────────

_AMBIGUOUS_RE = re.compile(
    r"\b(i\s*'?m\s+struggling|struggling\b|things\s+are\s+getting\s+worse|"
    r"i\s+don\s*'?t\s+know\s+what\s+to\s+do|can\s*'?t\s+cope|"
    r"everything\s+is\s+too\s+much)\b",
    re.I,
)

_SUBSTANTIVE_RE = re.compile(
    r"\b(craving|drink|drinking|relapse|withdrawal|anxious|panic|suicid|"
    r"hurt\s+myself|abuse|gaming|nicotine|alcohol|drug|therapist)\b",
    re.I,
)


def first_name(display_name: Optional[str]) -> str:
    if not display_name or not str(display_name).strip():
        return "there"
    return str(display_name).strip().split()[0]


def _time_of_day() -> str:
    h = datetime.now().hour
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "afternoon"
    if 17 <= h < 22:
        return "evening"
    return "night"


def _mood_from_score(mood_score: Optional[int]) -> str:
    if mood_score is None:
        return "not recorded"
    if mood_score >= 8:
        return "lighter"
    if mood_score >= 5:
        return "mixed"
    if mood_score >= 3:
        return "low"
    return "heavy"


def trust_context_or_default(patient_code: Optional[str], session_id: str) -> Dict[str, Any]:
    """TRUST context for prompts; neutral defaults when no patient is linked."""
    if patient_code:
        return build_trust_context(patient_code, session_id)
    return {
        "patient_name": "there",
        "addiction_type": "recovery",
        "todays_mood": "not recorded",
        "sleep_quality": 5,
        "craving_intensity": 5,
        "medication_taken": "not recorded",
        "missed_checkin_days": 0,
        "risk_level": "low",
        "time_of_day": _time_of_day(),
    }


def build_trust_context(patient_code: str, session_id: str) -> Dict[str, Any]:
    """Build the patient context vector used across TRUST layers."""
    patient = get_patient(patient_code) or {}
    scores = {}
    try:
        scores = get_session_scores(session_id) or {}
    except Exception as e:
        logger.debug("get_session_scores: %s", e)

    mood_s = scores.get("mood")
    sleep_s = scores.get("sleep")
    add_s = scores.get("addiction")

    # Scores are 0–10 best; craving intensity is "how bad" (invert addiction score)
    craving_intensity = max(0, min(10, 10 - add_s)) if add_s is not None else 5
    sleep_quality = sleep_s if sleep_s is not None else 5

    status = get_checkin_status(patient_code, hours=24 * 14)
    hours_since = status.get("hours_since_checkin")
    last_seen = status.get("last_seen")
    missed_days = 0
    if hours_since is not None:
        missed_days = int(hours_since // 24)
    elif last_seen:
        try:
            from datetime import timezone

            ls = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            if ls.tzinfo is None:
                ls = ls.replace(tzinfo=timezone.utc)
            delta = datetime.now(ls.tzinfo) - ls
            missed_days = max(0, int(delta.total_seconds() // 86400))
        except Exception:
            missed_days = 0

    risk = "low"
    if mood_s is not None and mood_s <= 3:
        risk = "medium"
    if sleep_s is not None and sleep_s <= 4:
        risk = "medium"
    if craving_intensity >= 7:
        risk = "high"
    if craving_intensity >= 9 or (mood_s is not None and mood_s <= 2):
        risk = "critical"
    if missed_days > 2:
        risk = "high" if risk == "low" else risk

    return {
        "patient_name": first_name(patient.get("display_name")),
        "addiction_type": (patient.get("programme") or "recovery").strip() or "recovery",
        "todays_mood": _mood_from_score(mood_s),
        "sleep_quality": sleep_quality,
        "craving_intensity": craving_intensity,
        "medication_taken": "not recorded",
        "missed_checkin_days": missed_days,
        "risk_level": risk,
        "time_of_day": _time_of_day(),
    }


def format_context_for_prompt(ctx: Dict[str, Any]) -> str:
    return (
        f"Patient name: {ctx['patient_name']}\n"
        f"Addiction focus: {ctx['addiction_type']}\n"
        f"Today's mood (inferred): {ctx['todays_mood']}\n"
        f"Sleep quality (0-10, higher=better): {ctx['sleep_quality']}\n"
        f"Craving intensity (0-10, higher=worse): {ctx['craving_intensity']}\n"
        f"Medication taken: {ctx['medication_taken']}\n"
        f"Approx. days since last check-in context: {ctx['missed_checkin_days']}\n"
        f"Risk level: {ctx['risk_level']}\n"
        f"Time of day: {ctx['time_of_day']}\n"
    )


def generate_trust_opening(
    patient_code: str,
    session_id: str,
    continuity_note: Optional[str] = None,
) -> Optional[str]:
    """TRUST Layers 1–2: combined opening. Returns None if generation fails."""
    ctx = build_trust_context(patient_code, session_id)
    block = format_context_for_prompt(ctx)
    extra = f"\nCONTINUITY NOTE:\n{continuity_note}\n" if continuity_note else ""
    prompt = f"{block}{extra}\nWrite the opening now."
    try:
        r = ollama.generate(
            model=OLLAMA_MODEL,
            system=LAYER_12_SYSTEM,
            prompt=prompt,
            options={"temperature": 0.45, "num_predict": 220},
        )
        text = (r.get("response") or "").strip()
        if len(text) < 20:
            return _fallback_opening(ctx)
        return text
    except Exception as e:
        logger.error("TRUST opening generate failed: %s", e)
        return _fallback_opening(ctx)


def _fallback_opening(ctx: Dict[str, Any]) -> str:
    """Rule-based fallback if the model is unavailable."""
    name = ctx["patient_name"]
    if name == "there":
        name = "Hi"
    missed = ctx["missed_checkin_days"]
    risk = ctx["risk_level"]
    sleep = ctx["sleep_quality"]
    crave = ctx["craving_intensity"]
    invite = (
        "You can share whatever feels most useful right now — or stay quiet and just be here."
    )
    if missed > 2:
        line = (
            f"{name}, you've been quiet for a few days — glad you're here. "
            f"This moment matters."
        )
        invite = "No need to catch everything up — just say where you are right now."
    elif risk in ("high", "critical"):
        line = f"{name}, your check-in signals have been intense lately — that takes courage to show up."
    elif sleep <= 4:
        line = f"{name}, sleep has been thin — that can color the whole day."
    elif crave >= 7:
        line = f"{name}, cravings have been loud today — being here is already a step."
    elif ctx["todays_mood"] in ("low", "heavy"):
        line = f"{name}, today sounds like it's had some weight to it."
    else:
        line = f"{name}, your check-in looked a little steadier today."
    return f"{line}\n\n{invite}"


def is_ambiguous_message(text: str) -> bool:
    t = text.strip()
    if len(t) > 220:
        return False
    if _SUBSTANTIVE_RE.search(t):
        return False
    return bool(_AMBIGUOUS_RE.search(t))


def generate_clarifying_question(user_message: str) -> str:
    """TRUST Layer 3: one clarifying question."""
    try:
        r = ollama.generate(
            model=OLLAMA_MODEL,
            system=LAYER_3_SYSTEM,
            prompt=f"Patient said:\n\"{user_message}\"",
            options={"temperature": 0.3, "num_predict": 80},
        )
        q = (r.get("response") or "").strip().split("\n")[0].strip()
        if q.endswith("?"):
            return q
        return "Is this more about the urge itself, or something that happened today?"
    except Exception as e:
        logger.error("Layer 3 clarify failed: %s", e)
        return "Is this more about the urge itself, or something that happened today?"


def layer4_resolution_suffix() -> str:
    return LAYER_4_RESOLUTION_BLOCK


def apply_layer5_close(
    response: str,
    intent: str,
    trust_ctx: Dict[str, Any],
    severity: str,
) -> str:
    """TRUST Layer 5: append one soft CTA sentence (not a question)."""
    if severity in ("critical",) and intent.startswith("crisis"):
        return response.strip()
    if intent in ("crisis_suicidal", "crisis_abuse", "behaviour_self_harm"):
        return response.strip()
    try:
        r = ollama.generate(
            model=OLLAMA_MODEL,
            system=LAYER_5_SYSTEM,
            prompt=(
                f"Intent: {intent}\nSeverity: {severity}\n"
                f"Context summary: risk={trust_ctx.get('risk_level')}, "
                f"craving={trust_ctx.get('craving_intensity')}\n\n"
                f"Assistant reply so far:\n{response}\n"
            ),
            options={"temperature": 0.35, "num_predict": 60},
        )
        close = (r.get("response") or "").strip().split("\n")[0].strip()
        if not close:
            return response.strip()
        if close.lower() in {"i'm here.", "i'm here"}:
            return response.strip()
        if "?" in close:
            return response.strip()
        return f"{response.strip()}\n\n{close}"
    except Exception as e:
        logger.error("Layer 5 failed: %s", e)
        return response.strip()


# ── Video selection (TRUST layer 4 part B) ───────────────────────────────────

_NO_VIDEO_INTENTS = {
    "greeting",
    "farewell",
    "gratitude",
    "unclear",
    "medication_request",
}

_VIDEO_PRIORITY_FALLBACK = (
    "mood_anxious",
    "addiction_alcohol",
    "behaviour_sleep",
    "addiction_drugs",
)


def trust_select_video(
    intent: str,
    trust_ctx: Dict[str, Any],
    session_scores: Dict[str, int],
    videos_shown: List[str],
) -> Optional[dict]:
    """
    Decide whether to attach a video. Respects 'last 3 sessions' via videos_shown
    (session-scoped recent video_ids).
    """
    if intent in _NO_VIDEO_INTENTS:
        return None
    if intent in ("severe_distress", "psychosis_indicator"):
        vid = get_video("mood_anxious")
        return _avoid_repeat(vid, videos_shown)

    craving = trust_ctx.get("craving_intensity", 5)
    sleep = trust_ctx.get("sleep_quality", 5)
    risk = trust_ctx.get("risk_level", "low")

    want = False
    if craving >= 7:
        want = True
    if sleep <= 4:
        want = True
    if risk in ("high", "critical"):
        want = True
    if intent.startswith("addiction") or intent.startswith("trigger"):
        want = True
    if intent == "rag_query":
        want = True

    if intent in ("mood_sad", "mood_lonely", "mood_guilty", "mood_angry", "mood_anxious"):
        want = True

    if not want:
        return None

    primary = get_video(intent)
    v = _avoid_repeat(primary, videos_shown)
    if v:
        return v
    for tag in _VIDEO_PRIORITY_FALLBACK:
        v = _avoid_repeat(get_video(tag), videos_shown)
        if v:
            return v
    return primary


def _avoid_repeat(video: Optional[dict], videos_shown: List[str]) -> Optional[dict]:
    if not video:
        return None
    vid = video.get("video_id")
    if vid and vid in videos_shown:
        return None
    return video


def register_video_shown(session: dict, video: Optional[dict]) -> None:
    if not video or not video.get("video_id"):
        return
    lst = session.setdefault("trust_videos_shown", [])
    lst.append(video["video_id"])
    session["trust_videos_shown"] = lst[-3:]
