"""
services_pipeline.py — Unified Chatbot Pipeline Services

Consolidates intent classification, response generation, and safety/policy
validation into a single module with clearly separated sections.

SECTIONS
========
  §1  INTENT CLASSIFIER   — IntentClassifier class
                            Multi-tier: priority patterns → intents.json → LLM → fallback
  §2  RESPONSE GENERATOR  — RESPONSE_TEMPLATES dict + ResponseGenerator class
                            Context-aware, 5-layer compliant responses per intent
  §3  SAFETY & POLICY     — SafetyChecker + PolicyChecker classes
                            Crisis detection, medication blocking, policy compliance
"""

import json
import logging
import random
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import ollama
    OLLAMA_AVAILABLE = True
except Exception:
    OLLAMA_AVAILABLE = False

try:
    from crisis_detector import get_crisis_detector, CONFIDENCE_INTERCEPT, CONFIDENCE_WARN
    _CRISIS_DETECTOR_AVAILABLE = True
except ImportError:
    _CRISIS_DETECTOR_AVAILABLE = False


# ════════════════════════════════════════════════════════════════════════════
# §1  INTENT CLASSIFIER
#     Multi-tier: priority pattern match → intents.json → LLM → fallback
# ════════════════════════════════════════════════════════════════════════════

class IntentClassifier:
    """Classifies user intents with multi-level fallback."""

    def __init__(self, ollama_available: bool = OLLAMA_AVAILABLE, intents_path: str = "intents.json"):
        self.ollama_available = ollama_available
        self.intents_map = self._load_intents(intents_path)
        self.priority_patterns = self._build_priority_patterns()
        self.pattern_tag_map = self._build_pattern_tag_map()

        if not self.ollama_available:
            logger.info("IntentClassifier: Ollama not available, using pattern-based fallback")

    def _load_intents(self, path: str) -> Dict:
        try:
            with open(path) as f:
                raw = re.sub(r"//.*", "", f.read())
                data = json.loads(raw)
                return {i["tag"]: i for i in data.get("intents", [])}
        except Exception as e:
            logger.warning(f"Failed to load intents from {path}: {e}")
            return {}

    def _build_priority_patterns(self) -> Dict[str, list]:
        """Safety-first priority pattern groups (checked in order)."""
        return {
            # Priority 0: Medication blocking
            "medication_request": [
                "medicine", "medication", "prescribe", "prescription", "dose", "dosage",
                "tablet", "capsule", "what should i take", "can i take",
                "which pill", "what medication", "milligram", "mg",
            ],
            # Priority 1: Immediate safety
            "crisis_suicidal": [
                "want to die", "kill myself", "end my life", "don't want to be here",
                "thinking about suicide", "suicide", "suicidal",
                "life is not worth living", "give up on life", "want to disappear forever",
                "nobody would miss me", "can't go on",
            ],
            "crisis_abuse": [
                "being abused", "someone is hurting me", "partner hits me", "beating",
                "scared of someone at home", "unsafe at home", "domestic violence",
                "afraid to go home", "someone is controlling me", "trapped at home",
                "he hits me", "she hits me", "they hit me", "hits me regularly",
                "abusive", "abuse me", "hitting me",
            ],
            "behaviour_self_harm": [
                "hurt myself", "cut myself", "self harm", "harm my body", "burn myself",
                "hit myself", "injure myself", "punish myself", "physical pain helps",
            ],
            # Priority 2: High-severity clinical signals
            "severe_distress": [
                "hopeless", "hopelessness", "nothing matters", "i feel empty",
                "i feel worthless", "no reason to live", "life has no meaning",
                "i feel trapped", "can't escape",
            ],
            "psychosis_indicator": [
                "voices talking to me", "hearing voices", "people watching me",
                "someone controlling my thoughts", "paranoid", "they are after me",
                "mind being controlled",
            ],
            "trigger_trauma": [
                "i was assaulted", "i was raped", "childhood abuse", "trauma memories",
                "flashbacks", "nightmares about it", "past events", "past memories",
                "thinking of past", "dwelling on past", "trauma", "painful memories",
                "couldn't get over", "something happened", "been through",
            ],
            # Priority 2b: Relapse disclosure (distinct from active craving)
            # Clinical behaviour goal: validate + normalise + invite reflection (no directives)
            "relapse_disclosure": [
                "i relapsed", "i relapse", "i slipped", "i had a slip", "i slipped up",
                "i drank last night", "i drank again", "i used again", "i used last night",
                "i smoked again", "i vaped again", "i gambled again", "i binged again",
                "i fell off the wagon", "i messed up and used", "i messed up and drank",
            ],
            "addiction_drugs": [
                "can't stop drinking", "withdrawal", "detox",
                "need alcohol", "need drugs", "need a drink",
                "need a beer", "need some beer", "need beer",
                "need a wine", "need some wine", "need wine",
                "need a whiskey", "need some whiskey",
                "need a vodka", "need some vodka", "need vodka",
                "need a rum", "need some rum", "need rum",
                "need a gin", "need some gin", "need gin",
                "need a shot", "need some shots", "need shots",
                "need bourbon", "need tequila", "need spirits",
                "need alcohol", "need some alcohol", "need more alcohol",
                "want alcohol", "want some alcohol", "want more alcohol",
                "craving beer", "craving wine", "want a beer", "want some beer",
                "craving vodka", "want a vodka", "want some vodka",
                "craving rum", "craving gin", "craving tequila", "craving bourbon",
                "craving a shot", "craving spirits",
                "want to drink", "want to use",
                "trying not to drink", "trying not to use",
                "stopping myself from drinking", "stopping myself from using",
                "urge to drink", "urge to use",
                "tempted to drink", "tempted to use",
                "thinking about drinking", "thinking about using",
                "craving alcohol", "craving drugs", "craving a drink",
                "drug craving", "substance craving",
                "cocaine", "heroin", "meth", "methamphetamine", "crack cocaine",
                "fentanyl", "opioid", "opioids", "ecstasy", "mdma", "ketamine",
                "amphetamine", "amphetamines", "crystal meth", "smack",
                "oxycodone", "morphine", "percocet",
            ],
            # Behavioural gaming cravings — for cross-addiction detection
            # (e.g. alcohol addict reaching for gaming as a substitute)
            "addiction_gaming": [
                "feel like gaming", "want to game", "need to game", "want to play games",
                "need to play games", "craving gaming", "craving some gaming",
                "want to play", "feel like playing games", "urge to game",
                "tempted to game", "thinking about gaming", "thinking about playing",
                "gaming all day", "game all day", "binge gaming", "gaming binge",
                "can't stop gaming", "can't stop playing", "game marathon",
                "need to play", "just want to play",
                "need some gaming", "need gaming", "need more gaming",
                "want some gaming", "want more gaming", "more gaming",
                "gaming", "play games", "video games",
            ],
            # Nicotine cravings
            "addiction_nicotine": [
                "need a cigarette", "need a smoke", "need to smoke", "want a cigarette",
                "want to smoke", "craving a cigarette", "craving nicotine",
                "urge to smoke", "tempted to smoke", "thinking about smoking",
                "need a vape", "want to vape", "need to vape", "craving a vape",
                "urge to vape", "tempted to vape", "thinking about vaping",
                "need a fag", "dying for a smoke", "dying for a cigarette",
                "can't stop smoking", "can't quit smoking",
                "reaching for a cigarette", "picking up a cigarette",
            ],
            # Social media cravings
            "addiction_social_media": [
                "need to check instagram", "need to check twitter", "need to check tiktok",
                "urge to scroll", "urge to check my phone", "need to scroll",
                "want to scroll", "tempted to scroll", "craving social media",
                "want to check my feed", "need to check my feed",
                "compulsive scrolling", "can't stop scrolling", "keep refreshing",
                "doom scrolling", "doomscrolling", "can't put my phone down",
                "need to post", "urge to post", "want to post", "need to check likes",
                "checking my phone constantly", "keep checking my phone",
                "need to check notifications", "urge to check notifications",
            ],
            # Gambling cravings
            "addiction_gambling": [
                "need to gamble", "want to gamble", "urge to gamble", "tempted to gamble",
                "craving to gamble", "thinking about gambling", "thinking about betting",
                "want to bet", "need to bet", "urge to bet", "tempted to bet",
                "want to go to the casino", "need to go to the casino",
                "want to play poker", "urge to play slots", "feeling lucky",
                "want to put a bet on", "want to place a bet", "need to place a bet",
                "urge to place a bet", "can't stop gambling", "gambling again",
                "lost money gambling", "chasing losses", "chasing my losses",
                "scratch cards", "need a flutter", "one more bet",
            ],
            # Priority 3: Behaviour (before mood so explicit symptoms beat vague mood words)
            "behaviour_sleep":  [
                "can't sleep", "cannot sleep", "struggling to sleep", "trouble sleeping",
                "difficulty sleeping", "sleep problem", "sleep trouble", "sleep disorder",
                "insomnia", "nightmares", "waking up", "wake up at", "wake up in",
                "sleepless", "sleeplessness", "no sleep", "not sleeping",
                "slept", "not slept", "haven't slept", "didn't sleep", "couldn't sleep",
                "sleep", "sleeping",
            ],
            "behaviour_fatigue": [
                "tired", "so tired", "very tired", "too tired", "much tired",
                "exhausted", "exhaustion", "fatigue", "fatigued",
                "drained", "physically drained", "worn out", "burnt out", "burnout",
                "no energy", "low energy", "lacking energy", "zero energy",
                "run down", "rundown", "feeling run down",
                "sick", "feeling sick", "unwell", "not well", "ill",
                "nausea", "nauseated", "body aches", "aching",
            ],
            "behaviour_eating": ["eating", "food", "appetite", "not eating", "eating habits", "weight"],
            # Priority 4: Venting (empathy-only — must fire before mood/unclear)
            "venting": [
                "this is so hard", "so hard", "it's too hard", "i can't do this anymore",
                "can't do this anymore", "i'm exhausted", "i'm so exhausted", "completely exhausted",
                "i can't take it anymore", "can't take it anymore", "i'm at my limit",
                "at my limit", "i'm at breaking point", "i'm breaking down", "breaking down",
                "i just need to vent", "need to vent", "i just want to vent", "want to vent",
                "i just want to let it out", "i need to let it out", "let it out",
                "everything is too much", "it's all too much", "too much right now",
                "i'm done", "i can't cope", "i just can't", "i give up",
                "i'm so tired of this", "tired of all this", "i'm worn out",
                "i'm falling apart", "i can't keep going like this",
                "i don't know how much more i can take",
            ],
            # Priority 4b: Mood
            "mood_sad":     ["sad", "depressed", "depression", "feeling down", "unhappy", "worthless", "feel like", "down in the dumps", "blue", "gloomy"],
            "mood_anxious": ["anxious", "anxiety", "worried", "nervous", "panicking", "panic attack", "stressed", "stress", "tense", "worried about"],
            "mood_angry":   ["angry", "rage", "furious", "frustrated", "irritated", "annoyed", "mad", "getting angry"],
            "mood_lonely":  ["alone", "lonely", "isolated", "no one", "nobody", "by myself"],
            "mood_guilty":  ["guilty", "guilt", "ashamed", "shame", "regret", "regretful"],
            # Priority 5: Small talk
            "greeting":  ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "good night", "howdy", "greetings", "what's up", "how are you"],
            "farewell":  ["bye", "goodbye", "see you", "see you later", "take care", "i have to go", "gotta go", "talk later", "i'm leaving", "that's all for now", "thanks bye"],
            "gratitude": ["thank you", "thanks", "thank you so much", "that was helpful", "you helped me", "i appreciate it", "really appreciate", "cheers"],
        }

    def _build_pattern_tag_map(self) -> Dict[str, str]:
        mapping = {}
        for tag, intent_data in self.intents_map.items():
            for pattern in intent_data.get("patterns", []):
                mapping[pattern.lower()] = tag
        return mapping

    # Maps addiction_type → primary craving intent tag (mirrors ResponseRouter._PRIMARY_INTENT_MAP)
    _ADDICTION_TYPE_TO_INTENT: Dict[str, str] = {
        "alcohol":      "addiction_drugs",
        "drugs":        "addiction_drugs",
        "gaming":       "addiction_gaming",
        "social_media": "addiction_social_media",
        "nicotine":     "addiction_nicotine",
        "smoking":      "addiction_nicotine",
        "gambling":     "addiction_gambling",
    }

    # Generic craving/urge phrases that are ambiguous without patient context
    _GENERIC_CRAVING_TERMS: list = [
        "craving", "urge to", "urge is", "the pull", "tempted",
        "really want", "need my", "want to use", "feel like i need",
        "can't resist", "feeling the urge", "urge feels", "so strong",
        "overwhelming urge", "strong urge", "urge is strong",
        "i want to give in", "about to give in",
    ]

    def classify(self, text: str, addiction_type: Optional[str] = None) -> str:
        """
        Classify user intent with multi-tier fallback.

        addiction_type — patient's primary registered addiction (e.g. 'alcohol', 'gaming').
                         When provided, generic craving language is routed to the correct
                         addiction intent instead of falling to rag_query.

        Tier 1 → priority patterns (safety-first)
        Tier 2 → intents.json patterns
        Tier 3 → LLM (if Ollama available)
        Tier 4 → keyword fallback (with addiction-context craving detection)
        """
        text_lower = text.lower().strip()

        # Tier 1a: if patient's addiction is known, detect generic craving language FIRST
        # (before safety priority patterns, because these are addiction-specific primary cravings)
        if addiction_type:
            _norm = addiction_type.lower().strip().replace(" ", "_").replace("-", "_")
            _primary = self._ADDICTION_TYPE_TO_INTENT.get(_norm)
            if _primary and any(t in text_lower for t in self._GENERIC_CRAVING_TERMS):
                # Only intercept if NOT already caught by a more specific safety pattern below
                # (safety patterns still take priority — this just closes the rag_query gap)
                _safety_intents = {
                    "crisis_suicidal", "crisis_abuse", "behaviour_self_harm",
                    "severe_distress", "psychosis_indicator", "medication_request",
                }
                safety_match = next(
                    (i for i, pats in self.priority_patterns.items()
                     if i in _safety_intents and any(p in text_lower for p in pats)),
                    None,
                )
                if not safety_match:
                    logger.debug(f"Classified as '{_primary}' (addiction-context craving)")
                    return _primary

        for intent, patterns in self.priority_patterns.items():
            if any(p in text_lower for p in patterns):
                logger.debug(f"Classified as '{intent}' (priority pattern)")
                return intent

        for pattern, tag in self.pattern_tag_map.items():
            if pattern in text_lower:
                logger.debug(f"Classified as '{tag}' (intents.json pattern)")
                return tag

        if self.ollama_available:
            llm_intent = self._llm_classify(text, addiction_type=addiction_type)
            if llm_intent:
                logger.debug(f"Classified as '{llm_intent}' (LLM)")
                return llm_intent

        fallback = self._pattern_classify_fallback(text_lower, addiction_type=addiction_type)
        logger.debug(f"Classified as '{fallback}' (fallback)")
        return fallback

    def classify_multi(self, text: str, addiction_type: Optional[str] = None) -> Tuple[str, List[str]]:
        """
        Returns (primary_intent, secondary_intents).

        Secondary intents are additional co-present signals found in the same
        message — e.g. "can't sleep and really craving a drink" gives:
            primary:    addiction_drugs
            secondary: [behaviour_sleep]

        Rules:
        - Safety-critical intents (crisis, self-harm, medication) are NEVER
          relegated to secondary.  If the primary is a safety intent, the
          secondary scan is skipped entirely.
        - Cap: at most 3 secondary intents to avoid noise.
        - When Ollama is available, secondary scan uses a single LLM multi-label
          call so synonyms, context, and paraphrasing are all understood.
        - Falls back to pattern-based scan when Ollama is unavailable.
        """
        primary = self.classify(text, addiction_type=addiction_type)

        _safety_intents = {
            "crisis_suicidal", "crisis_abuse", "behaviour_self_harm",
            "severe_distress", "psychosis_indicator", "medication_request",
        }
        # Never look for secondary signals when the primary is a safety event
        if primary in _safety_intents:
            return primary, []

        # ── LLM multi-label secondary scan ────────────────────────────────
        if self.ollama_available:
            secondary = self._llm_classify_multi(text, primary, _safety_intents, addiction_type)
            if secondary is not None:          # None = LLM failed → fall through to patterns
                return primary, secondary

        # ── Pattern-based fallback (Ollama unavailable or LLM call failed) ─
        text_lower = text.lower().strip()
        secondary: List[str] = []
        seen: set = {primary}

        for intent, patterns in self.priority_patterns.items():
            if intent in seen or intent in _safety_intents:
                continue
            if any(p in text_lower for p in patterns):
                secondary.append(intent)
                seen.add(intent)
                if len(secondary) >= 3:
                    return primary, secondary

        for pattern, tag in self.pattern_tag_map.items():
            if tag in seen or tag in _safety_intents:
                continue
            if pattern in text_lower:
                secondary.append(tag)
                seen.add(tag)
                if len(secondary) >= 3:
                    return primary, secondary

        return primary, secondary

    def _llm_classify(self, text: str, addiction_type: Optional[str] = None) -> Optional[str]:
        try:
            tags = list(self.intents_map.keys()) + ["medication_request", "rag_query", "venting"]
            prompt = (
                f"Classify this message into ONE tag from: {', '.join(tags[:20])}\n"
                f"Use 'venting' for messages expressing overwhelm, exhaustion, emotional fatigue, "
                f"frustration, or burnout — even when phrased implicitly (e.g. 'this is so hard', "
                f"'I can't do this anymore', 'I give up').\n"
                f"If unsure, return 'rag_query'\n"
                f"Message: \"{text}\"\n"
                f"Reply with ONLY the tag, nothing else."
            )
            response = ollama.generate(model="qwen2.5:7b-instruct", prompt=prompt, stream=False)
            tag = response["response"].strip().lower().strip('"\'')
            valid_tags = set(self.intents_map.keys()) | {"medication_request", "rag_query"}
            return tag if tag in valid_tags else None
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return None

    def _llm_classify_multi(
        self,
        text: str,
        primary: str,
        safety_intents: set,
        addiction_type: Optional[str] = None,
    ) -> Optional[List[str]]:
        """
        Ask the LLM to identify ALL secondary intents present in the message.

        Returns a list of secondary intent tags (excluding primary and safety intents),
        capped at 3. Returns None if the LLM call fails (caller falls back to patterns).

        Using a single LLM call means synonyms, paraphrasing, and contextual meaning
        are all understood — e.g. "wiped out" → behaviour_fatigue, "zonked" → behaviour_sleep,
        "fancy a flutter" → addiction_gambling.
        """
        try:
            # Build a focused tag list: exclude safety intents and primary already found
            all_tags = (
                list(self.intents_map.keys())
                + ["medication_request", "rag_query", "venting",
                   "behaviour_fatigue", "behaviour_sleep", "behaviour_eating",
                   "behaviour_isolation"]
            )
            candidate_tags = [
                t for t in all_tags
                if t != primary and t not in safety_intents
            ]
            # De-duplicate while preserving order
            seen_tags: set = set()
            unique_candidates: List[str] = []
            for t in candidate_tags:
                if t not in seen_tags:
                    seen_tags.add(t)
                    unique_candidates.append(t)

            addiction_hint = (
                f"The patient's registered addiction is '{addiction_type}'. "
                if addiction_type else ""
            )

            prompt = (
                f"You are a clinical intent classifier for an addiction support chatbot.\n"
                f"{addiction_hint}"
                f"The primary intent '{primary}' has already been identified.\n\n"
                f"Identify ALL additional concerns present in this message.\n"
                f"Consider synonyms, informal language, paraphrasing, and implied meaning.\n"
                f"Examples:\n"
                f"  'wiped out' → behaviour_fatigue\n"
                f"  'tossing and turning' → behaviour_sleep\n"
                f"  'fancy a flutter' → addiction_gambling\n"
                f"  'doom scrolling' → addiction_social_media\n"
                f"  'hitting the bottle' → addiction_alcohol\n\n"
                f"Choose ONLY from these tags (comma-separated, no explanations, max 3):\n"
                f"{', '.join(unique_candidates[:40])}\n\n"
                f"If no additional concerns are present, reply with: none\n\n"
                f"Message: \"{text}\"\n"
                f"Additional tags:"
            )

            response = ollama.generate(model="qwen2.5:7b-instruct", prompt=prompt, stream=False)
            raw = response["response"].strip().lower()

            if raw in ("none", "none.", "", "-", "n/a"):
                return []

            valid_tags = set(self.intents_map.keys()) | {
                "medication_request", "rag_query", "venting",
                "behaviour_fatigue",
            }
            secondary: List[str] = []
            seen: set = {primary} | safety_intents
            for token in re.split(r"[,\n]+", raw):
                tag = token.strip().strip('"\'').strip()
                if tag and tag in valid_tags and tag not in seen:
                    secondary.append(tag)
                    seen.add(tag)
                if len(secondary) >= 3:
                    break

            logger.debug(f"LLM multi-label secondary: {secondary}")
            return secondary

        except Exception as e:
            logger.warning(f"LLM multi-label classification failed: {e}")
            return None   # signals caller to fall back to pattern scan

    def _pattern_classify_fallback(self, text_lower: str, addiction_type: Optional[str] = None) -> str:
        for intent, patterns in self.priority_patterns.items():
            if any(p in text_lower for p in patterns):
                return intent
        if any(p in text_lower for p in ["feel like a burden", "feel like i'm dragging everyone"]):
            return "mood_guilty"
        # Implicit emotional distress — overwhelm, burnout, fatigue (no explicit label needed)
        _venting_keywords = [
            "so hard", "too hard", "can't do this", "can't cope", "can't keep going",
            "i give up", "i'm done", "i'm exhausted", "worn out", "burned out", "burnt out",
            "falling apart", "breaking down", "at my limit", "breaking point",
            "too much", "i can't take", "need to vent", "just want to vent",
            "so tired of", "drained", "running on empty", "running on fumes",
            "can't keep up", "can't handle", "can't get through",
            "don't know how much more", "i'm overwhelmed",
        ]
        if any(p in text_lower for p in _venting_keywords):
            return "venting"
        # Generic craving language — route to patient's primary addiction intent if known
        if addiction_type and any(t in text_lower for t in self._GENERIC_CRAVING_TERMS):
            _norm = addiction_type.lower().strip().replace(" ", "_").replace("-", "_")
            _primary = self._ADDICTION_TYPE_TO_INTENT.get(_norm)
            if _primary:
                return _primary
        if any(p in text_lower for p in ["work stress", "boss", "coworker", "job"]):
            return "trigger_stress"
        if any(p in text_lower for p in ["relationship", "partner", "girlfriend", "boyfriend", "spouse"]):
            return "trigger_relationship"
        if any(p in text_lower for p in ["money", "financial", "bills", "debt", "afford"]):
            return "trigger_financial"
        if any(p in text_lower for p in ["lost", "death", "died", "grief"]):
            return "trigger_grief"
        if any(p in text_lower for p in ["exercise", "physical", "body", "fitness"]):
            return "behaviour_exercise"
        return "rag_query"

    def get_intent_metadata(self, intent: str) -> Dict:
        severity_map = {
            "crisis_suicidal": "critical", "crisis_abuse": "critical",
            "behaviour_self_harm": "high", "severe_distress": "high",
            "psychosis_indicator": "high", "trigger_trauma": "high",
            "relapse_disclosure": "medium",
            "addiction_drugs": "high", "addiction_gaming": "high",
            "addiction_nicotine": "high", "addiction_gambling": "high",
            "addiction_social_media": "medium",
            "venting": "medium",
        }
        category_map = {
            "crisis_suicidal": "safety", "crisis_abuse": "safety",
            "behaviour_self_harm": "safety", "severe_distress": "mental_health",
            "psychosis_indicator": "mental_health", "trigger_trauma": "mental_health",
            "mood_sad": "mood", "mood_anxious": "mood", "mood_angry": "mood",
            "mood_lonely": "mood", "mood_guilty": "mood",
            "venting": "mood",
            "relapse_disclosure": "behavioral",
            "addiction_drugs": "behavioral", "addiction_gaming": "behavioral",
            "addiction_nicotine": "behavioral", "addiction_gambling": "behavioral",
            "addiction_social_media": "behavioral",
            "behaviour_sleep": "behavioral",
            "behaviour_eating": "behavioral", "medication_request": "safety",
            "greeting": "social", "farewell": "social", "gratitude": "social",
            "rag_query": "information",
        }
        _all_addiction_intents = {
            "addiction_drugs", "addiction_gaming", "addiction_nicotine",
            "addiction_gambling", "addiction_social_media", "relapse_disclosure",
        }
        return {
            "intent": intent,
            "severity": severity_map.get(intent, "medium"),
            "category": category_map.get(intent, "other"),
            "requires_resources": intent in {"crisis_suicidal", "crisis_abuse", "behaviour_self_harm"},
            "requires_follow_up": intent in _all_addiction_intents | {"trigger_trauma", "behaviour_self_harm"},
        }


