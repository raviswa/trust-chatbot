"""
daily_data_refresh.py — Automated daily synthetic data refresh for test patients.

Runs at midnight UTC via APScheduler (hooked into FastAPI lifespan).
Also called once on server startup if today's data is missing.

Inserts today's check-ins and wearable readings for all test patients using
upsert-safe logic:
  - daily_checkins: skips insert if a row for today already exists
  - wearable_readings: uses ON CONFLICT DO NOTHING (UNIQUE patient_id + reading_date)
"""

import logging
import random
from datetime import date, datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-patient base profiles — realistic clinical baselines with daily variance
# ---------------------------------------------------------------------------

PATIENT_PROFILES = {
    "PAT-001": {  # Arjun — Alcohol, stressed baseline
        "mood_pool": ["Stressed", "Stressed", "Anxious", "Neutral", "Hopeful"],
        "sleep_quality_range": (3, 6), "sleep_hours_range": (4.5, 6.5),
        "craving_range": (5, 9), "trigger_range": (5, 8),
        "medication": 0.90, "social": 0.20, "exercise": 0.15,
        "hr_range": (82, 95), "hrv_range": (14, 24),
        "stress_score_range": (0.60, 0.80), "stress_device_pool": ["High", "High", "Moderate"],
        "anomaly_chance": 0.40,
        "anomaly_pool": ["elevated resting heart rate", "poor overnight HRV recovery"],
    },
    "PAT-002": {  # Priya — Cannabis, anxious/isolated
        "mood_pool": ["Anxious", "Anxious", "Neutral", "Sad", "Hopeful"],
        "sleep_quality_range": (4, 7), "sleep_hours_range": (5.5, 7.0),
        "craving_range": (3, 7), "trigger_range": (3, 6),
        "medication": 0.92, "social": 0.25, "exercise": 0.20,
        "hr_range": (76, 88), "hrv_range": (18, 28),
        "stress_score_range": (0.50, 0.70), "stress_device_pool": ["Moderate", "Moderate", "Low"],
        "anomaly_chance": 0.25,
        "anomaly_pool": ["elevated morning anxiety markers", "reduced sleep efficiency"],
    },
    "PAT-003": {  # Karthik — Gaming, angry/sleep-deprived
        "mood_pool": ["Angry", "Angry", "Stressed", "Neutral", "Frustrated"],
        "sleep_quality_range": (2, 5), "sleep_hours_range": (3.5, 5.5),
        "craving_range": (4, 8), "trigger_range": (5, 9),
        "medication": 0.85, "social": 0.15, "exercise": 0.10,
        "hr_range": (85, 98), "hrv_range": (11, 20),
        "stress_score_range": (0.65, 0.85), "stress_device_pool": ["High", "High", "Severe"],
        "anomaly_chance": 0.50,
        "anomaly_pool": ["very low HRV and poor sleep", "high nocturnal HR"],
    },
    "PAT-004": {  # Divya — Trauma & Anxiety, PTSD
        "mood_pool": ["Anxious", "Anxious", "Overwhelmed", "Sad", "Neutral"],
        "sleep_quality_range": (2, 5), "sleep_hours_range": (3.5, 5.5),
        "craving_range": (1, 4), "trigger_range": (5, 10),
        "medication": 0.88, "social": 0.15, "exercise": 0.12,
        "hr_range": (88, 100), "hrv_range": (9, 16),
        "stress_score_range": (0.72, 0.92), "stress_device_pool": ["High", "Severe", "Severe"],
        "anomaly_chance": 0.60,
        "anomaly_pool": ["physiological stress markers elevated", "hyperarousal HR pattern"],
    },
    "PAT-005": {  # Rajesh — Nicotine, stressed but functional
        "mood_pool": ["Stressed", "Neutral", "Determined", "Anxious", "Hopeful"],
        "sleep_quality_range": (5, 8), "sleep_hours_range": (6.0, 7.5),
        "craving_range": (5, 9), "trigger_range": (4, 7),
        "medication": 0.95, "social": 0.55, "exercise": 0.30,
        "hr_range": (74, 85), "hrv_range": (22, 34),
        "stress_score_range": (0.45, 0.65), "stress_device_pool": ["Moderate", "Moderate", "Low"],
        "anomaly_chance": 0.20,
        "anomaly_pool": ["post-craving HR spike", "mild stress elevation"],
    },
    "PAT-006": {  # Ananya — Digital Addiction, restless but improving
        "mood_pool": ["Anxious", "Neutral", "Restless", "Hopeful", "Calm"],
        "sleep_quality_range": (5, 8), "sleep_hours_range": (6.0, 7.5),
        "craving_range": (2, 6), "trigger_range": (3, 6),
        "medication": 0.90, "social": 0.55, "exercise": 0.50,
        "hr_range": (70, 80), "hrv_range": (26, 38),
        "stress_score_range": (0.35, 0.55), "stress_device_pool": ["Low", "Low", "Moderate"],
        "anomaly_chance": 0.15,
        "anomaly_pool": ["mild evening cortisol elevation", "restlessness before sleep"],
    },
    "PAT-007": {  # Suresh — Grief Support, withdrawn/sad
        "mood_pool": ["Sad", "Sad", "Neutral", "Lonely", "Hopeful"],
        "sleep_quality_range": (3, 6), "sleep_hours_range": (4.5, 6.5),
        "craving_range": (0, 3), "trigger_range": (2, 6),
        "medication": 0.88, "social": 0.20, "exercise": 0.15,
        "hr_range": (68, 78), "hrv_range": (22, 32),
        "stress_score_range": (0.40, 0.60), "stress_device_pool": ["Moderate", "Low", "Low"],
        "anomaly_chance": 0.20,
        "anomaly_pool": ["low activity and reduced HR variability", "prolonged sedentary periods"],
    },
    "PAT-008": {  # Lakshmi — Alcohol (high risk)
        "mood_pool": ["Overwhelmed", "Overwhelmed", "Hopeless", "Angry", "Scared"],
        "sleep_quality_range": (1, 4), "sleep_hours_range": (2.5, 4.5),
        "craving_range": (7, 10), "trigger_range": (7, 10),
        "medication": 0.55, "social": 0.10, "exercise": 0.05,
        "hr_range": (92, 105), "hrv_range": (7, 14),
        "stress_score_range": (0.82, 0.97), "stress_device_pool": ["Severe", "Severe", "Critical"],
        "anomaly_chance": 0.80,
        "anomaly_pool": ["critical — very low HRV and elevated HR", "overnight physiological crisis markers"],
    },
    "PAT-009": {  # Vikram — Behavioural (Gambling), impulsive
        "mood_pool": ["Stressed", "Restless", "Anxious", "Neutral", "Determined"],
        "sleep_quality_range": (4, 7), "sleep_hours_range": (5.5, 7.0),
        "craving_range": (5, 8), "trigger_range": (5, 8),
        "medication": 0.80, "social": 0.45, "exercise": 0.25,
        "hr_range": (78, 90), "hrv_range": (16, 26),
        "stress_score_range": (0.55, 0.72), "stress_device_pool": ["Moderate", "Moderate", "High"],
        "anomaly_chance": 0.30,
        "anomaly_pool": ["impulsivity-linked HR pattern", "elevated evening stress response"],
    },
    "PAT-010": {  # Meera — Cannabis (discharged), recovering well
        "mood_pool": ["Hopeful", "Calm", "Positive", "Neutral", "Grateful"],
        "sleep_quality_range": (7, 10), "sleep_hours_range": (7.0, 8.5),
        "craving_range": (0, 3), "trigger_range": (0, 3),
        "medication": 0.98, "social": 0.75, "exercise": 0.65,
        "hr_range": (62, 72), "hrv_range": (35, 48),
        "stress_score_range": (0.18, 0.38), "stress_device_pool": ["Low", "Low", "Minimal"],
        "anomaly_chance": 0.08,
        "anomaly_pool": ["mild post-exercise HR elevation"],
    },
}


