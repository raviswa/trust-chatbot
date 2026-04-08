"""
chatbot_engine.py — Mental Health Chatbot Main Engine
"""
import json, random, re, logging
from datetime import datetime
from typing import Optional, List, Dict

import ollama
from language_sanitiser import sanitise_response, check_self_stigma, PERSON_FIRST_RULES
from rag_pipeline import retrieve, assemble_context, format_citations
from ethical_policy import (
    check_policy, validate_crisis_response,
    POLICY_DISCLOSURE_SHORT, POLICY_SUMMARY
)
from trust_layers import (
    apply_layer5_close,
    generate_clarifying_question,
    generate_trust_opening,
    is_ambiguous_message,
    layer4_resolution_suffix,
    register_video_shown,
    trust_context_or_default,
    trust_select_video,
)
from db import (
    ensure_patient, get_patient, get_patient_sessions,
    get_patient_full_history, get_checkin_status,
    get_recent_checkin_activity,
    get_session_scores, save_patient_score,
    ensure_session, update_session_meta, save_message,
    log_policy_violation, log_crisis_event,
    get_pending_crisis_events, get_policy_violation_summary,
    get_session_history, get_all_sessions, get_crisis_sessions,
    get_conversation_stats, get_top_intents
)
from video_map import get_video, get_score_group, get_score_label

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Load intents ─────────────────────────────────────────────────────────────

def _load_intents(path="intents.json"):
    with open(path) as f:
        raw = re.sub(r"//.*", "", f.read())
        return json.loads(raw)

INTENTS    = _load_intents()
INTENT_MAP = {i["tag"]: i for i in INTENTS["intents"]}
PATTERN_TAG_MAP = {}
for _intent in INTENTS["intents"]:
    for _pat in _intent.get("patterns", []):
        PATTERN_TAG_MAP[_pat.lower()] = _intent["tag"]

# ── Hard-coded safety responses ──────────────────────────────────────────────

MEDICATION_REFUSAL = """
I’m not able to recommend medications, dosages, or prescriptions.

Medication decisions require assessment by a licensed healthcare 
professional who can evaluate your symptoms, medical history, and 
possible risks.

For medication guidance, please consult:

• Your treating psychiatrist or physician
• A licensed mental health clinic
• Emergency services if symptoms feel urgent

I’m here to provide general information and support if that would help.
""".strip()

CRISIS_RESPONSE = """
I'm really sorry that you're going through something so painful right now. 
What you're describing sounds very difficult, and you deserve support.

You don't have to face this alone. If you can, please consider reaching out 
to someone right now who can help keep you safe.

Immediate support options:
• Emergency services: 112 / 911 / 999
• Crisis Text Line: Text HOME to 741741
• International crisis centres: https://www.iasp.info/resources/Crisis_Centres/

If possible, contacting a trusted friend, family member, or mental health 
professional right now can help you get through this moment.

If you'd like, you can also tell me what has been weighing on you.
""".strip()

ABUSE_RESPONSE = """Your safety is the most important thing right now.

If you are in immediate danger, please call emergency services immediately.
  • Emergency Services: 911 / 999 / 112
  • National Domestic Violence Hotline (US): 1-800-799-7233
  • Refuge (UK): 0808 2000 247

You are not alone. This is not your fault.""".strip()

SELF_HARM_RESPONSE = """
Thank you for sharing something so difficult. It sounds like you may be 
coping with a lot of emotional pain right now.

Many people who experience urges to harm themselves are trying to manage 
overwhelming feelings. You deserve understanding and support.

If you can, please consider reaching out today to someone who can support you:

• Emergency services: 112 / 911 / 999
• Crisis Text Line: Text HOME to 741741
• Local mental health professional or helpline

If you feel comfortable, you can tell me what has been happening recently.
""".strip()

SEVERE_DISTRESS_RESPONSE = (
    "I hear you, and I want you to know that what you are feeling matters deeply. "
    "Feelings of hopelessness or emptiness can be overwhelming, "
    "and you do not have to carry this alone.\n\n"
    "Please consider reaching out to someone who can support you right now:\n"
    "\u2022 Emergency services: 112 / 911 / 999\n"
    "\u2022 Crisis Text Line: Text HOME to 741741\n"
    "\u2022 International crisis centres: https://www.iasp.info/resources/Crisis_Centres/\n\n"
    "You deserve support. If you feel comfortable, I am here to listen."
)

PSYCHOSIS_RESPONSE = (
    "Thank you for sharing what you are experiencing. "
    "What you are going through sounds very distressing, "
    "and it is important that you speak with a qualified mental health professional as soon as possible.\n\n"
    "Please reach out for support now:\n"
    "\u2022 Emergency services: 112 / 911 / 999\n"
    "\u2022 Contact your treating psychiatrist or mental health team\n"
    "\u2022 Crisis Text Line: Text HOME to 741741\n\n"
    "If you are in immediate distress or feel unsafe, please call emergency services."
)

