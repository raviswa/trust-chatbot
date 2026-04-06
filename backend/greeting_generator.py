"""
greeting_generator.py — 5-Layer Clinical Greeting Generator

Generates context-aware opening greetings following the 5-Layer Conversation Model:

1. CONTEXTUAL OPENING
   - Never generic "How are you?"
   - Mirror patient's current state
   - Reference specific data (subjective + physiological + historical)

2. VALIDATION (Optional)
   - Normalize the struggle
   - Show it makes sense given context
   - Build therapeutic alliance

3. AGENCY
   - Invite, don't interrogate
   - Offer pathways (talk, tool, rest)
   - Honor patient autonomy

Implements Clinical Guardrails:
   • Lead with Patient's Reality: Never fact-check a patient
   • Silent Risk Adjustment: Use objective data to adjust risk, not tone
   • Contextual Bridge: Acknowledge struggle without identifying contradictions
"""

import logging
from typing import Optional
from patient_context import (
    SynthesizedContextVector,
    ToneDirective,
    PhysiologicalThreat,
    EmotionalState,
)

logger = logging.getLogger(__name__)


class GreetingGenerator:
    """Generates 5-Layer greetings informed by synthesized patient context."""
    
    def __init__(self):
        self.logger = logger
    
    def generate_greeting(
        self,
        context: SynthesizedContextVector,
        include_checkmarks: bool = False
    ) -> dict:
        """
        Generate a full greeting message following 5-Layer structure.
        
        Args:
            context: SynthesizedContextVector from synthesis engine
            include_checkmarks: Include explanation of data sources
        
        Returns:
            Dict with:
              greeting: Full greeting text
              layers: Breakdown of each layer
              tone: Tone directive that was applied
              risk_score: Final clinical risk score for backend
        """
        if not context.is_returning_user:
            # New user or very old data — use first-contact greeting
            return self._generate_first_contact_greeting(context)
        
        layers = {
            "contextual_opening": self._generate_contextual_opening(context),
            "validation": self._generate_validation(context),
            "agency": self._generate_agency(context),
        }
        
        # Assemble full greeting
        greeting_parts = [layers["contextual_opening"]]
        
        if layers["validation"]:
            greeting_parts.append("\n\n" + layers["validation"])
        
        if layers["agency"]:
            greeting_parts.append("\n\n" + layers["agency"])
        
        greeting_text = "".join(greeting_parts)
        
        if include_checkmarks:
            greeting_text += self._generate_data_sources_note(context)
        
        return {
            "greeting": greeting_text,
            "layers": layers,
            "tone": context.tone_directive.value,
            "risk_score": context.clinical_risk_score,
            "dominant_theme": context.dominant_theme,
            "data_freshness": {
                "subjective_hours_ago": context.subjective.hours_ago,
                "physiological_hours_ago": context.physiological.hours_ago,
                "is_returning_user": context.is_returning_user,
                "all_data_recent": context.all_data_recent,
            }
        }
    
    def _generate_first_contact_greeting(self, context: SynthesizedContextVector) -> dict:
        """Greeting for new users or when no recent data available."""
        name = context.patient_name
        
        greeting = (
            f"Hi {name} 👋 Welcome to TRUST AI. "
            "I'm here to listen and support you. "
            "This is a safe, private space — you can share what's on your mind today, "
            "and I'll meet you with care and understanding."
        )
        
        return {
            "greeting": greeting,
            "layers": {
                "contextual_opening": greeting,
                "validation": None,
                "agency": None,
            },
            "tone": ToneDirective.SUPPORTIVE.value,
            "risk_score": 30,
            "dominant_theme": "first_contact",
            "data_freshness": {
                "subjective_hours_ago": None,
                "physiological_hours_ago": None,
                "is_returning_user": False,
                "all_data_recent": False,
            }
        }
    
    def _generate_contextual_opening(self, context: SynthesizedContextVector) -> str:
        """
        Layer 1: Contextual Opening — Trust AI Style

        Lead directly with what the data shows, not a generic "how are you".
        Reference specific check-in details and name the clinical connection.

        Target style:
          "Hi Arjun. Your check-in showed stress today and low sleep quality.
           That combination can make cravings stronger. I'm here."
        """
        name = context.patient_name
        subj = context.subjective
        phys = context.physiological

        # ── Build what the check-in showed ───────────────────────────────────
        checkin_details = []
        phys_details = []
        clinical_connection = None

        if subj.is_recent():
            mood = subj.emotional_state.lower()
            mood_phrases = {
                "stressed":     "stress today",
                "anxious":      "anxiety today",
                "angry":        "frustration today",
                "sad":          "low mood today",
                "lonely":       "loneliness today",
                "guilty":       "feelings of guilt today",
                "overwhelmed":  "feeling overwhelmed today",
                "hopeful":      "a sense of hope today",
            }
            if mood in mood_phrases:
                checkin_details.append(mood_phrases[mood])

            if subj.sleep_quality is not None and subj.sleep_quality <= 5:
                checkin_details.append("low sleep quality")
            elif subj.sleep_quality is not None and subj.sleep_quality <= 7:
                checkin_details.append("average sleep last night")

            if subj.craving_intensity is not None and subj.craving_intensity >= 7:
                checkin_details.append("strong cravings")
            elif subj.craving_intensity is not None and subj.craving_intensity >= 5:
                checkin_details.append("some cravings present")

            if not subj.medication_taken:
                checkin_details.append("a missed medication dose")

            if subj.triggers_today:
                checkin_details.append(f"{subj.triggers_today[0]} as a trigger")

        # ── Add wearable context ──────────────────────────────────────────────
        if phys.is_recent():
            phys_note = self._build_physiological_note(context)
            if phys_note:
                phys_details.append(phys_note)

        # ── Clinical connection sentence ──────────────────────────────────────
        theme = context.dominant_theme
        has_stress   = any("stress" in d or "anxiety" in d or "frustration" in d for d in checkin_details)
        has_sleep    = any("sleep" in d for d in checkin_details)
        has_cravings = any("craving" in d for d in checkin_details)
        has_lonely   = any("loneli" in d for d in checkin_details)
        has_guilt    = any("guilt" in d for d in checkin_details)

        if has_stress and has_sleep:
            clinical_connection = "That combination can make cravings stronger and the day feel heavier."
        elif has_stress and has_cravings:
            clinical_connection = "Stress and cravings together take real strength to navigate."
        elif has_cravings:
            clinical_connection = "Strong cravings are a signal worth paying attention to."
        elif has_sleep and has_stress:
            clinical_connection = "Poor rest and stress feed each other — let's work through it together."
        elif has_sleep:
            clinical_connection = "Low sleep can affect mood, patience, and cravings all at once."
        elif has_lonely:
            clinical_connection = "Loneliness is one of the harder parts of recovery. You don't have to sit with it alone."
        elif has_guilt:
            clinical_connection = "Guilt can weigh heavily. You reached out today — that matters."
        elif phys_details:
            clinical_connection = "Your body is giving us some useful signals."

        # ── Historical anchor (when no recent check-in) ───────────────────────
        if not checkin_details and not phys_details:
            if context.historical.recurring_themes:
                theme_text = context.historical.recurring_themes[0].replace("_", " ")
                days = context.historical.days_since_last_session or 1
                return (
                    f"Hi {name}. Last time we spoke, {theme_text} was on your mind. "
                    f"Good to have you back — how are things sitting today?"
                )
            return f"Hi {name}. I'm here to listen and support you. What's on your mind today?"

        # ── Assemble the opening ──────────────────────────────────────────────
        sources = []
        if checkin_details:
            sources.append(f"Your check-in showed {', and '.join(checkin_details)}")
        if phys_details:
            sources.append(f"your wearable picked up {', and '.join(phys_details)}")

        opening = f"Hi {name}. " + "; ".join(sources) + "."
        if clinical_connection:
            opening += f" {clinical_connection}"

        return opening
    
    def _generate_validation(self, context: SynthesizedContextVector) -> Optional[str]:
        """
        Layer 2: Validation — brief, warm close.

        Trust AI style: one sentence that normalises the experience,
        then "I'm here." — not a long paragraph.
        """
        if not context.subjective.is_recent() and not context.physiological.is_recent():
            return None

        theme = context.dominant_theme
        subj  = context.subjective

        if "stress" in theme:
            return "That's not a sign of weakness — it's your nervous system working hard. I'm here."

        if "sleep" in theme:
            return "Sleep has a bigger effect on everything else than most people realise. I'm here."

        if "craving" in theme and subj.craving_intensity >= 7:
            triggers = f" Especially with {subj.triggers_today[0]} in the mix." if subj.triggers_today else ""
            return f"Cravings this strong are tough.{triggers} I'm here."

        if "lonely" in (context.emotional_anchor or ""):
            return "Loneliness is real, and reaching out today took courage. I'm here."

        if "angry" in (context.emotional_anchor or ""):
            return "Anger is often protecting something important underneath. I'm here to help you look at it."

        if "guilty" in (context.emotional_anchor or ""):
            return "Guilt can be heavy to carry. You don't have to carry it alone. I'm here."

        if "mood:sad" in theme:
            return "Low days are part of the journey — they don't erase the progress you've made. I'm here."

        if context.contradiction_detected:
            if context.contradiction_type == "patient_felt_rested_but_objectively_poor":
                return "Sometimes mind and body are out of sync. Your body may have been working harder than it felt. I'm here."
            if context.contradiction_type == "patient_calm_but_physiologically_stressed":
                return "Stress can hide beneath the surface. Let's gently explore what's happening. I'm here."

        return "What you're carrying is real. I'm here."
    
    def _generate_agency(self, context: SynthesizedContextVector) -> Optional[str]:
        """
        Layer 3: Agency
        
        Invite, don't interrogate. Offer pathways. Honor patient autonomy.
        
        Examples:
        - "You can tell me what's on your mind"
        - "I can suggest a grounding tool"
        - "You might need to just rest right now"
        """
        name = context.patient_name
        
        # Offer multiple pathways based on context
        if context.tone_directive == ToneDirective.CALM_GROUNDING:
            return (
                f"You can tell me what's on your mind, or if you'd rather, "
                f"I can walk you through a quick grounding practice right now — whatever feels right."
            )
        
        if context.tone_directive == ToneDirective.VALIDATING:
            return (
                f"{name}, you can share what's happening with me right now, "
                f"or I have some tools that have helped others with what you're experiencing. "
                f"What would be most helpful?"
            )
        
        if context.clinical_risk_score >= 70:
            # High risk — prioritize safety
            return (
                f"{name}, I want to make sure you're safe. "
                f"Tell me what's happening, and if things ever feel too intense, "
                f"we have crisis resources available immediately."
            )
        
        # Default agency
        return (
            f"I'm here to listen and support you. "
            f"You can tell me what's on your mind, or I can suggest something that's helped others today. "
            f"What would be most helpful right now?"
        )
    
    def _build_physiological_note(self, context: SynthesizedContextVector) -> Optional[str]:
        """Build a note about physiological state without sounding clinical."""
        threats = context.physiological_threats
        
        if PhysiologicalThreat.LOW_HRV in threats:
            return "your heart rate variability showed stress markers last night"
        
        if PhysiologicalThreat.HIGH_STRESS in threats:
            return "your stress levels were elevated"
        
        if PhysiologicalThreat.POOR_SLEEP in threats:
            hours = context.physiological.sleep_hours or 0
            return f"your wearable suggests you had around {int(hours)} hours of sleep"
        
        if PhysiologicalThreat.ELEVATED_HR in threats:
            return "your heart rate has been running a bit high"
        
        if PhysiologicalThreat.ANOMALY in threats:
            detail = context.physiological.anomaly_detail or "something shifted"
            return f"your wearable flagged {detail}"
        
        return None
    
    def _build_normalization(self, context: SynthesizedContextVector) -> Optional[str]:
        """Build normalization note explaining why current state makes sense."""
        theme = context.dominant_theme
        
        # Extract theme category
        if "stress" in theme:
            return (
                "That stress makes sense — and it's something we can work with together."
            )
        
        if "mood" in theme:
            mood = theme.split(":")[1] if ":" in theme else "challenging"
            return (
                f"Feeling {mood} is something many people experience on this journey. "
                f"You're not alone, and it can shift."
            )
        
        if "high_craving" in theme:
            return (
                "When cravings spike, it's your nervous system signaling for relief. "
                "That's normal — and there are strategies we can use right now."
            )
        
        return None
    
    def _generate_data_sources_note(
        self,
        context: SynthesizedContextVector
    ) -> str:
        """Generate note about which data sources were used (for debugging)."""
        sources = []
        
        if context.subjective.is_recent():
            sources.append(f"✓ Daily check-in ({context.subjective.hours_ago}h ago)")
        
        if context.physiological.is_recent():
            sources.append(f"✓ Wearables ({context.physiological.hours_ago}h ago)")
        
        if context.historical.last_session_timestamp:
            sources.append(f"✓ Session history ({context.historical.days_since_last_session}d ago)")
        
        if not sources:
            return "\n\n[No recent data — using first-contact greeting]"
        
        return "\n\n[Data sources: " + " | ".join(sources) + "]"


# ════════════════════════════════════════════════════════════════════════════
# FACTORY
# ════════════════════════════════════════════════════════════════════════════

_generator = GreetingGenerator()


def generate_greeting_message(
    context: SynthesizedContextVector,
    include_sources: bool = False
) -> dict:
    """
    Main entry point for greeting generation.
    
    Usage:
        from greeting_generator import generate_greeting_message
        from patient_context_synthesis import synthesize_patient_context, SubjectiveState
        
        # Build context
        context = synthesize_patient_context(
            subjective=SubjectiveState(
                emotional_state="stressed",
                craving_intensity=8,
                sleep_quality=2,
                checkin_timestamp="2026-03-27T14:00:00"
            ),
            patient_name="Alvin"
        )
        
        # Generate greeting
        result = generate_greeting_message(context)
        print(result["greeting"])
        print(result["tone"])  # "calm_grounding"
        print(result["risk_score"])  # 65
    """
    return _generator.generate_greeting(context, include_checkmarks=include_sources)
