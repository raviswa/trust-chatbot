"""
Crisis Detector — Three-Tier Fuzzy + Semantic Classification
=============================================================

Replaces exact-string crisis detection with a layered system:

  Tier 1  (<1 ms)   Exact / substring match on an *expanded* phrase corpus.
                     Same logic as current SafetyChecker but with far more phrases.
  Tier 2  (~2 ms)   Fuzzy sliding-window ratio via difflib.SequenceMatcher.
                     Catches paraphrases and slight reformulations.
  Tier 3  (~150 ms) Cosine similarity against pre-embedded anchor phrases using
                     nomic-embed-text (already running via Ollama for the RAG
                     pipeline).  Only triggered when tiers 1 & 2 both miss AND
                     the message contains at least one sentinel word.

Returned CrisisResult
─────────────────────
  category    str   "crisis_suicidal" | "behaviour_self_harm" | "crisis_abuse"
                     | "severe_distress" | "none"
  severity    str   "critical" | "high" | "medium" | "none"
  confidence  float 0.0 – 1.0
  method      str   "tier1_exact" | "tier2_fuzzy" | "tier3_semantic" | "none"

Interception Thresholds (imported by chatbot_engine.py)
────────────────────────────────────────────────────────
  CONFIDENCE_INTERCEPT = 0.72   Override intent → crisis, skip RAG + LLM
  CONFIDENCE_WARN      = 0.45   Inject crisis-context into system_prompt only

Severity → RAG behaviour
─────────────────────────
  critical (crisis_suicidal, crisis_abuse)
        confidence >= INTERCEPT → block RAG + LLM; return crisis template
  high   (behaviour_self_harm, severe_distress)
        confidence >= INTERCEPT → block RAG + LLM; return self-harm template
        confidence >= WARN      → allow LLM but inject safety system-prompt
  medium / none → normal flow
"""

from __future__ import annotations

import difflib
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
CONFIDENCE_INTERCEPT: float = 0.72   # Bypass RAG + LLM entirely
CONFIDENCE_WARN: float = 0.45        # Inject crisis context into system prompt

_FUZZY_MIN_RATIO: float = 0.68       # Minimum difflib ratio to count as Tier 2 hit
_SEMANTIC_MIN_SCORE: float = 0.55    # Minimum cosine sim to count as Tier 3 hit
_SEMANTIC_INTERCEPT_SCORE: float = 0.72   # Cosine sim that maps to CONFIDENCE_INTERCEPT

# ── Safe-phrase exclusions ───────────────────────────────────────────────────
# If the message matches any of these patterns the crisis tiers 2 & 3 are
# SKIPPED entirely, even when sentinel words are present.  These cover common
# alcohol/hangover contexts that superficially resemble crisis language.
_CRISIS_SAFE_PHRASES: tuple = (
    "every morning",
    "in the morning",
    "each morning",
    "waking up",
    "wake up feeling",
    "feel sick every",
    "feel rough",
    "feel terrible every",
    "feel this way every",
    "tired of feeling like this every",
    "tired of feeling this way",
    "tired of this every",
    "tired of hangovers",
    "tired of feeling hungover",
    "tired of feeling sick",
    "tired of being tired",
    "tired of waking up",
    "sick and tired of feeling",
    "feel awful in the morning",
    "feel awful every",
)

# ── Tier-3 Sentinel Words ────────────────────────────────────────────────────
# Tier-3 embedding is *only* invoked when at least one of these words appears.
# This prevents expensive ollama calls for clearly non-crisis messages.
# NOTE: "tired" removed — too broad, fires on morning-hangover complaints.
_TIER3_SENTINEL_WORDS: frozenset = frozenset({
    "point", "end", "ending", "over", "pain", "worth", "burden",
    "disappear", "gone", "better off", "miss me", "escape", "anymore",
    "hope", "future", "reason", "fighting", "dark", "thoughts", "continue",
    "existing", "exist", "leave", "without me", "keep going", "going on",
    "hurting", "punish", "deserve", "feel something", "release", "pressure",
    "no way out", "trapped", "scared", "afraid", "unsafe", "bruise",
    "can't go on", "give up", "gave up",
})