# ════════════════════════════════════════════════════════════════════════════
# §2  RESPONSE GENERATOR
#     Template-based with context personalisation and 5-layer enforcement
# ════════════════════════════════════════════════════════════════════════════

RESPONSE_TEMPLATES = {
    # ── Crisis (Critical Safety) ──────────────────────────────────────────
    "crisis_suicidal": {
        "type": "crisis", "severity": "critical", "show_resources": True,
        "base": (
            "I'm really sorry that you're going through something so painful right now. "
            "What you're describing sounds very difficult, and you deserve support.\n\n"
            "You don't have to face this alone. If you can, please consider reaching out "
            "to someone right now who can help keep you safe.\n\n"
            "Immediate support options:\n"
            "• Emergency services: 112 / 911 / 999\n"
            "• Crisis Text Line: Text HOME to 741741\n"
            "• International crisis centres: https://www.iasp.info/resources/Crisis_Centres/\n\n"
            "If you'd like, you can tell me what has been weighing on you."
        ),
    },
    "crisis_abuse": {
        "type": "crisis", "severity": "critical", "show_resources": True,
        "base": (
            "Your safety is the most important thing right now. I'm here to listen.\n\n"
            "If you are in immediate danger, please call emergency services immediately:\n"
            "• Emergency Services: 911 / 999 / 112\n"
            "• National Domestic Violence Hotline (US): 1-800-799-7233\n"
            "• Refuge (UK): 0808 2000 247\n"
            "• International resources: https://www.hotpeachpages.net/\n\n"
            "You are not alone. This is not your fault. If you feel safe to do so, "
            "please tell me more about what's happening."
        ),
    },
    "behaviour_self_harm": {
        "type": "crisis", "severity": "high", "show_resources": True,
        "base": (
            "Thank you for sharing something so difficult. It sounds like you may be "
            "coping with a lot of emotional pain right now.\n\n"
            "Many people who experience urges to harm themselves are trying to manage "
            "overwhelming feelings. You deserve understanding and support.\n\n"
            "If you can, please consider reaching out today:\n"
            "• Emergency services: 112 / 911 / 999\n"
            "• Crisis Text Line: Text HOME to 741741\n"
            "• Local mental health professional or helpline\n\n"
            "If you feel comfortable, tell me what has been happening recently."
        ),
    },
    # ── Trauma & Clinical ─────────────────────────────────────────────────
    "trigger_trauma": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "Thank you for trusting me with something so personal and painful. "
            "What you have been through sounds very difficult, "
            "and it takes real courage to speak about it.\n\n"
            "Trauma affects people in many ways, and your feelings are completely valid. "
            "A trauma-informed therapist can offer support specifically designed for what you're experiencing.\n\n"
            "I am here to listen if you would like to share more."
        ),
    },
    "addiction_drugs": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "Thank you for having the courage to share this with me. What you're going through is real "
            "and serious.\n\n"
            "Cravings and urges to use are powerful, and the fact that you're aware of them and trying "
            "to resist is a sign of real strength.\n\n"
            "Many people have successfully managed substance use with proper support:\n"
            "• Addiction counselor or therapist specialising in substance abuse\n"
            "• Support groups like AA, NA, or SMART Recovery\n"
            "• Medical treatment options (medication-assisted therapy)\n\n"
            "You don't have to do this alone."
        ),
    },
    "relapse_disclosure": {
        "type": "clinical", "severity": "medium", "show_resources": False,
        "base": (
            "Thank you for telling me this honestly. A slip can feel heavy, but it does not erase your effort "
            "or define your recovery.\n\n"
            "Relapse is often part of the recovery process, not proof that recovery is impossible. "
            "What matters most right now is understanding what happened with care, not judgment.\n\n"
            "If you're open to it, we can look at what was happening just before this and what support would "
            "help you most in the next 24 hours."
        ),
    },
    "addiction_gaming": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "Thank you for being honest about this urge.\n\n"
            "Gaming can become a powerful escape — especially when other stressors feel unmanageable. "
            "The urge you're feeling is real, and it deserves attention rather than judgment.\n\n"
            "Some steps that can help:\n"
            "\u2022 Speak with a therapist who specialises in behavioural addictions\n"
            "\u2022 Set a clear time boundary before you start (e.g. 30 minutes with a timer)\n"
            "\u2022 Identify what emotion or need is driving the urge right now\n\n"
            "You're showing real self-awareness by recognising this pattern."
        ),
    },
    "addiction_nicotine": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "Thank you for sharing this.\n\n"
            "Nicotine cravings are intensely physical — your brain is genuinely asking for something "
            "it's been conditioned to expect. The craving usually peaks within 3–5 minutes, then passes, "
            "even when it feels unbearable.\n\n"
            "What can help right now:\n"
            "• Delay 5 minutes and do something with your hands\n"
            "• Nicotine replacement (patches, gum, lozenges) can take the edge off acutely\n"
            "• Your GP can discuss Champix/Chantix or Zyban if appropriate\n"
            "• Apps like Smoke Free or QuitNow track your progress and support streaks\n\n"
            "You've resisted before. You can resist this one too."
        ),
    },
    "addiction_social_media": {
        "type": "clinical", "severity": "medium", "show_resources": True,
        "base": (
            "Thank you for recognising this pattern — that awareness is real progress.\n\n"
            "Social media is deliberately engineered to be compulsive: infinite scroll, variable reward, "
            "dopamine hits from likes and notifications. The urge you're feeling is partly by design, "
            "not a personal weakness.\n\n"
            "Some things that can help:\n"
            "• Set a screen time limit using your phone's built-in tools (iOS Screen Time / Android Digital Wellbeing)\n"
            "• Delete the apps and use the browser version instead — friction reduces impulse use\n"
            "• Replace the first 30 minutes of each day with something offline\n"
            "• A therapist specialising in digital wellness can address the underlying need\n\n"
            "What are you hoping to feel or find when you open the app right now?"
        ),
    },
    "addiction_gambling": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "Thank you for being open about this. Problem gambling is widely misunderstood "
            "but it is a recognised condition with effective treatment.\n\n"
            "The urge to gamble often spikes during stress, boredom, or after a loss "
            "(the 'chasing' impulse). Recognising where you are in that cycle matters.\n\n"
            "Support that genuinely helps:\n"
            "• Gamblers Anonymous: www.gamblersanonymous.org\n"
            "• National Gambling Helpline (UK): 0808 8020 133\n"
            "• National Council on Problem Gambling (US): 1-800-522-4700\n"
            "• Cognitive Behavioural Therapy is highly effective — speak to your GP\n\n"
            "You don't have to act on this urge. What is driving it today?"
        ),
    },
    "severe_distress": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "I hear you, and I want you to know that what you are feeling matters deeply. "
            "Feelings of hopelessness or emptiness can be overwhelming, "
            "and you do not have to carry this alone.\n\n"
            "Please consider reaching out to someone who can support you right now:\n"
            "• Emergency services: 112 / 911 / 999\n"
            "• Crisis Text Line: Text HOME to 741741\n\n"
            "You deserve support. If you feel comfortable, I am here to listen."
        ),
    },
    "psychosis_indicator": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "Thank you for sharing what you are experiencing. "
            "What you are going through sounds very distressing, "
            "and it is important that you speak with a qualified mental health professional as soon as possible.\n\n"
            "Please reach out for support now:\n"
            "• Emergency services: 112 / 911 / 999\n"
            "• Your treating psychiatrist or mental health team\n"
            "• Crisis Text Line: Text HOME to 741741"
        ),
    },
    # ── Mood (Medium severity) ────────────────────────────────────────────
    "mood_sad": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "I hear you. Sadness can feel really heavy and all-consuming sometimes.\n\n"
            "It's okay to feel down, and what you're experiencing is valid. "
            "Many people go through periods like this. "
            "The good news is that with support and time, things can improve.\n\n"
            "Tell me a bit more about what's been going on."
        ),
    },
    "mood_anxious": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Anxiety can feel really overwhelming. I understand.\n\n"
            "What you're experiencing is your mind trying to protect you, "
            "but sometimes it goes into overdrive. You're not alone in this.\n\n"
            "Try one small thing that's worked for you before — even just taking a few deep breaths."
        ),
    },
    "mood_angry": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Anger is a powerful emotion, and it sounds like you're dealing with some real frustrations.\n\n"
            "Anger often points to something that matters to you. "
            "When anger comes up, try naming what's underneath it — maybe hurt, frustration, or feeling unheard."
        ),
    },
    "mood_lonely": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Loneliness can feel really isolating. Thank you for sharing that with me.\n\n"
            "Human connection is fundamental, and what you're feeling is real and important. "
            "Even though you feel alone right now, reaching out like this is a step in the right direction."
        ),
    },
    "mood_guilty": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Guilt can be really powerful and painful.\n\n"
            "Sometimes guilt is telling us something important about our values. "
            "Other times, we're being too hard on ourselves. "
            "Self-compassion matters — try treating yourself like you would a good friend."
        ),
    },
    # ── Behaviour ────────────────────────────────────────────────────────
    "behaviour_sleep": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Sleep problems are really challenging and can affect everything else in your life.\n\n"
            "You're not alone — many people struggle with this. "
            "Start with one small change: a consistent bedtime, a phone-free hour before bed, or a calming routine."
        ),
    },
    "behaviour_eating": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Eating and our relationship with food can be really connected to how we're feeling emotionally.\n\n"
            "Be gentle with yourself. If you're struggling, a therapist or dietitian specialising in "
            "emotional eating can help. You deserve support."
        ),
    },
    # ── Trigger & behaviour intents (tailored responses in _get_addiction_aware_base) ──
    "trigger_stress": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": "Stress can be a powerful trigger. I'm here to talk through what's driving it.",
    },
    "trigger_relationship": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": "Relationship difficulties are genuinely hard. I'm here to listen — let's talk through it.",
    },
    "trigger_financial": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": "Financial pressure is real and stressful. You don't have to carry this alone.",
    },
    "trigger_grief": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": "Grief is one of the most painful experiences. I'm truly sorry for your loss.",
    },
    "behaviour_exercise": {
        "type": "supportive", "severity": "low", "show_resources": False,
        "base": "Physical activity is a powerful tool for wellbeing. I'm glad you're thinking about it.",
    },
    # ── Venting / Implicit Distress ────────────────────────────────────────
    # Overwhelm, emotional exhaustion, burnout, frustration — no advice, no solutions.
    # Empathy first + gentle emotional regulation suggestion with video.
    "venting": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "That sounds really hard, and it makes complete sense that you're feeling this way.\n\n"
            "You don't have to have the answers right now — just being here and saying it out loud takes courage.\n\n"
            "When everything feels like too much, a short breathing or grounding exercise can help bring things "
            "down just a little. I've shared one below if you'd like to try it."
        ),
    },
    # ── Small talk ───────────────────────────────────────────────────────
    "greeting":  {"type": "social", "severity": "low", "show_resources": False, "base": "Hello! I'm here to listen and support you. What's on your mind today?"},
    "farewell":  {"type": "social", "severity": "low", "show_resources": False, "base": "Thank you for talking with me. Please take care of yourself. Remember, if you need support, I'm always here."},
    "gratitude": {"type": "social", "severity": "low", "show_resources": False, "base": "I'm glad I could help. That's what I'm here for. Feel free to reach out anytime you need someone to talk to."},
    # ── Safety block ──────────────────────────────────────────────────────
    "medication_request": {
        "type": "safety", "severity": "medium", "show_resources": False,
        "base": (
            "I'm not able to recommend medications, dosages, or prescriptions.\n\n"
            "Medication decisions require assessment by a licensed healthcare professional "
            "who can evaluate your symptoms, medical history, and possible risks.\n\n"
            "For medication guidance, please consult:\n"
            "• Your treating psychiatrist or physician\n"
            "• A licensed mental health clinic\n"
            "• Emergency services if symptoms feel urgent"
        ),
    },
}