TRAUMA_RESPONSE_INTRO = (
    "Thank you for trusting me with something so personal and painful. "
    "What you have been through sounds very difficult, "
    "and it takes real courage to speak about it.\n\n"
    "Trauma affects people in many ways, and your feelings are completely valid. "
    "A trauma-informed therapist can offer support specifically designed for what you are experiencing.\n\n"
    "I am here to listen if you would like to share more, "
    "and I would gently encourage you to reach out to a professional when you feel ready.\n\n"
)

# ── Output safety filter ─────────────────────────────────────────────────────

UNSAFE_PATTERNS = [
    r"i recommend taking",    r"you should take",      r"the dosage is",
    r"\d+\s?mg\b",            r"twice daily",          r"once daily",
    r"take this medication",  r"prescrib",             r"the medication for this is",
    r"start taking",          r"increase the dose",    r"decrease the dose",
    r"three times a day",     r"as needed",            r"titrate",
]

def _is_unsafe(text):
    l = text.lower()
    return any(re.search(p, l) for p in UNSAFE_PATTERNS)

# ── Session memory ───────────────────────────────────────────────────────────

_sessions: Dict[str, dict] = {}

def get_session(sid):
    if sid not in _sessions:
        _sessions[sid] = {
            "history": [], "last_topic": None, "last_topic_label": None,
            "message_count": 0, "severity_flags": [],
            "started_at": datetime.now().isoformat(),
            "continuity_prompt": None,
            "prior_topics": [],
            "trust_videos_shown": [],
        }
    return _sessions[sid]

def update_session(sid, role, content, intent=None, severity=None,
                   citations=None, show_resources=False,
                   patient_id=None, patient_code=None,
                   policy_checked=False, policy_violation=False,
                   policy_violation_type=None):
    # ── In-memory (fast, used for context window) ─────────────
    s = get_session(sid)
    s["history"].append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
    s["message_count"] += 1
    skip = {"greeting","farewell","gratitude","unclear","coping_breathing",
            "coping_journaling","medication_request","rag_query"}
    if intent and intent not in skip:
        s["last_topic"]       = intent
        s["last_topic_label"] = _topic_label(intent)
    if severity and severity not in s["severity_flags"]:
        s["severity_flags"].append(severity)
    # Cache patient identity in session for reuse across turns
    if patient_id:   s["patient_id"]   = patient_id
    if patient_code: s["patient_code"] = patient_code
    # ── PostgreSQL persistence (permanent) ────────────────────
    try:
        _pid      = patient_id   or s.get("patient_id")
        _code     = patient_code or s.get("patient_code")
        is_crisis = intent in {"crisis_suicidal","crisis_abuse","behaviour_self_harm"}
        conv_id   = save_message(
            session_id=sid, role=role, content=content, intent=intent,
            severity=severity, citations=citations or [],
            show_resources=show_resources,
            has_rag_context=bool(citations),
            policy_checked=policy_checked,
            policy_violation=policy_violation,
            policy_violation_type=policy_violation_type,
            patient_id=_pid, patient_code=_code
        )
        update_session_meta(
            session_id=sid, role=role, intent=intent,
            last_topic=_topic_label(intent) if intent and intent not in skip else None,
            last_topic_tag=intent if intent and intent not in skip else None,
            severity=severity, is_crisis=is_crisis,
            crisis_intent=intent if is_crisis else None
        )
        if is_crisis and role == "assistant":
            log_crisis_event(
                session_id=sid, crisis_type=intent,
                trigger_message=s["history"][-2]["content"] if len(s["history"]) >= 2 else "",
                bot_response=content,
                patient_id=_pid, patient_code=_code,
                conversation_id=conv_id
            )
    except Exception as e:
        logger.error(f"DB persist failed (non-fatal): {e}")

def _history_text(sid, n=4):
    return "\n".join(
        ("User" if m["role"]=="user" else "Assistant") + ": " + m["content"]
        for m in get_session(sid)["history"][-n:]
    )

def _topic_label(tag):
    M = {
        "mood_sad":"feelings of sadness","mood_anxious":"anxiety",
        "mood_angry":"anger and frustration","mood_lonely":"loneliness",
        "mood_guilty":"feelings of guilt","behaviour_isolation":"social withdrawal",
        "behaviour_sleep":"sleep difficulties","behaviour_eating":"eating patterns",
        "behaviour_aggression":"managing anger","trigger_stress":"stress management",
        "trigger_trauma":"trauma","trigger_relationship":"relationship challenges",
        "trigger_grief":"grief and loss","trigger_financial":"financial stress",
        "addiction_alcohol":"alcohol use disorder","addiction_drugs":"substance use disorder",
        "addiction_gaming":"gaming habits","addiction_social_media":"social media use",
        "addiction_gambling":"gambling","addiction_food":"emotional eating",
        "addiction_work":"work-life balance","addiction_shopping":"compulsive shopping",
        "addiction_nicotine":"smoking and nicotine use",
        "addiction_pornography":"compulsive behaviour patterns",
    }
    return M.get(tag, "what you shared earlier")

