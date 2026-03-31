# Trust AI Clinical Design Framework — Complete Documentation

This repository now includes comprehensive documentation that maps the clinical design baseline (from the training images) to the actual codebase implementation.

---

## 📚 Documentation Overview

### For **Therapists & Clinical Staff**:
1. **[RESPONSE_VALIDATION_CHECKLIST.md](RESPONSE_VALIDATION_CHECKLIST.md)** 
   - Quick validation guide for individual chatbot responses
   - Red flag list (safety guardrails)
   - Example validations (good vs bad responses)
   - Use this when reviewing chatbot outputs

### For **QA & Testing Teams**:
2. **[CLINICAL_CONFIGURATION_PROTOCOL.md](CLINICAL_CONFIGURATION_PROTOCOL.md)**
   - Step-by-step testing protocol with 3 detailed scenarios
   - How to verify patient context is loaded
   - How to test intent classification
   - Configuration adjustments (tone, intents, videos)
   - Monitoring & troubleshooting guide
   - Deployment checklist

### For **Engineering Teams**:
3. **[CLINICAL_DESIGN_IMPLEMENTATION.md](CLINICAL_DESIGN_IMPLEMENTATION.md)**
   - Complete verification that all 8 core principles are implemented
   - Links to specific code locations
   - Data flow diagrams
   - Service architecture overview
   - Integration checklist

### For **Context in Conversations**:
4. **Session Memory** — `/memories/session/clinical_design_baseline.md`
   - Reference of all baseline principles from training images
   - Use in prompts when discussing the system

---

## 🎯 Core Clinical Design Principles

All 8 principles from the baseline images are **VERIFIED IMPLEMENTED**:

### 1. Patient Context Vector ✅
**Before patient types, chatbot knows**:
- Addiction type, baseline mood, primary triggers, support network
- Today's mood, sleep quality, craving intensity, medication status
- Last videos watched, content preferences, most effective content
- Live risk score (0-100), risk level, crisis flag, key risk drivers

**Implementation**: [`patient_context.py`](backend/patient_context.py) — `PatientContext` dataclass, 4 sources (onboarding, check-in, content, risk)

---

### 2. Intent Classification ✅
**Routes every message**:
- Venting / Emotional Expression
- Craving / Urge
- Seeking Information / Psychoeducation
- Progress / Positive Check-in
- Relapse Disclosure
- Crisis / Harm Ideation

**Implementation**: [`services_intent_classifier.py`](backend/services_intent_classifier.py) — Multi-level fallback (NLP → pattern matching)

---

### 3. Tone Engine ✅
**Maps risk level → voice profile**:
- **Low risk** → "Warm and energising" (celebrate wins, use name)
- **Medium risk** → "Calm and grounding" (slower pace, breathe-first)
- **High risk** → "Direct and immediate" (no preamble, one action)
- **Critical risk** → "Quiet and stabilising" (breathing anchor only)

**Implementation**: [`patient_context.py`](backend/patient_context.py) — `format_context_for_prompt()`, tone directives injected into system prompt

---

### 4. 3-Line Response Anatomy ✅
**Every text response**:
1. **Validation** — Acknowledge feeling without judgement (1 line)
2. **Normalisation** — Remove shame, contextualise in recovery (1 line)
3. **Bridge to Action** — One specific, immediately doable thing (1 line)

Example:
```
"That pull is real, and the fact you're here matters." [Validation]
"Cannabis affects anxiety regulation early in recovery—it's temporary." [Normalisation]
"Let's do one thing right now—[Urge Surfing video]" [Action]
```

**Implementation**: [`services_response_generator.py`](backend/services_response_generator.py) — Response templates + tone-based modification

---

### 5. Video Selection Logic ✅
**Personalised 3-5 min videos** based on:
- Intent class (craving/venting/info/crisis)
- Addiction type (alcohol/cannabis/nicotine/gaming/opioids/behavioral)
- Mood state (happy/stressed/sad/neutral/angry/lonely)
- Risk level (low/medium/high/critical)
- Watch history (avoid repeats)
- Time of day (morning=motivational, evening=calming)

