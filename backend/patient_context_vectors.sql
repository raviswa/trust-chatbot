/**
 * PATIENT CONTEXT VECTORS — AUDIT TABLE
 * 
 * Stores synthesized context vectors for every greeting shown to a patient.
 * 
 * Purpose:
 *   - Audit trail: Clinical team can review what greeting was shown and why
 *   - Analytics: Analyze trends in patient's emotional, physiological, historical state
 *   - Accountability: Understand reasoning for each greeting
 *   - Debugging: Trace synthesis decisions
 * 
 * Not a source of truth — clinical data lives in:
 *   - daily_checkins (subjective state)
 *   - wearable_readings (physiological state)
 *   - conversations (historical context)
 * 
 * This table is a SNAPSHOT of synthesis at greeting time.
 */

CREATE TABLE IF NOT EXISTS patient_context_vectors (
  vector_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Patient identifiers
  patient_id                   UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  patient_code                 VARCHAR(20),
  
  -- Session linkage (optional, if greeting shown during active session)
  session_id                   TEXT,
  
  -- ─────────────────────────────────────────────────────────────────────────
  -- DATA SOURCE AVAILABILITY
  -- ─────────────────────────────────────────────────────────────────────────
  
  -- Which data sources had recent data at time of synthesis
  has_subjective_data          BOOLEAN     DEFAULT false,
  has_physiological_data       BOOLEAN     DEFAULT false,
  has_historical_data          BOOLEAN     DEFAULT false,
  
  -- ─────────────────────────────────────────────────────────────────────────
  -- SYNTHESIS RESULTS
  -- ─────────────────────────────────────────────────────────────────────────
  
  -- What was the dominant clinical theme
  dominant_theme               VARCHAR(100),
  -- e.g. "emotional_distress:stressed", "high_craving:8", "poor_sleep", 
  --      "physiological_stress:low_hrv", "recurring_theme:workplace_stress"
  
  -- Primary feeling to validate
  emotional_anchor             VARCHAR(100),
  -- e.g. "feeling stressed and overwhelmed", "feeling lonely"
  
  -- Tone directive applied
  tone_directive               VARCHAR(50),
  -- "calm_grounding", "validating", "celebratory", "curious", "supportive", "crisis_safe"
  
  -- ─────────────────────────────────────────────────────────────────────────
  -- RISK SCORES (1-100 scale)
  -- ─────────────────────────────────────────────────────────────────────────
  
  -- Based on what patient reports (emotional state, subjective experience)
  subjective_risk_score        INTEGER     CHECK (subjective_risk_score BETWEEN 1 AND 100),
  
  -- Based on what wearables show (HRV, heart rate, stress, sleep, activity)
  objective_risk_score         INTEGER     CHECK (objective_risk_score BETWEEN 1 AND 100),
  
  -- 70% subjective + 30% objective (= final risk for clinical use)
  clinical_risk_score          INTEGER     CHECK (clinical_risk_score BETWEEN 1 AND 100),
  
  -- ─────────────────────────────────────────────────────────────────────────
  -- CONTRADICTION DETECTION
  -- ─────────────────────────────────────────────────────────────────────────
  
  -- Was there a conflict between subjective and objective data
  contradiction_detected       BOOLEAN     DEFAULT false,
  
  -- Type of contradiction if detected
  contradiction_type           VARCHAR(100),
  -- "patient_felt_rested_but_objectively_poor"
  -- "patient_calm_but_physiologically_stressed"
  
  -- ─────────────────────────────────────────────────────────────────────────
  -- DATA FRESHNESS
  -- ─────────────────────────────────────────────────────────────────────────
  
  -- How old was the subjective data (hours ago)
  subjective_hours_ago         DECIMAL(5,1),
  
  -- How old was the physiological data (hours ago)
  physiological_hours_ago      DECIMAL(5,1),
  
  -- Timestamps of when source data was created
  subjective_timestamp         TIMESTAMP,
  physiological_timestamp      TIMESTAMP,
  
  -- ─────────────────────────────────────────────────────────────────────────
  -- GREETING OUTPUT
  -- ─────────────────────────────────────────────────────────────────────────
  
  -- Full greeting message shown to patient
  greeting_text                TEXT,
  
  -- Greeting layers (captured separately for easy querying)
  contextual_opening           TEXT,   -- Layer 1: Never generic "how are you?"
  validation_note              TEXT,   -- Layer 2: Normalize the struggle
  agency_note                  TEXT,   -- Layer 3: Invite, don't interrogate
  
  -- ─────────────────────────────────────────────────────────────────────────
  -- AUDIT & TIMING
  -- ─────────────────────────────────────────────────────────────────────────
  
  created_at                   TIMESTAMP   DEFAULT now(),
  
  -- Helpful for historical tracking
  CONSTRAINT context_vector_unique UNIQUE (patient_id, created_at)
);

-- INDEXES for common queries

-- Most recent context vectors for a patient
CREATE INDEX idx_context_patient_time 
  ON patient_context_vectors(patient_id, created_at DESC);

-- Find all high-risk context vectors
CREATE INDEX idx_context_high_risk 
  ON patient_context_vectors(patient_code, clinical_risk_score DESC)
  WHERE clinical_risk_score > 60;

-- Find contradictions
CREATE INDEX idx_context_contradictions
  ON patient_context_vectors(patient_code, created_at DESC)
  WHERE contradiction_detected = true;

-- Find by tone directive (for tone effectiveness analysis)
CREATE INDEX idx_context_tone
  ON patient_context_vectors(patient_code, tone_directive, created_at DESC);

-- Find by dominant theme (pattern analysis)
CREATE INDEX idx_context_theme
  ON patient_context_vectors(patient_code, dominant_theme, created_at DESC);

-- Query by date range (trend analysis)
CREATE INDEX idx_context_time_range
  ON patient_context_vectors(patient_code, created_at DESC);

-- COMMENTS for documentation
COMMENT ON TABLE patient_context_vectors IS
  'Audit trail of synthesized patient context vectors. Stores the clinical reasoning behind each greeting. Not a source of truth for patient data.';

COMMENT ON COLUMN patient_context_vectors.dominant_theme IS
  'The primary clinical theme chosen for the greeting (emotional, physiological, or historical)';

COMMENT ON COLUMN patient_context_vectors.tone_directive IS
  'The conversational tone applied: calm_grounding, validating, celebratory, curious, supportive, or crisis_safe';

COMMENT ON COLUMN patient_context_vectors.clinical_risk_score IS
  'Final risk score = (subjective_risk × 0.7) + (objective_risk × 0.3). Used by backend for intervention urgency.';

COMMENT ON COLUMN patient_context_vectors.contradiction_detected IS
  'True if patient report contradicts wearable data (e.g., patient felt rested but slept 4 hours)';
