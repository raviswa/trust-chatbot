# Greeting Message Context Verification Report

**Date:** March 27, 2026  
**Status:** ⚠️ **INCOMPLETE IMPLEMENTATION**

---

## Executive Summary

The greeting message **references conversation history but does NOT currently fetch or display:**
- ❌ Daily check-in data (mood, craving intensity, sleep quality, medication)
- ❌ Wearables data (heart rate, HRV, sleep metrics, stress levels)
- ⚠️ Latest entry verification (no sorting by timestamp)

**Current State:** Frontend calls non-existent API endpoints. Greeting shows topics from conversation history only.

---

## User Request

> When the user logs into chatbot, he will be provided with a greeting message (GREET WITH CONTEXT). I would like to confirm if the greeting message is picking up the data from daily check-in, wearables and using whatever entry is the latest.

---

## Verification Results

### 1. Frontend Greeting Flow ✅ WORKING (Partially)

**File:** [frontend/pages/index.js](frontend/pages/index.js#L174-L201)

```javascript
async function selectPatient(p) {
  setPatient(p);
  setScreen('loading');
  
  try {
    // ❌ ISSUE: This endpoint doesn't exist
    const res = await fetch(`${API}/patient/${p.code}/checkin-status?hours=240`);
    const status = await res.json();
    setCheckin(status);

    let opening = '';
    if (status.has_recent_activity && status.topics_covered?.length > 0) {
      // ✅ Shows topics from history
      const topics = status.topics_covered.join(', ');
      const timeAgo = status.hours_since_checkin < 1
        ? `${Math.round(status.hours_since_checkin * 60)} minutes ago`
        : `${Math.round(status.hours_since_checkin)} hour${...}s ago`;
      
      opening = `Welcome back, ${p.name}. Last time we spoke about ${topics} (${timeAgo}). 
                 Are those still on your mind today, or is there something new you would like to talk about?`;
    } else {
      opening = `Hi ${p.name}, welcome. I am here to listen and support you...`;
    }

    setMessages([{ 
      role:'assistant', 
      content: opening, 
      intent: status.has_recent_activity ? 'continuity_greeting' : 'greeting' 
    }]);
  } catch(e) {
    // Falls back to generic greeting on error
    setMessages([{ role:'assistant', content:`Hi ${p.name}, I am here to support you. What is on your mind today?`, intent:'greeting' }]);
  }
}
```

**What This Does:**
- ✅ Fetches recent topics from conversation history
- ✅ Calculates time since last check-in
- ✅ Uses latest topic to personalize greeting
- ✅ Falls back gracefully on error

**What This DOESN'T Do:**
- ❌ Fetch daily check-in data
- ❌ Fetch wearables data
- ❌ Call any endpoint for daily_checkins table
- ❌ Call any endpoint for wearable_readings table

---

### 2. Backend API Endpoints ❌ MISSING

**File:** [backend/chatbot_engine.py](backend/chatbot_engine.py#L668-L696)

**Endpoints That Exist:**
```python
@app.get("/patient/{patient_code}")
@app.get("/patient/{patient_code}/sessions")
@app.get("/patient/{patient_code}/history")
@app.get("/admin/sessions")
```

**Endpoints Called by Frontend But NOT Implemented:**
```
❌ GET /patient/{patient_code}/checkin-status?hours=240
❌ POST /patient/{patient_code}/set-continuity
```

**Impact:** Frontend requests will fail a 404 error, causing the greeting to fall back to the generic message.

---

### 3. Daily Check-in Data ❌ NOT INTEGRATED

**Table Exists:** `daily_checkins` (SUPABASE_SCHEMA.sql)

**Schema Fields:**
```sql
CREATE TABLE daily_checkins (
  checkin_id UUID PRIMARY KEY,
  patient_id UUID NOT NULL REFERENCES patients(patient_id),
  checkin_date DATE,
  craving_intensity INTEGER (1-10),  -- ← Not in greeting
  mood VARCHAR,                      -- ← Not in greeting
  sleep_quality_rating INTEGER,      -- ← Not in greeting
  sleep_hours_logged DECIMAL,        -- ← Not in greeting
  medication_taken BOOLEAN,          -- ← Not in greeting
  triggers_today JSONB,              -- ← Not in greeting
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP
);
```

**Current Database Functions:**

[db.py - get_checkin_status()](backend/db.py#L582-L689)

```python
def get_checkin_status(patient_code: str, hours: int = 12) -> dict:
    """Query conversations table only — does NOT fetch daily_checkins table"""
    
    cur.execute("""
        SELECT c.intent, c.created_at, c.session_id
        FROM conversations c
        WHERE c.patient_code = %s
        AND c.role = 'user'
        AND c.intent = ANY(%s)
        AND c.created_at >= NOW() - (%s * INTERVAL '1 hour')
        ORDER BY c.created_at DESC
    """, (patient_code, ALL_CHECKIN_INTENTS, hours))
    
    # Maps intents to topics, but doesn't fetch actual daily_checkins table data
```

**ISSUE:** 
- ❌ Function queries **conversations** table (message history)
- ❌ Never queries **daily_checkins** table
- ❌ Returns intent tags from conversations (e.g., "mood_sad") not actual check-in data
- ❌ No timestamp sorting to ensure latest entry

**Daily Check-in Data Source:**
```
conversations table → intents like "mood_sad", "craving_3"
        ↓
Should query: daily_checkins table for actual recorded values
```

---

### 4. Wearables Data ❌ COMPLETELY UNUSED

**Table Exists:** `wearable_readings` (SUPABASE_SCHEMA.sql, lines 706-783)

**Schema Fields:**
```sql
CREATE TABLE wearable_readings (
  reading_id UUID PRIMARY KEY,
  patient_id UUID NOT NULL REFERENCES patients(patient_id),
  reading_date DATE NOT NULL,
  
  -- Device Data
  device_type VARCHAR(50),  -- Apple Watch, Fitbit, Samsung, etc.
  hr_bpm INTEGER,           -- Heart rate
  hrv_ms INTEGER,           -- Heart rate variability
  sleep_hours DECIMAL,      -- Hours slept
  sleep_quality_rating INTEGER,
  steps_today INTEGER,
  spo2_pct INTEGER,         -- Blood oxygen
  stress_level_device VARCHAR(10),
  
  -- Derived Scores
  physiological_stress_score DECIMAL(4,3),
  arousal_proxy_score DECIMAL(4,3),
  personal_anomaly_flag BOOLEAN,  -- Alert flag
  
  created_at TIMESTAMP DEFAULT now()
);
```

**Current Usage:** 
```
🔍 grep search for "wearable" → NO RESULTS
🔍 grep search for "heart_rate" → NO RESULTS
🔍 grep search for "hrv" → NO RESULTS
🔍 grep search for "sleep_quality" → NO RESULTS
```

**Functions That Should Exist But Don't:**
```python
❌ get_latest_wearable_reading(patient_code: str)
❌ get_wearables_for_period(patient_code: str, hours: int = 24)
❌ assess_wearable_anomalies(patient_code: str)
```

**Integration Points Missing:**
1. ❌ No wearables fetch in context builder
2. ❌ No wearables in greeting message
3. ❌ No anomaly detection trigger
4. ❌ No stress/HRV alert in conversation

---

### 5. Latest Entry Verification ❌ NOT GUARANTEED

**Current Query (db.py line 608):**
```python
cur.execute("""
    SELECT c.intent, c.created_at, c.session_id
    FROM conversations c
    WHERE c.patient_code = %s
    AND c.role = 'user'
    AND c.intent = ANY(%s)
    AND c.created_at >= NOW() - (%s * INTERVAL '1 hour')
    ORDER BY c.created_at DESC  -- ✅ This orders by creation time
""")
```

**Issue:**
- ✅ Conversations are ordered by `created_at DESC` 
- ❌ But daily_checkins table is never queried
- ❌ Wearable_readings are never queried
- ❌ No cross-table timestamp comparison

**What "Latest" Should Mean:**
```
Latest = MAX(
  COALESCE(last_conversation_at, MIN_DATE),
  COALESCE(last_daily_checkin_at, MIN_DATE),
  COALESCE(last_wearable_reading_at, MIN_DATE)
)
```

---

## Data Flow Diagram

### Current (Partial) Implementation
```
User logs in
    ↓
Frontend calls /patient/{code}/checkin-status
    ↓
❌ ERROR: Endpoint doesn't exist (404)
    ↓
Fallback to generic greeting
    ↓
"Hi {name}, welcome. I am here to listen and support you."
```

### What Should Happen (Target Implementation)
```
User logs in
    ↓
Frontend calls /patient/{code}/checkin-status?hours=240
    ↓
Backend query:
  - conversations table (conversation topics)      ✅ Already done
  - daily_checkins table (mood, cravings, sleep)  ❌ Missing
  - wearable_readings table (heart rate, stress)  ❌ Missing
    ↓
Find LATEST entry across all three tables
    ↓
Build context-rich greeting:
  "Welcome back {name}. Your last check-in {X hours ago} showed:
   - Mood: {mood}
   - Craving intensity: {1-10}
   - Sleep quality: {rating}
   - Heart rate: {bpm} bpm
   - Stress level: {low/moderate/high}
   
   Are those concerns still relevant, or is something new happening today?"
```

---

## Summary Table

| Component | Status | Details |
|-----------|--------|---------|
| Frontend greeting logic | ✅ Implemented | Calls API but endpoint missing |
| Backend `/patient/{code}/checkin-status` endpoint | ❌ Missing | Needs to be created |
| Backend `/patient/{code}/set-continuity` endpoint | ❌ Missing | Needs to be created |
| Query conversations for topics | ✅ Implemented | Working in `get_checkin_status()` |
| Query daily_checkins table | ❌ Missing | Function exists but not used |
| Query wearable_readings table | ❌ Missing | Function needs to be created |
| Latest entry selection | ⚠️ Partial | Only for conversations |
| Wearables anomaly detection | ❌ Missing | No alerting for anomalies |
| Stress level integration | ❌ Missing | Table exists but unused |
| Sleep data integration | ❌ Missing | Only partial (conversation history) |

---

## Recommendations

### Phase 1: Implement Missing Endpoints (Immediate)
1. Add `/patient/{code}/checkin-status?hours=240` endpoint
2. Add `/patient/{code}/set-continuity` endpoint
3. These should return combined data from:
   - Conversations (current topics)
   - Daily check-ins (confirmed data)
   - Wearables (physiological data)

### Phase 2: Data Integration (Next)
1. Create `get_latest_daily_checkin()` function in db.py
2. Create `get_latest_wearable_reading()` function in db.py
3. Integrate both into greeting context builder
4. Ensure timestamps are compared to select TRUE latest

### Phase 3: Wearables Enhancement (Future)
1. Implement anomaly alerting
2. Add stress/HRV commentary to greeting
3. Show trends (improving vs declining)
4. Trigger interventions based on wearable signals

---

## Files to Review

- [frontend/pages/index.js](frontend/pages/index.js#L174-L201) - Greeting call site
- [backend/chatbot_engine.py](backend/chatbot_engine.py#L600-L700) - API endpoints
- [backend/db.py](backend/db.py#L582-L689) - Database functions
- [backend/SUPABASE_SCHEMA.sql](backend/SUPABASE_SCHEMA.sql#L706-L783) - Table definitions
- [backend/patient_context.py](backend/patient_context.py#L1-L100) - Context building

---

## Conclusion

**Answer to User's Question:**

> "I would like to confirm if the greeting message is picking up the data from daily check-in, wearables and using whatever entry is the latest"

**Current Status:**
- ❌ **Daily check-in data:** NOT being used (table exists but unfetched)
- ❌ **Wearables data:** NOT being used (table exists but completely unused)
- ⚠️ **Latest entry:** Partially verified (only for conversation history)

**Root Cause:**
1. Missing API endpoints at `/patient/{code}/checkin-status`
2. Data fetching functions query conversations table only
3. No wearables integration anywhere in codebase
4. No daily_checkins table is queried for greeting context

The greeting message is working for **conversation continuity only**, but is NOT pulling context from daily check-ins or wearables as intended.