**Implementation**: [`video_map.py`](backend/video_map.py) — Intent-driven selector with multivariate logic

---

### 6. Crisis Override Layer ✅
**Hardcoded de-escalation** when:
- `urgency_score > 0.85` OR `crisis_flag = TRUE`

**Response**:
- Very short (max 2-3 sentences)
- Breathing video auto-loads
- Present tense only ("I'm here")
- No assessment questions
- Emergency resources listed
- Sponsor call triggered (Twilio)
- Kafka event logged

**Implementation**: [`chatbot_engine.py`](backend/chatbot_engine.py) — Crisis detection + override handler

---

### 7. Clinical Guardrails ✅
**8 Non-negotiable rules**:
- ❌ Never diagnose or label
- ❌ Never conduct risk assessment
- ❌ Never give medication advice
- ❌ Never simulate therapist ("I understand exactly how you feel")
- ❌ Never re-traumatise
- ❌ Never challenge firmly held beliefs
- ❌ Always offer human opt-out
- ❌ Maintain confidentiality framing

**Implementation**: 
- Response templates in [`services_response_generator.py`](backend/services_response_generator.py)
- Policy validation in [`services_safety_checker.py`](backend/services_safety_checker.py)
- Ethics framework in [`ethical_policy.py`](backend/ethical_policy.py)

---

### 8. Conversation Flow ✅
**Real examples from baseline**:
- Evening craving (alcohol, high risk, 9:47pm)
- Psychoeducation query (cannabis, medium risk, 2:15pm)

**Both verified in**:
- Intent classification working correctly
- Tone selection matching risk level
- 3-line response anatomy applied
- Video selection logic functional
- All guardrails respected

---

## 🔄 Data Flow

```
USER MESSAGE
    ↓
[Intent Classifier Service]
    ├─ Intent class (6 categories)
    ├─ Urgency score (0-1)
    └─ Crisis flag (T/F)
    ↓
[Context Manager Service]
    ├─ Load patient context vector
    ├─ Onboarding + check-in data
    ├─ Content history
    └─ Risk assessment
    ↓
[Select Tone]
    └─ risk_level → tone_profile
    ↓
[Build System Prompt]
    ├─ Patient context
    ├─ Tone directives
    ├─ Safety guardrails
    └─ Clinical guidelines
    ↓
[Check Crisis Threshold]
    ├─ YES (urgency > 0.85)
    │   └─ → Crisis Override Layer
    │       ├─ Hardcoded response
    │       ├─ Breathing video
    │       ├─ Sponsor call
    │       └─ Kafka event
    │
    └─ NO
        ├─ [Response Generator]
        │   └─ Select template
        │       └─ Apply tone
        │
        └─ [Video Selector]
            └─ Select video
                └─ intent + addiction + mood + risk + history
    ↓
[Safety Checker]
    ├─ Policy validation
    └─ Guardrail enforcement
    ↓
[Save to Database]
    └─ Message + metadata
    ↓
RESPONSE TO PATIENT
    ├─ Text (3-line anatomy)
    ├─ Video recommendation
    └─ Tone matched to risk
```

---

## 🗂️ Codebase Structure

```
backend/
├─ chatbot_engine.py              ← Main orchestrator
├─ patient_context.py              ← Context vector + tone selector
├─ services_intent_classifier.py    ← 6 intent classes
├─ services_context_manager.py      ← Session persistence
├─ services_response_generator.py   ← 3-line templates
├─ services_safety_checker.py       ← Guardrail validation
├─ video_map.py                     ← Video recommendations
├─ rag_pipeline.py                  ← Knowledge base (3TB corpus)
├─ ethical_policy.py                ← Clinical policy rules
└─ db_supabase.py / db.py / db_mock.py  ← Database layer (3-tier fallback)
```

---

## ✅ Validation Checklist

