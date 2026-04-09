#!/usr/bin/env python3
"""
Load Sample Data into Supabase
===============================

Creates realistic test patients and data for the chatbot.

Run with: python load_sample_data.py
"""

import os
import json
from datetime import datetime, timedelta, date
from dotenv import load_dotenv
import logging

# Load environment
dotenv_path = os.path.join(os.path.dirname(__file__), ".env.local")
load_dotenv(dotenv_path)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY required")

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sample patient data — each entry maps 1:1 to a use case document
SAMPLE_PATIENTS = [
    {
        # UC 1.1 — Alcohol, Indian (late-night loneliness, Bengaluru)
        "patient_code": "PAT-001",
        "first_name": "Arjun",
        "last_name": "Rao",
        "email": "arjun.rao@example.com",
        "phone": "+91 98765 00001",
        "date_of_birth": "1997-04-01",
        "gender": "Male",
        "country": "India",
        "profile": {
            "addiction_type": "Alcohol",
            "baseline_mood": ["lonely", "sad", "bored"],
            "primary_triggers": ["late night", "loneliness", "living alone"],
            "support_network": {},
            "work_status": "employed",
            "housing_status": "PG accommodation (alone)",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form"],
            "baseline_sleep_quality": 2,
            "baseline_stress": 7,
            "baseline_cravings": 6,
            "social_support": False,
        }
    },
    {
        # UC 1.2 — Alcohol, Global (after-work stress, New York)
        "patient_code": "PAT-002",
        "first_name": "Emily",
        "last_name": "Carter",
        "email": "emily.carter@example.com",
        "phone": "+1 347 900 0002",
        "date_of_birth": "1991-06-15",
        "gender": "Female",
        "country": "United States",
        "profile": {
            "addiction_type": "Alcohol",
            "baseline_mood": ["stressed", "angry", "lonely"],
            "primary_triggers": ["coming home from work", "high-pressure deadlines"],
            "support_network": {},
            "work_status": "employed",
            "housing_status": "stable (Brooklyn apartment)",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form", "narrative"],
            "baseline_sleep_quality": 2,
            "baseline_stress": 8,
            "baseline_cravings": 7,
            "social_support": False,
        }
    },
    {
        # UC 2.1 — Gaming, Indian (study-break procrastination, Delhi)
        "patient_code": "PAT-003",
        "first_name": "Rohan",
        "last_name": "Sharma",
        "email": "rohan.sharma@example.com",
        "phone": "+91 98765 00003",
        "date_of_birth": "2006-09-10",
        "gender": "Male",
        "country": "India",
        "profile": {
            "addiction_type": "Gaming",
            "baseline_mood": ["bored", "stressed", "lonely"],
            "primary_triggers": ["study breaks", "idle moments", "exam pressure"],
            "support_network": {"family": "Lives with family"},
            "work_status": "student",
            "housing_status": "stable (family home)",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form"],
            "baseline_sleep_quality": 3,
            "baseline_stress": 8,
            "baseline_cravings": 7,
            "social_support": False,
        }
    },
    {
        # UC 2.2 — Gaming, Global (late-night one-more-game, London)
        "patient_code": "PAT-004",
        "first_name": "Oliver",
        "last_name": "Thompson",
        "email": "oliver.thompson@example.com",
        "phone": "+44 7700 900004",
        "date_of_birth": "2008-11-22",
        "gender": "Male",
        "country": "United Kingdom",
        "profile": {
            "addiction_type": "Gaming",
            "baseline_mood": ["bored", "lonely", "stressed"],
            "primary_triggers": ["late night", "tiredness", "being alone in room"],
            "support_network": {"family": "Lives with family"},
            "work_status": "student",
            "housing_status": "stable (family home)",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form"],
            "baseline_sleep_quality": 2,
            "baseline_stress": 7,
            "baseline_cravings": 8,
            "social_support": False,
        }
    },
    {
        # UC 3.1 — Substance Use, Indian (emotional pain at night, Mumbai)
        "patient_code": "PAT-005",
        "first_name": "Priya",
        "last_name": "Nair",
        "email": "priya.nair@example.com",
        "phone": "+91 98765 00005",
        "date_of_birth": "2000-03-14",
        "gender": "Female",
        "country": "India",
        "profile": {
            "addiction_type": "Drugs",
            "baseline_mood": ["sad", "lonely", "guilty"],
            "primary_triggers": ["late night", "being alone", "emotional distress after breakup"],
            "support_network": {"family": "Lives with family but feels isolated"},
            "work_status": "employed",
            "housing_status": "stable (family home)",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["narrative"],
            "baseline_sleep_quality": 2,
            "baseline_stress": 8,
            "baseline_cravings": 7,
            "social_support": False,
        }
    },
    {
        # UC 3.2 — Substance Use, Global (anger after argument, Los Angeles)
        "patient_code": "PAT-006",
        "first_name": "Jordan",
        "last_name": "Reyes",
        "email": "jordan.reyes@example.com",
        "phone": "+1 310 900 0006",
        "date_of_birth": "1994-07-08",
        "gender": "Non-binary",
        "country": "United States",
        "profile": {
            "addiction_type": "Drugs",
            "baseline_mood": ["angry", "stressed", "sad"],
            "primary_triggers": ["arguments with partner", "emotional conflict"],
            "support_network": {},
            "work_status": "employed",
            "housing_status": "stable (lives alone)",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form"],
            "baseline_sleep_quality": 2,
            "baseline_stress": 9,
            "baseline_cravings": 8,
            "social_support": False,
        }
    },
    {
        # UC 4.1 — Nicotine, Indian (stressed work-break, Bengaluru)
        "patient_code": "PAT-007",
        "first_name": "Karthik",
        "last_name": "Reddy",
        "email": "karthik.reddy@example.com",
        "phone": "+91 98765 00007",
        "date_of_birth": "1997-01-20",
        "gender": "Male",
        "country": "India",
        "profile": {
            "addiction_type": "Nicotine",
            "baseline_mood": ["stressed", "angry", "tired"],
            "primary_triggers": ["work breaks", "after stressful meetings", "deadlines"],
            "support_network": {},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form"],
            "baseline_sleep_quality": 3,
            "baseline_stress": 8,
            "baseline_cravings": 7,
            "social_support": False,
        }
    },
    {
        # UC 5.1 — Agnostic, Indian (festival pressure + high urge, Bengaluru)
        "patient_code": "PAT-008",
        "first_name": "Ishan",
        "last_name": "Rao",
        "email": "ishan.rao@example.com",
        "phone": "+91 98765 00008",
        "date_of_birth": "2001-02-17",
        "gender": "Male",
        "country": "India",
        "profile": {
            "addiction_type": "Alcohol",
            "baseline_mood": ["stressed", "angry", "lonely"],
            "primary_triggers": ["festival gatherings", "family pressure", "social events"],
            "support_network": {},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form"],
            "baseline_sleep_quality": 2,
            "baseline_stress": 8,
            "baseline_cravings": 8,
            "social_support": False,
        }
    },
    {
        # UC 5.2 — Agnostic, Indian (all-or-nothing after setback, Bengaluru)
        "patient_code": "PAT-009",
        "first_name": "Sneha",
        "last_name": "Patil",
        "email": "sneha.patil@example.com",
        "phone": "+91 98765 00009",
        "date_of_birth": "1998-12-05",
        "gender": "Female",
        "country": "India",
        "profile": {
            "addiction_type": "Alcohol",
            "baseline_mood": ["sad", "stressed", "lonely"],
            "primary_triggers": ["missing a goal", "setbacks", "perfectionism"],
            "support_network": {},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["narrative", "short-form"],
            "baseline_sleep_quality": 3,
            "baseline_stress": 7,
            "baseline_cravings": 6,
            "social_support": False,
        }
    },
    {
        # UC 5.3 — Agnostic, Global (setback shame after 3-week streak, Toronto)
        "patient_code": "PAT-010",
        "first_name": "Alex",
        "last_name": "Chen",
        "email": "alex.chen@example.com",
        "phone": "+1 416 900 0010",
        "date_of_birth": "1992-08-30",
        "gender": "Non-binary",
        "country": "Canada",
        "profile": {
            "addiction_type": "Alcohol",
            "baseline_mood": ["sad", "stressed", "guilty"],
            "primary_triggers": ["missing a goal", "small relapse", "perfectionism"],
            "support_network": {},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["narrative", "short-form"],
            "baseline_sleep_quality": 2,
            "baseline_stress": 7,
            "baseline_cravings": 7,
            "social_support": False,
        }
    },
    {
        # UC 5.4 — Agnostic, Global (inner conflict before going out, New York)
        "patient_code": "PAT-011",
        "first_name": "Taylor",
        "last_name": "Brooks",
        "email": "taylor.brooks@example.com",
        "phone": "+1 917 900 0011",
        "date_of_birth": "1997-04-25",
        "gender": "Non-binary",
        "country": "United States",
        "profile": {
            "addiction_type": "Alcohol",
            "baseline_mood": ["stressed", "lonely", "conflicted"],
            "primary_triggers": ["social situations", "pre-action moments", "friends who drink"],
            "support_network": {},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form"],
            "baseline_sleep_quality": 3,
            "baseline_stress": 7,
            "baseline_cravings": 8,
            "social_support": False,
        }
    },
    {
        # UC 6.1 — Social Media, Indian (morning scroll habit, Hyderabad)
        "patient_code": "PAT-012",
        "first_name": "Aravind",
        "last_name": "Reddy",
        "email": "aravind.reddy@example.com",
        "phone": "+91 98765 00012",
        "date_of_birth": "2004-05-12",
        "gender": "Male",
        "country": "India",
        "profile": {
            "addiction_type": "Social Media",
            "baseline_mood": ["bored", "restless", "low motivation"],
            "primary_triggers": ["morning routine", "idle time after waking", "boredom"],
            "support_network": {},
            "work_status": "student",
            "housing_status": "stable",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form", "interactive"],
            "baseline_sleep_quality": 3,
            "baseline_stress": 6,
            "baseline_cravings": 7,
            "social_support": False,
        }
    },
    {
        # UC 6.2 — Social Media, Global (excitement posting urge, Los Angeles)
        "patient_code": "PAT-013",
        "first_name": "Sophia",
        "last_name": "Martinez",
        "email": "sophia.martinez@example.com",
        "phone": "+1 323 900 0013",
        "date_of_birth": "1998-09-22",
        "gender": "Female",
        "country": "United States",
        "profile": {
            "addiction_type": "Social Media",
            "baseline_mood": ["bored", "stressed", "lonely"],
            "primary_triggers": ["moments of excitement", "good news", "brand collaborations"],
            "support_network": {},
            "work_status": "employed",
            "housing_status": "stable",
            "diagnosed_conditions": [],
            "current_medications": [],
            "previous_treatment": False,
            "previous_treatment_notes": None,
            "communication_preference": "text",
            "content_preferences": ["short-form", "interactive"],
            "baseline_sleep_quality": 3,
            "baseline_stress": 6,
            "baseline_cravings": 7,
            "social_support": False,
        }
    },
]

