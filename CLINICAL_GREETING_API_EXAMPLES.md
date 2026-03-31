# Clinical Greeting API - Usage Examples

## Endpoints

### GET /patient/{code}/checkin-status

Fetches synthesized patient context for greeting generation.

**Endpoint:** `GET /patient/{patient_code}/checkin-status?hours=240`

**Query Parameters:**
- `code` (string, required): Patient code  
- `hours` (integer, optional): Look back this many hours for data (default: 240 = 10 days)

**Response:** Full greeting context with all layers

---

## Example 1: Returning User with Recent Check-in & Wearables

### Request
```bash
curl -X GET "http://localhost:8000/patient/ALVIN001/checkin-status?hours=240"
```

### Response
```json
{
  "status": "ok",
  "has_recent_activity": true,
  "topics_covered": ["stress", "sleep_difficulties", "workplace_challenges"],
  "hours_since_checkin": 2.5,
  "greeting": "Hi Alvin 👋 I see you're feeling stressed today, and your wearable showed some tension last night. That combination can definitely make things harder.\n\nStress and physical tension can affect everything — mood, patience, cravings, everything. The exhaustion you're experiencing makes sense. And I'm here.\n\nI'm here. You can tell me what's on your mind, or I can walk you through a quick grounding practice right now — whatever feels right.",
  "tone": "calm_grounding",
  "risk_score": 68,
  "dominant_theme": "emotional_distress:stressed",
  "data_freshness": {
    "subjective_hours_ago": 2.5,
    "physiological_hours_ago": 12.0,
    "is_returning_user": true,
    "all_data_recent": false
  },
  "layers": {
    "contextual_opening": "Hi Alvin 👋 I see you're feeling stressed today, and your wearable showed some tension last night. That combination can definitely make things harder.",
    "validation": "Stress and physical tension can affect everything — mood, patience, cravings, everything. The exhaustion you're experiencing makes sense. And I'm here.",
    "agency": "I'm here. You can tell me what's on your mind, or I can walk you through a quick grounding practice right now — whatever feels right."
  }
}
```

### How to Use (React)
```javascript
async function selectPatient(patient) {
  try {
    const response = await fetch(`/api/patient/${patient.code}/checkin-status?hours=240`);
    const context = await response.json();
    
    // Set greeting message
    setMessages([{
      role: 'assistant',
      content: context.greeting,
      intent: context.tone,  // For styling
      severity: context.risk_score > 70 ? 'high' : 'medium',
    }]);
    
    // Store context for later reference
    sessionStorage.setItem('greeting_context', JSON.stringify(context));
    
    // Show data freshness indicator
    if (!context.data_freshness.all_data_recent) {
      console.warn('Data is not all fresh:', context.data_freshness);
    }
  } catch (error) {
    // Fallback to generic greeting
    setMessages([{
      role: 'assistant',
      content: `Hi ${patient.name}, welcome. I'm here to listen and support you. What's on your mind today?`,
      intent: 'greeting'
    }]);
  }
}
```

---

## Example 2: New User or No Recent Data

### Request
```bash
curl -X GET "http://localhost:8000/patient/NEW_USER_001/checkin-status?hours=240"
```

### Response
```json
{
  "status": "ok",
  "has_recent_activity": false,
  "topics_covered": [],
  "hours_since_checkin": null,
  "greeting": "Hi there 👋 Welcome to TRUST AI. I'm here to listen and support you. This is a safe, private space — you can share what's on your mind today, and I'll meet you with care and understanding.",
  "tone": "supportive",
  "risk_score": 30,
  "dominant_theme": "first_contact",
  "data_freshness": {
    "subjective_hours_ago": null,
    "physiological_hours_ago": null,
    "is_returning_user": false,
    "all_data_recent": false
  },
  "layers": {
    "contextual_opening": "Hi there 👋 Welcome to TRUST AI. I'm here to listen and support you. This is a safe, private space — you can share what's on your mind today, and I'll meet you with care and understanding.",
    "validation": null,
    "agency": null
  }
}
```

