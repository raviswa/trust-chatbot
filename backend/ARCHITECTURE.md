# Chatbot Redesign - Microservices Architecture

## Design Overview

The chatbot has been redesigned from a monolithic architecture to a **microservices-based system** implementing the **minimal-question dialogue model** from the PowerPoint design.

### Key Design Principles

1. **"WHAT THE CHATBOT ALREADY KNOWS — THE PATIENT CONTEXT VECTOR"**
   - Patient context is maintained across conversation turns
   - Chatbot avoids asking redundant questions
   - Responses are personalized based on known context

2. **Minimal-Question Dialogue Model**
   - Only ask relevant questions (never more than 2 per turn)
   - Check patient context BEFORE asking questions
   - Prioritize listening and empathy over information gathering
   - Ask questions only when appropriate for the conversation severity

3. **Microservices Architecture**
   - Separation of concerns into focused services
   - Each service has a single responsibility
   - Services can be tested and deployed independently
   - Easy to enhance or replace individual services

## Microservices

### 1. **Intent Classifier Service** (`services_intent_classifier.py`)

**Responsibility**: Classify user intent with multi-tier fallback

**Architecture**:
- Tier 1: Priority pattern matching (safety-first)
- Tier 2: intents.json pattern matching
- Tier 3: LLM classification (Ollama, if available)
- Tier 4: Pattern-based fallback classification

**Key Features**:
- 40+ recognized intents across mental health domain
- Crisis detection as highest priority
- Medication request blocking
- Graceful fallback when Ollama unavailable

**API**:
```python
classifier = IntentClassifier()
intent = classifier.classify("I'm feeling really anxious")  # Returns: "mood_anxious"
metadata = classifier.get_intent_metadata("mood_anxious")   # Returns: severity, category, etc
```

### 2. **Context Manager Service** (`services_context_manager.py`)

**Responsibility**: Track and manage patient context vector

**What It Tracks**:
- **Demographics**: Age, gender, location, occupation (provided upfront)
- **Mental Health Profile**: Diagnosed conditions, medications, past treatments, trauma history
- **Current State**: Primary concerns, mood level, active severity flags, coping mechanisms, support system
- **Conversation History**: Total sessions, recurring themes, previous crises
- **Questions Already Asked**: Prevents repetition

**Key Features**:
- Automatic context extraction from conversations
- Intelligent question determination based on what's missing
- Minimal-question logic (returns at most 2 questions)
- Conversation continuity across sessions

**API**:
```python
context = get_or_create_context(session_id, patient_id, patient_code)

# Extract info from conversation
update_context_from_turn(session_id, user_message, intent, metadata)

# Determine what questions to ask next
questions = context.determine_questions_to_ask_next()  # Max 2 questions

# Check if we've asked something before
if not context.has_been_asked("ask_medications"):
    context.mark_question_asked("ask_medications")

# Get context summary for prompt injection
summary = context.get_relevant_context_summary()
```

### 3. **Response Generator Service** (`services_response_generator.py`)

**Responsibility**: Generate personalized, empathetic responses

**Architecture**:
- Template-based responses for known intents
- Context-aware personalization
- RAG integration for general queries
- Minimal-question incorporation

**Response Types**:
- **Crisis Responses**: Immediate safety with resources
- **Clinical Responses**: Trauma, addiction, severe distress with professional referrals
- **Supportive Responses**: Mood, behavioral, stress with empathetic listening
- **Social Responses**: Greetings, farewells, gratitude
- **Safety Responses**: Medication blocking, policy enforcement

**Key Features**:
- Content-validated templates for each intent
- Personalization based on context vector
- Minimal-question embedding in responses
- Fallback to RAG or generic responses

**API**:
```python
generator = ResponseGenerator()

# Generate response
response, metadata = generator.generate(
    intent="mood_anxious",
    user_message="I'm so worried about everything",
    context_vector=context,
)

# Get minimal question to ask
question = generator.get_next_minimal_question(context)

# Add question to response if appropriate
if generator.should_ask_question(context, last_q_asked=False):
    response = generator.add_minimal_question_to_response(response, question)
```

### 4. **Safety Checker Service** (`services_safety_checker.py`)

**Responsibility**: Multi-layer safety validation

**Safety Layers**:
1. **Medication Safety**: Detect and block unsafe medication recommendations
2. **Crisis Detection**: Identify crisis indicators in user messages
3. **Severe Distress Detection**: Flag multiple distress signals
4. **Response Validation**: Ensure our responses are safe and appropriate
5. **Policy Compliance**: Validate against organizational policies

**Key Features**:
- Priority-based crisis detection (suicidal > abuse > self-harm)
- Automatic event logging for monitoring
- Resource link generation per intent
- Policy rule enforcement

**API**:
```python
safety = SafetyChecker()

# Check user input for safety issues
is_safe, violation = safety.check_safety(user_message, intent)

# Validate our response
is_valid, error = safety.validate_response(bot_response, intent)

# Get resources for an intent
resources = safety.get_resource_links("crisis_suicidal")
```

## 6-Layer Message Handling Flow

When a message arrives, the chatbot goes through 6 layers:

