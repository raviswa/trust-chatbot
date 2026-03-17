from dotenv import load_dotenv
load_dotenv()

"""
language_sanitiser.py
─────────────────────────────────────────────────────────────────
Person-First Language Enforcement
Based on NIDA "Words Matter" + Person-First Language PDFs
─────────────────────────────────────────────────────────────────
"""

import re
from typing import Optional

STIGMA_REPLACEMENTS = {
    r"\ban addict\b":               "a person with a substance use disorder",
    r"\bthe addict\b":              "the person with a substance use disorder",
    r"\baddicts\b":                 "people with substance use disorders",
    r"\ban alcoholic\b":             "a person with alcohol use disorder",
    r"\bthe alcoholic\b":            "the person with alcohol use disorder",
    r"\balcoholic\b":                "person with alcohol use disorder",
    r"\bjunkie\b":                  "person who uses drugs",
    r"\bdrug abuser\b":             "person with a substance use disorder",
    r"\bsubstance abuser\b":        "person with a substance use disorder",
    r"\bformer addict\b":           "person in recovery",
    r"\breformed addict\b":         "person in long-term recovery",
    r"\bex-addict\b":               "person in long-term recovery",
    r"\bdrug habit\b":              "substance use disorder",
    r"\bdrinking habit\b":          "alcohol use disorder",
    r"\babusing drugs\b":           "misusing substances",
    r"\babusing alcohol\b":         "using alcohol harmfully",
    r"\bdrug abuse\b":              "substance use",
    r"\balcohol abuse\b":           "harmful alcohol use",
    r"\bsubstance abuse\b":         "substance use disorder",
    r"\bprescription abuse\b":      "prescription medication misuse",
    r"\bstaying clean\b":           "maintaining recovery",
    r"\bget clean\b":               "enter recovery",
    r"\bgot clean\b":               "entered recovery",
    r"\bclean time\b":              "time in recovery",
    r"\btesting dirty\b":           "testing positive",
    r"\btesting clean\b":           "testing negative",
    r"\bsubstitution therapy\b":    "opioid agonist therapy",
    r"\breplacement therapy\b":     "medication treatment for opioid use disorder",
    r"\baddicted baby\b":           "baby with neonatal abstinence syndrome",
    r"\bborn addicted\b":           "born with neonatal abstinence syndrome",
    r"\bdrug addict\b":             "person with a substance use disorder",
    r"\bsubstance addict\b":        "person with a substance use disorder",
    r"\brecovering addict\b":       "person in recovery",
    r"\bfell off the wagon\b":      "experienced a relapse",
    r"\bdrug habit\b":              "substance use disorder",
    r"\bintervention\b":            "evidence-based treatment",
}

SELF_STIGMA_PATTERNS = {
    r"\bi[\s''`]*(am|m)\s+an?\s+alcoholic\b": (
        "I hear you — thank you for trusting me with that. "
        "What you're describing is alcohol use disorder, a recognised medical "
        "condition, not a character flaw or moral failing. "
        "You are more than your relationship with alcohol. "
        "Can you tell me more about what's been happening?"
    ),
    r"\bi[\s''`]*(am|m)\s+an?\s+addict\b": (
        "Thank you for sharing that. What you're experiencing is a substance "
        "use disorder — a health condition, not a reflection of who you are. "
        "Many people live in long-term recovery and lead full, meaningful lives. "
        "What's been going on for you lately?"
    ),
    r"\bi[\s''`]*(am|m)\s+a?\s*junkie\b": (
        "I hear how you're describing yourself — and that label doesn't define you. "
        "What you're going through is a substance use disorder, a medical condition "
        "that deserves care and support, not judgment. "
        "You reached out, which takes real courage. What's been happening?"
    ),
    r"\bi[\s''`]*(am|m)\s+a?\s*drunk\b": (
        "I hear you. The way you're describing yourself tells me you've been "
        "carrying a lot of shame. What you're experiencing may be alcohol use "
        "disorder — a health condition many people recover from with the right support. "
        "How long have you been feeling this way?"
    ),
    r"\bi have a (bad )?habit\b": (
        "I hear how you're describing yourself, and that sounds like you've been carrying a lot of pain and self-judgment"
        "What you're describing may be alcohol use disorder — a recognised medical condition that many people recover from with the right support. "
        "Reaching out today shows strength. If you're comfortable, what has been most difficult recently?"
    ),

    r"\bi have a (bad )?habit\b": (
        "I want to gently reflect something — what you're describing sounds like "
        "more than a habit. Substance use disorders are medical conditions, and "
        "calling it a habit can make it harder to get the support you deserve. "
        "Can you tell me more about what's been going on?"
    ),

    r"\bi[''`]?m dirty\b": (
        "I hear that. The language of 'clean' and 'dirty' around substance use "
        "carries a lot of unnecessary shame. Where you are right now is simply "
        "a point in your journey — not a measure of your worth. "
        "What's been happening lately?"
    ),
}

PERSON_FIRST_RULES = """
LANGUAGE GUIDELINES — apply strictly in every response:

1. PERSON-FIRST: Say "person with a substance use disorder" NOT "addict".
   Say "person with alcohol use disorder" NOT "alcoholic".
   Say "person in recovery" NOT "former/reformed addict".

2. CLINICAL TERMS: Say "substance use" or "misuse" NOT "abuse".
   Use severity specifiers: mild / moderate / severe substance use disorder.

3. RECOVERY: Say "in recovery" or "in remission" NOT "clean".
   Say "currently using" NOT "dirty".

4. TREATMENT: Say "medication treatment" or "opioid agonist therapy"
   NOT "substitution therapy" or "replacement therapy".

5. NEVER echo stigmatising labels the user applies to themselves.
   Gently reframe using person-first clinical language.
"""


def sanitise_response(text: str) -> str:
    for pattern, replacement in STIGMA_REPLACEMENTS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def check_self_stigma(user_input: str) -> Optional[str]:
    for pattern, response in SELF_STIGMA_PATTERNS.items():
        if re.search(pattern, user_input, re.IGNORECASE):
            return response
    return None
