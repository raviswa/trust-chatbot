"""
ethical_policy.py
─────────────────────────────────────────────────────────────────
Ethical AI Policy Layer — Mental Health Chatbot
Trust AI Platform

Compliance frameworks addressed:
  ├── FDA         Software as a Medical Device (SaMD) guidance
  ├── EU AI Act   High-risk AI system requirements (Annex III)
  ├── WHO         Ethics and governance of AI for health (2021)
  ├── NIDA        Person-first, non-stigmatising language standards
  ├── APA         Ethical principles for AI in psychology
  └── HIPAA       Privacy and minimum-necessary data principles

This module:
  1. Declares the formal policy as a structured constant
  2. Enforces policy at runtime via response validation
  3. Logs all policy violations for audit trail
  4. Provides policy disclosure text for user-facing display
  5. Exports a single check_policy() function used by chatbot_engine.py

Usage in chatbot_engine.py:
    from ethical_policy import check_policy, POLICY_DISCLOSURE

    # Before returning any response to user:
    result = check_policy(response_text, intent, session_id)
    if result.violation:
        return result.safe_response
─────────────────────────────────────────────────────────────────
"""

import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════
# SECTION 1: FORMAL POLICY DECLARATION
# This is the canonical policy document for the system.
# Reference this in your compliance documentation.
# ═════════════════════════════════════════════════════════════════

AI_MENTAL_HEALTH_SAFETY_POLICY = """
╔══════════════════════════════════════════════════════════════╗
║         TRUST AI — MENTAL HEALTH CHATBOT                    ║
║         ETHICAL AI SAFETY POLICY                            ║
║         Version 1.0 | Effective: 2026                       ║
╚══════════════════════════════════════════════════════════════╝

SYSTEM CLASSIFICATION:
  This system is classified as an AI-powered informational
  and emotional support tool. It is NOT classified as, and
  must NOT be used as, a medical device, diagnostic tool,
  or clinical decision support system.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION A — THE SYSTEM MUST NOT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. DIAGNOSIS
     Must not provide, imply, or suggest any psychiatric,
     psychological, or medical diagnosis. This includes
     informal statements such as "you may have depression"
     or "this sounds like PTSD."
     Reference: FDA SaMD guidance, EU AI Act Article 22

  2. MEDICATION
     Must not recommend, name, describe dosages of, or
     suggest any prescription or over-the-counter medication,
     supplement, or psychoactive substance.
     Reference: FDA 21 CFR Part 820, WHO AI Ethics Principle 4

  3. REPLACEMENT OF PROFESSIONAL CARE
     Must not position itself as a substitute for licensed
     mental health professionals, psychiatrists, psychologists,
     counsellors, or clinical social workers.
     Reference: APA Ethical Principles 3.04, WHO AI Ethics

  4. INDEPENDENT CRISIS MANAGEMENT
     Must not attempt to de-escalate, manage, or resolve
     active suicidal ideation, self-harm, or abuse crises
     without immediately directing the user to emergency
     services or crisis professionals.
     Reference: EU AI Act Annex III (high-risk), WHO guideline

  5. DECEPTIVE IDENTITY
     Must not represent itself as a human, licensed therapist,
     doctor, or any regulated health professional.
     Reference: EU AI Act Article 52 (transparency obligations)

  6. DATA EXPLOITATION
     Must not use conversation data for commercial profiling,
     advertising targeting, or any purpose beyond direct
     service improvement with explicit consent.
     Reference: GDPR Article 9, HIPAA minimum necessary rule

  7. STIGMATISING LANGUAGE
     Must not use person-first language violations, including
     terms such as "addict", "alcoholic", "junkie", "clean",
     "dirty", or any language that defines a person by their
     condition.
     Reference: NIDA Words Matter, APA language guidelines

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION B — THE SYSTEM MUST:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. ENCOURAGE PROFESSIONAL SUPPORT
     Must actively and consistently encourage users to seek
     licensed professional help for clinical concerns,
     especially for addiction, trauma, crisis, and diagnosis.

  2. PERSON-FIRST NON-STIGMATISING LANGUAGE
     Must consistently use person-first language as defined
     in the NIDA "Words Matter" guidelines and APA style
     guide. Language must separate the person from their
     condition at all times.

  3. CRISIS RESOURCE PROVISION
     Must immediately provide relevant crisis resources
     (emergency services, crisis lines, helplines) whenever
     risk indicators are detected, including suicidal
     ideation, self-harm, or domestic abuse disclosures.

  4. EMPATHETIC AND TRAUMA-INFORMED TONE
     Must maintain a warm, non-judgmental, trauma-informed
     tone in all responses. Must not challenge, dismiss, or
     minimise a user's reported experience or emotion.

  5. TRANSPARENCY OF LIMITATIONS
     Must be honest about its limitations when asked. Must
     not overstate its capabilities or the reliability of
     its responses.

  6. HUMAN OVERSIGHT PATHWAY
     Must support clinical team review of flagged sessions
     (crisis, high-severity) via the admin API endpoints.
     All crisis interactions must be logged for review.

  7. EVIDENCE-BASED GROUNDING
     Must ground responses in verified research documents
     (RAG pipeline) rather than generating unsupported
     clinical claims.

  8. AUDIT TRAIL
     Must log all policy violations, intent classifications,
     severity flags, and crisis events to the database for
     compliance review.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION C — COMPLIANCE FRAMEWORK MAPPING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  FDA SaMD Guidance:
    → System classified as non-device informational tool
    → Does not meet SaMD definition (no clinical decision)
    → Medication block enforces this classification

  EU AI Act (2024):
    → Mental health AI classified as HIGH RISK (Annex III)
    → Requires: human oversight, transparency, audit logs
    → Implemented via: admin API, DB logging, policy disclosure

  WHO AI Ethics for Health (2021):
    → Principle 1 (Protecting autonomy): user always directed
      to professional for clinical decisions
    → Principle 4 (Ensuring safety): hard-coded crisis response,
      medication block, diagnosis prohibition
    → Principle 6 (Promoting equity): person-first language,
      non-stigmatising responses

  HIPAA (US):
    → Minimum necessary: only session data stored
    → No PHI transmitted to third parties
    → Crisis logs accessible only to authorised clinical staff

  NIDA Words Matter:
    → Full implementation in language_sanitiser.py
    → Self-stigma interceptor in chatbot_engine.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION D — POLICY GOVERNANCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Policy Owner:      Clinical Advisory Lead, Trust AI
  Technical Owner:   AI/ML Engineering Lead, Trust AI
  Review Cycle:      Quarterly, or after any regulatory update
  Last Reviewed:     2026
  Next Review Due:   Q3 2026

  This policy is enforced programmatically in ethical_policy.py
  and must be reviewed whenever chatbot_engine.py is modified.
"""