---

## Example 3: High Risk - Crisis Indicators

### Request
```bash
curl -X GET "http://localhost:8000/patient/ALEX003/checkin-status?hours=240"
```

### Response
```json
{
  "status": "ok",
  "has_recent_activity": true,
  "topics_covered": ["suicidal_ideation", "severe_distress", "hopelessness"],
  "hours_since_checkin": 0.5,
  "greeting": "Hi Alex 👋 I see you're feeling overwhelmed right now, and I want to make sure you're safe. Tell me what's happening, and if things ever feel too intense, we have crisis resources available immediately.",
  "tone": "crisis_safe",
  "risk_score": 92,
  "dominant_theme": "override_to_crisis",
  "data_freshness": {
    "subjective_hours_ago": 0.5,
    "physiological_hours_ago": 1.0,
    "is_returning_user": true,
    "all_data_recent": true
  },
  "layers": {
    "contextual_opening": "Hi Alex 👋 I see you're feeling overwhelmed right now...",
    "validation": "What you're going through makes sense. Your feelings are valid.",
    "agency": "I want to make sure you're safe. Tell me what's happening, and if things ever feel too intense, we have crisis resources available immediately."
  }
}
```

### How to Use (Show Crisis Banner)
```javascript
async function selectPatient(patient) {
  const context = await fetch(`/api/patient/${patient.code}/checkin-status`).then(r => r.json());
  
  if (context.tone === 'crisis_safe' || context.risk_score > 85) {
    // Show prominent crisis resources banner
    setShowCrisisResources(true);
    setCrisisMessage("If you are in crisis, call emergency services or text HOME to 741741");
  }
  
  setMessages([{ role: 'assistant', content: context.greeting }]);
}
```

---

## Example 4: Contradiction Handling (Patient vs Wearables)

### Request
```bash
curl -X GET "http://localhost:8000/patient/JORDAN002/checkin-status?hours=240"
```

### Scenario
- Patient reported: "Slept great, feeling good" (sleep_quality: 8)
- Wearable showed: 4 hours sleep, HRV: 16 (stress marker)

### Response
```json
{
  "status": "ok",
  "has_recent_activity": true,
  "topics_covered": ["wellness"],
  "hours_since_checkin": 1.5,
  "greeting": "Hi Jordan 👋 You're feeling good right now, which is wonderful.\n\nSometimes our mind and body are out of sync. You might feel rested, but your body may have been working hard all night. That can leave you depleted in ways you can't quite feel until midday.\n\nYou can share what's on your mind, or I can suggest something that's helped others today. What would be most helpful?",
  "tone": "validating",
  "risk_score": 45,
  "dominant_theme": "general_check_in",
  "data_freshness": {
    "subjective_hours_ago": 1.5,
    "physiological_hours_ago": 2.0,
    "is_returning_user": true,
    "all_data_recent": true
  },
  "layers": {
    "contextual_opening": "Hi Jordan 👋 You're feeling good right now, which is wonderful.",
    "validation": "Sometimes our mind and body are out of sync. You might feel rested, but your body may have been working hard all night. That can leave you depleted in ways you can't quite feel until midday.",
    "agency": "You can share what's on your mind, or I can suggest something that's helped others today. What would be most helpful?"
  }
}
```

**Key Feature:** Greeting honors what patient reported (feeling good) while silently adjusting risk score based on wearable data.

---

## Example 5: Recurring Theme Recognition

### Request
```bash
curl -X GET "http://localhost:8000/patient/MORGAN004/checkin-status?hours=240"
```

### Scenario
- Patient has spoken about workplace stress in 12 previous sessions
- Last message mentioned "my boss again today"
- Check-in shows elevated stress