# ════════════════════════════════════════════════════════════════════════════
# §2a RESPONSE ROUTER
#     Loaded once at startup from the DB response_routing table.
#     Provides fast (patient_addiction, intent) → routing strategy lookup.
#     Falls back to code-based logic if no DB row exists.
# ════════════════════════════════════════════════════════════════════════════

class ResponseRouter:
    """
    DB-driven routing matrix: (patient_addiction × detected_intent) → strategy.

    relationship values:
      primary       — patient craving their own primary addiction
      comorbidity   — patient craving a KNOWN secondary addiction (extra high risk)
      cross_high    — novel cross-craving: clinically high risk
      cross_medium  — novel cross-craving: moderate risk
            sleep | mood | trigger | behaviour | distress | relapse — non-addiction intents
    """

    # Which intent represents each addiction_type's PRIMARY craving
    _PRIMARY_INTENT_MAP: Dict[str, str] = {
        "alcohol":      "addiction_drugs",
        "drugs":        "addiction_drugs",
        "gaming":       "addiction_gaming",
        "social_media": "addiction_social_media",
        "nicotine":     "addiction_nicotine",
        "smoking":      "addiction_nicotine",
        "gambling":     "addiction_gambling",
        "work":         "addiction_work",
    }

    _ALL_ADDICTION_INTENTS: frozenset = frozenset({
        "addiction_drugs", "addiction_gaming", "addiction_social_media",
        "addiction_nicotine", "addiction_gambling", "addiction_work",
    })

    # Which cross pairs are inherently high-risk (used as code fallback)
    _HIGH_RISK_CROSS: frozenset = frozenset({
        ("gaming",       "addiction_drugs"),
        ("social_media", "addiction_drugs"),
        ("gambling",     "addiction_drugs"),
        ("nicotine",     "addiction_drugs"),
        ("alcohol",      "addiction_gambling"),
        ("drugs",        "addiction_gambling"),
    })

    def __init__(self, routing_rows: Optional[List[dict]] = None):
        # Index: (patient_addiction, detected_intent) → row
        self._index: Dict[tuple, dict] = {}
        if routing_rows:
            for row in routing_rows:
                key = (row["patient_addiction"], row["detected_intent"])
                self._index[key] = row
        logger.info(f"ResponseRouter: loaded {len(self._index)} routing rules from DB")

    def lookup(
        self,
        primary_addiction: str,
        intent: str,
        addictions: Optional[List[dict]] = None,
    ) -> dict:
        """
        Return routing dict for (patient_addiction, intent).

        Priority:
          1. Comorbidity detection  — patient has this as a KNOWN secondary addiction
          2. DB row                 — generic routing rule for this (addiction, intent) pair
          3. Code-derived fallback  — cross_high / cross_medium / generic

        Comorbidity takes priority over the generic DB cross-addiction row because the
        DB matrix is patient-agnostic; individual comorbidity status is patient-specific.
        """
        _norm = primary_addiction.lower().strip().replace(" ", "_").replace("-", "_")

        # 1. Comorbidity detection (patient-specific — must win over generic DB row)
        if addictions and intent in self._ALL_ADDICTION_INTENTS:
            secondary_types = [
                a["addiction_type"].lower().strip().replace(" ", "_")
                for a in addictions if not a.get("is_primary", True)
            ]
            for sec_type in secondary_types:
                sec_primary_intent = self._PRIMARY_INTENT_MAP.get(sec_type)
                if sec_primary_intent == intent:
                    sec_severity = (
                        a.get("severity", "high")
                        for a in addictions
                        if a["addiction_type"].lower().replace(" ", "_") == sec_type
                    )
                    return {
                        "relationship": "comorbidity",
                        "severity_override": next(sec_severity, "high"),
                        "video_key": self._default_video_key(intent),
                        "requires_escalation": True,
                        "source": "comorbidity",
                    }

        # 2. DB lookup (generic matrix — patient-agnostic)
        db_row = self._index.get((_norm, intent))
        if db_row:
            return {
                "relationship": db_row["relationship"],
                "severity_override": db_row.get("severity_override"),
                "video_key": db_row.get("video_key"),
                "requires_escalation": db_row.get("requires_escalation", False),
                "source": "db",
            }

        # 3. Code-derived: primary / cross-addiction fallback (no DB rows needed)
        primary_intent = self._PRIMARY_INTENT_MAP.get(_norm)
        if primary_intent and intent in self._ALL_ADDICTION_INTENTS:
            if intent == primary_intent:
                # PRIMARY craving — patient expressing urge for their own registered addiction
                return {
                    "relationship": "primary",
                    "severity_override": "high",
                    "video_key": self._default_video_key(intent),
                    "requires_escalation": False,
                    "source": "code_fallback",
                }
            # CROSS craving — patient reaching toward a different addictive behaviour
            is_high = (_norm, intent) in self._HIGH_RISK_CROSS
            return {
                "relationship": "cross_high" if is_high else "cross_medium",
                "severity_override": "high" if is_high else "medium",
                "video_key": self._default_video_key(intent),
                "requires_escalation": is_high,
                "source": "code_fallback",
            }

        return {
            "relationship": "generic",
            "severity_override": None,
            "video_key": None,
            "requires_escalation": False,
            "source": "generic",
        }

    def primary_intent_for(self, addiction_type: str) -> Optional[str]:
        _norm = addiction_type.lower().strip().replace(" ", "_").replace("-", "_")
        return self._PRIMARY_INTENT_MAP.get(_norm)

    @staticmethod
    def _default_video_key(intent: str) -> Optional[str]:
        _map = {
            "addiction_drugs":        "addiction_drugs",
            "addiction_gaming":       "addiction_gaming",
            "addiction_social_media": "addiction_social_media",
            "addiction_nicotine":     "addiction_nicotine",
            "addiction_gambling":     "addiction_gambling",
        }
        return _map.get(intent)


# Singleton router loaded once at process startup.
# chatbot_engine.py calls _init_response_router(rows) after loading the DB table.
_response_router: Optional[ResponseRouter] = None


def _init_response_router(routing_rows: Optional[List[dict]] = None) -> ResponseRouter:
    global _response_router
    _response_router = ResponseRouter(routing_rows or [])
    return _response_router


def get_response_router() -> ResponseRouter:
    global _response_router
    if _response_router is None:
        _response_router = ResponseRouter([])
    return _response_router


