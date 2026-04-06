-- ============================================================================
-- TRUST AI — SUPABASE MIGRATION
-- Apply to Supabase SQL Editor: https://app.supabase.com/project/odxtrlhrfivvxojizixw/sql
--
-- Adds the 3 missing tables + the unique constraint + 5 views.
-- Safe to run against the existing live schema — all statements use
-- CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS / CREATE OR REPLACE VIEW.
-- ============================================================================


-- ============================================================================
-- 1. MISSING UNIQUE CONSTRAINT on wearable_readings
--    Prevents duplicate rows per patient per day from daily_data_refresh.py
-- ============================================================================

ALTER TABLE wearable_readings
  ADD CONSTRAINT wearable_unique_daily UNIQUE (patient_id, reading_date);


-- ============================================================================
-- 2. patient_addictions  (table 16)
--    Junction table — one row per addiction type per patient.
--    Replaces the single onboarding_profiles.addiction_type for multi-addiction cases.
-- ============================================================================

CREATE TABLE IF NOT EXISTS patient_addictions (
  addiction_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id      UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  patient_code    VARCHAR(20) NOT NULL,

  addiction_type  TEXT        NOT NULL
    CHECK (addiction_type IN (
      'alcohol','drugs','gaming','social_media','nicotine','smoking','gambling','work'
    )),

  is_primary      BOOLEAN     NOT NULL DEFAULT FALSE,

  severity        TEXT        NOT NULL DEFAULT 'high'
    CHECK (severity IN ('critical','high','medium','low')),

  noted_at        DATE,
  clinical_notes  TEXT,
  is_active       BOOLEAN     DEFAULT TRUE,

  created_at      TIMESTAMP   DEFAULT now(),
  updated_at      TIMESTAMP   DEFAULT now(),

  UNIQUE (patient_id, addiction_type)
);

-- Enforce exactly one primary active addiction per patient
CREATE UNIQUE INDEX IF NOT EXISTS idx_patient_addictions_one_primary
  ON patient_addictions (patient_id)
  WHERE is_primary = TRUE AND is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_patient_addictions_code   ON patient_addictions(patient_code);
CREATE INDEX IF NOT EXISTS idx_patient_addictions_type   ON patient_addictions(addiction_type);
CREATE INDEX IF NOT EXISTS idx_patient_addictions_active ON patient_addictions(patient_id) WHERE is_active = TRUE;


-- ============================================================================
-- 3. response_routing  (table 17)
--    Clinician-editable matrix: (addiction × intent) → routing strategy.
--    Fixes the startup warning: "Could not find table 'public.response_routing'"
-- ============================================================================

CREATE TABLE IF NOT EXISTS response_routing (
  routing_id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_addiction   TEXT    NOT NULL,
  detected_intent     TEXT    NOT NULL,

  relationship        TEXT    NOT NULL
    CHECK (relationship IN (
      'primary','comorbidity','cross_high','cross_medium',
      'sleep','mood','trigger','behaviour','distress','relapse'
    )),

  severity_override   TEXT    CHECK (severity_override IN ('critical','high','medium','low')),
  video_key           TEXT,
  requires_escalation BOOLEAN DEFAULT FALSE,
  clinical_note       TEXT,
  is_active           BOOLEAN DEFAULT TRUE,

  created_at          TIMESTAMP DEFAULT now(),
  updated_at          TIMESTAMP DEFAULT now(),

  UNIQUE (patient_addiction, detected_intent)
);

CREATE INDEX IF NOT EXISTS idx_response_routing_pair
  ON response_routing(patient_addiction, detected_intent) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_response_routing_escalate
  ON response_routing(patient_addiction) WHERE requires_escalation = TRUE;