def clear_session(sid):
    _sessions.pop(sid, None)

def get_session_summary(sid):
    s = get_session(sid)
    return {"session_id":sid,"started_at":s["started_at"],
            "message_count":s["message_count"],"last_topic":s["last_topic_label"],
            "severity_flags":s["severity_flags"]}

# ── Intent classification ────────────────────────────────────────────────────

_GREETING   = {"hi","hello","hey","good morning","good afternoon","good evening",
                "good night","howdy","greetings","what's up","how are you","is anyone there"}
_FAREWELL   = {"bye","goodbye","see you","see you later","take care","i have to go",
                "gotta go","talk later","i'm leaving","that's all for now","thanks bye"}
_GRATITUDE  = {"thank you","thanks","thank you so much","that was helpful",
                "you helped me","i appreciate it","cheers","very helpful"}
_MEDICATION = {"medicine","medication","prescribe","prescription","dose","dosage",
                "tablet","capsule","what should i take","can i take","which pill",
                "what medication","milligram"}
_CRISIS     = {"want to die","kill myself","end my life","don't want to be here",
                "thinking about suicide","life is not worth living","give up on life",
                "want to disappear forever","nobody would miss me","can't go on"}
_ABUSE      = {"being abused","someone is hurting me","partner hits me",
                "scared of someone at home","unsafe at home","domestic violence",
                "afraid to go home","someone is controlling me"}
_SELF_HARM  = {"hurt myself","cut myself","self harm","harm my body","burn myself",
                "hit myself","injure myself","punish myself","physical pain helps me cope"}
_SEVERE_DISTRESS = { "hopeless","nothing matters","i feel empty","i feel worthless",
    "no reason to live","life has no meaning","i feel trapped"}

_SUBSTANCE_USE = {  "relapse","craving","can't stop drinking","using again",
    "withdrawal","detox","need alcohol","need drugs"}

_PSYCHOSIS_INDICATORS = { "voices talking to me","hearing voices","people watching me",
    "someone controlling my thoughts","paranoid","they are after me"}

_TRAUMA = { "i was assaulted","i was raped","childhood abuse",
    "trauma memories","flashbacks","nightmares about it"}

def classify_intent(text):
    l = text.lower().strip()
    # Priority 1: Immediate safety — always checked first
    if any(p in l for p in _CRISIS):              return "crisis_suicidal"
    if any(p in l for p in _ABUSE):               return "crisis_abuse"
    if any(p in l for p in _SELF_HARM):           return "behaviour_self_harm"
    # Priority 2: High-severity clinical signals — dedicated tags for targeted responses
    if any(p in l for p in _SEVERE_DISTRESS):     return "severe_distress"
    if any(p in l for p in _PSYCHOSIS_INDICATORS):return "psychosis_indicator"
    if any(p in l for p in _TRAUMA):              return "trigger_trauma"
    if any(p in l for p in _SUBSTANCE_USE):       return "addiction_drugs"
    # Priority 3: Medication block
    if any(p in l for p in _MEDICATION):          return "medication_request"
    # Priority 4: Small talk
    if any(p in l for p in _GREETING):            return "greeting"
    if any(p in l for p in _FAREWELL):            return "farewell"
    if any(p in l for p in _GRATITUDE):           return "gratitude"
    # Priority 5: intents.json pattern match
    for pat, tag in PATTERN_TAG_MAP.items():
        if pat in l: return tag
    # Priority 6: LLM fallback
    return _llm_classify(text)

def _llm_classify(text):
    tags = list(INTENT_MAP.keys()) + ["medication_request","rag_query"]
    prompt = (f"Classify this message into ONE tag from: {', '.join(tags)}\n"
              f"If it is a general health question, return: rag_query\n"
              f"Message: \"{text}\"\nReply with ONLY the tag.")
    try:
        r   = ollama.generate(model="qwen2.5:7b-instruct", prompt=prompt)
        tag = r["response"].strip().lower().strip('"\'')
        return tag if tag in tags else "rag_query"
    except Exception as e:
        logger.error(f"LLM classify failed: {e}")
        return "rag_query"

# ── System prompt builder ────────────────────────────────────────────────────

def _system_prompt(context, history_text, continuity_prompt=None,
                   trust_resolution: Optional[str] = None):
    ctx = context or "No specific context retrieved — respond with general empathetic support."
    continuity_block = (f"\n{continuity_prompt}\n" if continuity_prompt else "")
    trust_block = (f"\n{trust_resolution}\n" if trust_resolution else "")
    return f"""You are a compassionate mental health support assistant.
Your responses are grounded strictly in the provided research document context.

STRICT RULES:
1. Answer ONLY from the retrieved context below.
2. If not in context, say: "I don't have specific information on that in our current documents, but I'm here to listen."
3. NEVER recommend or name any medications, dosages, or prescriptions.
4. NEVER diagnose or provide treatment plans.
5. Always recommend consulting a qualified healthcare professional.
6. Be warm, empathetic, and non-judgmental.
7. Keep the reply concise (roughly 2-4 short lines of text) unless more detail is clearly needed.
{continuity_block}{trust_block}
{PERSON_FIRST_RULES}

RECENT CONVERSATION:
{history_text}

RETRIEVED CONTEXT:
{ctx}"""