# ═════════════════════════════════════════════════════════════════
# SECTION 2: USER-FACING DISCLOSURE TEXT
# Display this to users on first load and in the app footer
# ═════════════════════════════════════════════════════════════════

POLICY_DISCLOSURE = """
This AI assistant provides emotional support and health information only.

It is not a doctor, therapist, or licensed mental health professional,
and cannot replace professional medical or psychological care.

It will not provide diagnoses, medication advice, or clinical treatment.

If you are in crisis or need immediate help, please contact emergency
services or a crisis helpline.

Your conversations are stored securely and may be reviewed by our
clinical team to ensure your safety and improve the service.
""".strip()

POLICY_DISCLOSURE_SHORT = (
    "AI support tool only — not a substitute for professional care. "
    "No diagnoses or medication advice provided."
)


# ═════════════════════════════════════════════════════════════════
# SECTION 3: RUNTIME VIOLATION DETECTION
# Patterns that indicate a policy violation in a generated response
# ═════════════════════════════════════════════════════════════════

# A: Diagnosis violations — system implying a clinical diagnosis
DIAGNOSIS_PATTERNS = [
    r"you (have|are suffering from|are experiencing) (depression|anxiety disorder|PTSD|bipolar|schizophrenia|OCD|ADHD|BPD|personality disorder)",
    r"this (sounds like|suggests|indicates|is consistent with) (depression|anxiety|PTSD|bipolar|a disorder|a condition)",
    r"i (think|believe|suspect) you (have|may have) (a mental|a psychiatric|an anxiety|a mood)",
    r"you (appear to|seem to) (have|suffer from|be diagnosed with)",
    r"(diagnos|diagnosis|diagnosing)",
    r"you (meet the criteria|fit the criteria|show symptoms) (of|for)",
]

# B: Medication violations — naming or recommending any drug
MEDICATION_PATTERNS = [
    r"\d+\s?mg\b",
    r"(take|taking|prescribe|prescribed|recommend)\s+\w+\s+(tablet|capsule|pill|medication|drug)",
    r"(sertraline|fluoxetine|prozac|zoloft|lexapro|xanax|valium|adderall|ritalin|lithium|risperdal|abilify|wellbutrin|effexor|cymbalta|buspirone|clonazepam|lorazepam|diazepam|alprazolam)",
    r"(antidepressant|antipsychotic|anxiolytic|mood stabiliser|ssri|snri|maoi|benzodiazepine)",
    r"(dosage|dose|milligram|twice daily|once daily|three times a day|as needed)",
    r"i recommend (taking|using|trying) .{0,30} (mg|pill|tablet|medication)",
    r"you (should|could|might want to) (take|try|use) .{0,20} (for|to treat)",
]