-- Seed: encode current hardcoded routing logic into DB rows
INSERT INTO response_routing (patient_addiction, detected_intent, relationship, severity_override, video_key, requires_escalation, clinical_note) VALUES
  -- PRIMARY cravings
  ('alcohol',      'addiction_drugs',        'primary',      'high',   'addiction_alcohol',      false, 'Alcohol patient craving alcohol/substances — primary craving response'),
  ('drugs',        'addiction_drugs',        'primary',      'high',   'addiction_drugs',        false, 'Drug patient craving substances — primary craving response'),
  ('gaming',       'addiction_gaming',       'primary',      'high',   'addiction_gaming',       false, 'Gaming patient craving gaming — primary craving response'),
  ('social_media', 'addiction_social_media', 'primary',      'medium', 'addiction_social_media', false, 'Social media patient craving social media — primary response'),
  ('nicotine',     'addiction_nicotine',     'primary',      'high',   'addiction_nicotine',     false, 'Nicotine patient craving nicotine — primary craving response'),
  ('smoking',      'addiction_nicotine',     'primary',      'high',   'addiction_nicotine',     false, 'Smoking patient craving nicotine — primary craving response'),
  ('gambling',     'addiction_gambling',     'primary',      'high',   'addiction_gambling',     false, 'Gambling patient craving gambling — primary craving response'),
  -- CROSS-ADDICTION: behavioural → alcohol/drugs (HIGH risk)
  ('gaming',       'addiction_drugs',        'cross_high',   'high',   'addiction_drugs',        true,  'Gaming patient craving alcohol/drugs — high risk cross-addiction: clinician review'),
  ('social_media', 'addiction_drugs',        'cross_high',   'high',   'addiction_drugs',        true,  'Social media patient craving alcohol/drugs — high risk cross-addiction'),
  ('gambling',     'addiction_drugs',        'cross_high',   'high',   'addiction_drugs',        true,  'Gambling patient craving alcohol/drugs — high risk cross-addiction'),
  ('nicotine',     'addiction_drugs',        'cross_high',   'high',   'addiction_drugs',        false, 'Nicotine patient craving alcohol/drugs — elevated cross-craving risk'),
  -- CROSS-ADDICTION: substance → gambling (HIGH risk — shared impulsivity)
  ('alcohol',      'addiction_gambling',     'cross_high',   'high',   'addiction_gambling',     true,  'Alcohol patient craving gambling — high risk: impulsivity pathways overlap'),
  ('drugs',        'addiction_gambling',     'cross_high',   'high',   'addiction_gambling',     true,  'Drug patient craving gambling — high risk: impulsivity pathways overlap'),
  -- CROSS-ADDICTION: substance → behavioural (MEDIUM risk)
  ('alcohol',      'addiction_gaming',       'cross_medium', 'medium', 'addiction_gaming',       false, 'Alcohol patient craving gaming — moderate cross-craving; monitor for compulsion'),
  ('alcohol',      'addiction_social_media', 'cross_medium', 'medium', 'addiction_social_media', false, 'Alcohol patient craving social media — moderate cross-craving'),
  ('alcohol',      'addiction_nicotine',     'cross_medium', 'medium', 'addiction_nicotine',     false, 'Alcohol patient craving nicotine — moderate cross-craving'),
  ('drugs',        'addiction_gaming',       'cross_medium', 'medium', 'addiction_gaming',       false, 'Drug patient craving gaming — moderate cross-craving'),
  ('drugs',        'addiction_social_media', 'cross_medium', 'medium', 'addiction_social_media', false, 'Drug patient craving social media — moderate cross-craving'),
  ('drugs',        'addiction_nicotine',     'cross_medium', 'medium', 'addiction_nicotine',     false, 'Drug patient craving nicotine — moderate cross-craving'),
  -- CROSS-ADDICTION: gambling ↔ gaming (MEDIUM risk)
  ('gambling',     'addiction_gaming',       'cross_medium', 'medium', 'addiction_gaming',       false, 'Gambling patient craving gaming — moderate; watch for dopamine substitution'),
  ('gaming',       'addiction_gambling',     'cross_medium', 'medium', 'addiction_gambling',     false, 'Gaming patient craving gambling — moderate; watch for escalation to financial risk'),
  -- CROSS-ADDICTION: nicotine ↔ others
  ('nicotine',     'addiction_gaming',       'cross_medium', 'medium', 'addiction_gaming',       false, 'Nicotine patient craving gaming — cross-craving awareness'),
  ('nicotine',     'addiction_social_media', 'cross_medium', 'medium', 'addiction_social_media', false, 'Nicotine patient craving social media — cross-craving awareness'),
  ('nicotine',     'addiction_gambling',     'cross_medium', 'medium', 'addiction_gambling',     false, 'Nicotine patient craving gambling — cross-craving awareness'),
  -- SLEEP
  ('alcohol',      'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Alcohol patient reporting sleep problems'),
  ('drugs',        'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Drug patient reporting sleep problems (PAWS common)'),
  ('gaming',       'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Gaming patient reporting sleep problems (screen/cortisol)'),
  ('social_media', 'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Social media patient reporting sleep problems'),
  ('nicotine',     'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Nicotine patient reporting sleep problems (stimulant)'),
  ('smoking',      'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Smoking patient reporting sleep problems'),
  ('gambling',     'behaviour_sleep', 'sleep', 'medium', NULL, false, 'Gambling patient reporting sleep problems (rumination/financial stress)'),
  -- RELAPSE DISCLOSURE
  ('alcohol',      'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Alcohol relapse disclosure: normalise slip, avoid judgment/advice'),
  ('drugs',        'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Drug relapse disclosure: normalise slip, avoid judgment/advice'),
  ('gaming',       'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Gaming relapse disclosure: normalise slip, avoid judgment/advice'),
  ('social_media', 'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Social media relapse disclosure: normalise slip, avoid judgment/advice'),
  ('nicotine',     'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Nicotine relapse disclosure: normalise slip, avoid judgment/advice'),
  ('smoking',      'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Smoking relapse disclosure: normalise slip, avoid judgment/advice'),
  ('gambling',     'relapse_disclosure', 'relapse', 'medium', NULL, false, 'Gambling relapse disclosure: normalise slip, avoid judgment/advice')