# ── Expanded Exact/Substring Patterns (Tier 1) ────────────────────────────────
# Organised by category.  All patterns are lower-cased; matched against
# message.lower().
CRISIS_EXACT_PATTERNS: Dict[str, List[str]] = {

    "crisis_suicidal": [
        # ── Direct ──
        "want to die", "kill myself", "end my life", "end it all",
        "take my own life", "take my life", "suicide", "suicidal",
        "life is not worth living", "life isn't worth living",
        "give up on life", "gave up on life",
        "nobody would miss me", "no one would miss me",
        "can't go on", "cannot go on",
        "don't want to be here", "don't want to be alive",
        "don't want to live", "tired of living",
        "thinking about suicide", "thinking of suicide",
        "want to disappear forever", "wish i was dead",
        "wish i were dead", "i want to be dead",
        "i'd be better off dead", "i would be better off dead",
        # ── Oblique / Indirect ──
        "i don't see the point anymore", "i don't see the point of going on",
        "i've been thinking about ending it", "thinking about ending it",
        "i've been thinking about ending things", "thinking about ending things",
        "what's the point of going on", "whats the point of going on",
        "i can't see a future for myself", "i can't see a future",
        "there's no future for me", "there is no future for me",
        "nobody would miss me if i was gone", "nobody would miss me if i were gone",
        "everyone would be better off without me",
        "the world would be better without me",
        "the world would be better off without me",
        "i'm so tired of fighting", "so tired of fighting this",
        "i just want the pain to stop", "just want the pain to stop",
        "i don't want to be here anymore", "i don't want to exist",
        "i've had enough of this life", "had enough of this life",
        "sometimes i think about not waking up",
        "i think about not waking up",
        "i feel like i can't go on", "feels like i can't go on",
        "i've been having dark thoughts", "having dark thoughts",
        "dark thoughts about myself", "dark thoughts about my life",
        "there's no point in continuing", "no point continuing",
        "i just want to disappear", "want to just disappear",
        "i'm at the end of my rope", "at the end of my rope",
        "i have nothing left to live for", "nothing left to live for",
        "i'm thinking about not being here", "thinking about not being here",
        "tired of being a burden", "i'm a burden to everyone",
        "i'm so done with life", "so done with life",
        "i can't keep doing this", "i can't keep going",
        "i don't want to keep living like this",
        "i've given up trying", "i've given up on everything",
        "no reason to stay alive", "no reason to keep going",
        "i feel like ending things", "thinking of ending things",
        "thinking of harming myself seriously",
    ],

    "behaviour_self_harm": [
        # ── Direct ──
        "hurt myself", "cut myself", "cutting myself", "self harm",
        "self-harm", "selfharm", "harm my body", "burn myself",
        "burning myself", "hit myself", "hitting myself",
        "injure myself", "injuring myself", "punish myself",
        "punishing myself", "scratch myself", "scratching myself",
        "harm myself", "harming myself", "self mutilat",
        # ── Indirect ──
        "physical pain helps", "physical pain helps me feel",
        "hurting myself to cope", "hurting my body to cope",
        "i find ways to punish myself", "find ways to punish myself",
        "i deserve to feel pain", "i deserve pain",
        "hurt myself when i'm overwhelmed", "hurt myself when overwhelmed",
        "i've been doing things to hurt myself",
        "i've been hurting myself", "been hurting myself",
        "cutting to feel something", "cut to feel something",
        "pain to feel something", "pain helps me feel something",
        "the only way i cope is by hurting",
        "i scratch when i'm stressed", "scratching when stressed",
        "something bad to myself", "i need to feel pain",
        "i want to feel pain on the outside",
        "i want to feel pain", "wanting to feel pain",
        "release the pressure by hurting", "i burn when i'm angry",
        "i've started cutting", "started cutting again",
        "relapsed into self harm", "relapsing into self harm",
    ],

    "crisis_abuse": [
        "being abused", "i am being abused",
        "someone is hurting me", "someone hurts me",
        "partner hits me", "boyfriend hits me", "girlfriend hits me",
        "husband hits me", "wife hits me", "parent hits me",
        "he hits me", "she hits me", "they hit me",
        "hits me regularly", "hitting me", "beats me", "beating me",
        "domestic violence", "unsafe at home", "scared of someone at home",
        "afraid to go home", "afraid at home",
        "someone is controlling me", "controlling everything i do",
        "trapped at home", "trapped in my relationship",
        "abusive", "abuse me", "abusing me",
        "can't leave", "won't let me leave", "stopped from leaving",
        "threatened if i leave", "threatens me",
        "i'm scared of the person i live with",
        "scared of who i live with",
        "feel unsafe in my home", "don't feel safe at home",
        "bruises", "i have bruises", "covering up bruises",
        "someone controls", "controlling relationship",
        "i'm not safe at home",
    ],

    "severe_distress": [
        "hopeless", "hopelessness", "nothing matters",
        "i feel empty", "feel empty inside", "i feel worthless",
        "no reason to live", "no reason to be alive",
        "life has no meaning", "my life has no meaning",
        "i feel trapped", "feeling trapped", "can't escape",
        "everything is pointless", "everything feels pointless",
        "i feel numb", "feel completely numb", "total numbness",
        "i don't care about anything anymore",
        "don't care about anything", "nothing brings me joy",
        "i feel dead inside", "feel dead inside",
        "there's no way out", "no way out",
        "i just want to give up", "want to give up",
        "i've given up", "completely given up",
        "can't feel anything", "i can't feel anything",
        "i feel completely alone", "utterly alone",
    ],
}