# ── Response generators ──────────────────────────────────────────────────────

def _intents_response(tag):
    i = INTENT_MAP.get(tag)
    if i and i.get("responses"):
        return random.choice(i["responses"])
    return "I'm here and listening. Can you tell me more?"

def _topic_bridge(sid, base):
    s     = get_session(sid)
    label = s.get("last_topic_label")
    if not label or s["message_count"] < 2:
        return base
    bridges = [
        f" Whenever you're ready, we can return to {label}.",
        f" I'm here if you'd like to continue exploring {label}.",
        f" Feel free to come back to {label} whenever it feels right.",
    ]
    return base + random.choice(bridges)

def _small_talk(tag, sid, user_input, trust_ctx: Optional[Dict] = None):
    s          = get_session(sid)
    last_topic = s.get("last_topic_label")
    continuity = s.get("continuity_prompt", "")
    bridge_instr = (
        f"\nAt the end, gently mention you can return to '{last_topic}' "
        "whenever they are ready — one sentence only." if last_topic else ""
    )
    continuity_block = f"\n{continuity}\n" if continuity else ""
    prompt = (f"You are a warm, empathetic mental health support assistant.\n"
              f"{continuity_block}\n"
              f"Recent conversation:\n{_history_text(sid)}\n\n"
              f"User just said: \"{user_input}\"\n\n"
              f"Respond warmly and naturally. 2-3 sentences. "
              f"No medications or diagnoses.{bridge_instr}")
    try:
        r     = ollama.generate(model="qwen2.5:7b-instruct", prompt=prompt)
        reply = r["response"].strip()
        if _is_unsafe(reply):
            reply = _topic_bridge(sid, _intents_response(tag))
        else:
            reply = sanitise_response(reply)
        tc = trust_ctx or trust_context_or_default(None, sid)
        return apply_layer5_close(reply, tag, tc, "low")
    except Exception as e:
        logger.error(f"Small talk failed: {e}")
        reply = _topic_bridge(sid, _intents_response(tag))
        tc = trust_ctx or trust_context_or_default(None, sid)
        return apply_layer5_close(reply, tag, tc, "low")

def _contextual_rag(user_input, sid, intent, trust_ctx: Optional[Dict] = None,
                    apply_layer5: bool = True):
    """Intent-filtered RAG for known mental health intents."""
    chunks    = retrieve(user_input, intent=intent)
    context   = assemble_context(chunks)
    citations = format_citations(chunks)
    continuity = get_session(sid).get("continuity_prompt")
    tr_block   = layer4_resolution_suffix()
    system    = _system_prompt(
        context, _history_text(sid), continuity, trust_resolution=tr_block
    )
    try:
        r     = ollama.generate(model="qwen2.5:7b-instruct", system=system, prompt=user_input)
        reply = r["response"].strip()
    except Exception as e:
        logger.error(f"Contextual RAG failed: {e}")
        return {"response": _intents_response(intent), "citations": []}
    if _is_unsafe(reply):
        return {"response": MEDICATION_REFUSAL, "citations": [],
                "policy_checked": False, "policy_violation": False, "policy_violation_type": None}
    # Policy layer check
    policy = check_policy(reply, intent=intent, session_id=sid)
    if policy.violation:
        return {"response": policy.safe_response, "citations": [],
                "policy_checked": True, "policy_violation": True,
                "policy_violation_type": policy.violation_type}
    out = sanitise_response(reply)
    if apply_layer5:
        tc = trust_ctx or trust_context_or_default(None, sid)
        sev = str(INTENT_MAP.get(intent, {}).get("severity", "medium"))
        out = apply_layer5_close(out, intent, tc, sev)
    return {"response": out, "citations": citations,
            "policy_checked": True, "policy_violation": False, "policy_violation_type": None}

def _general_rag(user_input, sid, trust_ctx: Optional[Dict] = None,
                 apply_layer5: bool = True):
    """Unfiltered RAG for general health queries."""
    chunks    = retrieve(user_input, intent=None)
    context   = assemble_context(chunks)
    citations = format_citations(chunks)
    continuity = get_session(sid).get("continuity_prompt")
    tr_block   = layer4_resolution_suffix()
    system    = _system_prompt(
        context, _history_text(sid), continuity, trust_resolution=tr_block
    )
    try:
        r     = ollama.generate(model="qwen2.5:7b-instruct", system=system, prompt=user_input)
        reply = r["response"].strip()
    except Exception as e:
        logger.error(f"General RAG failed: {e}")
        return {"response": "I'm sorry, I had trouble retrieving information. Please try again.", "citations": []}
    if _is_unsafe(reply):
        return {"response": MEDICATION_REFUSAL, "citations": [],
                "policy_checked": False, "policy_violation": False, "policy_violation_type": None}
    # Policy layer check
    policy = check_policy(reply, intent=None, session_id=sid)
    if policy.violation:
        return {"response": policy.safe_response, "citations": [],
                "policy_checked": True, "policy_violation": True,
                "policy_violation_type": policy.violation_type}
    out = sanitise_response(reply)
    if apply_layer5:
        tc = trust_ctx or trust_context_or_default(None, sid)
        out = apply_layer5_close(out, "rag_query", tc, "medium")
    return {"response": out, "citations": citations,
            "policy_checked": True, "policy_violation": False, "policy_violation_type": None}

