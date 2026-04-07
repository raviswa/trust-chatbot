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
                # Abbreviated forms that bypass the LLM tier when offline
                "what meds", "which meds", "what med ", "what med?",
                "should i take", "what to take",
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
                # Indirect / understated disclosures
                "my partner scares me", "scared of my partner", "partner frightens me",
                "scared of my husband", "scared of my wife", "scared of my boyfriend",
                "scared of my girlfriend", "he scares me", "she scares me",
                "afraid of my partner", "afraid of my husband", "afraid of my wife",
                "scared to go home", "frightened to go home", "don't feel safe at home",
            ],
            "behaviour_self_harm": [
                "hurt myself", "cut myself", "self harm", "harm my body", "burn myself",
                "hit myself", "injure myself", "punish myself", "physical pain helps",
                # Indirect / understated self-harm disclosures
                "scratch myself", "scratching myself", "i scratch myself",
                "pick at my skin", "picking at my skin",
                "bite myself", "bite my skin", "pull my hair out",
                "bang my head", "bang my head against", "hit the wall",
                "dig my nails in", "digging nails into",
            ],
            # Priority 2: High-severity clinical signals
            "severe_distress": [
                "hopeless", "hopelessness", "nothing matters", "i feel empty",
                "i feel worthless", "no reason to live", "life has no meaning",
                "i feel trapped", "can't escape",
                # Variations that fall through to rag_query without Ollama
                "feel so empty", "feeling so empty", "completely empty inside",
                "feel completely empty", "feel completely worthless",
                "life feels meaningless", "life is meaningless", "feels pointless",
                "everything feels pointless", "everything is pointless",
                "feel worthless", "feeling worthless", "i am worthless",
                "what's the point", "what is the point", "no point anymore",
                "no point in anything",
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
                # Past-tense consumption disclosures (e.g. "had a beer last night")
                "had a beer", "had a drink", "had a few drinks", "had some drinks",
                "had a glass of wine", "had a glass of", "had a shot",
                "drank last night", "drank yesterday", "drank today",
                "used last night", "used again last", "used yesterday",
                "smoked last night", "vaped last night",
                "gambled last night", "gambled again", "gambled yesterday",
                "slipped last night", "slipped yesterday",
                # Broken promise / failed-attempt disclosures
                "said i'd stop", "said id stop", "told myself i'd stop",
                "promised i'd stop", "promised myself i'd stop",
                "said i'd quit", "said id quit",
                # Cycle of relapse / failed promises
                "keep promising myself i'll stop", "keep promising to stop",
                "promised to stop and didn't", "keep breaking my promise",
                "never manage to stop", "tried to stop but",
                "tried to quit but", "keep relapsing", "keep falling back",
                "keep falling off the wagon", "can't stay stopped", "cant stay stopped",
                # Relationship harm caused by drinking (drinking revealed as cause)
                "fight because of drinking", "fight because of my drinking",
                "argument because of drinking", "argument because of my drinking",
                "fight with my partner about", "fight with my wife about",
                "fight with my girlfriend about", "fight with my boyfriend about",
                "fight with my gf", "fight with my bf", "because of drinking again",
                # Consequences and damage caused by drinking
                "ruined everything", "ruined it again", "messed everything up",
                "family won't talk to me", "family won't speak to me",
                "lost my job because", "lost everything because",
                # Past-tense consumption with clear past context
                "drank a whole", "drank the whole", "drank an entire",
                "bottle by myself", "drank alone",
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
                # Dependence / dependency disclosure
                "dependent on alcohol", "dependent on drugs", "i think i'm dependent",
                "think i'm addicted", "am i an alcoholic", "think i have a drinking problem",
                # Alcohol quantity / minimisation questions
                "how many drinks", "drinks a day", "drinks per day",
                "can stop whenever i want", "stop whenever i want",
                "only drink at night", "i only drink", "just beer", "it's just beer",
                "other people drink", "people drink more", "others drink more",
                "worried about my drinking", "family is worried about my drinking",
                # Withdrawal symptoms (apostrophe and informal variants)
                "sick when i don't drink", "sick when i dont drink",
                "when i don't drink", "when i dont drink", "when i stop drinking",
                "sick without alcohol", "feel sick without",
                # Loss of control
                "losing control of my drinking", "feel like i'm losing control of my drinking",
                # Denial / rationalisation (person doesn't identify as having a problem)
                "everyone drinks", "everyone else drinks", "normal to drink",
                "drink to relax", "i drink to relax", "drinking to relax", "alcohol helps me relax",
                "not an alcoholic", "i'm not an alcoholic", "im not an alcoholic",
                "i'm not addicted", "im not addicted", "not addicted to alcohol",
                "just like to drink", "i just like drinking", "i enjoy drinking",
                "think i might have a drinking problem", "might have a drinking problem",
                "maybe have a drinking problem", "drinking problem",
                "drink a bit more than i should", "more than i should be drinking",
                "wife thinks i have a problem", "husband thinks i have a problem",
                "partner thinks i have a problem", "family thinks i have a problem",
                "friends think i have a problem",
                # Family / social concern (patient sharing others' worry)
                "family is worried about my drinking", "family worried about my drinking",
                "family concerned about my drinking", "partner worried about my drinking",
                "wife is worried about my drinking", "husband is worried about my drinking",
                "my family is worried", "worried about my drinking",
                "family won't stop telling me", "family keeps saying i drink too much",
                # Drinking-as-coping patterns
                "had a couple of drinks to unwind", "couple of drinks to unwind",
                "drink to unwind", "drink to wind down", "drank to take the edge off",
                "needed something to take the edge off", "take the edge off",
                "drink after work", "drink when stressed", "drink when anxious",
                "drank after a long day", "had a drink after a long day",
                "few drinks to unwind", "drink to cope", "drinking to cope",
                "use alcohol to cope", "alcohol to cope", "drink when things get hard",
                # Harm reduction / cutting back
                "want to cut back", "trying to cut back", "cut back on drinking",
                "cut down on drinking", "cut back my drinking", "reduce my drinking",
                "drink less", "drink a bit less", "cutting back on alcohol",
                "moderate my drinking", "manage my drinking", "control my drinking",
                "not necessarily quit", "don't want to quit completely", "just want to cut back",
                "tips to manage my drinking", "tips for my drinking", "tips to manage weekend drinking",
                "tips for weekend drinking", "manage weekend drinking", "manage my weekend drinking",
                "weekend drinking", "manage how much i drink",
                # Seeking help to quit
                "help me quit drinking", "help me stop drinking", "help me quit alcohol",
                "help me with my drinking", "help me cut back", "can you help me quit",
                "can you actually help me quit", "can you help me stop drinking",
                "want to quit drinking", "trying to quit drinking", "trying to stop drinking",
                "want to stop drinking", "want to give up drinking", "give up alcohol",
                # Getting through cravings / tonight
                "get through tonight without a drink", "get through tonight without drinking",
                "get through today without a drink", "get through this without drinking",
                "get through the night without drinking", "how to resist drinking tonight",
                "not drink tonight", "avoid drinking tonight", "sober tonight",
                # Quantity / risk awareness questions
                "how many drinks is too many", "how much is too much to drink",
                "how many drinks is considered", "what is a safe amount to drink",
                "how many units is too much", "how many drinks before it's a problem",
                "drinking every day bad", "is it bad to drink every day",
                "bad to drink alone", "bad to drink by yourself",
                # Clinical / technical disclosures
                "units a night", "units per night", "units a day", "units per day",
                "liver enzymes", "liver function", "alt was", "ast was", "ggt was", "liver test",
                "taper off", "taper down", "tapering", "want to taper",
                "drinking daily for", "drinking every day for",
                "naltrexone", "acamprosate", "disulfiram", "antabuse", "campral",
                "sinclair method", "audit-c", "alcohol use disorder", "aud",
                "ml of spirits", "ml of alcohol", "litres of spirits", "litres of alcohol",
                "bottle of spirits", "bottle of wine a day", "bottle a day", "bottle a night",
                # Active / real-time loss of control (intoxicated or craving now)
                "drinking right now", "drinking rn", "im drinking rn", "drinking as i",
                "one more drink", "1 more drink", "just one more drink", "just 1 more drink",
                "then i'll stop", "then ill stop", "and then i'll stop",
                "can't stop right now", "cant stop right now",
                # Quantity / consumption admission (present)
                "drink too much", "drunk too much", "drinking too much",
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
                # Normalised variants ("can not" with a space is not matched by "cannot")
                "can not sleep", "cannot seem to sleep", "unable to sleep",
                "been awake", "stayed awake", "lying awake", "lie awake",
                "staring at the ceiling", "tossing and turning",
                # Morning-after / post-drinking fatigue patterns
                "tired of feeling like this every morning", "feeling like this every morning",
                "feel like this every morning", "like this every morning",
                "tired every morning", "exhausted every morning", "awful every morning",
                "feel terrible every morning", "feel rough every morning",
                "wake up feeling terrible", "wake up feeling awful", "wake up feeling sick",
                "wake up every day feeling", "morning feeling sick", "sick every morning",
            ],
            "behaviour_fatigue": [
                # ── Core fatigue words ──────────────────────────────────────
                "tired", "so tired", "very tired", "too tired", "exhausted", "exhaustion",
                "fatigue", "fatigued", "drained", "physically drained",
                "worn out", "worn down", "worn through", "burnt out", "burned out", "burnout",
                # ── Energy / motivation deficit ─────────────────────────────
                "no energy", "low energy", "lacking energy", "zero energy", "no get-up-and-go",
                "no motivation", "lack of motivation", "no drive", "can't get going",
                "can't get started", "energy crash", "hit a wall", "hitting a wall",
                "running on fumes", "running on empty", "barely functioning",
                # ── Run-down / depleted ────────────────────────────────────
                "run down", "rundown", "feeling run down", "ground down", "spent",
                "depleted", "feel depleted", "feel empty", "feeling empty",
                # ── Sleepy / drowsy ────────────────────────────────────────
                "sleepy", "feeling sleepy", "drowsy", "drowsiness", "somnolent", "somnolence",
                "groggy", "grogginess", "feel groggy", "heavy eyelids", "eyelids are heavy",
                "can't keep my eyes open", "can barely keep my eyes open",
                "nodding off", "dropping off", "falling asleep at", "fighting sleep",
                "struggling to stay awake", "can't stay awake", "need a nap",
                "just want to sleep", "just want to rest", "could sleep for days",
                "could sleep forever", "yawning", "can't stop yawning",
                # ── British / colloquial slang ─────────────────────────────
                "knackered", "shattered", "wiped out", "wiped", "zonked", "zonked out",
                "bushed", "pooped", "pooped out", "beat", "dead tired", "dog tired",
                "done in", "done for", "bone tired", "bone weary", "flagging",
                "wrecked", "fried", "cream crackered", "dead on my feet",
                # ── Heavy / sluggish body ──────────────────────────────────
                "feel heavy", "feeling heavy", "body feels heavy", "legs feel heavy",
                "feel sluggish", "sluggish", "feeling sluggish", "slow moving",
                "hard to get up", "can't get up", "can't get out of bed in the morning",
                # ── Cognitive / mental fatigue ─────────────────────────────
                "brain fog", "brain fogged", "foggy brain", "foggy headed", "mental fog",
                "mentally drained", "mentally exhausted", "mentally fatigued",
                "can't focus", "can't concentrate", "feel flat", "feeling flat",
                # ── Clinical / medical terminology ─────────────────────────
                "lethargy", "lethargic", "malaise", "listless", "listlessness",
                "torpor", "torpid", "enervated", "enervation", "asthenia", "debilitated",
                "chronic fatigue", "cfs", "post-viral fatigue", "adrenal fatigue",
                # ── Physically unwell (non-crisis) ─────────────────────────
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
                # Confusion / helplessness
                "why do i keep", "don't know why i keep", "keep doing this to myself",
                "keep doin this",
                # Rough patch / lost / overwhelmed
                "having a rough time", "been having a rough time", "rough time lately",
                "rough few weeks", "rough few months", "rough patch",
                "don't know why i'm here", "not sure why i'm here", "i don't know why i'm here",
                "really struggling", "struggling a lot", "been struggling lately",
            ],
            # Priority 4b: Mood
            # NOTE: "feel like a burden" must appear in mood_guilty BEFORE mood_sad,
            # because mood_sad contains "feel like" as a substring that would match first.
            "mood_sad":     ["sad", "depressed", "depression", "feeling down", "unhappy", "worthless", "down in the dumps", "blue", "gloomy"],
            "mood_anxious": ["anxious", "anxiety", "worried", "nervous", "panicking", "panic attack", "stressed", "stress", "tense", "worried about"],
            "mood_angry":   ["angry", "rage", "furious", "frustrated", "irritated", "annoyed", "mad", "getting angry"],
            "mood_lonely":  ["alone", "lonely", "isolated", "no one", "nobody", "by myself"],
            "mood_guilty":  [
                "guilty", "guilt", "ashamed", "shame", "regret", "regretful",
                # Burden ideation — must be listed here so it is reached before
                # mood_sad's "feel like" pattern fires
                "feel like a burden", "feeling like a burden", "i am a burden",
                "i'm a burden", "feel like i'm dragging everyone",
                "feel like i drag everyone", "burden to everyone", "burden to my family",
                # Shame tied to alcohol-related behaviour
                "not proud of what i've become", "ashamed of what i've become",
                "not proud of who i've become", "ashamed of who i've become",
                "not the person i used to be", "not who i used to be",
                "my kids saw me drunk", "kids saw me drunk", "children saw me drunk",
                "my kid saw me drunk", "my son saw me drunk", "my daughter saw me drunk",
                "saw me drunk", "caught me drinking", "caught me drunk",
                "ashamed of my drinking", "embarrassed about my drinking",
                "i'm a failure", "im a failure", "i am a failure",
                "feel like a failure", "feeling like a failure",
                "failure because of drinking", "failing because of drinking",
                "i can't even stop", "can't even stop drinking",
            ],
            # Priority 5: Small talk
            "greeting":  ["hi ", "hello", "hey", "good morning", "good afternoon", "good evening", "good night", "howdy", "greetings", "what's up", "how are you"],
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
            "Thank you for trusting me with something so personal — what you've been through sounds incredibly difficult."
            " If memories feel overwhelming right now, try grounding yourself: name 5 things you can see in the room around you."
            " Would you like to share more about what's coming up for you?"
        ),
    },
    "addiction_drugs": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "Cravings are powerful and real, and I hear you for sharing this honestly."
            " Try urge surfing right now: observe the craving like a wave — notice it without acting on it, and it will peak and pass within about 15 minutes."
            " What's driving the craving right now?"
        ),
    },
    "relapse_disclosure": {
        "type": "clinical", "severity": "medium", "show_resources": False,
        "base": (
            "Thank you for telling me — a slip doesn't erase your effort or define your recovery."
            " Try to hold off any harsh self-judgment for today and instead ask yourself what was happening in the hours before the slip."
            " What do you think led up to it?"
        ),
    },
    "addiction_gaming": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "The pull to game when things feel hard is real, and it takes strength to name it."
            " Set a 15-minute timer before deciding to open a game — most urges lose their intensity in that window."
            " What's driving the urge today?"
        ),
    },
    "addiction_nicotine": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "Nicotine cravings are intensely physical and they pass — usually within 3–5 minutes."
            " Try the 4D technique right now: Delay 5 minutes, take Deep breaths, Drink water, and Do something with your hands."
            " What triggered the craving?"
        ),
    },
    "addiction_social_media": {
        "type": "clinical", "severity": "medium", "show_resources": True,
        "base": (
            "The pull to scroll can feel almost automatic, and I hear you."
            " Put your phone in another room for the next 20 minutes — the urge usually fades once the habit loop is broken."
            " What are you hoping to find when you open the app?"
        ),
    },
    "addiction_gambling": {
        "type": "clinical", "severity": "high", "show_resources": True,
        "base": (
            "The urge to gamble is powerful and treatable, and you've done the right thing by naming it."
            " Call the National Gambling Helpline right now — UK: 0808 8020 133 / US: 1-800-522-4700 — a brief conversation can interrupt the urge."
            " What's driving the urge today?"
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
            "I hear you — feeling low is really hard to carry."
            " Try telling one person you trust how you're feeling today, even just in a text."
            " What's behind the sadness?"
        ),
    },
    "mood_anxious": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Anxiety can feel completely overwhelming, and I hear you."
            " Try this right now: breathe in for 4 counts, hold for 4, breathe out for 6."
            " What's driving the anxiety today?"
        ),
    },
    "mood_angry": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Anger is telling you something important, and it makes sense you're feeling it."
            " Before acting on this feeling, try naming what's underneath it — hurt, frustration, or feeling unheard."
            " What happened to bring this up?"
        ),
    },
    "mood_lonely": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Loneliness is one of the most painful feelings, and I'm glad you shared that."
            " Send one message to someone you trust today — even just 'thinking of you' can start a real connection."
            " What's making you feel this way right now?"
        ),
    },
    "mood_guilty": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Guilt can be really heavy, and I want you to know I hear you."
            " Try asking yourself: would you judge a good friend this harshly for the same thing?"
            " What are you blaming yourself for?"
        ),
    },
    # ── Behaviour ────────────────────────────────────────────────────────
    "behaviour_fatigue": {
        "type": "supportive", "severity": "low", "show_resources": False,
        "base": (
            "Feeling worn out or sleepy is completely understandable — your body may just need rest."
            " If you can, give yourself permission to take a proper break today."
            " Is this a one-off tiredness, or has it been building up over a while?"
        ),
    },
    "behaviour_sleep": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Sleep problems are genuinely exhausting, and they affect everything else."
            " Try one change tonight: put your phone outside the bedroom and keep a consistent wake-up time."
            " How long has sleep been a struggle for you?"
        ),
    },
    "behaviour_eating": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Our relationship with food is often deeply tied to how we're feeling emotionally."
            " Before your next meal, try a slow breath and check in with how you're feeling, not just what you're craving."
            " What's been happening with eating lately?"
        ),
    },
    # ── Trigger & behaviour intents (tailored responses in _get_addiction_aware_base) ──
    "trigger_stress": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Stress can feel all-consuming, especially when it's connected to your recovery."
            " Take 2 minutes right now to write down what's stressing you most — getting it out of your head can help."
            " What's the main source of stress today?"
        ),
    },
    "trigger_relationship": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Relationship difficulties are genuinely painful, and it takes courage to talk about them."
            " Before the next difficult conversation, try giving yourself 10 minutes of quiet first to settle your emotions."
            " What's going on in the relationship?"
        ),
    },
    "trigger_financial": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "Financial stress is real and exhausting, and you don't have to carry it alone."
            " Write down just one financial concern for today — tackling one thing at a time reduces the overwhelm."
            " What's weighing on you most right now?"
        ),
    },
    "trigger_grief": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "I'm truly sorry for your loss — grief is one of the most painful things we go through."
            " Give yourself permission today to feel whatever comes up without trying to rush or manage it."
            " Would you like to tell me about them?"
        ),
    },
    "behaviour_exercise": {
        "type": "supportive", "severity": "low", "show_resources": False,
        "base": (
            "It's great that you're thinking about physical activity — it really does support recovery."
            " Start small: even a 10-minute walk outside today can shift your mood and energy."
            " What kind of activity feels manageable for you right now?"
        ),
    },
    # ── Venting / Implicit Distress ────────────────────────────────────────
    # Overwhelm, emotional exhaustion, burnout, frustration — no advice, no solutions.
    # Empathy first + gentle emotional regulation suggestion with video.
    "venting": {
        "type": "supportive", "severity": "medium", "show_resources": False,
        "base": (
            "That sounds really hard, and it makes complete sense that you're feeling overwhelmed."
            " Take one slow breath right now — you don't need to have the answers, just make a little space."
            " What's been weighing on you most today?"
        ),
    },
    # ── Small talk ───────────────────────────────────────────────────────
    "greeting":  {"type": "social", "severity": "low", "show_resources": False, "base": "Hello! I'm here to listen and support you. What's on your mind today?"},
    "farewell":  {"type": "social", "severity": "low", "show_resources": False, "base": "Thank you for talking with me. Please take care of yourself. Remember, if you need support, I'm always here."},
    "gratitude": {"type": "social", "severity": "low", "show_resources": False, "base": "I'm glad I could help. That's what I'm here for. Feel free to reach out anytime you need someone to talk to."},
    # ── Information / general query ───────────────────────────────────────
    "rag_query": {
        "type": "supportive", "severity": "low", "show_resources": False,
        "base": (
            "I hear you, and I want to give you a useful answer."
            " Based on what you've shared, I'm here to support you through this — whatever that looks like for you."
            " Can you tell me a bit more about what's going on right now so I can tailor what I share?"
        ),
    },
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
        "rag_query":         "I'm here and listening. What would be most helpful to talk through right now?",
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
        "behaviour_sleep", "behaviour_fatigue", "behaviour_aggression", "behaviour_exercise",
        "trigger_stress", "trigger_grief", "trigger_relationship", "trigger_financial",
        "addiction_alcohol", "addiction_drugs", "addiction_gaming", "addiction_nicotine",
        "addiction_gambling", "addiction_social_media", "addiction_work",
        "addiction_food", "addiction_shopping", "addiction_pornography",
        "relapse_disclosure", "rag_query",
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
                    # Split into sentences and remove only the LAST trailing question
                    # sentence — not the whole paragraph.  Templates are single-paragraph
                    # strings so naively blanking the line erases the entire body.
                    sentences = re.split(r'(?<=[.!?])\s+', line)
                    if sentences and sentences[-1].strip().endswith('?'):
                        sentences.pop()
                        stripped_question = True
                    lines[i] = ' '.join(sentences)
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
        specialized = self._get_addiction_aware_base(intent, template, context_vector, addiction_type, addictions, user_message=user_message)
        # _get_addiction_aware_base returns None when no specialized handler matched;
        # fall back to the intents.json response pool, selected by risk level.
        if specialized is not None:
            base_response = specialized
        else:
            base_response = self._select_from_pool(intent, template, context_vector)
        if context_vector:
            personalization = self._build_personalization(intent, context_vector, addiction_type=addiction_type)
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

    def _get_addiction_aware_base(self, intent: str, template: Dict, context_vector=None, addiction_type: Optional[str] = None, addictions: Optional[List[dict]] = None, user_message: str = "") -> str:
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
                    "Thank you for telling me — that honesty takes real courage."
                    " Try to hold off any harsh self-judgment for today and ask yourself what was happening in the hours before you drank."
                    " What do you think led up to it?"
                ),
                "drugs": (
                    "Thank you for sharing that — saying it out loud is a protective step."
                    " Try to hold off any harsh self-judgment and ask yourself what was happening in the hours before you used."
                    " What do you think led up to it?"
                ),
                "gaming": (
                    "Thank you for being direct about this slip — a lapse doesn't mean you've failed."
                    " Try asking yourself what need gaming was meeting in that moment, without blame."
                    " What was going on when it happened?"
                ),
                "social_media": (
                    "Thank you for sharing this so openly — a return to compulsive scrolling doesn't wipe out the work you've done."
                    " Try to gently notice what you were feeling right before the slip."
                    " What was the scrolling helping you cope with?"
                ),
                "nicotine": (
                    "Thank you for telling me — nicotine relapse is very common, especially under stress, and doesn't erase your effort."
                    " Try to treat this moment as information rather than self-criticism."
                    " What was happening just before you smoked?"
                ),
                "smoking": (
                    "Thank you for telling me — nicotine relapse is very common, especially under stress, and doesn't erase your effort."
                    " Try to treat this moment as information rather than self-criticism."
                    " What was happening just before you smoked?"
                ),
                "gambling": (
                    "Thank you for naming this — a slip doesn't define you or your recovery."
                    " Try to understand the moment with curiosity rather than judgment — lapses during high-pressure periods are part of the pattern to learn from."
                    " What was going on right before the bet?"
                ),
            }
            return _RELAPSE.get(addtype) or None

        # ── SLEEP responses (tailored per addiction type) ─────────────────────
        if intent == "behaviour_sleep":
            _SLEEP: Dict[str, str] = {
                "alcohol": (
                    "Sleep and alcohol are deeply linked — alcohol suppresses REM sleep and leaves you more exhausted, not less."
                    " Try one alcohol-free night and notice how you feel the next morning."
                    " How has sleep been affecting you lately?"
                ),
                "drugs": (
                    "Many substances disrupt sleep architecture even after stopping — this is called post-acute withdrawal and can last weeks."
                    " Start with one consistent wake time each morning, even if you slept poorly — it anchors your sleep cycle."
                    " How long has sleep been difficult?"
                ),
                "gaming": (
                    "Late-night gaming raises cortisol and suppresses melatonin, making it genuinely harder to wind down — this is physiology, not willpower."
                    " Try stopping all screens at least an hour before bed tonight."
                    " What time are you usually gaming until?"
                ),
                "social_media": (
                    "Late-night scrolling keeps your nervous system alert through blue light and emotional triggers."
                    " Try charging your phone outside the bedroom tonight — even that one change can shift your sleep significantly."
                    " What time do you usually put your phone down?"
                ),
                "nicotine": (
                    "Nicotine is a stimulant — smoking in the evening makes it genuinely harder to fall and stay asleep."
                    " Try cutting nicotine after 6 pm tonight and see if it makes a difference."
                    " How many hours of sleep are you typically getting?"
                ),
                "smoking": (
                    "Nicotine is a stimulant — smoking in the evening makes it genuinely harder to fall and stay asleep."
                    " Try cutting nicotine after 6 pm tonight and see if it makes a difference."
                    " How many hours of sleep are you typically getting?"
                ),
                "gambling": (
                    "Financial stress and rumination from gambling often disrupt sleep — your mind keeps running the numbers."
                    " Try a brief journaling practice before bed to get the worries out of your head and onto paper."
                    " What's been keeping you awake?"
                ),
            }
            return _SLEEP.get(addtype) or None

        # ── COMORBIDITY responses (known secondary addiction — escalated) ──────
        if is_comorbidity:
            patient_label  = _ADDICTION_LABEL.get(addtype, addtype.replace("_", " "))
            craving_label  = _CRAVING_LABEL.get(intent, intent.replace("addiction_", "").replace("_", " "))
            return (
                f"I want to make sure we take this seriously — you're managing both {patient_label} and {craving_label}, and when both are active the risk is significantly higher."
                f" Please reach out to your counsellor or support team specifically about this, as dual-addiction recovery benefits greatly from integrated treatment."
                " Is there something specific that's activated this urge today?"
            )

        # ── PRIMARY craving responses ─────────────────────────────────────────
        if is_primary:
            # ── Context-sensitive sub-routing for addiction_drugs (alcohol) ──
            # Messages that are NOT active cravings but relate to awareness,
            # concern, information-seeking, or harm-reduction intent.
            if addtype in ("alcohol", "drugs") and intent == "addiction_drugs":
                msg_lc = (user_message or "").lower()
                # Family / social concern messages
                _family_words = ("worried", "concerned", "think i have", "my family", "my wife",
                                 "my husband", "my partner", "my friends", "people say",
                                 "others say", "everyone says", "told me i", "said i drink")
                # Information-seeking / factual questions
                _info_words = ("how many", "how much", "what is", "is it bad", "is that a lot",
                               "what counts", "what are the", "what does", "how do i",
                               "how can i", "can you help", "can you actually", "help me",
                               "can i", "tips", "advice", "what should i", "what can i",
                               "get through tonight", "get through today", "manage my",
                               "cut back", "cut down", "reduce", "moderate")
                # Drinking-to-cope context
                _cope_words  = ("to unwind", "to relax", "to take the edge off",
                                "after work", "after a long day", "after a hard day",
                                "when stressed", "when things get hard", "to cope", "to numb")

                if any(w in msg_lc for w in _family_words):
                    return (
                        "It takes real honesty to share that — when the people closest to us notice a pattern, it's worth sitting with."
                        " Recovery support works best when family concern is met with curiosity rather than defence."
                        " What has your own gut been telling you about your drinking?"
                    )
                if any(w in msg_lc for w in _info_words):
                    return (
                        "That's an important question, and asking it shows real self-awareness."
                        " The recommended low-risk guideline is no more than 14 units a week (about 6 pints of beer or 10 small glasses of wine), spread over several days with alcohol-free days in between."
                        " Where does your current drinking sit compared to that?"
                    )
                if any(w in msg_lc for w in _cope_words):
                    return (
                        "Using alcohol to decompress after stress is very common — and very understandable."
                        " The difficulty is that alcohol disrupts the nervous system's real recovery, so the relief is short-lived and often deepens the stress cycle."
                        " What else helps you decompress when things feel overwhelming?"
                    )

            _PRIMARY: Dict[str, str] = {
                "alcohol": (
                    "Cravings for alcohol are powerful and recognising them is already a sign of strength."
                    " Try delaying for 15 minutes by doing something physical — a walk, a glass of water, or stepping outside."
                    " What's driving the urge right now?"
                ),
                "drugs": (
                    "Cravings during recovery are expected — not a sign of failure."
                    " Try riding this out for 15 minutes: the urge will peak and then weaken if you don't act on it."
                    " What's driving the urge right now?"
                ),
                "gaming": (
                    "The pull to game right now is real, and recognising it before acting is the hardest part."
                    " Set a 15-minute timer and do something physical or social before deciding whether to open a game."
                    " What's going on today that's making the urge feel stronger?"
                ),
                "social_media": (
                    "The pull to scroll can feel automatic — almost like muscle memory."
                    " Put your phone in another room for 20 minutes before deciding whether to open the app."
                    " What are you hoping to feel or find when you open it?"
                ),
                "nicotine": (
                    "Nicotine cravings peak around 3–5 minutes and then pass — you just need to get through the window."
                    " Try the 4D technique right now: Delay, Deep breaths, Drink water, Do something with your hands."
                    " What triggered this craving?"
                ),
                "smoking": (
                    "Nicotine cravings peak around 3–5 minutes and then pass — you just need to get through the window."
                    " Try the 4D technique right now: Delay, Deep breaths, Drink water, Do something with your hands."
                    " What triggered this craving?"
                ),
                "gambling": (
                    "The urge to gamble is real and treatable, and you've done the right thing by naming it."
                    " Call the National Gambling Helpline right now — UK: 0808 8020 133 / US: 1-800-522-4700 — a brief call can interrupt the urge."
                    " What's driving the urge today?"
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
                    f"When someone managing a {patient_label} addiction starts craving {craving_label}, it's often a sign of cross-addiction — the brain seeking a different dopamine source."
                    f" Please raise this with your counsellor or support network before acting on it."
                    " Is there something specific that triggered this craving today?"
                )

            # ── Alcohol/drugs patient craving gambling ──
            if addtype in ("alcohol", "drugs") and intent == "addiction_gambling":
                return (
                    f"For someone managing {patient_label} recovery, gambling urges carry extra risk — the same impulsivity pathways are heavily activated by both."
                    " Please speak with your counsellor or sponsor before acting on this urge."
                    " What's driving the urge toward gambling right now?"
                )

            # ── Substance patient craving a behavioural outlet (gaming/social_media) ──
            if addtype in ("alcohol", "drugs") and intent in ("addiction_gaming", "addiction_social_media"):
                return (
                    f"The urge toward {craving_label} when things feel difficult is very common in {patient_label} recovery — the same underlying need is seeking a different route."
                    " It's worth asking yourself: is this urge occasional, or is it becoming compulsive and hard to resist?"
                    f" If it's becoming compulsive, when did you notice the {craving_label} pull getting stronger?"
                )

            # ── Nicotine patient craving anything else ──
            if addtype in ("nicotine", "smoking") and intent != "addiction_nicotine":
                return (
                    f"Reaching toward {craving_label} is often a sign that something feels unmanageable, and cross-cravings are common during nicotine cessation."
                    f" Recognise the urge for what it is — a craving, not a necessity — and give it 15 minutes before deciding."
                    f" What's the underlying feeling driving the urge toward {craving_label}?"
                )

            # ── Gambling patient craving anything else ──
            if addtype == "gambling" and intent != "addiction_gambling":
                return (
                    f"Cross-craving is common in gambling recovery — the brain seeks stimulation or escape through a different outlet."
                    f" Ask yourself honestly: is this urge toward {craving_label} occasional, or is it starting to feel compulsive?"
                    " What's the feeling driving this urge right now?"
                )

            # ── Generic cross-addiction fallback (any remaining combination) ──
            return (
                f"Reaching toward {craving_label} while managing your {patient_label} recovery is worth paying attention to — cross-addiction is very common and doesn't mean you're doing anything wrong."
                f" The key question is whether this urge is occasional or becoming compulsive."
                " What's driving the urge toward this right now?"
            )

        # ── Normalize "smoking" → "nicotine" for shared-response lookups ──────
        _norm = "nicotine" if addtype == "smoking" else addtype

        # ── MOOD responses (tailored per addiction type) ───────────────────────
        _MOOD: Dict[str, Dict[str, str]] = {
            "mood_sad": {
                "alcohol": (
                    "I hear that you're feeling really low, and that matters."
                    " Try texting one person you trust right now — even just 'I'm struggling today' — rather than turning to a drink."
                    " What's behind the sadness?"
                ),
                "drugs": (
                    "Feeling low in recovery is hard, and I hear you."
                    " Try reaching out to your sponsor or counsellor today — this kind of low mood is worth talking through with someone who gets it."
                    " What's going on?"
                ),
                "gaming": (
                    "I hear you — feeling sad and wanting to lose yourself in a game makes complete sense."
                    " Try sitting with the feeling for just 5 minutes before opening a game; even that small pause can help."
                    " Is there something specific going on?"
                ),
                "social_media": (
                    "I'm sorry you're feeling this way — sadness and scrolling make a tough combination."
                    " Step away from social media for at least an hour right now; it often deepens low mood rather than lifting it."
                    " What's going on for you today?"
                ),
                "nicotine": (
                    "I hear that you're feeling down, and I want to acknowledge that."
                    " Be gentle with yourself today — if you're in a quit attempt, some of this low mood is your brain adjusting and it does improve."
                    " What's driving the sadness?"
                ),
                "gambling": (
                    "Sadness in gambling recovery is very real and very common, and I hear you."
                    " Be careful not to let this feeling push you toward gambling to chase a mood boost — that cycle deepens rather than relieves."
                    " Is the sadness connected to your gambling situation, or something else?"
                ),
            },
            "mood_anxious": {
                "alcohol": (
                    "Anxiety is really hard to sit with, and I hear you."
                    " Before reaching for a drink, try the 5-4-3-2-1 grounding technique: name 5 things you can see, 4 you can touch, 3 you can hear."
                    " What's generating the anxiety today?"
                ),
                "drugs": (
                    "Anxiety in recovery is very common and I hear you."
                    " Try slow diaphragmatic breathing right now: inhale for 4 counts, hold for 4, exhale for 6."
                    " What's specifically making you feel anxious?"
                ),
                "gaming": (
                    "Anxiety is really uncomfortable to sit with, and the pull to game to feel in control makes sense."
                    " Try a 10-minute walk outside before going online — it reduces cortisol more effectively than gaming does."
                    " What are you anxious about?"
                ),
                "social_media": (
                    "Social media and anxiety often push each other higher, and I hear you."
                    " Put your phone down for the next hour — even that brief break measurably lowers stress hormones."
                    " What's making you feel anxious today?"
                ),
                "nicotine": (
                    "Anxiety and nicotine have a complicated relationship — the cigarette often causes the anxiety it seems to fix."
                    " Try slow breathing for 2 minutes before you decide whether to smoke: inhale for 4, hold for 4, exhale for 6."
                    " What's making you feel anxious right now?"
                ),
                "gambling": (
                    "Anxiety and gambling often push each other, and I hear you."
                    " Before acting on any urge to gamble, try the 5-4-3-2-1 grounding technique: name 5 things you can see, 4 you can touch, 3 you can hear."
                    " What's at the root of the anxiety right now?"
                ),
            },
            "mood_angry": {
                "alcohol": (
                    "Anger is valid information, and I hear you."
                    " Put distance between the feeling and any decision to drink right now — alcohol lowers impulse control and makes anger harder to manage."
                    " What's made you angry today?"
                ),
                "drugs": (
                    "Anger is a natural part of recovery, and I hear you."
                    " Try channelling it physically first — a brisk walk or even punching a pillow — then sit with what's underneath it."
                    " What are you angry about?"
                ),
                "gaming": (
                    "Anger can feel really intense, and I hear you."
                    " Step away from the game for 20 minutes before going back — anger during gaming often spirals when you keep playing."
                    " Is this gaming-related anger, or is something else going on?"
                ),
                "social_media": (
                    "Social media is designed to amplify outrage, and I hear you."
                    " Close the app entirely for the next few hours before reacting to anything — the anger will feel different after some distance."
                    " What's made you angry today?"
                ),
                "nicotine": (
                    "Irritability and anger are among the most common nicotine withdrawal symptoms, and I hear you."
                    " This peaks around 2–3 days after stopping and then decreases — try a 10-minute walk to get through the peak."
                    " Is this withdrawal-related, or is something else driving the anger?"
                ),
                "gambling": (
                    "Anger is very common in gambling recovery, and I hear you."
                    " Be careful not to let the angry, defiant feeling push you toward gambling to 'take control' — reach out to your support before acting."
                    " What's made you angry today?"
                ),
            },
            "mood_lonely": {
                "alcohol": (
                    "Loneliness is one of the most common triggers for drinking, and I hear you."
                    " Try calling one person from your recovery network right now — even a 5-minute call can shift things meaningfully."
                    " What's driving the loneliness?"
                ),
                "drugs": (
                    "Loneliness and substance use are deeply connected, and recovery can feel isolating — I hear you."
                    " Try reaching out to your NA, AA, or SMART Recovery group today — connection is one of the most protective things in recovery."
                    " What does your support network look like right now?"
                ),
                "gaming": (
                    "Loneliness is real, and I hear you."
                    " Try making one real-world connection this week — a text, a call, a coffee — even if gaming communities feel safer right now."
                    " What's making you feel lonely?"
                ),
                "social_media": (
                    "Feeling lonely despite being constantly connected is one of social media's painful paradoxes, and I hear you."
                    " Try sending one direct, personal message to someone today instead of posting — real reciprocal contact feels different."
                    " What's going on?"
                ),
                "nicotine": (
                    "Loneliness can be a strong trigger for smoking, and I hear you."
                    " Think of one other way to create a social moment today that doesn't involve a cigarette — a walk with someone, a phone call."
                    " What's making you feel lonely right now?"
                ),
                "gambling": (
                    "Loneliness and gambling often go hand in hand, and I hear you."
                    " Reach out to one trusted person today — a friend, family member, or your support group — connection is one of the strongest guards against relapse."
                    " Is there someone you could reach out to right now?"
                ),
            },
            "mood_guilty": {
                "alcohol": (
                    "Guilt in alcohol recovery is really painful to carry, and I hear you."
                    " Try treating yourself with the compassion you'd offer a good friend — the cycle of drinking to escape guilt tends to deepen it, not resolve it."
                    " Is this guilt connected to your drinking, or something else?"
                ),
                "drugs": (
                    "People in recovery often carry enormous guilt, and I hear you."
                    " Try reminding yourself: the fact that you feel this means your values are intact — guilt is information, not the whole story of who you are."
                    " What's the guilt about, if you'd like to share?"
                ),
                "gaming": (
                    "Guilt and gaming often go together, and I hear you."
                    " Try making one small act of follow-through today — one call, one task completed — to start shifting the cycle."
                    " What does the guilt feel like it's about?"
                ),
                "social_media": (
                    "Guilt about time on social media is really common, and I hear you."
                    " Ask yourself: is this guilt about something you've actually done, or is the platform engineering you to feel less-than?"
                    " What's the guilt about?"
                ),
                "nicotine": (
                    "Guilt about smoking is very common, and I hear you."
                    " Be gentle with yourself — nicotine is genuinely addictive, and shame rarely creates lasting change; compassion does."
                    " What's the guilt about today?"
                ),
                "gambling": (
                    "Guilt is often the heaviest part of gambling recovery, and I hear you."
                    " Try sharing just one piece of this burden with your counsellor or support group today — you don't have to carry it alone."
                    " What would feel like a manageable first step?"
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
                    "Stress is one of the most common triggers for alcohol use, and I hear you."
                    " Try the HALT check right now: are you Hungry, Angry, Lonely, or Tired — addressing those first can take the edge off before reaching for a drink."
                    " What's the specific stressor?"
                ),
                "drugs": (
                    "Stress is the number one trigger for relapse, and I hear you."
                    " Lean on your support system right now rather than white-knuckling it alone — call your sponsor or a friend in recovery."
                    " What's stressing you right now?"
                ),
                "gaming": (
                    "Stress and the pull to game often go hand in hand, and I hear you."
                    " Try a 20-minute walk before going online — it reduces cortisol more effectively than gaming does."
                    " What's stressing you?"
                ),
                "social_media": (
                    "Stress and scrolling tend to make each other worse, and I hear you."
                    " Try something physically grounding instead — a short walk, making tea, or calling someone."
                    " What's the stressor?"
                ),
                "nicotine": (
                    "Stress is one of the most powerful smoking triggers, and I hear you."
                    " Try the 4D technique right now: Delay 5 minutes, Deep breathe, Drink water, Do something else."
                    " What's stressing you?"
                ),
                "gambling": (
                    "Stress is a major gambling trigger, and I hear you."
                    " Before acting on any urge to gamble, try writing down the stressor to get it out of your head."
                    " What's the stressor today?"
                ),
            },
            "trigger_relationship": {
                "alcohol": (
                    "Relationship stress and the urge to drink often go together, and I hear you."
                    " Try giving yourself 30 minutes before making any decisions — alcohol lowers impulse control and tends to make relationship conflicts worse."
                    " What's going on in the relationship?"
                ),
                "drugs": (
                    "Relationships can be one of the most painful parts of recovery, and I hear you."
                    " Reach out to your sponsor or counsellor today rather than managing this alone — relationship stress is a high-risk trigger."
                    " What's happening?"
                ),
                "gaming": (
                    "Relationships and gaming can come into real conflict, and I hear you."
                    " If someone important to you has raised concerns, try listening openly before responding — it's often a signal worth taking seriously."
                    " What's going on in the relationship?"
                ),
                "social_media": (
                    "Relationship stress and social media tend to amplify each other, and I hear you."
                    " Step away from social media while you're dealing with this — scrolling usually makes it harder to resolve, not easier."
                    " What's the relationship situation?"
                ),
                "nicotine": (
                    "Relationship stress and the urge to smoke often go together, and I hear you."
                    " Try taking 10 minutes to yourself before deciding whether to smoke — a brief pause between the feeling and the action matters."
                    " What's going on?"
                ),
                "gambling": (
                    "Relationship stress and gambling are deeply linked, and I hear you."
                    " Reach out to your counsellor or GamCare (UK: 0808 8020 133) today — relationship strain often escalates gambling risk."
                    " What's the relationship situation?"
                ),
            },
            "trigger_financial": {
                "alcohol": (
                    "Financial pressure is real and exhausting, and I hear you."
                    " Before reaching for a drink, try writing down the one financial concern weighing on you most right now — externalising it can reduce its grip."
                    " What's the financial situation?"
                ),
                "drugs": (
                    "Financial pressure in recovery is genuinely hard, and I hear you."
                    " Contact Citizens Advice or your local support services today — financial stress is a relapse trigger worth addressing directly."
                    " What's going on?"
                ),
                "gaming": (
                    "Gaming costs can add up quickly, and I hear you."
                    " Try calculating the actual monthly spend honestly — that number can be clarifying and motivating."
                    " What's the financial situation?"
                ),
                "social_media": (
                    "Financial stress and social media can intensify each other, and I hear you."
                    " Consider unfollowing aspirational or spending-trigger accounts while you're under financial pressure."
                    " What's the financial situation?"
                ),
                "nicotine": (
                    "The financial cost of smoking is significant, and it's worth taking seriously."
                    " Try calculating your annual smoking spend — for many people that number becomes a powerful motivator to quit."
                    " What's going on with the financial pressure?"
                ),
                "gambling": (
                    "Financial stress and gambling are deeply linked, and I hear you."
                    " Please reach out to GamCare (UK: 0808 8020 133) and StepChange (debt support, 0800 138 1111) today — specialist help for both is available."
                    " What's the financial situation right now?"
                ),
            },
            "trigger_grief": {
                "alcohol": (
                    "I'm truly sorry for your loss — grief is one of the heaviest things to carry."
                    " If a craving is present, try urge surfing: notice the craving like a wave, don't fight it, and let it peak and pass — it usually does within 15 minutes."
                    " Would you like to tell me what's happened?"
                ),
                "drugs": (
                    "I'm so sorry — grief is one of the most painful experiences, and I hear you."
                    " Try reaching out to a grief counsellor or therapist today who also understands substance use, so both can be held together."
                    " What's happened?"
                ),
                "gaming": (
                    "I'm sorry for what you're going through — grief is overwhelming, and I hear you."
                    " Allow yourself one brief, intentional moment today to sit with the feeling rather than escaping it."
                    " What's happened?"
                ),
                "social_media": (
                    "I'm really sorry — grief and social media make a painful combination."
                    " Consider stepping back from social media during this time — it often makes grief harder, not easier."
                    " What's happened?"
                ),
                "nicotine": (
                    "I'm sorry for what you're going through — grief is overwhelming, and reaching for something familiar makes sense."
                    " Be gentle with yourself, and let your GP or stop smoking service know what's happening so they can adjust their support."
                    " What's happened?"
                ),
                "gambling": (
                    "I'm sorry for what you're going through — grief can be a powerful gambling trigger."
                    " If the urge comes on, call the National Gambling Helpline before acting: UK 0808 8020 133."
                    " What's happened?"
                ),
            },
            "trigger_trauma": {
                "alcohol": (
                    "Trauma and alcohol use are very closely linked, and I hear you."
                    " Try grounding yourself right now: name 5 things you can see, 4 you can touch, 3 you can hear."
                    " Are you currently working with anyone on both the trauma and the alcohol?"
                ),
                "drugs": (
                    "Trauma and substance use are deeply connected, and I hear you."
                    " Try one grounding breath right now — inhale for 4, hold for 4, exhale for 6 — before we talk more."
                    " Are you getting support for the trauma as well as the substance use?"
                ),
                "gaming": (
                    "Trauma and gaming can connect in complex ways, and I hear you."
                    " Try grounding yourself right now: name 5 things you can see in the room around you."
                    " Are you getting any support for the trauma?"
                ),
                "social_media": (
                    "Trauma and social media can interact in really difficult ways, and I hear you."
                    " Consider a significant break from social media while you're working through this — it often re-triggers rather than helps."
                    " Are you getting support for what you've been through?"
                ),
                "nicotine": (
                    "Trauma and smoking are often connected, and I hear you."
                    " Make sure any quit attempt includes mental health support alongside nicotine support — please raise this with your GP."
                    " Are you getting support for the trauma?"
                ),
                "gambling": (
                    "Trauma and gambling can be closely connected, and I hear you."
                    " Please make sure your gambling support is trauma-aware — GamCare (UK: 0808 8020 133) can direct you to appropriate services."
                    " Are you getting support for the underlying trauma?"
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
                    "Nutrition and alcohol are deeply connected, and eating well in recovery really matters."
                    " Try stabilising your meals today with regular times and protein-rich food — it can also help reduce cravings."
                    " What's going on with your eating right now?"
                ),
                "drugs": (
                    "Appetite changes in recovery are very normal, and I hear you."
                    " Try making regular meals a priority today — even small, consistent ones — as food stability supports the neurological recovery process."
                    " What's going on with your eating?"
                ),
                "gaming": (
                    "Skipping or forgetting meals during gaming sessions is really common, and it affects mood and energy."
                    " Try setting a deliberate meal break away from the screen today."
                    " What's going on?"
                ),
                "social_media": (
                    "Social media and eating have a complicated relationship, and I hear you."
                    " If food-related content is affecting how you feel about eating, try unfollowing those accounts today."
                    " What's going on with your eating?"
                ),
                "nicotine": (
                    "Eating and smoking are closely linked, and weight concerns are one of the most common barriers to quitting."
                    " Talk to your GP specifically about this — they can help you plan for it so it doesn't stop you from trying."
                    " What's going on with eating?"
                ),
                "gambling": (
                    "Financial stress from gambling can directly affect eating, and I hear you."
                    " If food is a concern, please reach out to local support services or a food bank today alongside your gambling support."
                    " What's going on?"
                ),
            },
            "behaviour_exercise": {
                "alcohol": (
                    "Physical activity is one of the most powerful tools in alcohol recovery, and it's great you're thinking about it."
                    " Start today with a 20-minute brisk walk — even that has measurable effects on craving intensity."
                    " What's your relationship with exercise at the moment?"
                ),
                "drugs": (
                    "Exercise in recovery is genuinely powerful — it helps rebuild the systems substances disrupt."
                    " Try a short daily walk as a starting point — even 15 minutes creates structure and shifts mood."
                    " What's your relationship with physical activity?"
                ),
                "gaming": (
                    "Physical activity and gaming work well together in a balanced approach."
                    " Try one active session today — even a 20-minute walk — to see how it shifts your energy and mood."
                    " What's your relationship with physical activity right now?"
                ),
                "social_media": (
                    "Exercise and stepping away from screens are two of the best things you can do for mental health."
                    " Try making a daily offline activity a consistent anchor — even a 20-minute walk without your phone."
                    " What does your physical activity look like at the moment?"
                ),
                "nicotine": (
                    "Exercise and quitting smoking are strongly linked — physical activity reduces cravings and helps manage weight concerns."
                    " Try scheduling a short walk to coincide with your most common smoking urges today."
                    " What's your current activity level?"
                ),
                "gambling": (
                    "Exercise during high-urge periods is one of the most effective alternatives to gambling."
                    " Plan a physical activity specifically for the times you're most tempted — often evenings or weekends."
                    " What does your physical activity look like?"
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

        # ── Generic addiction_drugs fallback when addiction_type is unknown ──
        # Fires when onboarding profile is missing from the DB (no registered
        # addiction type).  Provides an empathetic, alcohol-appropriate response
        # rather than falling through to the generic intents.json pool.
        if intent == "addiction_drugs":
            return (
                "Recognising that alcohol is playing a bigger role than you'd like takes real courage."
                " Try delaying for 15 minutes — do something physical or drink a glass of water before deciding anything."
                " The urge will peak and pass, usually within 15 to 30 minutes."
            )

        return None

    def _build_personalization(self, intent: str, context_vector, addiction_type: Optional[str] = None) -> Optional[str]:
        if not context_vector:
            return None

        risk = getattr(getattr(context_vector, "risk", None), "risk_level", "") or ""
        risk_lc = str(risk).lower()
        onboarding = getattr(context_vector, "onboarding", None)
        checkin = getattr(context_vector, "checkin", None)

        addiction_value = addiction_type or getattr(onboarding, "addiction_type", None)
        addiction_label = self._humanize_addiction_type(addiction_value)

        if risk_lc == "critical":
            return "I can hear that you're going through something really difficult right now."

        signals = self._summarize_patient_state(checkin)

        if addiction_label and signals:
            return f"I understand you're working on recovery from {addiction_label}, and {signals}."
        if addiction_label:
            return f"I understand you're working on recovery from {addiction_label}."
        if signals:
            return f"Given what your system is carrying, {signals}."
        if getattr(context_vector, "session_message_count", 0) > 1:
            return "Thank you for continuing to open up with me."
        return None

    def _humanize_addiction_type(self, addiction_type: Optional[str]) -> Optional[str]:
        if not addiction_type:
            return None
        labels = {
            "alcohol": "alcohol",
            "drugs": "substance use",
            "gaming": "gaming",
            "social_media": "social media",
            "nicotine": "nicotine",
            "smoking": "smoking",
            "gambling": "gambling",
            "food": "compulsive eating",
            "work": "overworking",
            "shopping": "compulsive shopping",
            "pornography": "compulsive sexual content use",
        }
        norm = str(addiction_type).lower().strip().replace(" ", "_").replace("-", "_")
        return labels.get(norm, norm.replace("_", " "))

    def _summarize_patient_state(self, checkin) -> Optional[str]:
        if not checkin:
            return None

        parts: List[str] = []
        craving = getattr(checkin, "craving_intensity", None)
        sleep = getattr(checkin, "sleep_quality", None)
        mood = (getattr(checkin, "todays_mood", "") or "").lower()

        if isinstance(craving, (int, float)) and craving >= 7:
            parts.append("strong cravings may be making everything feel louder")
        elif isinstance(craving, (int, float)) and craving >= 5:
            parts.append("some cravings are already in the background")

        if isinstance(sleep, (int, float)) and sleep <= 4:
            parts.append("low sleep can make recovery moments feel heavier")
        elif isinstance(sleep, (int, float)) and sleep <= 6:
            parts.append("average sleep can still leave the nervous system a bit exposed")

        if mood in {"anxious", "stress", "stressed", "panic", "nervous"}:
            parts.append("anxiety may be tightening the nervous system")
        elif mood in {"sad", "low", "depressed", "lonely", "angry", "guilty"}:
            parts.append(f"a {mood} mood state may be adding extra pressure")

        if not parts:
            return None
        if len(parts) == 1:
            return parts[0]
        return parts[0] + " and " + parts[1]

    def _generate_fallback(self, intent: str, user_message: str, context_vector=None) -> str:
        if self.rag_handler:
            try:
                rag_response = self.rag_handler(user_message)
                if rag_response:
                    return rag_response
            except Exception as e:
                logger.error(f"RAG handler failed: {e}")

        personalization = self._build_personalization(intent, context_vector)
        fallback_pool = [
            "Thank you for sharing that. We can take this one step at a time.",
            "What you are naming matters, and it makes sense to slow this down rather than rush past it.",
            "There is enough here to work with carefully, without forcing an answer all at once.",
            "We do not have to solve everything right now; the next honest step is enough for this moment.",
        ]
        base = random.choice(fallback_pool)

        if personalization:
            return personalization + "\n\n" + base
        return base

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

        NOTE: medication-unsafe patterns are intentionally NOT checked against the
        patient's incoming message here — patients routinely describe their own
        prescriptions (e.g. "It's prescribed by my doctor"). Medication safety checks
        on generated responses are handled separately in validate_response().

        Crisis detection now uses CrisisDetector (3-tier: exact → fuzzy → semantic).
        """
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