def _int_range(lo, hi):
    return random.randint(lo, hi)


def _float_range(lo, hi, decimals=2):
    return round(random.uniform(lo, hi), decimals)


def _build_checkin(patient_id: str, patient_code: str) -> dict:
    p = PATIENT_PROFILES[patient_code]
    today = date.today().isoformat()
    sleep_q = _int_range(*p["sleep_quality_range"])
    craving = _int_range(*p["craving_range"])
    exercise_done = random.random() < p["exercise"]
    row = {
        "patient_id": patient_id,
        "checkin_date": today,
        "todays_mood": random.choice(p["mood_pool"]),
        "sleep_quality": sleep_q,
        "sleep_hours": _float_range(*p["sleep_hours_range"], 1),
        "craving_intensity": craving,
        "trigger_intensity": _int_range(*p["trigger_range"]),
        "medication_taken": random.random() < p["medication"],
        "social_contact": random.random() < p["social"],
        "exercise_done": exercise_done,
        "trigger_exposure_flag": craving >= 7 or random.random() < 0.3,
        "checkin_completed_via": "chat",
    }
    if exercise_done:
        row["exercise_duration_minutes"] = _int_range(15, 45)
    return row


def _build_wearable(patient_id: str, patient_code: str) -> dict:
    p = PATIENT_PROFILES[patient_code]
    today = date.today().isoformat()
    anomaly = random.random() < p["anomaly_chance"]
    row = {
        "patient_id": patient_id,
        "reading_date": today,
        "hr_bpm": _int_range(*p["hr_range"]),
        "hrv_ms": _int_range(*p["hrv_range"]),
        "sleep_hours": _float_range(*p["sleep_hours_range"], 1),
        "steps_today": _int_range(500, 9000),
        "physiological_stress_score": _float_range(*p["stress_score_range"]),
        "stress_level_device": random.choice(p["stress_device_pool"]),
        "personal_anomaly_flag": anomaly,
    }
    if anomaly and p["anomaly_pool"]:
        row["personal_anomaly_detail"] = random.choice(p["anomaly_pool"])
    return row