class ResponseGenerator:
    """Generates empathetic, context-aware responses with 5-layer compliance."""

    def __init__(self, rag_handler=None, intents_path: str = "intents.json"):
        self.rag_handler = rag_handler
        self.response_templates = RESPONSE_TEMPLATES
        self._intent_responses: Dict[str, List[str]] = self._load_intent_responses(intents_path)

    def _load_intent_responses(self, path: str) -> Dict[str, List[str]]:
        """Load the response pools from intents.json — used when no specialized handler fires."""
        try:
            with open(path) as f:
                raw = re.sub(r"//.*", "", f.read())
                data = json.loads(raw)
                return {
                    i["tag"]: i["responses"]
                    for i in data.get("intents", [])
                    if i.get("responses")
                }
        except Exception as e:
            logger.warning(f"ResponseGenerator: could not load intent responses from {path}: {e}")
            return {}

    def generate(
        self,
        intent: str,
        user_message: str,
        context_vector=None,
        additional_context: str = None,
        addiction_type: Optional[str] = None,
        addictions: Optional[List[dict]] = None,
        system_prompt: str = None,
        profile_flags: Optional[Dict] = None,
    ) -> Tuple[str, Dict]:
        """
        Generate response for the given intent with context awareness.

        addictions — ordered list from patient_addictions table (primary first).
                     If provided, enables comorbidity detection and DB routing.
        addiction_type — single-string fallback (backward compat).

        Returns (response_text, metadata_dict).
        """
        # Resolve primary addiction type from list if available
        if addictions and not addiction_type:
            primary = next((a for a in addictions if a.get("is_primary")), addictions[0] if addictions else None)
            if primary:
                addiction_type = primary["addiction_type"]

        template = self.response_templates.get(intent)

        if template:
            response = self._generate_from_template(
                intent, template, user_message, context_vector, addiction_type, addictions
            )
        else:
            response = self._generate_fallback(intent, user_message, context_vector)

        # Fetch routing metadata so callers can read requires_escalation / video_key
        routing = get_response_router().lookup(
            primary_addiction=addiction_type or "",
            intent=intent,
            addictions=addictions,
        ) if addiction_type else {"relationship": "generic", "severity_override": None, "video_key": None, "requires_escalation": False, "source": "no_addiction"}

        # Post-process template/pool responses for patients with psychosis/bipolar history.
        # LLM-generated responses are controlled via the system prompt directive in
        # CLINICAL_SAFETY_OVERRIDES; template responses need this guard because they are
        # pre-written static strings that can contain metaphors.
        if profile_flags and profile_flags.get("bipolar_or_psychosis_history"):
            response = self._psychosis_language_guard(response)

        response = self._enforce_5layer_rules(response, intent)

        metadata = {
            "intent": intent,
            "severity": routing.get("severity_override") or (template["severity"] if template else "medium"),
            "type": template["type"] if template else "unknown",
            "show_resources": template.get("show_resources", False) if template else False,
            "generated_at": datetime.now().isoformat(),
            "routing": routing,  # full routing info for chatbot_engine video selection
            "show_feedback": intent in self._INTERVENTION_INTENTS,
        }
        return response, metadata

    # ── Psychosis/bipolar history language guard ──────────────────────────
    # Template and pool responses are pre-written static strings and never see the
    # LLM system prompt. This guard enforces the clinical language rules for patients
    # with a bipolar or psychosis history: no metaphors, literal and concrete only.

    # Direct substitution map — ordered so longer phrases match before substrings.
    _PSYCHOSIS_METAPHOR_MAP: List[Tuple[str, str]] = [
        # Craving metaphors
        ("the craving is a wave",           "the craving is temporary — it will pass"),
        ("craving is a wave",               "the craving is temporary — it will pass"),
        ("cravings are like waves",         "cravings are temporary — they pass"),
        ("ride the wave",                   "wait for the craving to pass"),
        ("ride not fight",                  "wait for it to pass"),
        ("urge surfing",                    "waiting for the urge to pass"),
        ("surf the urge",                   "wait for the urge to pass"),
        ("the pull",                        "the urge"),
        # Grief / emotion metaphors
        ("grief is love with nowhere to go", "grief is a painful feeling"),
        ("love with nowhere to go",          "a painful feeling"),
        ("waves of grief",                  "episodes of grief"),
        ("sit with",                        "notice"),
        ("sitting with",                    "noticing"),
        # Brain/biology metaphors
        ("your brain is rewiring itself",   "your body is adjusting"),
        ("brain is rewiring",               "body is adjusting"),
        ("rewiring",                        "adjusting"),
        ("neurological stress spike",       "physical stress response"),
        ("mesolimbic",                      "reward-response"),
        ("chemical shortcut",               "a substance"),
        # Abstract/figurative phrases
        ("the next 15 minutes matter more than the next 15 months",
                                            "the next 15 minutes are important"),
        ("where choice lives",              ""),
        ("stay with me",                    "I am here."),
    ]

    def _psychosis_language_guard(self, response: str) -> str:
        """
        Post-process a template or pool response for patients with psychosis/bipolar history.

        Rules applied:
          1. Replace known metaphorical phrases with literal equivalents.
          2. Remove any sentence that still contains a simile marker
             ('like a', 'as if', 'as though', 'just like') after substitutions.
          3. Strip any trailing sentence that ends with a '?' — open-ended prompts
             are too ambiguous for this population.
          4. Ensure the response is not left empty.
        """
        import re

        text = response

        # Step 1 — Direct phrase substitution (case-insensitive match, preserve rest)
        for metaphor, literal in self._PSYCHOSIS_METAPHOR_MAP:
            pattern = re.compile(re.escape(metaphor), re.IGNORECASE)
            replacement = literal if literal else ""
            text = pattern.sub(replacement, text)

        # Step 2 — Remove sentences containing residual simile markers
        # Split into sentence-like chunks preserving paragraph breaks
        paragraphs = text.split("\n")
        cleaned_paragraphs = []
        _simile_re = re.compile(
            r"\b(like a|like an|as if|as though|just like|feels like a|feels as)\b",
            re.IGNORECASE,
        )
        for para in paragraphs:
            # Split paragraph into sentences on '.', '!', preserving the delimiter
            sentences = re.split(r"(?<=[.!])\s+", para.strip())
            kept = [s for s in sentences if s and not _simile_re.search(s)]
            cleaned_paragraphs.append(" ".join(kept))

        text = "\n".join(p for p in cleaned_paragraphs if p.strip())

        # Step 3 — Strip trailing question (open-ended prompts are not appropriate)
        lines = text.split("\n")
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip():
                if lines[i].strip().endswith("?"):
                    lines[i] = ""
                break
        text = "\n".join(lines).strip()

        # Step 4 — Guard against empty result
        if not text.strip():
            text = "I hear you. Take three slow breaths now."

        return text

    # ── Layer 5 agency-close map ─────────────────────────────────────────
    # Per Slide 4 Layer 5: every response must end with a tool, practice, or opt-out.
    # Never a question. Applied after all response generation paths.
    _AGENCY_CLOSE: Dict[str, str] = {
        # Mood
        "mood_sad":          (
            "If you would like, try one small thing for yourself right now — "
            "a glass of water, two minutes outside, or simply placing your hand on your chest "
            "and taking one slow breath."
        ),
        "mood_anxious":      (
            "Try this now: breathe in for 4 counts, hold for 4, breathe out for 6. "
            "Repeat twice. Notice what shifts."
        ),
        "mood_angry":        (
            "Before responding to anyone, try stepping away for 5 minutes. "
            "Press your feet to the floor and take three slow breaths. That gap is where choice lives."
        ),
        "mood_lonely":       "You don't have to respond to anything right now. I'm here whenever you're ready.",
        "mood_guilty":       "You don't have to have it all figured out. I'm here whenever you want to keep talking.",
        "mood_happy":        "Hold onto that feeling. I'm here whenever you'd like to talk.",
        # Venting / distress
        "venting":           "You don't have to respond or explain anything. I'm here.",
        "severe_distress":   (
            "Try pressing your feet firmly to the floor right now. "
            "Notice the weight. Take one slow breath. I'm here."
        ),
        # Behaviour
        "behaviour_sleep":   (
            "One step tonight: try charging your phone outside your bedroom — just for one night — "
            "and notice the difference in the morning."
        ),
        "behaviour_eating":  "Be gentle with yourself today. No pressure to change anything right now.",
        "behaviour_isolation": "You don't have to reach out to anyone today. Just noticing the feeling is enough for now.",
        "behaviour_aggression": (
            "If you feel a wave building, try leaving the situation for 5 minutes before you respond. "
            "That gap is where you get to choose."
        ),
        "behaviour_exercise": (
            "One step: a 10-minute walk today, with your phone in your pocket rather than in your hand. That counts."
        ),
        # Triggers
        "trigger_stress":    (
            "Right now, try the 5-4-3-2-1 technique: name 5 things you can see, 4 you can touch, "
            "3 you can hear. It takes 90 seconds and slows your nervous system down."
        ),
        "trigger_grief":     (
            "Place your hand on your chest. Take one slow breath. "
            "The next few minutes are what matter most right now."
        ),
        "trigger_trauma":    "If you'd like to share more, I'm here. Take all the time you need — there is no pressure.",
        "trigger_relationship": "You don't have to resolve anything right now. I'm here to listen.",
        "trigger_financial": "One step at a time. You do not have to solve all of this today.",
        # Addiction cravings
        "addiction_drugs":       (
            "The urge will peak and pass — usually within 15 to 30 minutes. "
            "Try to delay, breathe, and drink a glass of water before deciding anything."
        ),
        "addiction_gaming":      (
            "Try setting a 15-minute timer before opening anything. Give yourself that gap first."
        ),
        "addiction_nicotine":    (
            "Try the 4D method right now: Delay 5 minutes. Deep breath. Drink water. "
            "Do something with your hands. The craving will peak and pass."
        ),
        "addiction_gambling":    (
            "If the urge is strong, call before you act:\n"
            "• UK: 0808 8020 133  •  US: 1-800-522-4700\n"
            "The call can happen now. Acting on the urge can wait."
        ),
        "addiction_social_media": (
            "Put your phone in another room for 20 minutes. Just 20 minutes. See what shifts."
        ),
        "addiction_work":        (
            "One small boundary: close one tab or task you don't need right now. "
            "Small limits matter."
        ),
        "relapse_disclosure":    (
            "Take your time. You don't need answers right now — "
            "saying it out loud is already the hard part."
        ),
        # Safety-adjacent
        "behaviour_self_harm":   (
            "Please reach out to someone who can keep you safe right now — "
            "you deserve that support."
        ),
        # Social / general
        "greeting":          "Take your time — I'm here whenever you're ready.",
        "farewell":          "Take care of yourself. I'm here whenever you need to talk.",
        "gratitude":         "I'm glad it helped. I'm here whenever you need me.",
        "unclear":           "Take your time — I'm listening.",
        "rag_query":         "Take your time — I'm here whenever you're ready to share more.",
    }

    # Intents whose responses already carry explicit safety directives —
    # appending a second agency close would dilute the critical message.
    _SKIP_AGENCY_INTENTS: frozenset = frozenset({
        "crisis_suicidal", "crisis_abuse", "medication_request", "psychosis_indicator",
    })

    # Intents where an active coping tool was delivered — eligible for binary feedback.
    # Layer 5, Rule 1: all these responses receive a feedback nudge + 👍/👎 UI buttons.
    _INTERVENTION_INTENTS: frozenset = frozenset({
        "mood_sad", "mood_anxious", "mood_angry", "severe_distress",
        "behaviour_sleep", "behaviour_aggression", "behaviour_exercise",
        "trigger_stress", "trigger_grief",
        "addiction_drugs", "addiction_gaming", "addiction_nicotine",
        "addiction_gambling", "addiction_social_media", "addiction_work",
        "relapse_disclosure",
    })

    # Closing line appended after every intervention (Layer 5 Rule 1 — binary feedback).
    _FEEDBACK_NUDGE = "Did that help quiet the noise? Tap below when you're ready."

    def _enforce_5layer_rules(self, response_text: str, intent: str) -> str:
        """
        Layer 5 compliance: every response must end with a tool, practice, or opt-out.
        Never a question (Slide 4, Layer 5).

        Steps:
        1. Strip any trailing question line (any line ending with '?').
        2. If a question was stripped — or none was but the last content line is still a '?'
           (edge case) — append the intent-appropriate agency close.
        """
        lines = response_text.split('\n')
        stripped_question = False

        # Walk backwards to find the last non-empty line
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()
            if line:
                if line.endswith('?'):
                    lines[i] = ''
                    stripped_question = True
                break

        response_text = '\n'.join(lines).strip()

        if intent in self._SKIP_AGENCY_INTENTS:
            return response_text

        if stripped_question:
            agency = self._AGENCY_CLOSE.get(intent, "I'm here whenever you're ready to continue.")
            response_text = response_text.rstrip() + "\n\n" + agency

        # Binary feedback nudge — appended unconditionally for all active-coping interventions.
        # The frontend renders 👍/👎 buttons when show_feedback=True; this text frames them.
        if intent in self._INTERVENTION_INTENTS:
            response_text = response_text.rstrip() + "\n\n" + self._FEEDBACK_NUDGE

        return response_text.strip()

    def _generate_from_template(self, intent: str, template: Dict, user_message: str, context_vector=None, addiction_type: Optional[str] = None, addictions: Optional[List[dict]] = None) -> str:
        specialized = self._get_addiction_aware_base(intent, template, context_vector, addiction_type, addictions)
        # _get_addiction_aware_base returns None when no specialized handler matched;
        # fall back to the intents.json response pool, selected by risk level.
        if specialized is not None:
            base_response = specialized
        else:
            base_response = self._select_from_pool(intent, template, context_vector)
        if context_vector:
            personalization = self._build_personalization(intent, context_vector)
            if personalization:
                base_response = personalization + "\n\n" + base_response
        return base_response

    def _select_from_pool(self, intent: str, template: Dict, context_vector=None) -> str:
        """
        Pick from intents.json response pool with risk-level weighting.

        Risk weighting rationale:
          high/critical  — first 60 % of pool (assumed to be more clinically grounded phrasing)
          low/medium     — full pool (all responses are appropriate)

        Falls back to template["base"] if no pool exists for this intent.
        """
        pool = self._intent_responses.get(intent)
        if not pool:
            return template["base"]

        risk_level = "medium"
        if context_vector and hasattr(context_vector, "risk") and context_vector.risk:
            risk_level = (getattr(context_vector.risk, "risk_level", None) or "medium").lower()

        if risk_level in ("critical", "high") and len(pool) > 2:
            # Restrict to the first 60 % of responses (more serious / clinical phrasing).
            cutoff = max(2, int(len(pool) * 0.6))
            return random.choice(pool[:cutoff])

        return random.choice(pool)

    def _get_addiction_aware_base(self, intent: str, template: Dict, context_vector=None, addiction_type: Optional[str] = None, addictions: Optional[List[dict]] = None) -> str:
        """
        Return a clinically differentiated response for key intents.

        Four scenarios handled:
          PRIMARY      — patient expressing urge for their own primary addiction
          COMORBIDITY  — patient expressing urge for a KNOWN secondary addiction (high risk)
          CROSS        — patient expressing urge for a novel different addictive behaviour
          SLEEP/MOOD/TRIGGER/BEHAVIOUR — contextualised per addiction type
          SLEEP     — sleep advice tailored to the patient's specific addiction

        Clinical basis for cross-addiction responses: the same mesolimbic reward
        pathway underlies all addictive behaviours; when one is restricted, cravings
        for substitute behaviours frequently emerge (addiction transfer / cross-addiction).
        """
        if not addiction_type:
            if addictions:
                primary = next((a for a in addictions if a.get("is_primary")), addictions[0] if addictions else None)
                if primary:
                    addiction_type = primary["addiction_type"]
            elif context_vector and hasattr(context_vector, "onboarding") and context_vector.onboarding:
                addiction_type = context_vector.onboarding.addiction_type
                # Also try to get addictions list from context_vector
                if not addictions and hasattr(context_vector.onboarding, "addictions"):
                    addictions = context_vector.onboarding.addictions or []

        # Normalise: "Social Media" → "social_media", "Alcohol" → "alcohol", etc.
        addtype = (addiction_type or "").lower().strip().replace(" ", "_").replace("-", "_")

        # ── Use ResponseRouter for relationship classification ─────────────────
        router = get_response_router()
        routing = router.lookup(
            primary_addiction=addtype,
            intent=intent,
            addictions=addictions,
        )
        relationship = routing["relationship"]

        # ── Lookup tables ─────────────────────────────────────────────────────
        _ADDICTION_LABEL: Dict[str, str] = {
            "alcohol":      "alcohol",
            "drugs":        "substance use",
            "gaming":       "gaming",
            "social_media": "social media",
            "nicotine":     "nicotine / smoking",
            "smoking":      "smoking",
            "gambling":     "gambling",
        }
        _CRAVING_LABEL: Dict[str, str] = {
            "addiction_drugs":        "alcohol or substances",
            "addiction_gaming":       "gaming",
            "addiction_social_media": "social media",
            "addiction_nicotine":     "nicotine / smoking",
            "addiction_gambling":     "gambling",
        }

        _ALL_ADDICTION_INTENTS = frozenset(_CRAVING_LABEL.keys())
        primary_intent = router.primary_intent_for(addtype)
        is_primary     = relationship == "primary"
        is_comorbidity = relationship == "comorbidity"
        is_cross       = relationship in ("cross_high", "cross_medium")

        # ── RELAPSE DISCLOSURE responses (non-judgmental, no directives) ─────
        if intent == "relapse_disclosure":
            _RELAPSE: Dict[str, str] = {
                "alcohol": (
                    "Thank you for telling me you drank. That honesty matters.\n\n"
                    "A slip does not cancel your recovery — it is a signal that things were hard in that moment, "
                    "not a verdict on you.\n\n"
                    "We can slow this down together and understand what was happening before last night, "
                    "so this becomes information you can use rather than a reason to judge yourself."
                ),
                "drugs": (
                    "Thank you for sharing that you used again. Saying it out loud takes courage.\n\n"
                    "This does not erase your progress. Relapse can happen in recovery, and talking about it "
                    "openly is a protective step.\n\n"
                    "If you're willing, we can map what was happening before you used so we can understand "
                    "the pattern with compassion and clarity."
                ),
                "gaming": (
                    "Thank you for being direct about this slip.\n\n"
                    "Falling back into gaming patterns under stress is common and does not mean you've failed. "
                    "It means something in that moment needed attention.\n\n"
                    "We can look at what led up to it and what need gaming was meeting, without blame."
                ),
                "social_media": (
                    "Thank you for sharing this so openly.\n\n"
                    "A return to compulsive scrolling can happen during recovery and it does not wipe out "
                    "the work you've already done.\n\n"
                    "If you'd like, we can unpack what was happening right before the slip and what the "
                    "scrolling was helping you cope with."
                ),
                "nicotine": (
                    "Thank you for telling me you smoked again. That honesty is important.\n\n"
                    "Nicotine relapse is very common, especially under stress, and it doesn't mean your effort "
                    "was wasted.\n\n"
                    "We can look at what happened just before the cigarette so this moment becomes useful "
                    "information rather than self-criticism."
                ),
                "smoking": (
                    "Thank you for telling me you smoked again. That honesty is important.\n\n"
                    "Nicotine relapse is very common, especially under stress, and it doesn't mean your effort "
                    "was wasted.\n\n"
                    "We can look at what happened just before the cigarette so this moment becomes useful "
                    "information rather than self-criticism."
                ),
                "gambling": (
                    "Thank you for sharing that you gambled again. Naming it takes courage.\n\n"
                    "A slip does not define you. In gambling recovery, lapses can happen during high-pressure "
                    "periods and are best understood, not moralised.\n\n"
                    "If you're open to it, we can map what was going on right before the bet so this becomes "
                    "a turning point in understanding the pattern."
                ),
            }
            return _RELAPSE.get(addtype) or None

        # ── SLEEP responses (tailored per addiction type) ─────────────────────
        if intent == "behaviour_sleep":
            _SLEEP: Dict[str, str] = {
                "alcohol": (
                    "Sleep and alcohol are deeply connected — and not in a good way.\n\n"
                    "While alcohol can make you feel drowsy, it suppresses REM sleep and fragments your "
                    "sleep cycle, often leaving you more exhausted than before. Over time this creates a "
                    "cycle that's hard to break. One small step: try a single alcohol-free night and "
                    "notice how you feel the next morning."
                ),
                "drugs": (
                    "Many substances severely disrupt sleep architecture even after you stop using — "
                    "this is called post-acute withdrawal syndrome (PAWS) and it can last weeks or months.\n\n"
                    "Sleep hygiene matters more than ever in recovery: consistent wake times, "
                    "no screens an hour before bed, and avoiding caffeine after 2 pm are strong starts. "
                    "Your prescriber can also discuss short-term sleep support if needed."
                ),
                "gaming": (
                    "Sleep problems are really challenging, especially when gaming late into the night "
                    "is part of the picture.\n\n"
                    "Screen exposure raises cortisol and suppresses melatonin, making it genuinely harder "
                    "to wind down — this is physiology, not willpower. One small step: try stopping gaming "
                    "at least an hour before bed and replace it with something low-stimulation. "
                    "Even a few nights of this can shift things."
                ),
                "social_media": (
                    "Sleep and social media are in direct conflict — and your brain pays the price.\n\n"
                    "Late-night scrolling keeps your nervous system alert through blue light and emotional "
                    "triggers. Try a hard phone cut-off 45 minutes before bed and charge your phone "
                    "outside the bedroom. Even switching to greyscale mode in the evening can reduce "
                    "the pull significantly."
                ),
                "nicotine": (
                    "Nicotine is a stimulant — smoking, especially in the evening, makes it genuinely "
                    "harder to fall and stay asleep, and reduces deep sleep quality.\n\n"
                    "Cutting nicotine after 6 pm is one of the most effective sleep improvements smokers "
                    "can make. 24-hour nicotine patches can manage overnight cravings without "
                    "the sleep-disrupting stimulant effect."
                ),
                "smoking": (  # same as nicotine
                    "Nicotine is a stimulant — smoking, especially in the evening, makes it genuinely "
                    "harder to fall and stay asleep, and reduces deep sleep quality.\n\n"
                    "Cutting nicotine after 6 pm is one of the most effective sleep improvements smokers "
                    "can make. 24-hour nicotine patches can manage overnight cravings without "
                    "the sleep-disrupting stimulant effect."
                ),
                "gambling": (
                    "Difficulty sleeping often goes hand in hand with problem gambling — financial stress, "
                    "rumination about losses, and cortisol spikes from near-wins all disrupt sleep.\n\n"
                    "Addressing the gambling is the most direct route to better sleep overall. "
                    "In the short term, a brief journaling practice before bed can externalise the worry "
                    "so your mind isn't still running the numbers when you close your eyes."
                ),
            }
            return _SLEEP.get(addtype) or None

        # ── COMORBIDITY responses (known secondary addiction — escalated) ──────
        if is_comorbidity:
            patient_label  = _ADDICTION_LABEL.get(addtype, addtype.replace("_", " "))
            craving_label  = _CRAVING_LABEL.get(intent, intent.replace("addiction_", "").replace("_", " "))
            # Determine severity of the secondary addiction from the addictions list
            sec_severity = "high"
            if addictions:
                for a in addictions:
                    atype = a.get("addiction_type", "").lower().replace(" ", "_").replace("-", "_")
                    if router.primary_intent_for(atype) == intent and not a.get("is_primary"):
                        sec_severity = a.get("severity", "high")
                        break
            concern_word = "addiction" if sec_severity in ("critical", "high") else "concern"
            return (
                "I want to make sure we address this carefully — this is important.\n\n"
                f"You are managing both {patient_label} and {craving_label} as known areas of concern. "
                f"When both are active at the same time, the risk is significantly higher than managing "
                f"either alone — each can trigger or accelerate the other through the same underlying "
                f"reward and impulsivity pathways.\n\n"
                f"This urge toward {craving_label} is not a new cross-craving — it is your {craving_label} "
                f"{concern_word} reasserting itself. Please treat it with the same seriousness as "
                f"your {patient_label} recovery.\n\n"
                "Please reach out to your counsellor or support team about this specifically — "
                "dual-addiction recovery benefits significantly from integrated treatment.\n\n"
                "Is there something specific that has activated this urge today?"
            )

        # ── PRIMARY craving responses ─────────────────────────────────────────
        if is_primary:
            _PRIMARY: Dict[str, str] = {
                "alcohol": (
                    "Thank you for having the courage to share this. What you're going through is real.\n\n"
                    "Cravings for alcohol are powerful, and recognising them is already a sign of strength. "
                    "Reaching for a drink when you're tired or struggling is a very common pattern — "
                    "but there are strategies that genuinely help:\n"
                    "• An addiction counsellor specialising in alcohol use\n"
                    "• AA or SMART Recovery support groups\n"
                    "• Medical options like medication-assisted treatment\n\n"
                    "You don't have to do this alone."
                ),
                "drugs": (
                    "Thank you for sharing this. Cravings during recovery are expected — not a sign of failure.\n\n"
                    "Acting on a craving tends to intensify the next one; riding it out weakens it over time. "
                    "If the urge feels overwhelming right now, reach out to your sponsor, "
                    "support group, or a counsellor before acting on it:\n"
                    "• NA: https://www.na.org / AA: https://www.aa.org\n"
                    "• SMART Recovery: https://www.smartrecovery.org/\n\n"
                    "What is driving the urge right now?"
                ),
                "gaming": (
                    "I hear you — the pull to game right now is real.\n\n"
                    "Recognising the urge before acting on it is genuinely the hardest part, "
                    "and you're already doing that by naming it here.\n\n"
                    "A few things that can help in this moment:\n"
                    "• Delay the urge by 15 minutes — set a timer and do something physical or social\n"
                    "• Ask yourself what you are trying to escape or feel right now\n"
                    "• If gaming does happen, set a hard stop time before you start\n\n"
                    "What is going on today that is making the urge feel stronger?"
                ),
                "social_media": (
                    "I hear you. The pull to scroll can feel automatic — almost like muscle memory.\n\n"
                    "The urge usually passes within a few minutes if you can interrupt the pattern. "
                    "Try putting your phone in another room for 20 minutes before deciding whether to open it.\n\n"
                    "What are you hoping to feel or find when you open the app right now?"
                ),
                "nicotine": (
                    "Nicotine cravings are intensely physical and they peak around 3–5 minutes — then they pass.\n\n"
                    "You've noticed this urge, which is already the hardest step. "
                    "Try the 4D technique: Delay, Deep breathing, Drink water, Do something else.\n\n"
                    "If cravings remain frequent and intense, nicotine replacement therapy or prescription "
                    "options (Champix / Zyban) are highly effective — worth discussing with your GP."
                ),
                "smoking": (
                    "Nicotine cravings are intensely physical and they peak around 3–5 minutes — then they pass.\n\n"
                    "You've noticed this urge, which is already the hardest step. "
                    "Try the 4D technique: Delay, Deep breathing, Drink water, Do something else.\n\n"
                    "If cravings remain frequent and intense, nicotine replacement therapy or prescription "
                    "options (Champix / Zyban) are highly effective — worth discussing with your GP."
                ),
                "gambling": (
                    "Thank you for being honest about this. The urge to gamble is real and treatable.\n\n"
                    "The craving often spikes during stress, boredom, or after a previous loss "
                    "(the 'chasing' impulse). Recognising where you are in that cycle is important.\n\n"
                    "Right now:\n"
                    "• National Gambling Helpline (UK): 0808 8020 133\n"
                    "• National Council on Problem Gambling (US): 1-800-522-4700\n"
                    "• Gamblers Anonymous: www.gamblersanonymous.org\n\n"
                    "What is driving the urge today?"
                ),
            }
            return _PRIMARY.get(addtype) or None

        # ── CROSS-addiction responses ─────────────────────────────────────────
        if is_cross:
            patient_label = _ADDICTION_LABEL.get(addtype, addtype.replace("_", " "))
            craving_label = _CRAVING_LABEL.get(intent, intent.replace("addiction_", ""))

            # ── High-risk substance cross: behavioural addict craving alcohol/drugs ──
            if addtype in ("gaming", "social_media", "gambling") and intent == "addiction_drugs":
                return (
                    f"Thank you for sharing this — I want to make sure we take it seriously.\n\n"
                    f"When someone managing a {patient_label} addiction starts craving {craving_label}, "
                    f"it is often a sign of cross-addiction: the brain's reward system seeking a different "
                    f"dopamine source when the primary behaviour is being restricted. "
                    f"This is a clinically recognised pattern — not simply a stress reaction.\n\n"
                    f"Acting on this urge could open a second front that becomes harder to manage "
                    f"alongside your {patient_label} recovery. Please raise this with your counsellor "
                    f"or support network before acting on it.\n\n"
                    "Is there something specific that triggered this craving today?"
                )

            # ── Alcohol/drugs patient craving gambling ──
            if addtype in ("alcohol", "drugs") and intent == "addiction_gambling":
                return (
                    "I want to gently flag something important.\n\n"
                    f"For someone managing {patient_label} recovery, gambling urges carry extra risk. "
                    f"The same impulsivity and reward-seeking pathways involved in {patient_label} use "
                    f"are heavily activated by gambling. Problem gambling and substance use disorders "
                    f"co-occur very frequently, and each makes the other harder to manage.\n\n"
                    "If this urge feels strong, please speak with your counsellor or sponsor before acting on it:\n"
                    "• National Gambling Helpline (UK): 0808 8020 133\n"
                    "• National Council on Problem Gambling (US): 1-800-522-4700"
                )

            # ── Substance patient craving a behavioural outlet (gaming/social_media) ──
            if addtype in ("alcohol", "drugs") and intent in ("addiction_gaming", "addiction_social_media"):
                return (
                    f"I hear you. The urge toward {craving_label} when things feel difficult is understandable.\n\n"
                    f"In {patient_label} recovery, reaching for a behavioural outlet is very common — "
                    f"the same underlying need (to escape, to feel relief) is seeking a different route. "
                    f"An occasional {craving_label} outlet isn't necessarily harmful.\n\n"
                    f"It's worth sitting with this question: is this urge occasional, or is it becoming "
                    f"compulsive and hard to resist on its own? "
                    f"If it's becoming compulsive, raising it with your counsellor is the smart move — "
                    f"it means you're paying attention, not that you've failed."
                )

            # ── Nicotine patient craving anything else ──
            if addtype in ("nicotine", "smoking") and intent != "addiction_nicotine":
                return (
                    f"I hear you. Reaching toward {craving_label} is often a sign "
                    f"that something feels unmanageable right now.\n\n"
                    f"For someone working on nicotine cessation, cross-cravings are common — "
                    f"the brain is looking for any available reward pathway. "
                    f"Recognising the urge for what it is (a craving, not a necessity) "
                    f"gives you a moment of choice.\n\n"
                    f"What is the underlying feeling that's driving the urge toward {craving_label} right now?"
                )

            # ── Gambling patient craving anything else ──
            if addtype == "gambling" and intent != "addiction_gambling":
                return (
                    f"I hear you — the urge toward {craving_label} makes sense when you're working "
                    f"hard to stay away from gambling.\n\n"
                    f"Cross-craving is common in gambling recovery: the brain seeks stimulation or "
                    f"escape through a different outlet. An occasional {craving_label} outlet can be "
                    f"harmless — but if it starts to feel compulsive or you're using it to chase the "
                    f"same rush, it is worth raising with your counsellor.\n\n"
                    "What is the feeling that is driving this urge right now?"
                )

            # ── Generic cross-addiction fallback (any remaining combination) ──
            return (
                f"Thank you for sharing this.\n\n"
                f"Reaching toward {craving_label} while managing your {patient_label} recovery "
                f"is something worth paying attention to. "
                f"Cross-addiction — where a craving for one behaviour or substance transfers to another — "
                f"is very common in recovery and doesn't mean you're doing anything wrong.\n\n"
                f"The key question is whether this urge is occasional or becoming compulsive. "
                f"Talking it through with your counsellor or support group is always a good step.\n\n"
                "What is driving the urge toward this right now?"
            )

        # ── Normalize "smoking" → "nicotine" for shared-response lookups ──────
        _norm = "nicotine" if addtype == "smoking" else addtype

        # ── MOOD responses (tailored per addiction type) ───────────────────────
        _MOOD: Dict[str, Dict[str, str]] = {
            "mood_sad": {
                "alcohol": (
                    "I hear that you're feeling really low right now, and I want to acknowledge that.\n\n"
                    "Sadness and alcohol use are closely connected — alcohol is a CNS depressant which means "
                    "that, while a drink may feel numbing in the moment, it tends to deepen and prolong low "
                    "mood over time, creating a cycle that becomes harder to break.\n\n"
                    "Please try to avoid reaching for alcohol to manage how you're feeling tonight. "
                    "Is there someone you can be with or talk to right now?\n\n"
                    "What's behind the sadness today?"
                ),
                "drugs": (
                    "I hear you — feeling low in recovery can be really hard, especially when substances "
                    "used to feel like they took the edge off.\n\n"
                    "Sadness and substance use often co-occur, and recovery itself can initially feel "
                    "joyless as your brain's reward system heals — a phenomenon called anhedonia. "
                    "It is temporary, though it doesn't feel that way when you're in it.\n\n"
                    "Please don't use this feeling as evidence that things won't get better. "
                    "Raising this with your prescriber or counsellor is worth doing — there are effective treatments. "
                    "What's going on today?"
                ),
                "gaming": (
                    "I hear you. Sadness is worth sitting with rather than escaping — though I understand "
                    "the pull to lose yourself in a game right now.\n\n"
                    "Gaming can provide temporary relief but often deepens isolation and low mood over time, "
                    "especially if it is replacing activities that would genuinely restore you.\n\n"
                    "Tell me more about what's making you feel this way. Is there something specific going on?"
                ),
                "social_media": (
                    "I'm sorry you're feeling this way. Sadness and social media make a difficult combination — "
                    "algorithms tend to surface more emotionally charged content when you're already low, "
                    "and comparison with curated highlight reels can intensify the feeling.\n\n"
                    "If you're feeling down, please consider stepping away from social media for at least "
                    "an hour. The pull to scroll can masquerade as self-care but often isn't.\n\n"
                    "What's going on for you today?"
                ),
                "nicotine": (
                    "I hear that you're feeling down, and I want to acknowledge that.\n\n"
                    "Nicotine has a complex relationship with mood — it artificially activates dopamine "
                    "pathways and then leaves you lower when levels drop. If you're trying to cut down "
                    "or quit, some of this low feeling is your brain recalibrating, and it does improve.\n\n"
                    "Please be gentle with yourself. What's driving the sadness today?"
                ),
                "gambling": (
                    "I hear you — and I want you to know that sadness is very common in gambling recovery. "
                    "Losses, the weight of secrets carried, and the impact on relationships all accumulate. "
                    "This isn't weakness; it's a human response to something genuinely painful.\n\n"
                    "Please be careful not to let this sadness drive you back toward gambling as a way to "
                    "chase a feeling of winning or control — that cycle tends to deepen rather than relieve.\n\n"
                    "Is the sadness connected to your gambling situation, or to something else? I'm here to listen."
                ),
            },
            "mood_anxious": {
                "alcohol": (
                    "Anxiety and alcohol have a tricky relationship — alcohol can feel like it calms things "
                    "down, but it actually causes rebound anxiety as it wears off (sometimes called 'hangxiety'). "
                    "Over time, alcohol worsens anxiety rather than managing it, even though the short-term "
                    "relief feels real.\n\n"
                    "If there's an urge to drink right now, please try a grounding exercise first: "
                    "5 things you can see, 4 you can touch, 3 you can hear. Anxiety peaks and passes.\n\n"
                    "What's generating the anxiety today?"
                ),
                "drugs": (
                    "Anxiety in recovery is very common — many substances create withdrawal anxiety, and "
                    "adjusting to life without them can feel overwhelming at first.\n\n"
                    "If the anxiety feels physical or very intense, please let your treatment team know — "
                    "it may warrant a medication review. In the moment, slow diaphragmatic breathing "
                    "(inhale 4 counts, hold 4, exhale 6) can activate your parasympathetic nervous system.\n\n"
                    "What's specifically making you feel anxious?"
                ),
                "gaming": (
                    "I hear you. Anxiety is really uncomfortable to sit with, and the pull toward gaming "
                    "as something controllable makes sense.\n\n"
                    "It's worth noting that highly competitive or fast-paced gaming can actually increase "
                    "cortisol over the session, even when it provides a brief escape from external worries. "
                    "What are you anxious about — is there something specific?"
                ),
                "social_media": (
                    "Social media and anxiety are often tightly linked — constant comparison, FOMO, "
                    "notification pressure, and volatile comment sections all keep stress hormones elevated.\n\n"
                    "Even a 24-hour social media break has been shown to measurably lower cortisol. "
                    "It feels counterintuitive, but putting the phone down is one of the fastest ways "
                    "to reduce baseline anxiety.\n\n"
                    "What's making you feel anxious today?"
                ),
                "nicotine": (
                    "Here's something important to understand: nicotine feels like it relieves anxiety, "
                    "but that feeling is actually just ending the withdrawal anxiety from your previous "
                    "cigarette. The cigarette caused the anxiety it appears to fix.\n\n"
                    "This is one of the most significant things to know about smoking — your baseline "
                    "anxiety would be lower if you weren't smoking. That doesn't make quitting easy, "
                    "but it changes how to think about it.\n\n"
                    "What's making you feel anxious right now?"
                ),
                "gambling": (
                    "Anxiety and gambling often go together — the anticipation before a bet, financial "
                    "stress, anxiety about debts, the secrecy, the fear of being found out.\n\n"
                    "Please be careful that the anxiety doesn't push you toward gambling as a way to "
                    "feel in control or experience an adrenaline release — for many people, that cycle "
                    "drives anxiety and gambling to reinforce each other.\n\n"
                    "If the anxiety feels overwhelming:\n"
                    "• National Gambling Helpline (UK): 0808 8020 133\n\n"
                    "What's at the root of the anxiety right now?"
                ),
            },
            "mood_angry": {
                "alcohol": (
                    "I hear that you're feeling angry, and that's valid. Anger is important information.\n\n"
                    "I want to flag something gently: if there's alcohol around or a temptation to drink "
                    "because you're angry, please try to put distance between the feeling and the decision. "
                    "Alcohol lowers impulse control and makes anger harder to manage — decisions made "
                    "while drinking in this state often make things significantly worse.\n\n"
                    "What's made you angry today?"
                ),
                "drugs": (
                    "I hear you. Anger is a really natural part of recovery — anger at the years lost, at "
                    "circumstances, at people. All of that is valid.\n\n"
                    "What's worth watching is whether anger becomes a relapse trigger. Using as a way "
                    "to 'not care' about the anger is one of the most common patterns. Try to name "
                    "the anger, channel some of it physically, and then sit with what's underneath it.\n\n"
                    "What are you angry about?"
                ),
                "gaming": (
                    "I hear you. Anger can feel really intense — and gaming communities can be toxic, "
                    "with frustrations from losing, poor connections, or being treated badly online.\n\n"
                    "If anger from gaming is spilling into the rest of your day, that's worth paying "
                    "attention to. Research suggests rage-quitting cycles follow dopamine frustration "
                    "patterns similar to other compulsive behaviours.\n\n"
                    "Is this gaming-related anger, or is something else going on?"
                ),
                "social_media": (
                    "I hear you. Social media is specifically designed to amplify outrage — anger-inducing "
                    "content gets more engagement, so algorithms surface more of it.\n\n"
                    "If you find yourself furious after scrolling, that's often the platform working as "
                    "designed rather than something you genuinely need to engage with. The simplest "
                    "move: close the app entirely for a few hours before reacting.\n\n"
                    "What's made you angry today?"
                ),
                "nicotine": (
                    "I hear you. Irritability and anger are among the most common symptoms during nicotine "
                    "withdrawal — they're largely physical, not just psychological.\n\n"
                    "If you're going through a quit attempt, please know that this irritability peaks "
                    "around 2–3 days after stopping and then decreases significantly. It is not permanent, "
                    "even though it feels overwhelming right now.\n\n"
                    "Is this withdrawal-related, or is something else driving the anger?"
                ),
                "gambling": (
                    "I hear you. Anger is very common in gambling recovery — anger at yourself for losses, "
                    "anger at the situation, anger that feels like it has nowhere to go.\n\n"
                    "Please be careful not to let anger push you toward gambling as a way to 'take control' "
                    "or 'win back'. The chasing impulse often starts with an angry, defiant feeling. "
                    "If that's happening, please reach out to your support before acting on it.\n\n"
                    "What's made you angry today?"
                ),
            },
            "mood_lonely": {
                "alcohol": (
                    "Loneliness is one of the most painful human experiences, and one of the most common "
                    "triggers for drinking. I want to take this seriously.\n\n"
                    "Drinking alone, or drinking to take the edge off loneliness, tends to deepen rather "
                    "than fix it — isolation and alcohol often reinforce each other.\n\n"
                    "Are there people in your recovery network — a sponsor, a group, anyone — you could "
                    "reach out to today? Even a brief phone call can shift things meaningfully.\n\n"
                    "What's driving the loneliness?"
                ),
                "drugs": (
                    "Loneliness and substance use are deeply connected. Many people find that their social "
                    "circle was bound up in using, and recovery can initially feel very isolating as "
                    "those connections fade.\n\n"
                    "Building a new support network is one of the most important and underrated parts of "
                    "recovery. NA, AA, SMART Recovery, or a community group all help with this. "
                    "You don't have to feel alone in this.\n\n"
                    "What does your support network look like right now?"
                ),
                "gaming": (
                    "I hear you. Loneliness is real, and online gaming communities can feel like genuine "
                    "connection — and sometimes they are. But there's also a risk of substituting that "
                    "for real-life relationships in a way that deepens isolation long-term.\n\n"
                    "Are there people you've been less in contact with since gaming became more central? "
                    "Even one real-world connection this week can help.\n\n"
                    "What's making you feel lonely?"
                ),
                "social_media": (
                    "I hear you — and this is one of social media's great paradoxes: constant connection "
                    "that leaves people feeling more alone. Curated highlight reels make others' lives "
                    "look full, and passive scrolling gives none of the reciprocal feelings of real connection.\n\n"
                    "If loneliness is strong, please try to make one direct, human contact today — even "
                    "a single text to someone, not a post. What's going on?"
                ),
                "nicotine": (
                    "I hear you. Loneliness can be a strong trigger for smoking — social smoking especially, "
                    "where a cigarette gives you a reason to step outside and be around others.\n\n"
                    "If that's part of what's going on, it's worth thinking about other ways to create "
                    "those social moments that don't involve smoking.\n\n"
                    "What's making you feel lonely right now?"
                ),
                "gambling": (
                    "I hear you. Loneliness and gambling often go together — gambling can feel like social "
                    "engagement (especially at a casino or in a betting group), but it typically deepens "
                    "isolation over time, particularly when secrecy sets in.\n\n"
                    "Reconnecting with people is one of the most protective things against gambling relapse. "
                    "Is there someone — a trusted friend, family member, or support group — you could "
                    "reach out to today?"
                ),
            },
            "mood_guilty": {
                "alcohol": (
                    "Guilt is a really painful emotion, and people in alcohol recovery often carry a lot "
                    "of it — things said or done while drinking, missed moments, relationships affected.\n\n"
                    "Please be careful not to let guilt become a driver back toward drinking. "
                    "The cycle of drinking to escape guilt, then feeling guilty about drinking, "
                    "is one of the most common traps. Self-compassion isn't making excuses — "
                    "it's what makes change sustainable.\n\n"
                    "Is this guilt connected to your drinking, or to something else?"
                ),
                "drugs": (
                    "I hear how much you're carrying. People in recovery often carry enormous guilt — "
                    "for the impact on family, for things done to fund use, for relapses.\n\n"
                    "Please hear this: guilt is information, but it isn't the whole story of who you are. "
                    "The fact that you feel it means your values are intact. Recovery itself is a form "
                    "of making amends. Raising this with a therapist or counsellor specialising in "
                    "substance use can be really valuable.\n\n"
                    "What's the guilt about, if you'd like to share?"
                ),
                "gaming": (
                    "Guilt and gaming often go together — guilt about time not spent with family or friends, "
                    "neglected responsibilities, promises broken. I hear you.\n\n"
                    "Recognising what matters to you is the first step. The guilt is pointing to your "
                    "values, not defining you. Making one small act of follow-through today — one call, "
                    "one task completed — can start to shift the cycle.\n\n"
                    "What does the guilt feel like it's about?"
                ),
                "social_media": (
                    "I hear you. Guilt about time spent on social media, things posted, or comparing "
                    "yourself unfavourably to others is really common.\n\n"
                    "It's worth asking: is this guilt about something you've actually done, or guilt "
                    "that the platform is engineered to make you feel less-than? Social media profits "
                    "from insecurity. Not all guilt is earned.\n\n"
                    "What's the guilt about?"
                ),
                "nicotine": (
                    "I hear you. Guilt about smoking — the health impact, the cost, the effect on those "
                    "around you — is very common, and it's often what motivates the decision to quit.\n\n"
                    "Please be gentle with yourself. Nicotine is genuinely addictive — this is not a "
                    "willpower failure. The answer isn't to shame yourself into stopping; it's finding "
                    "the right combination of support and strategy.\n\n"
                    "What's the guilt about today?"
                ),
                "gambling": (
                    "Guilt is often one of the heaviest parts of gambling recovery — the money lost, "
                    "the lies told to cover it, the impact on family. This is real, and you don't "
                    "have to carry it alone.\n\n"
                    "Please know that guilt and shame often drive people back to gambling as an escape — "
                    "which makes the situation worse, not better. Gamblers Anonymous and specialist "
                    "counselling specifically address this guilt in a structured way:\n"
                    "• National Gambling Helpline (UK): 0808 8020 133\n"
                    "• GamCare: www.gamcare.org.uk\n\n"
                    "What would it feel like to share some of this burden with the right support?"
                ),
            },
        }
        mood_resp = _MOOD.get(intent, {}).get(_norm)
        if mood_resp:
            return mood_resp

        # ── TRIGGER responses (tailored per addiction type) ────────────────────
        _TRIGGER: Dict[str, Dict[str, str]] = {
            "trigger_stress": {
                "alcohol": (
                    "Stress is one of the most common triggers for alcohol use — the urge to 'take the "
                    "edge off' at the end of a difficult day is deeply conditioned for many people in "
                    "alcohol recovery.\n\n"
                    "The HALT check is worth doing right now: are you Hungry, Angry, Lonely, or Tired "
                    "alongside the stress? Addressing those first matters. Deep breathing and a brief "
                    "walk reduce cortisol faster than alcohol does, without the rebound.\n\n"
                    "What's the specific stressor?"
                ),
                "drugs": (
                    "Stress is the number one trigger for substance use relapse — this is extremely "
                    "well-documented clinically. Your brain has a well-worn pathway from 'stressed' "
                    "to 'use', and stress reactivates it.\n\n"
                    "This is the moment to lean on your support system rather than white-knuckle it alone. "
                    "Tell your sponsor, call a friend in recovery, or attend a meeting tonight if possible. "
                    "The urge will pass faster with support than alone.\n\n"
                    "What's stressing you right now?"
                ),
                "gaming": (
                    "I hear you. Stress and gaming are often tightly connected — gaming as a way to "
                    "feel in control when other things feel out of control, or to escape pressure.\n\n"
                    "It's worth asking: is gaming actually lowering your stress, or is it delaying it "
                    "while adding new stressors — time lost, tasks undone, sleep disrupted? "
                    "Sometimes a 20-minute walk manages cortisol more effectively.\n\n"
                    "What's stressing you?"
                ),
                "social_media": (
                    "Stress and social media tend to make each other worse — scrolling when stressed "
                    "gives the brain low-effort stimulation but doesn't resolve the underlying problem, "
                    "and comparison and outrage content often adds to the stress load.\n\n"
                    "Something physically grounding — a walk, making tea, calling someone — is more "
                    "effective at actually reducing cortisol than scrolling.\n\n"
                    "What's the stressor?"
                ),
                "nicotine": (
                    "Stress is one of the most powerful smoking triggers — and the belief that smoking "
                    "relieves stress is one of nicotine addiction's most effective lies.\n\n"
                    "Nicotine does not reduce stress. It relieves the withdrawal stress that builds "
                    "between cigarettes, while nicotine itself is a stimulant that elevates heart rate "
                    "and blood pressure. The relief is real, but so is the cycle driving it.\n\n"
                    "The 4D technique (Delay, Deep breathing, Drink water, Do something else) can "
                    "genuinely interrupt the urge. What's stressing you?"
                ),
                "gambling": (
                    "Stress is a major gambling trigger — the fantasy of a win that would 'fix everything' "
                    "can feel very compelling under pressure. The problem is that gambling under stress "
                    "almost always deepens it rather than resolving anything.\n\n"
                    "If financial stress is part of what's driving this, please reach out to a debt "
                    "counsellor in addition to gambling support:\n"
                    "• National Gambling Helpline (UK): 0808 8020 133\n"
                    "• StepChange (debt advice, UK): 0800 138 1111\n\n"
                    "What's the stressor today?"
                ),
            },
            "trigger_relationship": {
                "alcohol": (
                    "Relationship stress and alcohol are closely linked — conflict can feel easier to "
                    "avoid with a drink, or alcohol can fuel conflict that damages the relationship further.\n\n"
                    "If alcohol is affecting a key relationship, an honest conversation with a counsellor "
                    "about the dynamic can be really clarifying. Partners and families can also access "
                    "support through Al-Anon (UK: 020 7403 0888).\n\n"
                    "What's going on in the relationship?"
                ),
                "drugs": (
                    "I hear you. Relationships can be one of the most painful parts of recovery — the "
                    "damage done, the trust that needs rebuilding, the fear of losing people who matter.\n\n"
                    "Relationship stress is also a high-risk relapse trigger. Please reach out to your "
                    "sponsor or counsellor if it feels overwhelming — rather than trying to manage it alone.\n\n"
                    "What's happening?"
                ),
                "gaming": (
                    "I hear you. Relationships and gaming can come into real conflict — time spent gaming "
                    "at the expense of a partner, family, or friends is one of the most common reasons "
                    "people seek help for gaming concerns.\n\n"
                    "If someone important to you has raised concerns, please take that seriously. "
                    "It's often a signal worth listening to rather than defending against.\n\n"
                    "What's going on in the relationship?"
                ),
                "social_media": (
                    "Relationship stress and social media often amplify each other — social media can be "
                    "a source of relationship conflict (jealousy, comparison, public arguments), and "
                    "when relationships feel difficult, scrolling can become a way to avoid addressing it.\n\n"
                    "What's the relationship situation you're dealing with?"
                ),
                "nicotine": (
                    "Relationship stress and smoking often go together — smoking as a coping mechanism, "
                    "or relationship conflict about smoking itself (a partner wanting you to quit, "
                    "disagreements about cost or health).\n\n"
                    "If a relationship is part of why you want to quit, that's valid motivation — "
                    "though the most durable motivation tends to come from within as well.\n\n"
                    "What's going on?"
                ),
                "gambling": (
                    "Relationship stress and gambling have a devastatingly close connection. Problem "
                    "gambling often destroys trust through money hidden, lies told, financial damage, "
                    "and time away. If a relationship is under strain because of gambling, please know "
                    "this is very common and recoverable with the right support.\n\n"
                    "GamAnon supports family members affected by gambling:\n"
                    "• GamCare (UK): 0808 8020 133\n"
                    "• Gamblers Anonymous: www.gamblersanonymous.org\n\n"
                    "What's the relationship situation?"
                ),
            },
            "trigger_financial": {
                "alcohol": (
                    "Financial pressure is real, and it can be a significant trigger for drinking — "
                    "the urge to escape the worry is understandable, even if it doesn't resolve anything.\n\n"
                    "If alcohol spending is contributing to the financial strain, addressing the drinking "
                    "is one of the most direct financial interventions available. Citizens Advice (UK) "
                    "can help with debt and benefits.\n\n"
                    "What's the financial situation?"
                ),
                "drugs": (
                    "Financial pressure in recovery is common and serious. Substance use is expensive, "
                    "and maintaining recovery while managing debt or financial instability is genuinely hard.\n\n"
                    "Please explore what financial support is available alongside your recovery support. "
                    "Citizens Advice (UK) or local social services can help with debt, benefits, "
                    "and emergency support.\n\n"
                    "What's going on?"
                ),
                "gaming": (
                    "Gaming can be expensive — subscriptions, hardware, microtransactions. If gaming "
                    "spending is creating financial stress, it's worth being honest about the actual "
                    "monthly cost.\n\n"
                    "Microtransaction structures are deliberately designed to encourage spending. "
                    "If in-game spending feels hard to control, that's worth raising with a counsellor — "
                    "it can be a sign of deeper compulsive patterns.\n\n"
                    "What's the financial situation?"
                ),
                "social_media": (
                    "Financial stress and social media can intensify each other — influencer content "
                    "promoting aspirational lifestyles, targeted advertising, or MLM schemes that "
                    "target people in financial difficulty.\n\n"
                    "If you're finding yourself spending on things promoted through social media, "
                    "please look carefully at that pattern. What's the financial situation?"
                ),
                "nicotine": (
                    "The financial cost of smoking is significant — often hundreds or thousands of pounds "
                    "a year. For many people, calculating the actual annual cost is one of the strongest "
                    "motivators to quit.\n\n"
                    "NHS Stop Smoking services are free and include NRT at low cost — worth accessing "
                    "if you haven't already. What's going on with the financial pressure?"
                ),
                "gambling": (
                    "Financial stress and gambling are deeply linked — financial crisis is often the "
                    "moment when the true scale of a gambling problem becomes undeniable.\n\n"
                    "Please reach out for specialist support urgently if you are in financial difficulty "
                    "due to gambling:\n"
                    "• National Gambling Helpline (UK): 0808 8020 133\n"
                    "• GamCare: www.gamcare.org.uk\n"
                    "• StepChange (debt support, UK): 0800 138 1111\n"
                    "• Gamblers Anonymous: www.gamblersanonymous.org\n\n"
                    "You don't have to manage this alone. What's the financial situation right now?"
                ),
            },
            "trigger_grief": {
                "alcohol": (
                    "I'm deeply sorry for your loss. What you're feeling right now is real and it's heavy — "
                    "and I'm not going to minimise that.\n\n"
                    "Here's something important to understand about what's happening in your body right now: "
                    "grief creates an acute neurological stress spike. Your brain — already rewired by alcohol "
                    "use — is actively seeking a chemical shortcut to numb that spike. That urge, if it comes, "
                    "is not weakness. It is a predictable biological response. But acting on it will not "
                    "process the grief. It will pause it, extend it, and make the next wave harder to survive.\n\n"
                    "If a craving is present right now, I want you to try something called urge surfing. "
                    "A craving is not a command — it is a wave. It will peak and subside on its own, "
                    "usually within 15 to 30 minutes. You do not need to fight it. You only need to "
                    "ride it without acting. Notice it. Name it. Let it move.\n\n"
                    "Right now, in this moment: where in your body do you feel the tightness of this grief "
                    "or urge? Your chest? Your throat? Your stomach? Can you place your hand there?\n\n"
                    "The next 15 minutes matter more than the next 15 months. Stay with me."
                ),
                "drugs": (
                    "Grief is one of the most painful experiences, and using to numb it is completely "
                    "understandable — even if it's not the answer in the long run.\n\n"
                    "Grief needs to be felt to be processed, even though that's agonising. A grief "
                    "counsellor or therapist who understands substance use can hold both at once. "
                    "You don't have to carry this alone.\n\n"
                    "What's happened?"
                ),
                "gaming": (
                    "I'm sorry for what you're going through. Gaming can feel like a safe place to "
                    "disappear when grief is overwhelming — and temporary relief is understandable.\n\n"
                    "But grief does ask to be felt. If gaming is becoming a way to completely avoid "
                    "it rather than take short breaks from it, that can complicate the grieving process. "
                    "One gentle step: allow yourself a brief intentional moment today to sit with the grief.\n\n"
                    "What's happened?"
                ),
                "social_media": (
                    "I'm really sorry. Social media after a loss can be particularly painful — memories "
                    "surfacing, memorial pages, other people's comments, or simply carrying grief while "
                    "seeing others' normal lives.\n\n"
                    "If social media is making your grief feel harder or more complicated, it's okay "
                    "to step back from it during this time.\n\n"
                    "What's happened?"
                ),
                "nicotine": (
                    "I'm sorry for what you're going through. Grief is overwhelming, and reaching for "
                    "something familiar and constant like a cigarette makes complete sense.\n\n"
                    "Please be gentle with yourself during this time. If a quit attempt is underway and "
                    "grief has made it feel impossible, let your GP or stop smoking service know — "
                    "so they can support you appropriately rather than add pressure.\n\n"
                    "What's happened?"
                ),
                "gambling": (
                    "I'm sorry for what you're going through. Grief can be a powerful trigger for gambling "
                    "— the desire to feel something, take a risk, or chase a brief high when everything "
                    "feels dark and numb.\n\n"
                    "Please be particularly careful right now. Grief-driven gambling can escalate quickly. "
                    "If the urge comes on, please call your helpline before acting:\n"
                    "• National Gambling Helpline (UK): 0808 8020 133\n\n"
                    "What's happened?"
                ),
            },
            "trigger_trauma": {
                "alcohol": (
                    "I hear you. Trauma and alcohol use disorder have one of the highest co-occurrence "
                    "rates of any mental health and addiction pairing — this is not coincidence. "
                    "Alcohol is often used to manage the nervous system dysregulation that trauma creates.\n\n"
                    "The most effective treatment for this combination is trauma-informed care — "
                    "modalities like EMDR, Trauma-Focused CBT, or Seeking Safety work with both at once. "
                    "General counselling without trauma focus is often insufficient.\n\n"
                    "Are you currently working with anyone on both the trauma and the alcohol?"
                ),
                "drugs": (
                    "Trauma and substance use are very closely linked — for many people, substances "
                    "were the most effective way available to manage overwhelming trauma symptoms.\n\n"
                    "Recovery works best when the trauma is also addressed. Trauma-informed therapy "
                    "(EMDR, Seeking Safety, TF-CBT) is available and effective. Your recovery team "
                    "should know about the trauma so treatment can be adapted.\n\n"
                    "Are you currently getting support for the trauma as well as the substance use?"
                ),
                "gaming": (
                    "I hear you. Trauma and gaming can connect in complex ways — gaming can provide "
                    "a dissociative space that regulates an overwhelmed nervous system, and in that "
                    "sense it makes complete sense as a response to trauma.\n\n"
                    "But it can also prevent processing. A therapist trained in trauma — particularly "
                    "one who works with behavioural addictions — can help find a path through that "
                    "doesn't require either being overwhelmed or fully escaping.\n\n"
                    "Are you getting any support for the trauma?"
                ),
                "social_media": (
                    "Trauma and social media interact in difficult ways — exposure to traumatic content "
                    "online, having your own trauma echoed back through news or social content, or "
                    "being re-traumatised through digital connections to the source of trauma.\n\n"
                    "If social media is surfacing or worsening trauma symptoms, please consider a "
                    "significant break from it. A trauma-informed therapist can also help you manage "
                    "triggers in a structured way.\n\n"
                    "Are you getting support for what you've been through?"
                ),
                "nicotine": (
                    "I hear you. Trauma and smoking are often connected — smoking as a way to regulate "
                    "a nervous system that feels chronically dysregulated, or as ritualistic comfort "
                    "during overwhelming periods.\n\n"
                    "If you're carrying trauma, please make sure any quit attempt includes mental health "
                    "support alongside the nicotine support. A trauma-informed GP or therapist can "
                    "help coordinate this.\n\n"
                    "Are you getting support for the trauma?"
                ),
                "gambling": (
                    "Trauma and gambling can connect through the adrenaline and dissociation that "
                    "gambling provides — for some people, it becomes a way to feel alive or present "
                    "when trauma has left them numb, or to escape intrusive thoughts.\n\n"
                    "Please make sure any gambling support you receive is trauma-aware. The helpline "
                    "can direct you to appropriate services:\n"
                    "• GamCare (UK): 0808 8020 133\n"
                    "• Gamblers Anonymous: www.gamblersanonymous.org\n\n"
                    "Are you getting support for the underlying trauma?"
                ),
            },
        }
        trigger_resp = _TRIGGER.get(intent, {}).get(_norm)
        if trigger_resp:
            return trigger_resp

        # ── BEHAVIOUR (eating & exercise) tailored per addiction type ──────────
        _BEHAVIOUR_OTHER: Dict[str, Dict[str, str]] = {
            "behaviour_eating": {
                "alcohol": (
                    "Nutrition and alcohol have a significant relationship. Heavy drinking often "
                    "displaces proper eating, disrupts blood sugar regulation, and depletes key "
                    "nutrients — especially thiamine (vitamin B1).\n\n"
                    "In recovery, stabilising eating — regular meals, blood sugar balance — can "
                    "also help reduce cravings. What's going on with your eating right now?"
                ),
                "drugs": (
                    "Appetite changes are very normal in recovery — many substances suppress appetite, "
                    "and getting back to regular eating can take time. Some people find they gain weight "
                    "in early recovery as appetite returns, which brings its own challenges.\n\n"
                    "Please be gentle with yourself around food. Regular meals with protein and complex "
                    "carbohydrates can support the neurological recovery process.\n\n"
                    "What's going on with your eating?"
                ),
                "gaming": (
                    "Eating and gaming often interact — skipping meals to keep playing, eating while "
                    "gaming without awareness, or forgetting to eat entirely during long sessions. "
                    "Over time, irregular eating affects energy, mood, and concentration.\n\n"
                    "Setting deliberate meal breaks away from the screen is a small but effective step. "
                    "What's going on?"
                ),
                "social_media": (
                    "Social media and eating have a complicated relationship — exposure to idealised "
                    "bodies, diet culture content, fitness influencers, or food-shaming communities "
                    "can all impact how you feel about eating.\n\n"
                    "If you're struggling with eating, please seek support from a healthcare professional "
                    "rather than diet content online, which is not a substitute for proper nutritional support.\n\n"
                    "What's going on with your eating?"
                ),
                "nicotine": (
                    "Eating and smoking are closely linked. Some people smoke to manage appetite or "
                    "weight; others worry about gaining weight if they quit — this is one of the most "
                    "common barriers to stopping, and it's worth addressing directly.\n\n"
                    "nicotine replacement therapy and regular exercise both help manage appetite "
                    "during a quit attempt. Please don't let weight concerns stop you from trying — "
                    "your GP can help plan for this specifically.\n\n"
                    "What's going on with eating?"
                ),
                "gambling": (
                    "Gambling and eating can be directly affected by financial stress — not being able "
                    "to afford food, stress eating, or simply forgetting to eat during a gambling session.\n\n"
                    "If financial strain is affecting your ability to eat properly, please reach out "
                    "to your local food bank or financial support services in addition to gambling support.\n\n"
                    "What's going on?"
                ),
            },
            "behaviour_exercise": {
                "alcohol": (
                    "Exercise is one of the most clinically supported tools in alcohol recovery — "
                    "it rebuilds natural dopamine systems, reduces cravings, improves sleep, "
                    "and lowers anxiety. If you're already doing some physical activity, that's excellent.\n\n"
                    "Even a 20-minute brisk walk has measurable effects on craving intensity. "
                    "Starting small is absolutely enough.\n\n"
                    "What's your relationship with exercise at the moment?"
                ),
                "drugs": (
                    "Physical exercise in recovery is powerful — it helps rebuild the dopamine and "
                    "endorphin systems that substance use disrupts, reduces post-acute withdrawal "
                    "symptoms, and provides healthy structure to the day.\n\n"
                    "Running groups specifically for people in recovery exist in many areas and "
                    "combine physical activity with peer support. Even a brief daily walk is a meaningful start.\n\n"
                    "What's your relationship with physical activity?"
                ),
                "gaming": (
                    "Physical activity and gaming can seem like opposites, but they work well "
                    "together in a balanced approach.\n\n"
                    "For some people, gamifying exercise helps — apps like Zombies Run, Pokémon GO, "
                    "or Zwift for cycling can bridge both worlds. The key is getting the body moving, "
                    "which changes cortisol and dopamine levels in a way that gaming alone can't replicate.\n\n"
                    "What's your relationship with physical activity right now?"
                ),
                "social_media": (
                    "Exercise and stepping away from screens are two of the most evidence-based "
                    "things you can do for mental health — and they work well together.\n\n"
                    "If you can make a daily offline physical activity a consistent anchor — even "
                    "a 20-minute walk without your phone — that alone can significantly shift mood "
                    "and reduce the pull to scroll.\n\n"
                    "What does your physical activity look like at the moment?"
                ),
                "nicotine": (
                    "Exercise and quitting smoking are strongly linked — regular physical activity "
                    "reduces nicotine cravings, improves lung function over time, and helps manage "
                    "the weight concerns that stop many people from making a quit attempt.\n\n"
                    "Consider scheduling exercise to coincide with your most common smoking urges. "
                    "What's your current activity level?"
                ),
                "gambling": (
                    "Exercise during high-urge periods is one of the most effective alternatives "
                    "to gambling — it gives the brain a natural dopamine and endorphin response "
                    "without the financial or psychological risk.\n\n"
                    "Planning a physical activity specifically for the times you're most tempted "
                    "(often evenings or weekends) is a harm reduction strategy worth discussing "
                    "with your counsellor.\n\n"
                    "What does your physical activity look like?"
                ),
            },
        }
        behaviour_resp = _BEHAVIOUR_OTHER.get(intent, {}).get(_norm)
        if behaviour_resp:
            return behaviour_resp

        # ── SEVERE DISTRESS (tailored per addiction type) ──────────────────────
        if intent == "severe_distress":
            _SEVERE_DISTRESS: Dict[str, str] = {
                "alcohol": (
                    "I can hear that you're going through something really overwhelming right now, "
                    "and I want to take this seriously.\n\n"
                    "I want to check in: are you safe? Is there any urge to drink or to hurt yourself?\n\n"
                    "Please don't face this alone. If the distress feels unbearable, please reach out:\n"
                    "• Samaritans (UK): 116 123\n"
                    "• Crisis Text Line: Text HOME to 741741\n\n"
                    "I'm here. Tell me what's going on."
                ),
                "drugs": (
                    "I hear that you're in a really difficult place right now — this sounds serious, "
                    "and I want to make sure you're safe.\n\n"
                    "Are you safe right now? Is there any urge to use, or to hurt yourself?\n\n"
                    "Please reach out for support immediately:\n"
                    "• Samaritans (UK): 116 123\n"
                    "• Crisis Text Line: Text HOME to 741741\n"
                    "• SAMHSA National Helpline (US): 1-800-662-4357\n\n"
                    "You matter. Please keep talking to me."
                ),
                "gaming": (
                    "I can hear how much pain you're in right now. This sounds really serious.\n\n"
                    "Are you safe? Is there anything going on that's making you feel you want to harm "
                    "yourself, or that things can't go on?\n\n"
                    "Please reach out to someone who can support you right now:\n"
                    "• Samaritans (UK): 116 123\n"
                    "• Crisis Text Line: Text HOME to 741741\n\n"
                    "Stay with me — tell me what's going on."
                ),
                "social_media": (
                    "I can hear that you're going through something really overwhelming. "
                    "This sounds serious and I want to make sure you're safe.\n\n"
                    "Are you safe right now? Is anything making you feel like you want to hurt yourself?\n\n"
                    "Please reach out immediately:\n"
                    "• Samaritans (UK): 116 123\n"
                    "• Crisis Text Line: Text HOME to 741741\n\n"
                    "I'm here. Please keep talking."
                ),
                "nicotine": (
                    "I can hear that you're in real distress right now. I want to make sure you're safe.\n\n"
                    "Are you feeling safe? Is there anything beyond nicotine that's driving this "
                    "level of distress?\n\n"
                    "Please reach out if things feel overwhelming:\n"
                    "• Samaritans (UK): 116 123\n"
                    "• Crisis Text Line: Text HOME to 741741\n\n"
                    "Tell me what's happening."
                ),
                "gambling": (
                    "I can hear that you're in real pain right now, and I want to take this seriously. "
                    "Financial and relationship consequences of gambling can feel catastrophic — "
                    "that level of distress is understandable, even as it feels unbearable.\n\n"
                    "Are you safe right now? Please tell me honestly.\n\n"
                    "If you're in crisis, please reach out immediately:\n"
                    "• Samaritans (UK): 116 123\n"
                    "• National Gambling Helpline (UK): 0808 8020 133\n"
                    "• Crisis Text Line: Text HOME to 741741\n\n"
                    "You don't have to face this alone."
                ),
            }
            return _SEVERE_DISTRESS.get(_norm) or None

        return None

    def _build_personalization(self, intent: str, context_vector) -> Optional[str]:
        if context_vector and hasattr(context_vector, 'risk'):
            if context_vector.risk.risk_level == "Critical":
                return "I can hear that you're going through something really difficult right now."
            if hasattr(context_vector, 'onboarding') and context_vector.onboarding:
                if context_vector.onboarding.addiction_type:
                    return f"I understand you're working on recovery from {context_vector.onboarding.addiction_type}."
            if context_vector.session_message_count > 1:
                return "Thank you for continuing to open up with me."
        return None

    def _generate_fallback(self, intent: str, user_message: str, context_vector=None) -> str:
        if self.rag_handler:
            try:
                rag_response = self.rag_handler(user_message)
                if rag_response:
                    return rag_response
            except Exception as e:
                logger.error(f"RAG handler failed: {e}")
        return random.choice([
            "Thank you for sharing that. Can you tell me a bit more about what you mean?",
            "I hear you. That sounds important. What would you like support with?",
            "I'm listening. Help me understand what's going on for you.",
            "That's worth exploring. Can you share more details?",
        ])

    def get_next_minimal_question(self, context_vector) -> Optional[Dict]:
        if context_vector and hasattr(context_vector, 'determine_questions_to_ask_next'):
            questions = context_vector.determine_questions_to_ask_next()
            if questions:
                return questions[0]
        return None

    def should_ask_question(self, context_vector, last_question_asked: bool) -> bool:
        if not context_vector or last_question_asked:
            return False
        questions = context_vector.determine_questions_to_ask_next()
        return len(questions) > 0 and context_vector.message_count >= 2

    def add_minimal_question_to_response(self, base_response: str, question: Dict) -> str:
        return base_response + f"\n\n{question['text']}"