# C: Professional replacement violations — claiming to be or replace a professional
REPLACEMENT_PATTERNS = [
    r"as your (therapist|doctor|psychiatrist|counsellor|psychologist)",
    r"i (am|function as|act as) (your )?(therapist|doctor|psychiatrist|counsellor)",
    r"(instead of|instead of seeing) (a therapist|a doctor|professional help)",
    r"you (don't need|no longer need|might not need) (a therapist|professional|a doctor)",
    r"i can (treat|diagnose|cure|manage your|handle your mental)",
]

# D: Deceptive identity violations
IDENTITY_PATTERNS = [
    r"i am (a |your )?(human|therapist|doctor|psychiatrist|nurse|counsellor|clinician)",
    r"as a (licensed|qualified|certified|registered) (therapist|psychologist|counsellor)",
    r"in my (clinical|medical|therapeutic|professional) (opinion|judgment|experience)",
]

# Compile all patterns for performance
_COMPILED_PATTERNS = {
    "diagnosis":     [re.compile(p, re.IGNORECASE) for p in DIAGNOSIS_PATTERNS],
    "medication":    [re.compile(p, re.IGNORECASE) for p in MEDICATION_PATTERNS],
    "replacement":   [re.compile(p, re.IGNORECASE) for p in REPLACEMENT_PATTERNS],
    "identity":      [re.compile(p, re.IGNORECASE) for p in IDENTITY_PATTERNS],
}


# ═════════════════════════════════════════════════════════════════
# SECTION 4: SAFE FALLBACK RESPONSES
# Used when a violation is detected — never generated by LLM
# ═════════════════════════════════════════════════════════════════

VIOLATION_FALLBACKS = {
    "diagnosis": (
        "I'm not able to provide or suggest diagnoses — that requires "
        "a qualified mental health professional who can properly assess you. "
        "What I can do is listen and share information from our research documents. "
        "Would you like to talk more about what you've been experiencing?"
    ),
    "medication": (
        "I'm not able to recommend medications, dosages, or treatments. "
        "This is outside my scope and requires a licensed medical professional. "
        "Please speak with your doctor or psychiatrist for medication guidance. "
        "Is there something else I can help you understand?"
    ),
    "replacement": (
        "I want to be clear — I'm an AI support tool, not a replacement for "
        "professional mental health care. A qualified therapist or counsellor "
        "can offer personalised, clinical support that goes far beyond what "
        "I'm able to provide. I'd really encourage you to explore that."
    ),
    "identity": (
        "I should be transparent — I'm an AI assistant, not a human therapist "
        "or medical professional. I can offer information and a listening ear, "
        "but for clinical support, please reach out to a qualified professional."
    ),
}


# ═════════════════════════════════════════════════════════════════
# SECTION 5: POLICY CHECK RESULT
# ═════════════════════════════════════════════════════════════════

@dataclass
class PolicyCheckResult:
    violation:        bool
    violation_type:   Optional[str]
    original_response: str
    safe_response:    str
    checked_at:       str


# ═════════════════════════════════════════════════════════════════
# SECTION 6: MAIN POLICY ENFORCEMENT FUNCTION
# Call this on every outgoing response before returning to user
# ═════════════════════════════════════════════════════════════════

def check_policy(
    response_text: str,
    intent: Optional[str]      = None,
    session_id: Optional[str]  = None
) -> PolicyCheckResult:
    """
    Validates an outgoing response against the ethical AI policy.

    Checks for:
      - Diagnosis violations
      - Medication violations
      - Professional replacement violations
      - Deceptive identity violations

    Args:
        response_text:  The LLM-generated response to validate
        intent:         The detected intent (for logging context)
        session_id:     Session ID (for audit logging)

    Returns:
        PolicyCheckResult with:
          .violation        — True if a violation was found
          .violation_type   — which policy rule was violated
          .safe_response    — use this if violation is True
          .original_response — the original (violating) text
    """
    checked_at = datetime.now().isoformat()

    for violation_type, patterns in _COMPILED_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(response_text):
                # Log the violation for audit trail
                logger.warning(
                    f"POLICY VIOLATION | type={violation_type} | "
                    f"intent={intent} | session={session_id} | "
                    f"pattern='{pattern.pattern[:60]}'"
                )

                safe = VIOLATION_FALLBACKS.get(violation_type, (
                    "I'm not able to provide that type of information. "
                    "Please consult a qualified healthcare professional."
                ))

                return PolicyCheckResult(
                    violation          = True,
                    violation_type     = violation_type,
                    original_response  = response_text,
                    safe_response      = safe,
                    checked_at         = checked_at
                )

    # No violation found
    return PolicyCheckResult(
        violation          = False,
        violation_type     = None,
        original_response  = response_text,
        safe_response      = response_text,
        checked_at         = checked_at
    )


