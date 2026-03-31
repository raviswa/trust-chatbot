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
    # ── Alcohol ──────────────────────────────────────────────────────────────
    r"\bi[\s''`]*(am|m)\s+an?\s+alcoholic\b": (
        "I hear you — thank you for trusting me with that. "
        "What you're describing is alcohol use disorder, a recognised medical "
        "condition, not a character flaw or moral failing. "
        "You are not the label — alcohol use is a behaviour your brain has learned, "
        "and behaviours can change with the right support. "
        "Right now, try this: place both feet flat on the floor, take one slow breath, "
        "and name one thing in the room you can see. Grounding first, then we talk."
    ),
    r"\bi[\s''`]*(am|m)\s+a?\s*drunk\b": (
        "I hear the shame in how you're describing yourself — and I want to gently "
        "offer another frame. What you're experiencing may be alcohol use disorder, "
        "a health condition that millions of people live with and recover from. "
        "The urge or pattern is not you. "
        "Drink a glass of water right now, slowly. That single act is a signal to "
        "your body that you are taking care of it."
    ),
    # ── Substances (general) ─────────────────────────────────────────────────
    r"\bi[\s''`]*(am|m)\s+an?\s+addict\b": (
        "Thank you for sharing that — it takes courage to say it out loud. "
        "What you're experiencing is a substance use disorder — a health condition, "
        "not a reflection of your character or your worth. "
        "The dependency is something you're managing, not something you are. "
        "Take three slow breaths right now. In through the nose, out through the mouth. "
        "That is the first step — not a label."
    ),
    r"\bi[\s''`]*(am|m)\s+a?\s*junkie\b": (
        "That label carries a lot of pain — and it does not define you. "
        "What you're going through is a substance use disorder, a medical condition "
        "that deserves care and support, not judgment. "
        "You reached out today, which is already the hardest part. "
        "Ground yourself now: press your feet to the floor and take two slow breaths "
        "before we continue."
    ),
    r"\bi have a (bad )?habit\b": (
        "I want to gently reflect something — what you're describing sounds like "
        "more than a habit. Dependency disorders are medical conditions, and "
        "framing it as 'just a habit' can make it harder to get the support you deserve. "
        "You are not the behaviour. "
        "One small step right now: drink a glass of water and take one slow breath. "
        "Then tell me more when you're ready."
    ),
    r"\bi[''`]?m dirty\b": (
        "The language of 'clean' and 'dirty' around substance use carries a lot of "
        "unnecessary shame — and none of that shame belongs to you. "
        "Where you are right now is simply a point in your journey, not a measure "
        "of your worth. "
        "Try this: press both feet firmly to the floor, take two slow breaths, "
        "and notice one thing you can feel physically right now."
    ),
    # ── Nicotine ─────────────────────────────────────────────────────────────
    r"\bi[\s''`]*(am|m)\s+(a\s+)?(hopeless\s+|chain\s+)?smoker\b": (
        "It sounds like you're feeling really discouraged by your relationship with "
        "nicotine right now — and that discouragement makes complete sense. "
        "Smoking is a behaviour your brain has learned to depend on for relief; "
        "it is not who you are. "
        "Since the urge may be peaking right now, try Deep Exhalation: "
        "breathe in slowly for 4 counts, hold for 2, breathe out for 8. "
        "That long exhale mimics the relief pattern of a cigarette without the smoke. "
        "Try 3 rounds now."
    ),
    r"\bi[\s''`]*(am|m)\s+(a\s+)?vape\s+(addict|junkie)\b": (
        "I hear how you're describing yourself — and that label does not define you. "
        "Nicotine dependency is a physical and psychological condition tied to how "
        "the brain's reward system responds to stimulation, not a personal failing. "
        "Since the urge to vape may be strong right now, try this: "
        "breathe in for 4 counts, hold for 2, breathe out for 8. "
        "Three rounds. The long exhale gives your nervous system the same signal "
        "without the nicotine."
    ),
    r"\bi[\s''`]*(am|m|have\s+been)\s+(addicted|hooked)\s+to\s+(smoking|cigarettes?|vaping|nicotine)\b": (
        "It sounds like you're feeling trapped by your relationship with nicotine — "
        "and that is a real, recognised physical dependency, not a weakness. "
        "Nicotine changes how the brain manages dopamine; quitting is genuinely hard, "
        "and struggling does not mean you are failing. "
        "Right now, try 3 rounds of Deep Exhalation: "
        "in for 4 counts, hold for 2, out for 8. "
        "Your body gets the relief signal without the smoke."
    ),
    # ── Gambling ─────────────────────────────────────────────────────────────
    r"\bi[\s''`]*(am|m)\s+(a\s+)?(gambling|compulsive)\s+addict\b": (
        "I hear how you're describing yourself right now — and that label does not "
        "define you. "
        "Gambling disorder is a recognised condition involving how the brain's "
        "reward system responds to risk and anticipation; it is something you are "
        "managing, not something you are. "
        "The urge is loud today. Before acting on it: "
        "press both feet to the floor, take 3 slow breaths, and wait 15 minutes. "
        "Most urges peak and then ease within that window."
    ),
    r"\bi[\s''`]*(am|m)\s+a\s+(compulsive\s+)?gambler\b": (
        "The gambling urge is loud right now — and I want to separate that urge "
        "from who you are. "
        "Gambling disorder is a brain-based condition rooted in how the reward "
        "system processes risk, not a measure of your character or discipline. "
        "Right now: step away from any screen or betting app, press your feet firmly "
        "to the floor, and take 3 slow breaths. "
        "The urge will peak and ease — usually within 15 minutes."
    ),
    r"\bi[\s''`]*(am|m)\s+a\s+(loser|degenerate)\b": (
        "I hear how much pain is behind those words — and I want to say clearly: "
        "that is not who you are. "
        "Gambling disorder reshapes how the brain processes risk and reward; "
        "it is a condition, not a verdict on your worth. "
        "Right now, try one concrete step: move to a different room, press your "
        "feet to the floor, and take 3 slow breaths before doing anything else."
    ),
    r"\bi\s+can[''`]?t\s+stop\s+(betting|gambling)\b": (
        "I hear you — and the fact that you're saying that tells me you're "
        "aware of the pull and you don't want it to win. "
        "That awareness is important. Gambling urges are driven by the brain's "
        "reward system; they are not a character flaw. "
        "Right now: close any betting app or browser tab, press both feet to the "
        "floor, take 3 slow breaths, and wait 15 minutes. "
        "The urge will ease — it always peaks and passes."
    ),
    r"\bi[\s''`]*(am|m|have\s+been)\s+(addicted|hooked)\s+to\s+gambling\b": (
        "It sounds like you're feeling really trapped by your relationship with "
        "gambling right now — and that is a recognised condition, not a personal "
        "defect. "
        "The gambling urge hijacks the brain's reward system; struggling with it "
        "is not a reflection of your strength or your character. "
        "One step right now: close every betting tab or app, press your feet to "
        "the floor, and take 3 slow breaths. "
        "Most urges peak and ease within 15 minutes — stay with me through it."
    ),
    # ── Gaming / Digital / Screen ─────────────────────────────────────────────
    r"\bi[\s''`]*(am|m)\s+(a\s+)?gaming\s+addict\b": (
        "I hear how you're describing yourself — and that label does not tell the "
        "whole story. "
        "Gaming disorder is about how the brain's dopamine system responds to "
        "feedback loops and reward; it is a pattern, not your identity. "
        "The screen urge is high right now. "
        "Try a 30-second sensory reset: name 3 things you can see and 2 things "
        "you can hear right now. "
        "That small pause creates real space between the urge and the action."
    ),
    r"\bi[\s''`]*(am|m|have\s+been)\s+(addicted|hooked)\s+to\s+(my\s+)?phone\b": (
        "It sounds like your phone use is feeling out of control — and you're not "
        "alone in that. "
        "Phone and social media platforms are engineered to capture attention "
        "through the same dopamine pathways involved in other dependencies; "
        "struggling with them is not a weakness. "
        "Right now: put your phone face-down in another room and try a 30-second "
        "sensory reset — name 3 things you can see and 2 things you can hear. "
        "That gap between urge and action is where change happens."
    ),
    r"\bi[\s''`]*(am|m)\s+(a\s+)?screen\s+slave\b": (
        "I hear how trapped you're feeling — and I want to gently offer another "
        "frame. "
        "Digital dependency is a real condition driven by how platforms are "
        "designed to hold attention, not a reflection of your willpower or worth. "
        "Right now, take 30 seconds: put the device down, name 3 things you can "
        "see and 2 things you can hear. "
        "That sensory reset interrupts the loop."
    ),
    r"\bi[\s''`]*(am|m|have\s+been)\s+(addicted|hooked)\s+to\s+social\s+media\b": (
        "It sounds like your relationship with social media is feeling really "
        "hard to manage right now. "
        "Social media is designed to be compelling — the scrolling loop activates "
        "the same reward pathway as other dependencies. "
        "Struggling with it is not a character flaw. "
        "Right now: put your phone in another room for 20 minutes, then come back "
        "and tell me how that felt. "
        "Twenty minutes is all we need for the urge to ease."
    ),
    r"\bi[\s''`]*(am|m)\s+(a\s+)?phone\s+addict\b": (
        "I hear you — and that label does not define you. "
        "Phone dependency activates the same dopamine-reward loops as other "
        "recognised dependencies; it is a pattern your brain has learned, "
        "not a fixed part of who you are. "
        "Try this now: put your phone face-down, name 3 things you can see and "
        "2 things you can hear. "
        "That 30-second reset interrupts the cycle."
    ),
    # ── Work ─────────────────────────────────────────────────────────────────
    r"\bi[\s''`]*(am|m)\s+(a\s+)?workaholic\b": (
        "I hear how you're describing yourself. "
        "Compulsive working is often a response to anxiety, unmet needs, or a "
        "nervous system that has learned to equate busyness with safety — "
        "not a personality trait or something to be proud of or ashamed of. "
        "One step right now: close one tab or app you don't need open, and take "
        "three slow breaths before opening anything new."
    ),
    # ── Food ─────────────────────────────────────────────────────────────────
    r"\bi[\s''`]*(am|m|have\s+been)\s+(a\s+food\s+addict|(addicted|hooked)\s+to\s+food)\b": (
        "I hear how you're describing yourself — and I want to gently offer "
        "another frame. "
        "Emotional eating and food dependency are often responses to how the "
        "nervous system manages stress and discomfort, not reflections of "
        "your character or discipline. "
        "Right now: place your hand on your stomach, take one slow breath, and "
        "notice what feeling was present just before the urge. "
        "Name it — out loud or in your head. That naming is the first step."
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