# ── Session continuity / check-in greeting ──────────────────────────────────

def build_checkin_greeting(patient_code: str):
    # Checks last 12hrs of patient activity.
    # Returns a personalised continuity greeting dict or None.
    activity = get_recent_checkin_activity(patient_code, within_hours=12)
    if not activity or not activity.get("has_activity"):
        return None

    name   = activity.get("display_name") or "there"
    topics = activity.get("topics_discussed", [])
    crisis = activity.get("was_crisis", False)
    count  = activity.get("message_count", 0)

    # Crisis continuity — highest priority
    if crisis:
        msg = (
            "Welcome back" + (", " + name if name != "there" else "") + ". "
            "I want to check in with you — last time we spoke you were going through "
            "something very difficult. "
            "How are you feeling right now? Are you safe?"
        )
        return {"message": msg, "intent": "checkin_crisis",
                "severity": "high", "show_resources": True,
                "topics_discussed": topics, "was_crisis": True, "message_count": count}

    # Normal continuity
    greeting = "Welcome back" + (", " + name if name != "there" else "") + ". "
    if not topics:
        msg = greeting + "It is good to see you again. How are you doing today?"
    elif len(topics) == 1:
        msg = (greeting + f"Earlier today we were talking about {topics[0]}. "
               "Are you still experiencing this, or is there something else on your mind?")
    elif len(topics) == 2:
        msg = (greeting + f"Earlier today we touched on {topics[0]} and {topics[1]}. "
               "Are either of these still affecting you, or would you like to talk about something else?")
    else:
        tlist = ", ".join(topics[:-1]) + " and " + topics[-1]
        msg = (greeting + f"Earlier today we covered quite a bit — {tlist}. "
               "Is any of this still on your mind, or has something new come up?")

    return {"message": msg, "intent": "checkin_continuity",
            "severity": "low", "show_resources": False,
            "topics_discussed": topics, "was_crisis": False, "message_count": count}


# ── Main handler ─────────────────────────────────────────────────────────────

def _log_policy_if_needed(rag_result, session_id, intent, patient_id, patient_code):
    # Writes to policy_violations table if a breach was intercepted
    if rag_result.get("policy_violation"):
        s = get_session(session_id)
        log_policy_violation(
            session_id=session_id,
            violation_type=rag_result.get("policy_violation_type", "unknown"),
            intent_at_time=intent,
            patient_id=patient_id or s.get("patient_id"),
            patient_code=patient_code or s.get("patient_code"),
        )