# ── Anchor Phrases for Semantic Embedding (Tier 3) ───────────────────────────
# These are embedded once at startup.  They cover the OBLIQUE and INDIRECT
# expressions that exact patterns can never exhaustively list.  The embedding
# space then allows cosine proximity matching against the user's message.
ANCHOR_PHRASES: Dict[str, List[str]] = {

    "crisis_suicidal": [
        "I don't see the point of living anymore",
        "I've been thinking about ending it all",
        "What's the point of going on with my life",
        "Nobody would miss me if I just disappeared",
        "The world would honestly be better off without me",
        "I'm so tired of battling every single day",
        "I just want all this pain to stop for good",
        "I don't want to be here on this earth anymore",
        "I have absolutely nothing left to live for",
        "I've been having very dark thoughts about ending my life",
        "I'm thinking about not being around anymore",
        "I feel like everyone around me would be better off without me",
        "Sometimes I lie awake thinking about not waking up",
        "I have completely given up any hope that life will get better",
        "There's simply no point in continuing like this",
        "I'm at the absolute end of my rope with everything",
        "I feel like such a burden on everyone who cares about me",
        "I just want to escape and never come back",
        "I'm done with this life and can't see a way forward",
        "I've been struggling with thoughts about suicide",
        "Lately I've been thinking that everyone would be happier if I wasn't here",
        "I feel like I'm just going through the motions with no real reason",
    ],

    "behaviour_self_harm": [
        "Physical pain helps me actually feel something real",
        "I find ways to punish myself when I feel overwhelmed",
        "I've been hurting my body as a way to cope with emotional pain",
        "I scratch or cut myself when I can't handle the pressure",
        "I feel like I deserve to feel physical pain for what I've done",
        "Hurting myself is the only outlet I have when things get too much",
        "I've been doing harmful things to my own body",
        "I want to feel pain on the outside instead of just the inside",
        "I've been cutting as a way to release the pressure I feel",
        "When I'm angry at myself I end up hurting my body",
        "I've relapsed back into harming myself again",
        "Injuring myself briefly makes the emotional pain bearable",
    ],

    "crisis_abuse": [
        "I'm genuinely scared of the person I'm living with",
        "Someone in my home controls every single thing I do",
        "I'm afraid to go back home because of what might happen",
        "I have bruises but I can't tell anyone how I really got them",
        "I feel completely trapped and unable to leave my relationship",
        "Someone threatens what they'll do if I ever try to get help",
        "I feel unsafe inside my own home with the people there",
        "The person I live with hurts me and I don't know what to do",
        "I'm being hurt by someone and I'm too scared to speak up",
        "My partner makes me feel afraid every single day",
    ],

    "severe_distress": [
        "I feel completely empty and hollow inside",
        "Nothing I do or feel matters to me anymore",
        "I feel utterly worthless and without any value",
        "I feel completely numb and disconnected from everything",
        "I've stopped caring about anything because nothing helps",
        "I feel totally alone and trapped without any way out",
        "Everything feels completely pointless and meaningless",
        "I feel dead inside even though I'm still physically alive",
    ],
}

# ── Severity Mapping ──────────────────────────────────────────────────────────
_SEVERITY: Dict[str, str] = {
    "crisis_suicidal":    "critical",
    "crisis_abuse":       "critical",
    "behaviour_self_harm": "high",
    "severe_distress":    "high",
    "none":               "none",
}


