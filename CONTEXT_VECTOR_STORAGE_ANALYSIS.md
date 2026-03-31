# Patient Context Vector Storage - Analysis & Recommendations

**Date:** March 27, 2026

---

## Question
Should we create a separate database table for storing the consolidated/synthesized patient context vector?

---

## Analysis

### Current Architecture (In-Memory Synthesis)
```
Frontend requests greeting
    ↓
Backend synthesizes on-demand:
  - Query daily_checkins
  - Query wearable_readings
  - Query conversations
    ↓
Compute context vector in memory
    ↓
Generate greeting
    ↓
Return to frontend
    ↓
Data discarded (not persisted)
```

### Option 1: NO NEW TABLE (Current Implementation)

**Pros:**
- ✅ Single source of truth (data stays where it's generated)
- ✅ No data duplication
- ✅ Always reflects latest data (real-time)
- ✅ Simpler schema (no sync issues)
- ✅ Faster deployment (no migration needed)
- ✅ Works great for initial MVP

**Cons:**
- ❌ Every greeting request requires 3 DB queries
- ❌ Synthesis computation repeated on every request
- ❌ No audit trail (unknown what context was shown to patient)
- ❌ Hard to analyze patterns of context vectors over time
- ❌ If synthesis logic changes, can't replay what was generated
- ❌ Clinical team can't review "what greeting was presented and why"

**When to use:** Ready for quick deployment, want to iterate on synthesis logic

---

### Option 2: CREATE lightweight "context_vectors" TABLE for Auditing

**Pros:**
- ✅ Audit trail: exact context presented to each patient
- ✅ Analytics: analyze how patient's context evolves over time
- ✅ Clinical review: teams can understand why specific greeting was chosen
- ✅ Performance optimization: can cache results
- ✅ Easier debugging: review what data was used at greeting time
- ✅ Support for future features (relapse prediction, trend analysis)

**Cons:**
- ❌ Additional table complexity
- ❌ Potential for stale data if synthesis rules improve
- ❌ Need to decide: store on every greeting? hourly? daily?
- ❌ Migration required
- ❌ More storage

**Schema (Lightweight):**
```sql
CREATE TABLE patient_context_vectors (
  vector_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID REFERENCES patients(patient_id),
  session_id TEXT,
  
  -- What data sources were found
  has_subjective_data BOOLEAN,
  has_physiological_data BOOLEAN,
  has_historical_data BOOLEAN,
  
  -- Key synthesis results
  dominant_theme VARCHAR(100),
  emotional_anchor VARCHAR(100),
  tone_directive VARCHAR(50),
  
  -- Risk scores
  subjective_risk_score INTEGER,
  objective_risk_score INTEGER,
  clinical_risk_score INTEGER,
  
  -- Contradiction flag
  contradiction_detected BOOLEAN,
  contradiction_type VARCHAR(100),
  
  -- Data timestamps (when data was generated)
  subjective_timestamp TIMESTAMP,
  physiological_timestamp TIMESTAMP,
  historical_timestamp TIMESTAMP,
  
  -- Greeting that was shown
  greeting_text TEXT,
  
  -- Metadata
  created_at TIMESTAMP DEFAULT now(),
  INDEX idx_patient_time (patient_id, created_at DESC)
);
```

**When to use:** Production deployment, need audit trail & analytics

---

### Option 3: CREATE Heavy "context_snapshots" TABLE (Save Everything)

**Pros:**
- ✅ Complete historical record
- ✅ Can replay exact scenario
- ✅ Rich data for ML/pattern analysis

**Cons:**
- ❌ Much larger storage footprint
- ❌ Stores redundant data
- ❌ Slower writes
- ❌ Overkill for most use cases

**Not recommended** - too much overhead

---

## Recommendation

### Short Term (MVP Phase)
**Use Option 1: NO NEW TABLE**

Rationale:
- Get working quickly
- Iteration velocity is high (synthesis rules will change)
- Real-time synthesis is more robust
- Can add auditing later

Implementation: **Already done** ✅

---

### Medium Term (Production, 2-4 weeks in)
**Migrate to Option 2: Lightweight Audit Table**

Rationale:
- Teams need audit trail for clinical governance
- 3 DB queries per greeting is acceptable latency
- Lightweight table adds minimal overhead
- Enables valuable analytics

Implementation: Add `patient_context_vectors` table

---

## Detailed Implementation (Option 2)

### Step 1: Create Table

```sql
CREATE TABLE patient_context_vectors (
  vector_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  patient_code VARCHAR(20),
  session_id TEXT,
  
  -- Data source flags
  has_subjective_data BOOLEAN DEFAULT false,
  has_physiological_data BOOLEAN DEFAULT false,
  has_historical_data BOOLEAN DEFAULT false,
  
  -- Synthesis results
  dominant_theme VARCHAR(100),
  emotional_anchor VARCHAR(100),
  tone_directive VARCHAR(50),
  
  -- Risk scores
  subjective_risk_score INTEGER,
  objective_risk_score INTEGER,
  clinical_risk_score INTEGER,
  
  -- Contradiction detection
  contradiction_detected BOOLEAN DEFAULT false,
  contradiction_type VARCHAR(100),
  
  -- Data freshness
  subjective_hours_ago DECIMAL(5,1),
  physiological_hours_ago DECIMAL(5,1),
  
  -- Timestamps of source data (when that data was generated)
  subjective_timestamp TIMESTAMP,
  physiological_timestamp TIMESTAMP,
  
  -- The greeting that was shown
  greeting_text TEXT,
  
  -- Greeting layers
  contextual_opening TEXT,
  validation_note TEXT,
  agency_note TEXT,
  
  -- Metadata
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_context_patient_time ON patient_context_vectors(patient_id, created_at DESC);
CREATE INDEX idx_context_theme ON patient_context_vectors(patient_code, dominant_theme);
CREATE INDEX idx_context_risk ON patient_context_vectors(patient_code, clinical_risk_score DESC);
```

### Step 2: Add Save Function to db.py

```python
def save_context_vector(
    patient_id: str,
    patient_code: str,
    session_id: Optional[str],
    context: SynthesizedContextVector,
    greeting: dict
) -> bool:
    """
    Save synthesized context vector for audit trail and analytics.
    
    Args:
        patient_id: UUID of patient
        patient_code: Patient code
        session_id: Session ID (optional, for linking)
        context: SynthesizedContextVector from synthesis engine
        greeting: Dict returned from greeting_generator
    
    Returns:
        True if saved successfully, False otherwise
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO patient_context_vectors (
                    patient_id, patient_code, session_id,
                    has_subjective_data, has_physiological_data, has_historical_data,
                    dominant_theme, emotional_anchor, tone_directive,
                    subjective_risk_score, objective_risk_score, clinical_risk_score,
                    contradiction_detected, contradiction_type,
                    subjective_hours_ago, physiological_hours_ago,
                    subjective_timestamp, physiological_timestamp,
                    greeting_text, contextual_opening, validation_note, agency_note
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                patient_id, patient_code, session_id,
                context.subjective.is_recent(),
                context.physiological.is_recent(),
                bool(context.historical.session_count),
                context.dominant_theme,
                context.emotional_anchor,
                context.tone_directive.value,
                context.subjective_risk_score,
                context.objective_risk_score,
                context.clinical_risk_score,
                context.contradiction_detected,
                context.contradiction_type,
                context.subjective.hours_ago,
                context.physiological.hours_ago,
                context.subjective.checkin_timestamp,
                context.physiological.wearable_timestamp,
                greeting["greeting"],
                greeting["layers"]["contextual_opening"],
                greeting["layers"]["validation"],
                greeting["layers"]["agency"]
            ))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"save_context_vector failed: {e}")
        return False
```

### Step 3: Call Save Function After Greeting is Generated

In `chatbot_engine.py`, after generating greeting:

```python
@app.get("/patient/{patient_code}/checkin-status")
async def get_patient_checkin_context(patient_code: str, hours: int = 240):
    """..."""
    try:
        # ... (synthesis code)
        
        greeting_result = generate_greeting_message(context, include_sources=False)
        
        # SAVE TO AUDIT TABLE (async/non-blocking)
        try:
            save_context_vector(
                patient_id=patient.get("id"),
                patient_code=patient_code,
                session_id=None,  # Would come from request if available
                context=context,
                greeting=greeting_result
            )
        except Exception as audit_error:
            logger.warning(f"Failed to save context vector: {audit_error}")
            # Don't fail the greeting if auditing fails
        
        return {
            "status": "ok",
            "greeting": greeting_result["greeting"],
            # ... rest of response
        }
```

---

## Use Cases Enabled by Audit Table

### Use Case 1: Clinical Review
"Show me the last 10 greetings presented to this patient and the clinical reasoning"
```sql
SELECT 
    created_at,
    tone_directive,
    dominant_theme,
    clinical_risk_score,
    greeting_text
FROM patient_context_vectors
WHERE patient_id = $1
ORDER BY created_at DESC
LIMIT 10;
```

### Use Case 2: Trend Analysis
"Is this patient's risk score trending up or down?"
```sql
SELECT 
    DATE(created_at),
    AVG(clinical_risk_score) as avg_risk,
    COUNT(*) as greetings_per_day
FROM patient_context_vectors
WHERE patient_id = $1
    AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY DATE(created_at);
```

### Use Case 3: Synthesis Quality Metrics
"Which dominant themes are most common? How often do contradictions occur?"
```sql
SELECT 
    dominant_theme,
    tone_directive,
    COUNT(*) as frequency,
    AVG(clinical_risk_score) as avg_risk,
    SUM(CASE WHEN contradiction_detected THEN 1 ELSE 0 END) as contradictions
FROM patient_context_vectors
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY dominant_theme, tone_directive
ORDER BY frequency DESC;
```

### Use Case 4: Personal Anomaly Detection
"When did this patient's context vector deviate from their normal pattern?"
```sql
SELECT 
    created_at,
    clinical_risk_score,
    tone_directive,
    contradiction_detected,
    contradiction_type
FROM patient_context_vectors
WHERE patient_id = $1
    AND clinical_risk_score > (
        SELECT AVG(clinical_risk_score) * 1.5
        FROM patient_context_vectors
        WHERE patient_id = $1
            AND created_at >= NOW() - INTERVAL '90 days'
    )
ORDER BY created_at DESC;
```

---

## Decision Matrix

| Factor | Option 1 (No Table) | Option 2 (Audit Table) |
|--------|---|---|
| **Deployment Speed** | ⚡ Fast, no migration | 🟡 Needs migration |
| **Real-time Accuracy** | ✅ Always current | ✅ As current as save frequency |
| **Audit Trail** | ❌ No | ✅ Yes |
| **Analytics** | ❌ Limited | ✅ Rich |
| **Storage Overhead** | ✅ Minimal | 🟡 ~1KB per greeting |
| **Query Latency** | ✅ 3 DB queries | ✅ 3 DB queries (+ async save) |
| **Complexity** | ✅ Simple | 🟡 Moderate |
| **Clinical Governance** | ❌ No audit trail | ✅ Full audit trail |

---

## Final Recommendation

### Immediate (Now)
**Use Option 1**: No new table
- Ship to production
- Get real patient data
- Refine synthesis rules based on feedback

### Within 2-4 Weeks
**Add Option 2**: Lightweight audit table
- Provides governance & accountability
- Enables clinical team insights
- Low overhead
- Minimal code complexity

### Not Recommended
**Option 3**: Heavy snapshots table
- Too much storage
- Too much overhead
- Table design is above

---

## Implementation Order

1. **Today**: Deploy with Option 1 (already done ✅)
2. **Week 1**: Monitor greeting quality, collect feedback
3. **Week 2**: Create `patient_context_vectors` table in staging
4. **Week 3**: Test saving context vectors
5. **Week 4**: Deploy to production with audit table

---

## If You Want Audit Table Now...

The table schema above is ready to deploy. You would need to:

1. Create the table (SQL provided)
2. Add `save_context_vector()` function to db.py
3. Call it after greeting generation in chatbot_engine.py
4. Add index on patient_id + created_at for fast queries

**Estimated effort:** 2-3 hours

Would you like me to implement the audit table now or stick with Option 1 for MVP?