### Response
```json
{
  "status": "ok",
  "has_recent_activity": true,
  "topics_covered": ["stress", "workplace_challenges"],
  "hours_since_checkin": 3.0,
  "greeting": "Hi Morgan 👋 I see you're feeling stressed today. Last time we talked, workplace challenges were on your mind. Is that still coming up for you, or is there something new you'd like to talk about?\n\nWork stress is one of the most common triggers I see, and it makes complete sense that it affects everything — your sleep, your mood, your ability to cope. I'm here to help you find ways through this.\n\nYou can tell me what's happening at work, or we could explore some ways to manage the stress response in your body right now. What feels most urgent?",
  "tone": "validating",
  "risk_score": 52,
  "dominant_theme": "recurring_theme:workplace_stress",
  "data_freshness": {
    "subjective_hours_ago": 3.0,
    "physiological_hours_ago": null,
    "is_returning_user": true,
    "all_data_recent": false
  },
  "layers": {
    "contextual_opening": "Hi Morgan 👋 I see you're feeling stressed today. Last time we talked, workplace challenges were on your mind. Is that still coming up for you, or is there something new you'd like to talk about?",
    "validation": "Work stress is one of the most common triggers I see, and it makes complete sense that it affects everything — your sleep, your mood, your ability to cope. I'm here to help you find ways through this.",
    "agency": "You can tell me what's happening at work, or we could explore some ways to manage the stress response in your body right now. What feels most urgent?"
  }
}
```

---

## Response Status Codes

### 200 OK - Success
Greeting generated successfully. Check `status` field for "ok".

### 200 OK - Graceful Fallback
If data is completely unavailable, still returns 200 with generic greeting:
```json
{
  "status": "error",
  "has_recent_activity": false,
  "greeting": "Hi [name], welcome. I'm here to listen and support you. What's on your mind today?",
  "error": "Database connection failed"
}
```

### Error Fields
- `error`: Human-readable error message
- `status`: "ok" or "error"
- `greeting`: Always provided (fallback if needed)

---

## Frontend Integration Checklist

- [ ] Update patient selection flow to call new endpoint
- [ ] Parse `data_freshness` to determine greeting type
- [ ] Use `tone` field for message styling/styling class
- [ ] Display crisis banner if `tone === "crisis_safe"` or `risk_score > 85`
- [ ] Log `dominant_theme` for analytics
- [ ] Show optional "Data sources:" in dev mode using `data_freshness`
- [ ] Handle error case with fallback greeting
- [ ] Test with all 5 examples above
- [ ] Verify greeting displays with correct line breaks

---

## Tone CSS Classes

```css
/* Styling based on tone field */
.greeting-supportive { border-left: 3px solid #60a5fa; } /* blue */
.greeting-validating { border-left: 3px solid #34d399; } /* teal */
.greeting-calm_grounding { border-left: 3px solid #fbbf24; } /* amber */
.greeting-crisis_safe { 
  border-left: 3px solid #ef4444; 
  background: #fee2e2;
}
```

---

## Call Flow Diagram

```
Frontend: selectPatient(patient)
    ↓
GET /patient/{code}/checkin-status?hours=240
    ↓
Backend: 
  - Fetch from daily_checkins (subjective)
  - Fetch from wearable_readings (physiological)
  - Fetch from conversations (historical)
    ↓
Synthesis:
  - Detect contradictions
  - Calculate risk scores
  - Determine tone
    ↓
Generate Greeting:
  - Layer 1: Contextual Opening
  - Layer 2: Validation
  - Layer 3: Agency
    ↓
Return Response:
  {
    greeting: "...",
    tone: "calm_grounding",
    risk_score: 65,
    ...
  }
    ↓
Frontend: Display greeting, set tone styling
```

---

## Performance Notes

- **Typical Response Time:** 50-200ms (3 DB queries)
- **Cache:** Consider caching responses for 5 minutes per patient
- **Rate Limit:** No hard limit, but monitor for abuse
- **Concurrent Users:** Each request is independent; good for scaling

---

## Support

For issues or questions, refer to:
- `GREETING_SYNTHESIS_IMPLEMENTATION.md` — Full implementation guide
- `patient_context_synthesis.py` — Synthesis logic
- `greeting_generator.py` — Greeting generation