# ═════════════════════════════════════════════════════════════════
# SECTION 7: CRISIS PROTOCOL VALIDATOR
# Separate check — ensures crisis responses always include resources
# ═════════════════════════════════════════════════════════════════

CRISIS_INTENTS = {
    "crisis_suicidal",
    "crisis_abuse",
    "behaviour_self_harm"
}

CRISIS_RESOURCE_MARKERS = [
    "741741",           # Crisis Text Line
    "emergency",
    "911", "999", "112",
    "crisis line",
    "helpline",
    "iasp.info",
    "befrienders",
    "samhsa",
]

def validate_crisis_response(response_text: str, intent: str) -> bool:
    """
    Validates that crisis responses contain at least one
    emergency resource reference.

    Returns True if valid, False if resources are missing.
    WHO AI Ethics Principle 4: ensuring safety.
    """
    if intent not in CRISIS_INTENTS:
        return True  # not a crisis response — no check needed

    lowered = response_text.lower()
    has_resource = any(marker in lowered for marker in CRISIS_RESOURCE_MARKERS)

    if not has_resource:
        logger.error(
            f"CRISIS RESPONSE MISSING RESOURCES | intent={intent} | "
            f"response preview: '{response_text[:80]}'"
        )
        return False

    return True


# ═════════════════════════════════════════════════════════════════
# SECTION 8: POLICY SUMMARY FOR LOGGING / ADMIN API
# ═════════════════════════════════════════════════════════════════

POLICY_SUMMARY = {
    "version":          "1.0",
    "effective_date":   "2026",
    "classification":   "Informational AI Support Tool — NOT a medical device",
    "compliance": [
        "FDA SaMD Guidance (non-device classification)",
        "EU AI Act 2024 — High Risk AI (Annex III)",
        "WHO Ethics and Governance of AI for Health 2021",
        "NIDA Words Matter Language Guidelines",
        "APA Ethical Principles for AI in Psychology",
        "HIPAA Minimum Necessary Rule",
    ],
    "prohibitions": [
        "Clinical diagnosis (any form)",
        "Medication recommendations or dosage guidance",
        "Replacement of licensed professional care",
        "Independent crisis management without escalation",
        "Deceptive identity as human/professional",
        "Stigmatising or person-last language",
    ],
    "requirements": [
        "Encourage professional support in every relevant response",
        "Person-first non-stigmatising language (NIDA standard)",
        "Immediate crisis resource provision on risk detection",
        "Empathetic trauma-informed tone throughout",
        "Full audit trail of all interactions in PostgreSQL",
        "Human oversight via admin API for flagged sessions",
        "Evidence-based responses grounded in RAG pipeline",
    ]
}


# ═════════════════════════════════════════════════════════════════
# SECTION 9: PRINT POLICY (utility for CLI / logging)
# ═════════════════════════════════════════════════════════════════

def print_policy():
    """Prints the full policy to stdout. Useful for compliance audits."""
    print(AI_MENTAL_HEALTH_SAFETY_POLICY)


if __name__ == "__main__":
    print_policy()
    print("\n" + "="*60)
    print("POLICY SUMMARY")
    print("="*60)
    import json
    print(json.dumps(POLICY_SUMMARY, indent=2))

    print("\n" + "="*60)
    print("RUNTIME VIOLATION TEST")
    print("="*60)

    test_cases = [
        ("You have depression and anxiety disorder.",          "diagnosis"),
        ("I recommend taking 50mg of sertraline daily.",       "medication"),
        ("As your therapist, I suggest you try this.",         "replacement"),
        ("I am a licensed clinical psychologist.",             "identity"),
        ("I hear you. That sounds really difficult.",          "clean — no violation"),
    ]

    for text, expected in test_cases:
        result = check_policy(text, intent="test", session_id="test-000")
        status = "VIOLATION" if result.violation else "CLEAN"
        print(f"\n  Input    : {text[:60]}")
        print(f"  Expected : {expected}")
        print(f"  Result   : {status} {('| type: ' + result.violation_type) if result.violation else ''}")