def run_daily_refresh():
    """
    Insert today's check-in and wearable reading for all test patients.
    Safe to call multiple times — skips patients where today's row already exists.
    """
    today = date.today().isoformat()
    logger.info(f"[DailyRefresh] Starting daily data refresh for {today}")

    try:
        import os
        from dotenv import load_dotenv
        from supabase import create_client

        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            logger.warning("[DailyRefresh] Supabase credentials not found — skipping refresh")
            return

        client = create_client(url, key)

        # Fetch all test patients
        resp = client.table("patients").select("patient_id,patient_code").execute()
        patients = resp.data or []
        if not patients:
            logger.warning("[DailyRefresh] No patients found in DB — skipping")
            return

        checkin_ok = 0
        wearable_ok = 0
        checkin_skip = 0
        wearable_skip = 0

        for p in patients:
            patient_id = p["patient_id"]
            patient_code = p["patient_code"]

            if patient_code not in PATIENT_PROFILES:
                continue  # Only refresh test patients with known profiles

            # ── Daily check-in (skip if today already exists) ──────────────
            existing_checkin = (
                client.table("daily_checkins")
                .select("checkin_date")
                .eq("patient_id", patient_id)
                .eq("checkin_date", today)
                .execute()
            )
            if existing_checkin.data:
                checkin_skip += 1
            else:
                try:
                    client.table("daily_checkins").insert(_build_checkin(patient_id, patient_code)).execute()
                    checkin_ok += 1
                except Exception as e:
                    logger.warning(f"[DailyRefresh] {patient_code} checkin insert failed: {e}")

            # ── Wearable reading (upsert — UNIQUE patient_id + reading_date) ─
            existing_wearable = (
                client.table("wearable_readings")
                .select("reading_date")
                .eq("patient_id", patient_id)
                .eq("reading_date", today)
                .execute()
            )
            if existing_wearable.data:
                wearable_skip += 1
            else:
                try:
                    client.table("wearable_readings").insert(_build_wearable(patient_id, patient_code)).execute()
                    wearable_ok += 1
                except Exception as e:
                    logger.warning(f"[DailyRefresh] {patient_code} wearable insert failed: {e}")

        logger.info(
            f"[DailyRefresh] Done — "
            f"checkins: {checkin_ok} inserted, {checkin_skip} already existed | "
            f"wearables: {wearable_ok} inserted, {wearable_skip} already existed"
        )

    except Exception as e:
        logger.error(f"[DailyRefresh] Unhandled error: {e}", exc_info=True)