def create_response_generator(rag_handler=None) -> ResponseGenerator:
    return ResponseGenerator(rag_handler=rag_handler)


# ════════════════════════════════════════════════════════════════════════════
# §3  SAFETY & POLICY CHECKERS
#     Crisis detection, medication blocking, ethical policy compliance
# ════════════════════════════════════════════════════════════════════════════

class SafetyChecker:
    """Multi-layer safety validation: medication, crisis, severe distress."""

    def __init__(self):
        self.medication_unsafe_patterns = [
            r"i recommend taking", r"you should take", r"the dosage is",
            r"\d+\s?mg\b", r"twice daily", r"once daily", r"take this medication",
            r"prescrib", r"the medication for this is", r"start taking",
            r"increase the dose", r"decrease the dose", r"three times a day",
            r"as needed", r"titrate",
        ]
        # Legacy exact-pattern lists kept as ultra-fast pre-filter only.
        # Full crisis detection is now delegated to CrisisDetector (3-tier).
        self.crisis_patterns = {
            "suicidal":  ["want to die", "kill myself", "end my life", "suicide",
                          "life is not worth living", "nobody would miss me"],
            "abuse":     ["being abused", "domestic violence", "partner hits me",
                          "unsafe at home"],
            "self_harm": ["hurt myself", "cut myself", "self harm", "burn myself"],
        }
        self.severe_distress_patterns = [
            "hopeless", "hopelessness", "nothing matters",
            "i feel empty", "i feel worthless", "no reason to live", "can't escape",
        ]
        # 3-tier semantic detector
        self._crisis_detector = get_crisis_detector() if _CRISIS_DETECTOR_AVAILABLE else None

    def check_safety(self, message: str, intent: str) -> Tuple[bool, Optional[Dict]]:
        """
        Comprehensive safety check. Returns (is_safe, violation_or_None).
        is_safe=False only for medication abuse in bot output.
        Crisis/distress returns is_safe=True with metadata for routing.

        Crisis detection now uses CrisisDetector (3-tier: exact → fuzzy → semantic).
        """
        is_safe, med_violation = self._check_medication_safety(message)
        if not is_safe:
            return False, med_violation

        # Delegate to 3-tier CrisisDetector when available; fall back to
        # legacy exact-pattern checks when the module cannot be imported.
        if self._crisis_detector is not None:
            result = self._crisis_detector.detect(message)
            if result.confidence >= CONFIDENCE_WARN:
                severity_label = result.severity
                meta: Dict = {
                    "type": "crisis_indicator" if result.severity == "critical" else "severe_distress",
                    "crisis_type": result.category,
                    "severity": severity_label,
                    "confidence": result.confidence,
                    "detection_method": result.method,
                    "details": (
                        f"Semantic crisis detected [{result.method}]: "
                        f"{result.category} (confidence={result.confidence:.2f})"
                    ),
                    "recommended_action": (
                        "Use crisis response template, provide emergency resources, log event"
                        if result.severity == "critical"
                        else "Use distress response template, offer crisis resources"
                    ),
                }
                logger.warning(
                    "CrisisDetector [%s]: %s confidence=%.2f",
                    result.method, result.category, result.confidence,
                )
                return True, meta
            return True, None

        # ── Legacy fallback (no CrisisDetector module) ──────────────────
        distress = self._check_severe_distress(message)
        if distress:
            logger.warning(f"Severe distress detected: {distress['details']}")
            return True, distress

        crisis = self._check_crisis_indicators(message)
        if crisis:
            logger.warning(f"Crisis indicator detected: {crisis['details']}")
            return True, crisis

        return True, None

    def check_medication_safety(self, message: str) -> Tuple[bool, Optional[Dict]]:
        message_lower = message.lower()
        for pattern in self.medication_unsafe_patterns:
            if re.search(pattern, message_lower):
                return False, {
                    "type": "medication_unsafe", "severity": "high",
                    "details": "Response contains unsafe medication recommendation",
                    "recommended_action": "Block and redirect to MEDICATION_REFUSAL response",
                }
        return True, None

    # backward-compat alias
    _check_medication_safety = check_medication_safety

    def check_crisis_indicators(self, message: str) -> Optional[Dict]:
        message_lower = message.lower()
        for crisis_type, patterns in self.crisis_patterns.items():
            if any(p in message_lower for p in patterns):
                return {
                    "type": "crisis_indicator", "crisis_type": crisis_type,
                    "severity": "critical",
                    "details": f"User expressed {crisis_type} indicators",
                    "recommended_action": "Use crisis response template, provide resources, log event",
                }
        return None

    _check_crisis_indicators = check_crisis_indicators

    def _check_severe_distress(self, message: str) -> Optional[Dict]:
        message_lower = message.lower()
        count = sum(1 for p in self.severe_distress_patterns if p in message_lower)
        if count >= 2:
            return {
                "type": "severe_distress", "severity": "high",
                "details": f"Multiple severe distress indicators detected ({count})",
                "recommended_action": "Use severe distress response template, offer crisis resources",
            }
        return None

    def validate_response(self, response: str, intent: str) -> Tuple[bool, Optional[str]]:
        is_safe, violation = self._check_medication_safety(response)
        if not is_safe:
            return False, f"Response contains unsafe medication content: {violation['details']}"
        if len(response) == 0:
            return False, "Empty response generated"
        if len(response) < 10:
            return False, "Response too short to be meaningful"
        if intent in {"crisis_suicidal", "crisis_abuse", "behaviour_self_harm"}:
            if not any(p in response.lower() for p in ["emergency", "services", "support", "call"]):
                return False, "Crisis response missing required crisis resources/phrases"
        return True, None

    def should_log_event(self, intent: str, severity: str) -> bool:
        critical_intents = {
            "crisis_suicidal", "crisis_abuse", "behaviour_self_harm",
            "severe_distress", "psychosis_indicator", "trigger_trauma",
        }
        return intent in critical_intents or severity == "critical"

    def get_resource_links(self, intent: str) -> Dict[str, str]:
        return {
            "crisis_suicidal": {"emergency": "112 / 911 / 999", "crisis_text": "Text HOME to 741741", "international": "https://www.iasp.info/resources/Crisis_Centres/"},
            "crisis_abuse":    {"emergency": "911 / 999 / 112", "us_domestic": "1-800-799-7233", "uk_refuge": "0808 2000 247", "international": "https://www.hotpeachpages.net/"},
            "behaviour_self_harm": {"emergency": "112 / 911 / 999", "crisis_text": "Text HOME to 741741"},
            "trigger_trauma":  {"type": "therapist", "recommendation": "Trauma-informed therapist or EMDR specialist"},
            "addiction_drugs": {"aa_na": "https://www.aa.org / https://www.na.org", "smart_recovery": "https://www.smartrecovery.org/", "medical_treatment": "Consult addiction medicine specialist"},
        }.get(intent, {})