```
Layer 0: Input Validation
    ↓
    - Check message is valid and non-empty
    - Load/create patient context

Layer 1: Safety Checks
    ↓
    - Check for medication content → Block if unsafe
    - Check for crisis indicators
    - Validate policy compliance

Layer 2: Intent Classification
    ↓
    - Use IntentClassifier service
    - Get severity and category

Layer 3: Context Extraction & Management
    ↓
    - Extract info from user message
    - Update context vector
    - Determine minimal questions to ask

Layer 4: Response Generation
    ↓
    - Generate base response using templates
    - Incorporate context personalization
    - Add minimal-question if appropriate
    - Try RAG for general queries

Layer 5: Response Validation
    ↓
    - Validate safety
    - Check policy compliance
    - Sanitize response
    - Check for self-stigma and reframe

↓ Result returned
```

## Minimal-Question Dialogue Implementation

The system implements minimal questioning through:

### 1. **Context Awareness**
```python
# Before asking "What medications are you on?", check context
if context.mental_health_profile["current_medications"]:
    # We already know this, skip the question
    pass
```

### 2. **Question Prioritization**
```python
# Get next priority questions (max 2)
questions = context.determine_questions_to_ask_next()
# Returns: [
#     {"id": "ask_support_system", "priority": 15, ...},
#     {"id": "ask_previous_help", "priority": 12, ...}
# ]
```

### 3. **Situational Awareness**
```python
# Only ask during appropriate moments
should_ask = (
    len(questions) > 0
    and message_count >= 2        # After initial exchange
    and not last_question_asked   # Not twice in a row
    and severity in ["low", "medium"]  # Not during crises
)
```

### 4. **Integration into Responses**
```python
base_response = "Thank you for sharing that with me..."
if should_ask_question:
    next_question = questions[0]
    response = base_response + f"\n\n{next_question['text']}"
    context.mark_question_asked(next_question["id"])
```

## Migration Guide

### Step 1: Update Imports

If you're upgrading an older integration, import from the current `chatbot_engine.py` entrypoint:

```python
from chatbot_engine import handle_message
```

### Step 2: No API Changes Required

The main `handle_message()` function signature remains the same:

```python
result = handle_message(
    message="I'm feeling anxious",
    session_id="session-123",
    patient_id="pat-001",
    patient_code="PAT-001",
)
```

### Step 3: Enhanced Response Object

The response now includes additional fields:

```python
{
    "response": "...",                    # Main response text
    "intent": "mood_anxious",              # Classified intent
    "severity": "medium",                  # Critical/High/Medium/Low
    "show_resources": True,                # Should show resources
    "resource_links": {...},               # Resource URLs by category
    "context_summary": "Known conditions: anxiety, anxiety, Current concerns: mood",
    "has_minimal_question": True,          # Includes a minimal question
    "metadata": {
        "intent_category": "mood",         # Category of intent
        "requires_follow_up": False,       # Needs professional follow-up
        "citations": [...],                # RAG citations if applicable
    }
}
```

## File Structure

```
backend/
├── chatbot_engine.py                  # Main orchestrator (microservices engine)
├── services_intent_classifier.py      # Intent classification (NEW)
├── services_context_manager.py        # Context vector management (NEW)
├── services_response_generator.py     # Response generation (NEW)
├── services_safety_checker.py         # Safety & policy validation (NEW)
├── pages/api/chat.js                  # FastAPI endpoint (update import)
└── [other files unchanged]
```

## Testing the New Architecture

### Test 1: Minimal Questions Not Asked Twice

```python
session_id = "test-001"
patient_id = "pat-001"
patient_code = "PAT-001"

# Turn 1: Ask about support system
r1 = handle_message("I'm feeling really sad", session_id, patient_id, patient_code)
assert "Do you have people you can talk to" in r1["response"]

# Turn 2: Should NOT ask the same question again
r2 = handle_message("It's been going on for weeks", session_id, patient_id, patient_code)
assert "Do you have people you can talk to" not in r2["response"]  # ✓ PASS
```

### Test 2: Crisis Response Priority

```python
# High-severity input should trigger crisis response without asking questions
r = handle_message("I want to kill myself", session_id, patient_id, patient_code)
assert r["severity"] == "critical"
assert r["show_resources"] == True
assert "emergency services" in r["response"].lower()
```

### Test 3: Context Extraction

```python
# Medical context should be extracted
r1 = handle_message("I'm on antidepressants for depression", session_id, patient_id, patient_code)

# Subsequent questions shouldn't ask about medications
r2 = handle_message("What else can help?", session_id, patient_id, patient_code)
context = _get_context_if_exists(session_id)
assert "depression" in context.mental_health_profile["diagnosed_conditions"]
assert context.has_been_asked("ask_current_meds") or context.mental_health_profile["current_medications"]
```

## Deployment Checklist

- [ ] Test backward compatibility with existing API endpoints
- [ ] Verify all service imports work correctly
- [ ] Test with Ollama available and unavailable
- [ ] Verify Supabase/PostgreSQL/Mock database fallback
- [ ] Load test with multiple concurrent sessions
- [ ] Monitor error logs during transition
- [ ] Verify crisis detection still works
- [ ] Test minimal-question logic across conversation scenarios

## Benefits of New Architecture

1. **Modularity**: Each service is independent and testable
2. **Scalability**: Services can be scaled independently
3. **Maintainability**: Clear separation of concerns
4. **Extensibility**: Easy to add new intent classes, responses, or safety rules
5. **User Experience**: Minimal, context-aware conversations
6. **Safety First**: Multi-layer safety checks prevent harmful responses
7. **Monitoring**: Better event tracking and analytics

## Future Enhancements

- Move services to separate processes/containers
- Add caching layer for context vectors (Redis)
- Implement A/B testing framework for response templates
- Add user feedback loop for response quality
- Multi-language support in context manager
- Advanced NLP for better intent classification
- Predictive question recommendation using conversation history