# ── Data Container ────────────────────────────────────────────────────────────
@dataclass
class CrisisResult:
    category:   str   = "none"
    severity:   str   = "none"
    confidence: float = 0.0
    method:     str   = "none"

    @property
    def is_crisis(self) -> bool:
        return self.confidence >= CONFIDENCE_INTERCEPT

    @property
    def is_potential_crisis(self) -> bool:
        return self.confidence >= CONFIDENCE_WARN


# ── Core Detector ─────────────────────────────────────────────────────────────
class CrisisDetector:
    """
    Three-tier crisis detection engine.

    Usage
    -----
    detector = CrisisDetector()
    detector.initialize()          # pre-compute anchor embeddings (call once)
    result = detector.detect(msg)  # returns CrisisResult
    """

    def __init__(self) -> None:
        self._anchor_embeddings: Dict[str, List[List[float]]] = {}
        self._initialized = False

    # ── Public API ────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Pre-embed anchor phrases so runtime latency is minimal."""
        try:
            import ollama
            for category, phrases in ANCHOR_PHRASES.items():
                vecs: List[List[float]] = []
                for phrase in phrases:
                    try:
                        resp = ollama.embeddings(model="nomic-embed-text", prompt=phrase)
                        vecs.append(resp["embedding"])
                    except Exception as e:
                        logger.debug(f"Anchor embed failed for '{phrase[:40]}': {e}")
                self._anchor_embeddings[category] = vecs
            self._initialized = True
            logger.info(
                "CrisisDetector: pre-embedded %d anchor categories",
                len(self._anchor_embeddings),
            )
        except Exception as e:
            logger.warning(
                "CrisisDetector: ollama unavailable — tier-3 semantic matching disabled. (%s)", e
            )
            self._initialized = False

    def detect(self, message: str) -> CrisisResult:
        """
        Run all tiers and return the highest-confidence CrisisResult.
        Processing stops early if a tier reaches CONFIDENCE_INTERCEPT.
        """
        if not message:
            return CrisisResult()

        msg_lower = message.lower()

        # ── Safe-phrase gate: skip tiers 2 & 3 for known non-crisis contexts ──
        # These are common alcohol/hangover/fatigue expressions that superficially
        # resemble crisis language but are NOT crisis statements.
        _is_safe_phrase = any(sp in msg_lower for sp in _CRISIS_SAFE_PHRASES)

        # ── Tier 1: Exact / substring match ──────────────────────────────
        t1 = self._tier1_exact(msg_lower)
        if t1.confidence >= CONFIDENCE_INTERCEPT:
            return t1

        # If a safe phrase gates this message, stop here (don't run fuzzy/semantic).
        if _is_safe_phrase:
            return t1  # confidence = 0.0 unless tier-1 fired

        # ── Tier 2: Fuzzy ratio ───────────────────────────────────────────
        t2 = self._tier2_fuzzy(msg_lower)
        best = t1 if t1.confidence >= t2.confidence else t2
        if best.confidence >= CONFIDENCE_INTERCEPT:
            return best

        # ── Tier 3: Semantic embedding ────────────────────────────────────
        # Only run if the message contains at least one sentinel word
        # (avoids 150 ms ollama call for obviously non-crisis messages).
        words_in_msg = set(msg_lower.split())
        has_sentinel = bool(words_in_msg & _TIER3_SENTINEL_WORDS) or any(
            sw in msg_lower for sw in _TIER3_SENTINEL_WORDS if " " in sw
        )

        if has_sentinel:
            t3 = self._tier3_semantic(message)
            if t3.confidence > best.confidence:
                best = t3

        return best

    # ── Tier 1 ────────────────────────────────────────────────────────────

    def _tier1_exact(self, msg_lower: str) -> CrisisResult:
        """Exact substring match on the expanded pattern corpus."""
        for category, patterns in CRISIS_EXACT_PATTERNS.items():
            for pattern in patterns:
                if pattern in msg_lower:
                    return CrisisResult(
                        category=category,
                        severity=_SEVERITY[category],
                        confidence=1.0,
                        method="tier1_exact",
                    )
        return CrisisResult()

    # ── Tier 2 ────────────────────────────────────────────────────────────

    def _tier2_fuzzy(self, msg_lower: str) -> CrisisResult:
        """
        Sliding-window fuzzy comparison using difflib.SequenceMatcher.

        Pre-filtered by a set of sentinel words to avoid running against
        clearly non-crisis messages (prevents false positives on 'can't sleep'
        or 'need a beer').

        For each 4–8 token window of the message, compute the best ratio
        against each tier-1 exact phrase.  Returns the overall best match if
        it exceeds _FUZZY_MIN_RATIO.
        """
        # Guard: at least one unambiguous distress/crisis word must be present.
        _TIER2_SENTINEL_WORDS = {
            "die", "dead", "kill", "killed", "death", "dying",
            "hurt", "harm", "harming", "hurting", "injure", "injuring",
            "abuse", "abused", "abusing", "abuser",
            "cut", "cutting", "burn", "burning", "scratch", "scratching",
            "safe", "unsafe", "danger", "dangerous",
            "disappear", "disappearing", "vanish",
            "ending", "ended", "end it", "end things",
            "hopeless", "worthless", "pointless", "meaningless",
            "trapped", "escape", "escaping",
            "nothing", "nobody", "no one",
            "sick of", "had enough",
            "dark thoughts", "dark thought",
            "burden", "burdening",
            "miss me", "without me", "better off",
        }
        has_sentinel = (
            any(w in msg_lower for w in _TIER2_SENTINEL_WORDS)
            or any(sw in msg_lower for sw in _TIER2_SENTINEL_WORDS if " " in sw)
        )
        if not has_sentinel:
            return CrisisResult()

        words = msg_lower.split()
        if len(words) < 3:
            return CrisisResult()

        best_ratio = 0.0
        best_category = "none"

        # Build windows of 3–8 tokens to match against phrase fragments
        window_sizes = [4, 5, 6, 7, 8]

        for category, patterns in CRISIS_EXACT_PATTERNS.items():
            for phrase in patterns:
                phrase_words = phrase.split()
                for ws in (w for w in window_sizes if w >= len(phrase_words) - 1):
                    for i in range(max(1, len(words) - ws + 1)):
                        window = " ".join(words[i : i + ws])
                        ratio = difflib.SequenceMatcher(
                            None, window, phrase
                        ).ratio()
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_category = category

        if best_ratio >= _FUZZY_MIN_RATIO:
            # Scale confidence: ratio=1.0 → confidence=0.90 (below exact-match 1.0)
            confidence = min(best_ratio * 0.90, 0.90)
            return CrisisResult(
                category=best_category,
                severity=_SEVERITY.get(best_category, "none"),
                confidence=confidence,
                method="tier2_fuzzy",
            )
        return CrisisResult()

    # ── Tier 3 ────────────────────────────────────────────────────────────

    def _tier3_semantic(self, message: str) -> CrisisResult:
        """
        Cosine similarity against pre-embedded anchor phrases.
        Returns CrisisResult with confidence == cosine score if above threshold.
        """
        if not self._initialized or not self._anchor_embeddings:
            return CrisisResult()

        try:
            msg_vec = self._embed(message)
            if not msg_vec:
                return CrisisResult()

            best_score = 0.0
            best_category = "none"

            for category, anchor_vecs in self._anchor_embeddings.items():
                for anchor_vec in anchor_vecs:
                    score = self._cosine(msg_vec, anchor_vec)
                    if score > best_score:
                        best_score = score
                        best_category = category

            if best_score >= _SEMANTIC_MIN_SCORE:
                return CrisisResult(
                    category=best_category,
                    severity=_SEVERITY.get(best_category, "none"),
                    confidence=best_score,
                    method="tier3_semantic",
                )
        except Exception as e:
            logger.debug("Crisis detector tier-3 failed: %s", e)

        return CrisisResult()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _embed(self, text: str) -> Optional[List[float]]:
        """Embed text using ollama nomic-embed-text (same model as RAG pipeline)."""
        try:
            import ollama
            resp = ollama.embeddings(model="nomic-embed-text", prompt=text)
            return resp.get("embedding") or []
        except Exception:
            return []

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(y * y for y in b))
        if mag_a == 0.0 or mag_b == 0.0:
            return 0.0
        return dot / (mag_a * mag_b)


# ── Module-level singleton ────────────────────────────────────────────────────
# Imported directly by chatbot_engine.py and services_pipeline.py
_detector_instance: Optional[CrisisDetector] = None


def get_crisis_detector() -> CrisisDetector:
    """Return (and lazily initialise) the module-level CrisisDetector singleton."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = CrisisDetector()
        _detector_instance.initialize()
    return _detector_instance