def handle_message(user_input: str, session_id: str,
                   patient_code: Optional[str] = None) -> dict:
    """
    Main entry point. Call from FastAPI route or Next.js API.
    Returns: response, intent, severity, show_resources, citations, session_id, timestamp

    patient_code: your internal patient/user ID from your auth system.
                  Pass this on every request so messages are linked to the patient.
    """
    user_input = user_input.strip()
    if not user_input:
        return _result("I'm here and listening. What's on your mind?",
                       "unclear","low",False,[],session_id)

    # Resolve patient identity and ensure session exists in PostgreSQL
    patient_id = None
    if patient_code:
        patient_id = ensure_patient(patient_code)
    ensure_session(session_id, patient_id=patient_id, patient_code=patient_code)

    trust_ctx = trust_context_or_default(patient_code, session_id)

    # Save user message to DB with patient identity
    update_session(session_id, "user", user_input,
                   patient_id=patient_id, patient_code=patient_code)

    user_turns = sum(1 for m in get_session(session_id)["history"] if m["role"] == "user")

    # ── TRUST Layer 1+2 — greet with context + invite (first user turn, greeting, with patient) ──
    _raw_intent = classify_intent(user_input)
    if _raw_intent == "greeting" and patient_code and user_turns == 1:
        continuity_note = None
        act = get_recent_checkin_activity(patient_code, within_hours=12)
        if act and act.get("has_activity"):
            topics = act.get("topics_discussed") or []
            if act.get("was_crisis"):
                continuity_note = (
                    "Recent conversation included crisis-level distress; acknowledge with care."
                )
            elif topics:
                continuity_note = "Topics recently discussed: " + ", ".join(topics[:6])
        msg = generate_trust_opening(
            patient_code, session_id, continuity_note=continuity_note
        )
        if msg:
            update_session(
                session_id,
                "assistant",
                msg,
                "greeting",
                "low",
                patient_id=patient_id,
                patient_code=patient_code,
            )
            return _result(
                msg,
                "greeting",
                "low",
                False,
                [],
                session_id,
                trust_layers="1+2",
            )

    # Pipeline: Self-stigma reframe
    reframe = check_self_stigma(user_input)
    if reframe:
        intent = classify_intent(user_input)
        reply = apply_layer5_close(reframe, intent, trust_ctx, "medium")
        update_session(session_id, "assistant", reply, intent, "medium",
                       patient_id=patient_id, patient_code=patient_code)
        return _result(reply, intent, "medium", False, [], session_id)

    # Pipeline: Classify intent
    intent = classify_intent(user_input)
    logger.info(f"[{session_id}] intent={intent} | '{user_input[:60]}'")

    # Pipeline: Critical safety (hard-coded) — crisis_events via update_session
    sess = get_session(session_id)
    if intent == "crisis_suicidal":
        vid = get_video("mood_anxious")
        if vid:
            register_video_shown(sess, vid)
        update_session(session_id,"assistant",CRISIS_RESPONSE,intent,"critical",show_resources=True,
                       patient_id=patient_id, patient_code=patient_code)
        return _result(CRISIS_RESPONSE,intent,"critical",True,[],session_id, video=vid)
    if intent == "crisis_abuse":
        update_session(session_id,"assistant",ABUSE_RESPONSE,intent,"critical",show_resources=True,
                       patient_id=patient_id, patient_code=patient_code)
        return _result(ABUSE_RESPONSE,intent,"critical",True,[],session_id)
    if intent == "behaviour_self_harm":
        vid = get_video("mood_anxious")
        if vid:
            register_video_shown(sess, vid)
        update_session(session_id,"assistant",SELF_HARM_RESPONSE,intent,"critical",show_resources=True,
                       patient_id=patient_id, patient_code=patient_code)
        return _result(SELF_HARM_RESPONSE,intent,"critical",True,[],session_id, video=vid)

    # Severe distress / psychosis — optional TRUST-aligned video
    scores_for_video = get_session_scores(session_id) or {}

    if intent == "severe_distress":
        vid = trust_select_video(
            intent, trust_ctx, scores_for_video, sess.get("trust_videos_shown", [])
        )
        if vid:
            register_video_shown(sess, vid)
        update_session(session_id,"assistant",SEVERE_DISTRESS_RESPONSE,intent,"high",show_resources=True,
                       patient_id=patient_id, patient_code=patient_code)
        return _result(SEVERE_DISTRESS_RESPONSE,intent,"high",True,[],session_id, video=vid)

    if intent == "psychosis_indicator":
        vid = trust_select_video(
            intent, trust_ctx, scores_for_video, sess.get("trust_videos_shown", [])
        )
        if vid:
            register_video_shown(sess, vid)
        update_session(session_id,"assistant",PSYCHOSIS_RESPONSE,intent,"critical",show_resources=True,
                       patient_id=patient_id, patient_code=patient_code)
        return _result(PSYCHOSIS_RESPONSE,intent,"critical",True,[],session_id, video=vid)

    # Medication block
    if intent == "medication_request":
        reply = apply_layer5_close(MEDICATION_REFUSAL, intent, trust_ctx, "low")
        update_session(session_id,"assistant",reply,intent,"low",
                       patient_id=patient_id, patient_code=patient_code)
        return _result(reply,intent,"low",False,[],session_id)

    # ── TRUST Layer 3 — one clarifying question when intent is still ambiguous ──
    if intent in ("unclear", "rag_query") and is_ambiguous_message(user_input):
        q = generate_clarifying_question(user_input)
        update_session(session_id, "assistant", q, intent, "low",
                       patient_id=patient_id, patient_code=patient_code)
        return _result(q, intent, "low", False, [], session_id, trust_layers="3")

    # Trauma — RAG + intro; TRUST Layer 4 in RAG, Layer 5 on full message
    if intent == "trigger_trauma":
        r        = _contextual_rag(
            user_input, session_id, intent, trust_ctx, apply_layer5=False
        )
        _log_policy_if_needed(r, session_id, intent, patient_id, patient_code)
        response = TRAUMA_RESPONSE_INTRO + r["response"]
        response = apply_layer5_close(response, intent, trust_ctx, "high")
        update_session(session_id,"assistant",response,intent,"high",
                       citations=r["citations"],show_resources=True,
                       patient_id=patient_id, patient_code=patient_code,
                       policy_checked=r.get("policy_checked",False),
                       policy_violation=r.get("policy_violation",False),
                       policy_violation_type=r.get("policy_violation_type"))
        return _result(response,intent,"high",True,r["citations"],session_id,
                       trust_layers="4+5")

    # Small talk — TRUST Layer 5 on generator output; no video
    if intent in {"greeting","farewell","gratitude","unclear"}:
        reply    = _small_talk(intent, session_id, user_input, trust_ctx)
        severity = INTENT_MAP.get(intent, {}).get("severity","low")
        update_session(session_id,"assistant",reply,intent,severity,
                       patient_id=patient_id, patient_code=patient_code)
        get_session(session_id)["continuity_prompt"] = None
        return _result(reply, intent, severity, False, [], session_id,
                       show_score=False, video=None, trust_layers="5")

    # ── Score + video helpers (video_map.py + db + TRUST) ─────────────────────
    def _should_show_score(sid, cur_intent):
        """Returns score prompt dict if not yet captured for this group, else None."""
        group = get_score_group(cur_intent)
        if not group:
            return None
        try:
            existing = get_session_scores(sid)
            if group in existing:
                return None
        except Exception:
            pass
        # Mark in memory immediately to prevent double-showing
        s = get_session(sid)
        if "pending_scores" not in s:
            s["pending_scores"] = set()
        if group in s.get("pending_scores", set()):
            return None
        s["pending_scores"].add(group)
        return {"needed": True, "group": group, "label": get_score_label(cur_intent)}

    def _resolve_trust_video(cur_intent: str):
        s = get_session(session_id)
        sc = get_session_scores(session_id) or {}
        v = trust_select_video(
            cur_intent, trust_ctx, sc, s.get("trust_videos_shown", [])
        )
        if v:
            register_video_shown(s, v)
        return v

    # Known intent → intent-filtered RAG (TRUST Layers 4–5 inside _contextual_rag)
    if intent in INTENT_MAP:
        obj        = INTENT_MAP[intent]
        severity   = obj.get("severity","medium")
        show_res   = obj.get("always_show_resources",False)
        r          = _contextual_rag(user_input, session_id, intent, trust_ctx)
        _log_policy_if_needed(r, session_id, intent, patient_id, patient_code)
        show_score = _should_show_score(session_id, intent)
        video      = _resolve_trust_video(intent)
        update_session(session_id,"assistant",r["response"],intent,severity,
                       citations=r["citations"],show_resources=show_res,
                       policy_checked=r.get("policy_checked",False),
                       policy_violation=r.get("policy_violation",False),
                       policy_violation_type=r.get("policy_violation_type"),
                       patient_id=patient_id, patient_code=patient_code)
        return _result(r["response"],intent,severity,show_res,r["citations"],
                       session_id, show_score=show_score, video=video,
                       trust_layers="4+5")

    # General query → full RAG
    r          = _general_rag(user_input, session_id, trust_ctx)
    _log_policy_if_needed(r, session_id, "rag_query", patient_id, patient_code)
    show_score = _should_show_score(session_id, intent)
    video      = _resolve_trust_video("rag_query")
    update_session(session_id,"assistant",r["response"],"rag_query","medium",
                   citations=r["citations"],
                   policy_checked=r.get("policy_checked",False),
                   policy_violation=r.get("policy_violation",False),
                   policy_violation_type=r.get("policy_violation_type"),
                   patient_id=patient_id, patient_code=patient_code)
    return _result(r["response"],"rag_query","medium",False,r["citations"],
                   session_id, show_score=show_score, video=video,
                   trust_layers="4+5")