def insert_todays_checkins(patient_map):
    """Insert today's check-in for all 10 patients with clinically meaningful data."""
    print("\n" + "="*60)
    print("LOADING TODAY'S CHECK-INS")
    print("="*60)

    # Each entry mirrors the use case check-in data (sliders/selections from use case docs)
    TODAY_CHECKINS = {
        "PAT-001": {  # Arjun Rao — UC 1.1 Alcohol Indian: Lonely+Sad, Sleep 2/10, Stress 8, Cravings 7
            "todays_mood": "Lonely",
            "sleep_quality": 2,
            "sleep_hours": 5.0,
            "craving_intensity": 7,
            "trigger_intensity": 8,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-002": {  # Emily Carter — UC 1.2 Alcohol Global: Stressed+Angry, Sleep 2/10, Stress 8, Cravings 8
            "todays_mood": "Stressed",
            "sleep_quality": 2,
            "sleep_hours": 5.5,
            "craving_intensity": 8,
            "trigger_intensity": 8,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-003": {  # Rohan Sharma — UC 2.1 Gaming Indian: Stressed, Sleep 3/10, Stress 7, Cravings 8
            "todays_mood": "Stressed",
            "sleep_quality": 3,
            "sleep_hours": 6.0,
            "craving_intensity": 8,
            "trigger_intensity": 7,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-004": {  # Oliver Thompson — UC 2.2 Gaming Global: Lonely+Stressed, Sleep 2/10, Stress 7, Cravings 9
            "todays_mood": "Lonely",
            "sleep_quality": 2,
            "sleep_hours": 4.5,
            "craving_intensity": 9,
            "trigger_intensity": 7,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-005": {  # Priya Nair — UC 3.1 Substance Indian: Sad+Lonely, Sleep 2/10, Stress 7, Cravings 8
            "todays_mood": "Sad",
            "sleep_quality": 2,
            "sleep_hours": 5.0,
            "craving_intensity": 8,
            "trigger_intensity": 7,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-006": {  # Jordan Reyes — UC 3.2 Substance Global: Angry, Sleep 3/10, Stress 9, Cravings 9
            "todays_mood": "Angry",
            "sleep_quality": 3,
            "sleep_hours": 5.5,
            "craving_intensity": 9,
            "trigger_intensity": 9,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-007": {  # Karthik Reddy — UC 4.1 Nicotine Indian: Stressed, Sleep 4/10, Stress 8, Cravings 8
            "todays_mood": "Stressed",
            "sleep_quality": 4,
            "sleep_hours": 6.0,
            "craving_intensity": 8,
            "trigger_intensity": 8,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-008": {  # Ishan Rao — UC 5.1 Agnostic Indian: Stressed+Sad, Sleep 3/10, Stress 8, Cravings 9
            "todays_mood": "Stressed",
            "sleep_quality": 3,
            "sleep_hours": 5.0,
            "craving_intensity": 9,
            "trigger_intensity": 8,
            "medication_taken": False,
            "social_contact": True,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-009": {  # Sneha Patil — UC 5.2 Agnostic Indian: Sad+Stressed, Sleep 4/10, Stress 7, Cravings 6
            "todays_mood": "Sad",
            "sleep_quality": 4,
            "sleep_hours": 6.5,
            "craving_intensity": 6,
            "trigger_intensity": 7,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-010": {  # Alex Chen — UC 5.3 Agnostic Global: Sad+Stressed, Sleep 3/10, Stress 8, Cravings 7
            "todays_mood": "Sad",
            "sleep_quality": 3,
            "sleep_hours": 5.5,
            "craving_intensity": 7,
            "trigger_intensity": 8,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-011": {  # Taylor Brooks — UC 5.4 Agnostic Global: Stressed+Lonely, Sleep 4/10, Stress 7, Cravings 8
            "todays_mood": "Stressed",
            "sleep_quality": 4,
            "sleep_hours": 6.0,
            "craving_intensity": 8,
            "trigger_intensity": 7,
            "medication_taken": False,
            "social_contact": True,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-012": {  # Aravind Reddy — UC 6.1 Social Media Indian: Bored, Sleep 4/10, Stress 5, Cravings 8
            "todays_mood": "Bored",
            "sleep_quality": 4,
            "sleep_hours": 7.0,
            "craving_intensity": 8,
            "trigger_intensity": 5,
            "medication_taken": False,
            "social_contact": False,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
        "PAT-013": {  # Sophia Martinez — UC 6.2 Social Media Global: Happy, Sleep 5/10, Stress 4, Cravings 8
            "todays_mood": "Happy",
            "sleep_quality": 5,
            "sleep_hours": 7.5,
            "craving_intensity": 8,
            "trigger_intensity": 4,
            "medication_taken": False,
            "social_contact": True,
            "exercise_done": False,
            "trigger_exposure_flag": True,
        },
    }

    today = date.today().isoformat()
    for patient_code, patient_id in patient_map.items():
        checkin_data = TODAY_CHECKINS.get(patient_code, {})
        if not checkin_data:
            continue
        checkin_data["patient_id"] = patient_id
        checkin_data["checkin_date"] = today
        checkin_data["checkin_completed_via"] = "chat"
        try:
            client.table("daily_checkins").insert(checkin_data).execute()
            print(f"✅ {patient_code} — today's check-in ({checkin_data['todays_mood']}, "
                  f"sleep {checkin_data.get('sleep_quality')}/10, "
                  f"cravings {checkin_data.get('craving_intensity')}/10)")
        except Exception as e:
            print(f"⚠️  {patient_code} today's check-in: {str(e)[:80]}")


def insert_todays_wearables(patient_map):
    """Insert today's wearable reading for all 10 patients."""
    print("\n" + "="*60)
    print("LOADING TODAY'S WEARABLE READINGS")
    print("="*60)

    # Wearable data — calibrated to match use case risk scores and check-in mood data
    TODAY_WEARABLES = {
        "PAT-001": {"hr_bpm": 88, "hrv_ms": 18, "sleep_hours": 5.0, "steps_today": 2100, "physiological_stress_score": 0.73, "stress_level_device": "High",    "personal_anomaly_flag": True,  "personal_anomaly_detail": "elevated HR; low HRV consistent with late-night loneliness pattern"},
        "PAT-002": {"hr_bpm": 92, "hrv_ms": 14, "sleep_hours": 5.5, "steps_today": 3200, "physiological_stress_score": 0.79, "stress_level_device": "High",    "personal_anomaly_flag": True,  "personal_anomaly_detail": "post-work stress spike; HR elevated after commute"},
        "PAT-003": {"hr_bpm": 86, "hrv_ms": 17, "sleep_hours": 6.0, "steps_today": 900,  "physiological_stress_score": 0.75, "stress_level_device": "High",    "personal_anomaly_flag": True,  "personal_anomaly_detail": "sedentary study-break pattern; elevated stress markers"},
        "PAT-004": {"hr_bpm": 94, "hrv_ms": 12, "sleep_hours": 4.5, "steps_today": 700,  "physiological_stress_score": 0.80, "stress_level_device": "High",    "personal_anomaly_flag": True,  "personal_anomaly_detail": "late-night gaming; very low HRV; sleep severely curtailed"},
        "PAT-005": {"hr_bpm": 89, "hrv_ms": 16, "sleep_hours": 5.0, "steps_today": 1600, "physiological_stress_score": 0.77, "stress_level_device": "High",    "personal_anomaly_flag": True,  "personal_anomaly_detail": "elevated stress markers consistent with nighttime emotional distress"},
        "PAT-006": {"hr_bpm": 97, "hrv_ms": 11, "sleep_hours": 5.5, "steps_today": 2200, "physiological_stress_score": 0.83, "stress_level_device": "Severe",  "personal_anomaly_flag": True,  "personal_anomaly_detail": "post-argument spike; highest HR reading in 30 days"},
        "PAT-007": {"hr_bpm": 83, "hrv_ms": 20, "sleep_hours": 6.0, "steps_today": 3800, "physiological_stress_score": 0.70, "stress_level_device": "High",    "personal_anomaly_flag": True,  "personal_anomaly_detail": "stress elevated during work hours; consistent with nicotine craving cycle"},
        "PAT-008": {"hr_bpm": 91, "hrv_ms": 15, "sleep_hours": 5.0, "steps_today": 4500, "physiological_stress_score": 0.74, "stress_level_device": "High",    "personal_anomaly_flag": True,  "personal_anomaly_detail": "stress elevated during festival social exposure window"},
        "PAT-009": {"hr_bpm": 80, "hrv_ms": 22, "sleep_hours": 6.5, "steps_today": 3100, "physiological_stress_score": 0.66, "stress_level_device": "Moderate", "personal_anomaly_flag": False},
        "PAT-010": {"hr_bpm": 82, "hrv_ms": 20, "sleep_hours": 5.5, "steps_today": 2800, "physiological_stress_score": 0.70, "stress_level_device": "High",    "personal_anomaly_flag": True,  "personal_anomaly_detail": "moderate stress elevation post-slip; shame response pattern"},
        "PAT-011": {"hr_bpm": 85, "hrv_ms": 19, "sleep_hours": 6.0, "steps_today": 5200, "physiological_stress_score": 0.68, "stress_level_device": "Moderate", "personal_anomaly_flag": True,  "personal_anomaly_detail": "pre-social-event stress; HRV dip consistent with anticipatory anxiety"},
        "PAT-012": {"hr_bpm": 72, "hrv_ms": 28, "sleep_hours": 7.0, "steps_today": 1200, "physiological_stress_score": 0.52, "stress_level_device": "Moderate", "personal_anomaly_flag": False},
        "PAT-013": {"hr_bpm": 76, "hrv_ms": 30, "sleep_hours": 7.5, "steps_today": 6800, "physiological_stress_score": 0.44, "stress_level_device": "Low",      "personal_anomaly_flag": False},
    }

    now = datetime.now().isoformat()
    for patient_code, patient_id in patient_map.items():
        wearable = TODAY_WEARABLES.get(patient_code, {})
        if not wearable:
            continue
        wearable["patient_id"] = patient_id
        wearable["reading_date"] = date.today().isoformat()
        try:
            client.table("wearable_readings").insert(wearable).execute()
            print(f"✅ {patient_code} — HR {wearable['hr_bpm']}bpm, "
                  f"HRV {wearable['hrv_ms']}ms, "
                  f"stress {wearable['physiological_stress_score']}, "
                  f"sleep {wearable['sleep_hours']}h")
        except Exception as e:
            print(f"⚠️  {patient_code} wearable: {str(e)[:80]}")



    print("\n" + "="*60)
    print("LOADING SAMPLE PATIENTS")
    print("="*60)
    
    patient_map = {}  # Store patient_id by patient_code
    
    for patient_data in SAMPLE_PATIENTS:
        try:
            profile_data = patient_data.pop("profile")
            
            # Insert patient
            response = client.table("patients").insert(patient_data).execute()
            patient = response.data[0]
            patient_id = patient["patient_id"]
            patient_map[patient_data["patient_code"]] = patient_id
            
            print(f"✅ {patient_data['patient_code']} — {patient_data['first_name']} {patient_data['last_name']}")
            
            # Insert onboarding profile
            profile_data["patient_id"] = patient_id
            profile_data["completed_at"] = datetime.now().isoformat()
            client.table("onboarding_profiles").insert(profile_data).execute()
            
        except Exception as e:
            print(f"❌ {patient_data['patient_code']} — {str(e)[:80]}")
    
    return patient_map


def insert_daily_checkins(patient_map):
    """Insert sample daily checkins."""
    print("\n" + "="*60)
    print("LOADING SAMPLE DAILY CHECKINS")
    print("="*60)
    
    moods = ["Happy", "Neutral", "Sad", "Angry", "Stressed", "Lonely"]
    
    for patient_code, patient_id in list(patient_map.items())[:3]:  # Just first 3
        # Create checkins for last 7 days
        for days_ago in range(7, 0, -1):
            checkin_date = (date.today() - timedelta(days=days_ago)).isoformat()
            
            checkin = {
                "patient_id": patient_id,
                "checkin_date": checkin_date,
                "todays_mood": moods[days_ago % len(moods)],
                "sleep_quality": 5 + (days_ago % 4),
                "sleep_hours": 6.0 + (days_ago % 3),
                "craving_intensity": 3 + (days_ago % 5),
                "medication_taken": True,
                "trigger_intensity": 4 + (days_ago % 4),
                "social_contact": days_ago % 2 == 0,
                "exercise_done": days_ago % 3 == 0,
                "exercise_duration_minutes": 30 if days_ago % 3 == 0 else None,
            }
            
            try:
                client.table("daily_checkins").insert(checkin).execute()
            except Exception as e:
                print(f"⚠️  Checkin for {patient_code} ({checkin_date}): {str(e)[:60]}")
        
        print(f"✅ {patient_code} — 7 days of checkins")


def insert_sessions_and_messages(patient_map):
    """Insert sample sessions and messages."""
    print("\n" + "="*60)
    print("LOADING SAMPLE SESSIONS & MESSAGES")
    print("="*60)
    
    intents = [
        "craving_support",
        "medication_reminder",
        "sleep_support",
        "trigger_management",
        "motivation",
        "emotional_check",
    ]
    
    for patient_code, patient_id in list(patient_map.items())[:2]:  # First 2
        # Create 2 sessions per patient
        for session_num in range(1, 3):
            try:
                session = {
                    "patient_id": patient_id,
                    "patient_code": patient_code,
                    "started_at": (datetime.now() - timedelta(days=7-session_num*3)).isoformat(),
                    "message_count": 4,
                    "last_intent": intents[session_num % len(intents)],
                    "peak_risk_level": ["Low", "Medium", "High"][session_num % 3],
                    "crisis_detected": False,
                }
                
                session_resp = client.table("sessions").insert(session).execute()
                session_id = session_resp.data[0]["session_id"]
                
                # Add 4 messages (2 user, 2 bot)
                messages = [
                    {"role": "user", "content": "I'm feeling really stressed today", "intent": "emotional_check", "severity": "medium"},
                    {"role": "assistant", "content": "I hear you. Tell me more about what's happening.", "response_tone": "warm"},
                    {"role": "user", "content": "Work was overwhelming and I'm craving badly", "intent": "craving_support", "severity": "high"},
                    {"role": "assistant", "content": "Let's work through this together. Have you called your sponsor yet?", "response_tone": "calm"},
                ]
                
                for msg in messages:
                    msg["session_id"] = session_id
                    msg["patient_id"] = patient_id
                    if msg["role"] == "assistant":
                        msg.pop("intent", None)
                    client.table("messages").insert(msg).execute()
                
                print(f"✅ {patient_code} — Session {session_num} with 4 messages")
                
            except Exception as e:
                print(f"⚠️  Session for {patient_code}: {str(e)[:60]}")


def insert_risk_assessments(patient_map):
    """Insert sample risk assessments."""
    print("\n" + "="*60)
    print("LOADING SAMPLE RISK ASSESSMENTS")
    print("="*60)
    
    for patient_code, patient_id in list(patient_map.items())[:3]:
        try:
            risk = {
                "patient_id": patient_id,
                "live_risk_score": 35 + (hash(patient_code) % 40),
                "risk_level": "Medium",
                "key_risk_drivers": ["sleep -20", "cravings +15", "mood -10"],
                "crisis_flag": False,
            }
            
            client.table("risk_assessments").insert(risk).execute()
            print(f"✅ {patient_code} — Risk score {risk['live_risk_score']}")
            
        except Exception as e:
            print(f"⚠️  Risk for {patient_code}: {str(e)[:60]}")

def insert_patients():
    raise NotImplementedError


def main():
    print("\n" + "="*60)
    print("SUPABASE SAMPLE DATA LOADER")
    print("="*60)
    
    # 1. Insert patients + profiles
    patient_map = insert_patients() # type: ignore
    
    if not patient_map:
        print("\n❌ No patients inserted. Check your Supabase connection.")
        return
    
    # 2. Insert checkins (7 historical days)
    insert_daily_checkins(patient_map)

    # 3. Insert today's check-ins (contextual greeting data)
    insert_todays_checkins(patient_map)

    # 4. Insert today's wearable readings
    insert_todays_wearables(patient_map)

    # 5. Insert sessions + messages
    insert_sessions_and_messages(patient_map)

    # 6. Insert risk assessments
    insert_risk_assessments(patient_map)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✅ Loaded {len(patient_map)} patients")
    print(f"✅ Loaded onboarding profiles")
    print(f"✅ Loaded daily checkins (7 historical days)")
    print(f"✅ Loaded today's check-ins for all 10 patients")
    print(f"✅ Loaded today's wearable readings for all 10 patients")
    print(f"✅ Loaded sample sessions & messages")
    print(f"✅ Loaded risk assessments")
    print("\nYour database is ready for testing!")


if __name__ == "__main__":
    main()
