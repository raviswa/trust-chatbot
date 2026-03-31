# 📖 Clinical Design Documentation Index

This is your **complete reference** for how Trust AI implements the clinical design baseline principles from the training images.

---

## 🎯 Quick Start (Choose Your Role)

### 👨‍⚕️ **I'm a Therapist or Clinical Lead**
→ Start with: [RESPONSE_VALIDATION_CHECKLIST.md](RESPONSE_VALIDATION_CHECKLIST.md)
- Quickly validate any chatbot response
- Understand guardrails
- Know the red flags

---

### 🧪 **I'm a QA or Testing Person**
→ Start with: [CLINICAL_CONFIGURATION_PROTOCOL.md](CLINICAL_CONFIGURATION_PROTOCOL.md)
- 3 step-by-step test scenarios
- Configuration guide
- Troubleshooting help
- Deployment checklist

---

### 💻 **I'm an Engineer or Developer**
→ Start with: [CLINICAL_DESIGN_IMPLEMENTATION.md](CLINICAL_DESIGN_IMPLEMENTATION.md)
- Full code verification
- Data flow diagrams
- Service architecture
- Links to exact code locations

---

## 📚 Complete Documentation Set

### 1️⃣ **CLINICAL_FRAMEWORK_OVERVIEW.md** ← START HERE
- High-level summary of all 8 principles
- How they're implemented
- Data flow diagram
- Quick validation checklist
- Current status table

### 2️⃣ **RESPONSE_VALIDATION_CHECKLIST.md** ← FOR THERAPISTS
- Validate individual responses in <2 min
- 5-part anatomy check
- Intent-specific requirements (venting, craving, crisis, etc.)
- Red flag list (never acceptable)
- Quick testing flow

### 3️⃣ **CLINICAL_CONFIGURATION_PROTOCOL.md** ← FOR QA & TESTING
- Pre-conversation setup
- 3 detailed test scenarios with expected output
- How to verify each component works
- Configuration for adjustments
- Monitoring guide
- Troubleshooting
- Deployment checklist

### 4️⃣ **CLINICAL_DESIGN_IMPLEMENTATION.md** ← FOR ENGINEERING
- Detailed verification of 8 principles
- Code locations (line numbers)
- Data structure walkthrough
- Integration checklist
- Service dependencies
- Example conversation flows

### 5️⃣ **Session Memory: clinical_design_baseline.md** ← FOR CONTEXT
- Reference copy of baseline principles
- Intent categories
- Response anatomy
- Tone profiles
- Guardrails summary
- Conversation examples
- Use in AI conversations for context

---

## 🎬 The 8 Core Principles

All **VERIFIED IMPLEMENTED** in code:

| # | Principle | What It Is | Where It's Coded | Validation Doc |
|---|-----------|-----------|------------------|-----------------|
| 1 | **Patient Context Vector** | Chatbot knows patient state before they speak | `patient_context.py` | [IMPL](CLINICAL_DESIGN_IMPLEMENTATION.md#-1-patient-context-vector) |
| 2 | **Intent Classification** | Routes message to correct response type (6 categories) | `services_intent_classifier.py` | [IMPL](CLINICAL_DESIGN_IMPLEMENTATION.md#-2-intent-classification-pipeline) |
| 3 | **Tone Engine** | Adapts voice to risk level (4 profiles) | `patient_context.py:format_context_for_prompt()` | [IMPL](CLINICAL_DESIGN_IMPLEMENTATION.md#-3-tone-engine) |
| 4 | **3-Line Response** | Validation → Normalisation → Action | `services_response_generator.py` | [IMPL](CLINICAL_DESIGN_IMPLEMENTATION.md#-4-response-composition) |
| 5 | **Video Selection** | Personalised therapeutic video (3-5 min) | `video_map.py` | [IMPL](CLINICAL_DESIGN_IMPLEMENTATION.md#-5-video-selection-logic) |
| 6 | **Crisis Override** | Hardcoded de-escalation (urgency >0.85) | `chatbot_engine.py` | [IMPL](CLINICAL_DESIGN_IMPLEMENTATION.md#-6-crisis-override-layer) |
| 7 | **Guardrails** | 8 safety rules (never diagnose, etc.) | `services_safety_checker.py` + `ethical_policy.py` | [IMPL](CLINICAL_DESIGN_IMPLEMENTATION.md#-7-clinical-guardrails) |
| 8 | **Real Examples** | Validated conversation flows | `chatbot_engine.py` | [IMPL](CLINICAL_DESIGN_IMPLEMENTATION.md#-8-conversation-flow-example-validation) |

---

## 🔍 How to Use This Documentation

### **Scenario 1: Reviewing a Bot Response**
```
"Is this response clinically appropriate?"

→ Use: RESPONSE_VALIDATION_CHECKLIST.md
→ Steps: 
   1. Identify the intent (venting? craving? crisis?)
   2. Check risk level
   3. Run 5-part anatomy check
   4. Verify no red flags
   → Takes <2 min
```

---

### **Scenario 2: Testing the Whole System**
```
"I need to test craving detection and video selection"

→ Use: CLINICAL_CONFIGURATION_PROTOCOL.md
→ Steps:
   1. Follow Test Scenario 1 (Craving During High Risk Time)
   2. Send exact patient message
   3. Verify 7 expected response elements
   4. Check video recommended
   → Takes ~5 min
```

---

### **Scenario 3: Updating Tone Instructions**
```
"Therapists want higher empathy in Medium risk responses"

→ Use: CLINICAL_CONFIGURATION_PROTOCOL.md → "Adjusting Tone Instructions"
→ Steps:
   1. Open patient_context.py
   2. Find Medium risk tone line
   3. Update text
   4. Test with Scenario 2
   5. Verify in system prompt output
   → Takes ~10 min
```

---

### **Scenario 4: Understanding the Data Flow**
```
"How does patient data flow from onboarding to the response?"

→ Use: CLINICAL_DESIGN_IMPLEMENTATION.md → Data Flow section
→ Or: CLINICAL_FRAMEWORK_OVERVIEW.md → "🔄 Data Flow" diagram
→ Or: See mermaid diagram below
```

---

## 📊 Reference Diagrams

### Request-Response Flow
```
Patient Message
    ↓
Intent Classification (6 categories + urgency score)
    ↓
Load Patient Context Vector (4 sources)
    ↓
Select Tone (risk level → 1 of 4 tone profiles)
    ↓
Inject Context + Tone into System Prompt
    ↓
Is Urgency > 0.85 OR Crisis Flag?
    ├─ YES → Crisis Override (hardcoded + breathing video)
    └─ NO → LLM Generation (template + RAG + personality injection)
    ↓
Apply 3-Line Response Anatomy
    ├─ Line 1: Validation
    ├─ Line 2: Normalisation
    └─ Line 3: Action
    ↓
Select Video (6 input signals)
    ↓
Safety Check (8 guardrails)
    ↓
Save to Database
    ↓
Response to Patient
```

---

## 🎯 Key Metrics to Monitor

Track these weekly to ensure clinical compliance:

| Metric | Target | Where to Check |
|--------|--------|-----------------|
| Intent classification accuracy | >90% | DB: `messages.classified_intent` |
| Tone injection rate | 100% | Logs: grep "TONE:" |
| Response time | <3s | DB: `response_time` column |
| Crisis detection accuracy | >95% | Manual review + DB |
| Video recommendation relevance | >85% | QA feedback |
| Guardrail violations | 0 | `ethical_policy.py` logs |
| Session continuity | 100% | DB: conversation history loads |

---

## 🚨 Red Flags (Never Acceptable)

If you see any of these in chatbot responses → **STOP and escalate**:

```
❌ "You have anxiety disorder" (diagnosing)
❌ "Are you thinking of hurting yourself?" (risk assessment)
❌ "You should reduce your medication" (medical advice)
❌ "I understand exactly how you feel" (simulating therapist)
❌ List of 5 tips (not immediate action)
❌ Response longer than 5 sentences
❌ Ends with question (interrogation)
❌ "We're training our AI on this conversation" (consent breach)
```

→ See full list in [RESPONSE_VALIDATION_CHECKLIST.md#-red-flags](RESPONSE_VALIDATION_CHECKLIST.md#-red-flags-never-acceptable)

---

## 🔧 Quick Configuration Guide

| Task | Where | Difficulty |
|------|-------|------------|
| Adjust tone for a risk level | `patient_context.py:278-290` | Easy |
| Add a new intent | `intents.json` + `services_intent_classifier.py` + `services_response_generator.py` | Medium |
| Change crisis threshold | `services_intent_classifier.py:CRISIS_THRESHOLD` | Easy (⚠️ requires testing) |
| Add a new video | `video_map.py` + video file | Easy |
| Adjust response template | `services_response_generator.py:RESPONSE_TEMPLATES` | Easy |

See full instructions in [CLINICAL_CONFIGURATION_PROTOCOL.md](CLINICAL_CONFIGURATION_PROTOCOL.md)

---

## 📞 Navigation

### By Role
- **Therapist**: [RESPONSE_VALIDATION_CHECKLIST.md](RESPONSE_VALIDATION_CHECKLIST.md)
- **QA/Tester**: [CLINICAL_CONFIGURATION_PROTOCOL.md](CLINICAL_CONFIGURATION_PROTOCOL.md)
- **Engineer**: [CLINICAL_DESIGN_IMPLEMENTATION.md](CLINICAL_DESIGN_IMPLEMENTATION.md)

### By Task
- **Validate a response**: [Validation Checklist](RESPONSE_VALIDATION_CHECKLIST.md#for-any-response-check)
- **Test the system**: [Test Scenarios](CLINICAL_CONFIGURATION_PROTOCOL.md#-testing-a-patient-conversation)
- **Configure settings**: [Configuration Guide](CLINICAL_CONFIGURATION_PROTOCOL.md#-configuration-adjustments)
- **Understand architecture**: [Implementation Doc](CLINICAL_DESIGN_IMPLEMENTATION.md)
- **Quick overview**: [Framework Overview](CLINICAL_FRAMEWORK_OVERVIEW.md)

### By Principle
1. [Patient Context](CLINICAL_DESIGN_IMPLEMENTATION.md#-1-patient-context-vector)
2. [Intent Classification](CLINICAL_DESIGN_IMPLEMENTATION.md#-2-intent-classification-pipeline)
3. [Tone Engine](CLINICAL_DESIGN_IMPLEMENTATION.md#-3-tone-engine)
4. [3-Line Anatomy](CLINICAL_DESIGN_IMPLEMENTATION.md#-4-response-composition)
5. [Video Selection](CLINICAL_DESIGN_IMPLEMENTATION.md#-5-video-selection-logic)
6. [Crisis Override](CLINICAL_DESIGN_IMPLEMENTATION.md#-6-crisis-override-layer)
7. [Guardrails](CLINICAL_DESIGN_IMPLEMENTATION.md#-7-clinical-guardrails)
8. [Flows](CLINICAL_DESIGN_IMPLEMENTATION.md#-8-conversation-flow-example-validation)

---

## ✅ Validation Status

All 8 principles from the baseline images are:
- ✅ Documented
- ✅ Implemented in code
- ✅ Verified with code links
- ✅ Ready for validation/testing

**Last Updated**: March 23, 2026

---

**Questions?** Start with the role-specific document at the top of this page.