class PolicyChecker:
    """Validate responses against organisational policies."""

    def __init__(self, policy_config: Dict = None):
        self.config = policy_config or {}

    def check_policy_compliance(self, response: str, intent: str) -> Tuple[bool, Optional[Dict]]:
        if self._contains_medical_advice(response):
            return False, {
                "rule": "no_medical_advice", "severity": "high",
                "message": "Response contains medical advice without professional qualification",
            }
        if intent in {"crisis_suicidal", "crisis_abuse", "behaviour_self_harm"}:
            if not self._has_crisis_resources(response):
                return False, {
                    "rule": "require_crisis_resources", "severity": "critical",
                    "message": "Crisis response missing required emergency resources",
                }
        if intent in {"trigger_trauma", "addiction_drugs", "psychosis_indicator"}:
            if not self._recommends_professional_help(response):
                logger.warning(f"Policy: Intent {intent} should recommend professional help")
        return True, None

    def _contains_medical_advice(self, text: str) -> bool:
        patterns = [
            r"you have (?:diabetes|cancer|bipolar|schizophrenia|psychosis|epilepsy|dementia|alzheimer)",
            r"this will cure",
            r"guaranteed to",
        ]
        return any(re.search(p, text.lower()) for p in patterns)

    def _has_crisis_resources(self, text: str) -> bool:
        return any(i in text.lower() for i in ["emergency", "911", "999", "crisis", "call", "text"])

    def _recommends_professional_help(self, text: str) -> bool:
        return any(t in text.lower() for t in ["therapist", "counselor", "psychiatrist", "professional", "mental health", "specialist", "treatment"])


def create_safety_checker() -> SafetyChecker:
    return SafetyChecker()


def create_policy_checker(config: Dict = None) -> PolicyChecker:
    return PolicyChecker(config)