def _result(response, intent, severity, show_resources,
            citations, session_id, show_score=None, video=None, score_data=None,
            trust_layers: Optional[str] = None, **extra):
    out = {
        "response":       response,
        "intent":         intent,
        "severity":       severity,
        "show_resources": show_resources,
        "citations":      citations,
        "session_id":     session_id,
        "timestamp":      datetime.now().isoformat(),
        "score_data":     show_score or score_data,
        "video":          video,
    }
    if trust_layers is not None:
        out["trust_layers"] = trust_layers
    out.update(extra)
    return out

# ── FastAPI wrapper ──────────────────────────────────────────────────────────

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(title="Mental Health Chatbot API", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])

    class ChatRequest(BaseModel):
        message:      str
        session_id:   str
        patient_code: Optional[str] = None  # your internal patient/user ID

    class SessionRequest(BaseModel):
        session_id: str

    @app.post("/chat")
    async def chat(req: ChatRequest):
        return handle_message(req.message, req.session_id, req.patient_code)

    @app.post("/session/clear")
    async def session_clear(req: SessionRequest):
        clear_session(req.session_id)
        return {"status":"cleared","session_id":req.session_id}

    @app.get("/session/{session_id}/summary")
    async def session_summary(session_id: str):
        return get_session_summary(session_id)

    @app.get("/health")
    async def health():
        return {"status":"ok","timestamp":datetime.now().isoformat()}

    @app.get("/documents")
    async def documents():
        from rag_pipeline import get_document_list
        return {"documents": get_document_list()}

    @app.get("/policy")
    async def policy():
        return POLICY_SUMMARY

    @app.get("/policy/disclosure")
    async def policy_disclosure():
        return {"disclosure": POLICY_DISCLOSURE_SHORT}

    @app.get("/checkin/{patient_code}")
    async def checkin_status(patient_code: str):
        result = build_checkin_greeting(patient_code)
        if result:
            return {"has_activity": True, **result}
        return {"has_activity": False, "message": None,
                "topics_discussed": [], "was_crisis": False}

    @app.get("/patient/{patient_code}")
    async def patient_profile(patient_code: str):
        return get_patient(patient_code) or {"error": "Patient not found"}

    @app.get("/patient/{patient_code}/sessions")
    async def patient_sessions(patient_code: str):
        return {"sessions": get_patient_sessions(patient_code)}

    @app.get("/patient/{patient_code}/history")
    async def patient_history(patient_code: str):
        return {"history": get_patient_full_history(patient_code)}

    @app.get("/patient/{patient_code}/checkin-status")
    async def checkin_status(patient_code: str, hours: int = 12):
        """
        Called by Flutter on app open BEFORE the chat screen loads.
        Returns topics covered in last 12 hrs and a continuity_prompt
        for the bot to use as its opening message context.
        """
        return get_checkin_status(patient_code, hours)

    @app.post("/patient/{patient_code}/set-continuity")
    async def set_continuity(patient_code: str, req: SessionRequest):
        """
        Called by Flutter after the summary card is shown.
        Loads the continuity_prompt into the in-memory session so the
        first bot response references prior topics naturally.
        """
        status = get_checkin_status(patient_code)
        if status["has_recent_activity"] and status["continuity_prompt"]:
            s = get_session(req.session_id)
            s["continuity_prompt"] = status["continuity_prompt"]
            s["prior_topics"]      = status["topics_covered"]
            return {"status": "continuity_set", "topics": status["topics_covered"]}
        return {"status": "no_recent_activity"}

    @app.get("/admin/sessions")
    async def admin_sessions():
        return {"sessions": get_all_sessions()}

    @app.get("/admin/crisis")
    async def admin_crisis():
        return {"crisis_sessions": get_crisis_sessions()}

    class ScoreRequest(BaseModel):
        session_id:   str
        patient_code: Optional[str] = None
        score_group:  str
        score:        int
        intent:       Optional[str] = None

    @app.post("/session/score")
    async def save_score(req: ScoreRequest):
        """Called by frontend when patient submits a score slider value."""
        s   = get_session(req.session_id)
        pid = s.get("patient_id")
        save_patient_score(
            session_id   = req.session_id,
            patient_code = req.patient_code or s.get("patient_code"),
            score_group  = req.score_group,
            score        = req.score,
            intent       = req.intent,
            patient_id   = pid
        )
        # Clear pending flag so group won't be asked again this session
        if "pending_scores" in s:
            s["pending_scores"].discard(req.score_group)
        return {"status": "saved", "group": req.score_group, "score": req.score}

    @app.get("/admin/crisis/pending")
    async def admin_crisis_pending():
        return {"pending": get_pending_crisis_events()}

    @app.get("/admin/stats")
    async def admin_stats():
        return get_conversation_stats()

    @app.get("/admin/intents")
    async def admin_intents():
        return {"top_intents": get_top_intents()}

    class ScoreRequest(BaseModel):
        session_id:   str
        patient_code: Optional[str] = None
        score_group:  str
        score:        int
        intent:       Optional[str] = None

    @app.post("/session/score")
    async def save_score(req: ScoreRequest):
        """Called by frontend when patient submits a score slider value."""
        s   = get_session(req.session_id)
        pid = s.get("patient_id")
        save_patient_score(
            session_id   = req.session_id,
            patient_code = req.patient_code or s.get("patient_code"),
            score_group  = req.score_group,
            score        = req.score,
            intent       = req.intent,
            patient_id   = pid
        )
        # Clear pending flag so group won't be asked again this session
        if "pending_scores" in s:
            s["pending_scores"].discard(req.score_group)
        return {"status": "saved", "group": req.score_group, "score": req.score}

    @app.get("/admin/crisis/pending")
    async def admin_crisis_pending():
        return {"pending_crisis_events": get_pending_crisis_events()}

    @app.get("/admin/policy/violations")
    async def admin_policy_violations():
        return {"violation_summary": get_policy_violation_summary()}

    @app.get("/session/{session_id}/history")
    async def session_history(session_id: str):
        from db import get_session_history
        return {"history": get_session_history(session_id)}

except ImportError:
    pass  # FastAPI optional

# ── Quick test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Mental Health Chatbot Engine — Test Mode")
    print("=" * 60)
    sid   = "test-001"
    tests = [
        "Hello",
        "I'm an alcoholic and I can't stop drinking",
        "I've been feeling very anxious lately",
        "I spend all night gaming and skip meals",
        "What medication should I take for anxiety?",
        "I want to die",
        "Thanks, that was really helpful",
        "Bye"
    ]
    for msg in tests:
        print(f"\nUser    : {msg}")
        r = handle_message(msg, sid)
        print(f"Bot     : {r['response'][:200]}")
        print(f"Intent  : {r['intent']} | Severity: {r['severity']}")
        if r.get("citations"):
            print(f"Sources : {', '.join(r['citations'])}")
        if r.get("show_resources"):
            print("⚠️  Show crisis resources")
        print("-" * 50)