ON CONFLICT (patient_addiction, detected_intent) DO NOTHING;


-- ============================================================================
-- 4. patient_context_vectors  (audit table)
--    Stores synthesized context vectors for every greeting shown to a patient.
--    Referenced by db_supabase.py and chatbot_engine.py.
-- ============================================================================

CREATE TABLE IF NOT EXISTS patient_context_vectors (
  vector_id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

  patient_id                   UUID        NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
  patient_code                 VARCHAR(20),
  session_id                   TEXT,

  -- Data source availability
  has_subjective_data          BOOLEAN     DEFAULT false,
  has_physiological_data       BOOLEAN     DEFAULT false,
  has_historical_data          BOOLEAN     DEFAULT false,

  -- Synthesis results
  dominant_theme               VARCHAR(100),
  emotional_anchor             VARCHAR(100),
  tone_directive               VARCHAR(50),

  -- Risk scores (1–100)
  subjective_risk_score        INTEGER     CHECK (subjective_risk_score BETWEEN 1 AND 100),
  objective_risk_score         INTEGER     CHECK (objective_risk_score BETWEEN 1 AND 100),
  clinical_risk_score          INTEGER     CHECK (clinical_risk_score BETWEEN 1 AND 100),

  -- Contradiction detection
  contradiction_detected       BOOLEAN     DEFAULT false,
  contradiction_type           VARCHAR(100),

  -- Data freshness
  subjective_hours_ago         DECIMAL(5,1),
  physiological_hours_ago      DECIMAL(5,1),
  subjective_timestamp         TIMESTAMP,
  physiological_timestamp      TIMESTAMP,

  -- Greeting output
  greeting_text                TEXT,
  contextual_opening           TEXT,
  validation_note              TEXT,
  agency_note                  TEXT,

  created_at                   TIMESTAMP   DEFAULT now(),

  CONSTRAINT context_vector_unique UNIQUE (patient_id, created_at)
);