Before going live with responses, run through:

### Therapist Check (RESPONSE_VALIDATION_CHECKLIST.md)
- [ ] Does response show context awareness (knows patient state)?
- [ ] Is tone appropriate for risk level?
- [ ] Does it follow 3-line anatomy?
- [ ] Does it end with action, not interrogation?
- [ ] Does it avoid all 8 red flags?

### QA Check (CLINICAL_CONFIGURATION_PROTOCOL.md)
- [ ] Intent classified correctly?
- [ ] Tone directive in system prompt?
- [ ] Video offered & appropriate?
- [ ] Crisis threshold tested?
- [ ] Response time <3s?

### Engineering Check (CLINICAL_DESIGN_IMPLEMENTATION.md)
- [ ] All services called in correct order?
- [ ] Patient context loaded from DB?
- [ ] Risk level accurately computed?
- [ ] Response template applied correctly?
- [ ] Logs show full data flow?

---

## 🚀 Getting Started

### 1. Understand the Baseline
Read the 8 baseline images provided (clinical design principles)

### 2. Review Implementation
Read [CLINICAL_DESIGN_IMPLEMENTATION.md](CLINICAL_DESIGN_IMPLEMENTATION.md) to verify each principle is coded

### 3. Test Individual Responses
Use [RESPONSE_VALIDATION_CHECKLIST.md](RESPONSE_VALIDATION_CHECKLIST.md) when reviewing chatbot outputs

### 4. Test Full Conversations
Follow [CLINICAL_CONFIGURATION_PROTOCOL.md](CLINICAL_CONFIGURATION_PROTOCOL.md) test scenarios

### 5. Configure & Deploy
Use [CLINICAL_CONFIGURATION_PROTOCOL.md](CLINICAL_CONFIGURATION_PROTOCOL.md) configuration section for any adjustments

---

## 🔍 Current Status

**All 8 principles from baseline images are VERIFIED IMPLEMENTED**

| Principle | Status | Code Location |
|-----------|--------|---------------|
| Patient Context Vector | ✅ | `patient_context.py` |
| Intent Classification | ✅ | `services_intent_classifier.py` |
| Tone Engine | ✅ | `patient_context.py:format_context_for_prompt()` |
| 3-Line Response Anatomy | ✅ | `services_response_generator.py` |
| Video Selection | ✅ | `video_map.py` |
| Crisis Override | ✅ | `chatbot_engine.py` |
| Clinical Guardrails | ✅ | `services_safety_checker.py` + `ethical_policy.py` |
| Conversation Flow | ✅ | `chatbot_engine.py` orchestration |

---

## 📞 Documentation Links

| Document | Purpose | Audience |
|----------|---------|----------|
| [RESPONSE_VALIDATION_CHECKLIST.md](RESPONSE_VALIDATION_CHECKLIST.md) | Quick response validation | Therapists, QA |
| [CLINICAL_CONFIGURATION_PROTOCOL.md](CLINICAL_CONFIGURATION_PROTOCOL.md) | Testing & configuration | QA, Engineering |
| [CLINICAL_DESIGN_IMPLEMENTATION.md](CLINICAL_DESIGN_IMPLEMENTATION.md) | Implementation verification | Engineering |
| Session Memory (baseline) | Principle reference | All (context-scoped) |

---

## ✨ Next Steps

1. **Review responses** in production using [RESPONSE_VALIDATION_CHECKLIST.md](RESPONSE_VALIDATION_CHECKLIST.md)
2. **Run test scenarios** from [CLINICAL_CONFIGURATION_PROTOCOL.md](CLINICAL_CONFIGURATION_PROTOCOL.md)
3. **Monitor metrics** (intent accuracy, crisis detection, response time)
4. **Gather clinical feedback** from therapists on tone appropriateness
5. **Iterate** based on feedback using configuration protocol

---

**This framework ensures Trust AI responds as a therapist would—context-aware, trauma-informed, and clinically safe.**