CREATE INDEX IF NOT EXISTS idx_context_patient_time
  ON patient_context_vectors(patient_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_context_high_risk
  ON patient_context_vectors(patient_code, clinical_risk_score DESC)
  WHERE clinical_risk_score > 60;

CREATE INDEX IF NOT EXISTS idx_context_contradictions
  ON patient_context_vectors(patient_code, created_at DESC)
  WHERE contradiction_detected = true;

CREATE INDEX IF NOT EXISTS idx_context_tone
  ON patient_context_vectors(patient_code, tone_directive, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_context_theme
  ON patient_context_vectors(patient_code, dominant_theme, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_context_time_range
  ON patient_context_vectors(patient_code, created_at DESC);


-- ============================================================================
-- 5. VIEWS  (CREATE OR REPLACE — safe to re-run)
-- ============================================================================

-- Latest daily check-in per patient
CREATE OR REPLACE VIEW latest_checkins AS
SELECT DISTINCT ON (patient_id)
  patient_id, checkin_id, checkin_date, todays_mood, stress_score,
  sleep_quality, sleep_hours, rest_level, craving_intensity,
  medication_taken, trigger_exposure_flag, triggers_today, trigger_intensity,
  recovery_activity_today, recovery_social_support, social_contact,
  addiction_specific_data, negative_affect, high_life_stress,
  exercise_done, self_care_activities, checkin_risk_score,
  checkin_completed_via, missed_checkin_days, created_at
FROM daily_checkins
ORDER BY patient_id, checkin_date DESC;


-- Patient snapshot for admin dashboard
CREATE OR REPLACE VIEW patient_snapshot AS
SELECT
  p.patient_id, p.patient_code, p.first_name, p.is_active, p.last_active_at,
  s.session_id,
  s.started_at        AS last_session_start,
  s.session_type      AS last_session_type,
  r.live_risk_score, r.risk_level, r.risk_score_delta,
  r.risk_trend_7day,  r.ai_confidence_score,
  lc.todays_mood, lc.stress_score, lc.sleep_quality,
  lc.craving_intensity, lc.trigger_exposure_flag, lc.missed_checkin_days
FROM patients p
LEFT JOIN sessions s ON p.patient_id = s.patient_id
  AND s.started_at = (SELECT MAX(started_at) FROM sessions WHERE patient_id = p.patient_id)
LEFT JOIN risk_assessments r ON s.session_id = r.session_id
  AND r.computed_at = (SELECT MAX(computed_at) FROM risk_assessments WHERE patient_id = p.patient_id)
LEFT JOIN latest_checkins lc ON p.patient_id = lc.patient_id;


-- Open crisis events requiring follow-up
CREATE OR REPLACE VIEW open_crisis_events AS
SELECT e.*, p.first_name, p.patient_code
FROM crisis_events e
JOIN patients p ON e.patient_id = p.patient_id
WHERE e.followup_completed = false
ORDER BY e.created_at DESC;


-- Full patient context vector — assembled before patient types a word
CREATE OR REPLACE VIEW patient_context_vector AS
SELECT
  p.patient_id, p.patient_code,
  p.first_name            AS patient_name,
  p.preferred_language, p.timezone,
  -- Onboarding
  o.addiction_type, o.baseline_mood, o.primary_triggers,
  o.trauma_history, o.suicide_attempt_history, o.cognitive_impairment,
  o.family_member_uses, o.drug_using_peers, o.uses_substance_for_sleep,
  o.high_impulsivity, o.avoidant_coping, o.low_self_efficacy,
  o.low_motivation, o.emotion_regulation_difficulty, o.cue_reactivity,
  o.insomnia, o.mutual_help_group, o.support_network,
  o.sleep_quality_baseline, o.craving_frequency_baseline,
  o.medication_adherence_baseline,
  -- Latest check-in
  lc.checkin_date, lc.todays_mood, lc.stress_score, lc.sleep_quality,
  lc.rest_level, lc.sleep_hours, lc.craving_intensity, lc.medication_taken,
  lc.trigger_exposure_flag, lc.recovery_activity_today,
  lc.recovery_social_support, lc.addiction_specific_data,
  lc.negative_affect, lc.high_life_stress, lc.missed_checkin_days,
  -- Latest risk assessment
  r.live_risk_score, r.risk_level, r.risk_score_delta, r.risk_trend_7day,
  r.key_risk_drivers, r.crisis_flag, r.ai_confidence_score,
  r.tone_applied          AS last_tone_applied,
  -- Latest wearable
  w.reading_date          AS wearable_date,
  w.hr_bpm, w.hrv_ms, w.spo2_pct, w.steps_today, w.restlessness_level,
  w.sleep_hours           AS wearable_sleep_hours,
  w.sleep_quality_derived AS wearable_sleep_quality,
  w.physiological_stress_score, w.arousal_proxy_score,
  w.personal_anomaly_flag, w.stress_level_device,
  -- Last video shown
  ce.content_title        AS last_video_title,
  ce.content_id           AS last_video_id,
  ce.completion_pct       AS last_video_completion,
  ce.shown_at             AS last_video_shown_at,
  ce.skipped              AS last_video_skipped
FROM patients p
LEFT JOIN onboarding_profiles o ON p.patient_id = o.patient_id
LEFT JOIN latest_checkins lc    ON p.patient_id = lc.patient_id
LEFT JOIN LATERAL (
  SELECT * FROM risk_assessments
  WHERE patient_id = p.patient_id
  ORDER BY computed_at DESC LIMIT 1
) r ON true
LEFT JOIN LATERAL (
  SELECT * FROM wearable_readings
  WHERE patient_id = p.patient_id
  ORDER BY reading_date DESC LIMIT 1
) w ON true
LEFT JOIN LATERAL (
  SELECT * FROM content_engagement
  WHERE patient_id = p.patient_id
  ORDER BY shown_at DESC LIMIT 1
) ce ON true;


-- 7-day risk trend per patient
CREATE OR REPLACE VIEW risk_trend_7day AS
SELECT
  ra.patient_id,
  DATE(ra.computed_at)             AS risk_date,
  AVG(ra.live_risk_score)::INTEGER AS avg_risk_score,
  MAX(ra.live_risk_score)          AS peak_risk_score,
  BOOL_OR(ra.crisis_flag)          AS had_crisis
FROM risk_assessments ra
WHERE ra.computed_at >= NOW() - INTERVAL '7 days'
GROUP BY ra.patient_id, DATE(ra.computed_at)
ORDER BY ra.patient_id, risk_date DESC;
