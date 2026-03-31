"""
video_map.py
─────────────────────────────────────────────────────────────────
Maps intent tags to curated YouTube videos.
Temporary solution until a proper video CMS is in place.
Each entry has: url, title, thumbnail, description.
─────────────────────────────────────────────────────────────────
"""

# YouTube thumbnail URL pattern
def yt_thumb(vid_id):
    return f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg"

VIDEO_MAP = {
    # ── Mood ─────────────────────────────────────────────────────
    "mood_sad": {
        "url":         "https://www.youtube.com/watch?v=jDTBTMHzFjQ",
        "video_id":    "jDTBTMHzFjQ",
        "title":       "Understanding and Coping with Low Mood",
        "thumbnail":   yt_thumb("jDTBTMHzFjQ"),
        "description": "Practical techniques for managing feelings of sadness",
    },
    "mood_anxious": {
        "url":         "https://www.youtube.com/watch?v=WWloIAQpMkQ",
        "video_id":    "WWloIAQpMkQ",
        "title":       "5-Minute Anxiety Relief — Breathing Exercise",
        "thumbnail":   yt_thumb("WWloIAQpMkQ"),
        "description": "A simple breathing technique to calm anxiety",
    },
    "mood_angry": {
        "url":         "https://www.youtube.com/watch?v=BsVq5R_F6RA",
        "video_id":    "BsVq5R_F6RA",
        "title":       "Managing Anger — Healthy Coping Strategies",
        "thumbnail":   yt_thumb("BsVq5R_F6RA"),
        "description": "Evidence-based techniques for managing anger",
    },
    "mood_lonely": {
        "url":         "https://www.youtube.com/watch?v=n3Xv_g3g-mA",
        "video_id":    "n3Xv_g3g-mA",
        "title":       "Overcoming Loneliness — Building Connection",
        "thumbnail":   yt_thumb("n3Xv_g3g-mA"),
        "description": "Steps to rebuild social connection and reduce isolation",
    },
    "mood_guilty": {
        "url":         "https://www.youtube.com/watch?v=ZizdB0TgAVM",
        "video_id":    "ZizdB0TgAVM",
        "title":       "Self-Compassion — Letting Go of Guilt",
        "thumbnail":   yt_thumb("ZizdB0TgAVM"),
        "description": "Developing self-compassion and processing guilt",
    },

    # ── Behaviour ────────────────────────────────────────────────
    "behaviour_sleep": {
        "url":         "https://www.youtube.com/watch?v=nm1TxQj9IsQ",
        "video_id":    "nm1TxQj9IsQ",
        "title":       "Better Sleep — Science-Backed Tips",
        "thumbnail":   yt_thumb("nm1TxQj9IsQ"),
        "description": "Practical sleep hygiene strategies",
    },
    "behaviour_isolation": {
        "url":         "https://www.youtube.com/watch?v=n3Xv_g3g-mA",
        "video_id":    "n3Xv_g3g-mA",
        "title":       "Overcoming Social Withdrawal",
        "thumbnail":   yt_thumb("n3Xv_g3g-mA"),
        "description": "Steps to re-engage with others at your own pace",
    },
    "behaviour_eating": {
        "url":         "https://www.youtube.com/watch?v=Xv9Msv2KLmc",
        "video_id":    "Xv9Msv2KLmc",
        "title":       "Emotional Eating — Breaking the Cycle",
        "thumbnail":   yt_thumb("Xv9Msv2KLmc"),
        "description": "Understanding and addressing emotional eating patterns",
    },

    # ── Addiction ────────────────────────────────────────────────
    "addiction_alcohol": {
        "url":         "https://www.youtube.com/watch?v=6EghiY_s2ts",
        "video_id":    "6EghiY_s2ts",
        "title":       "Understanding Alcohol Use Disorder — Recovery",
        "thumbnail":   yt_thumb("6EghiY_s2ts"),
        "description": "What recovery looks like and how to start",
    },
    "addiction_drugs": {
        "url":         "https://www.youtube.com/watch?v=5-Ld6FBpXgA",
        "video_id":    "5-Ld6FBpXgA",
        "title":       "Substance Use Recovery — First Steps",
        "thumbnail":   yt_thumb("5-Ld6FBpXgA"),
        "description": "Practical first steps toward recovery",
    },
    "addiction_gaming": {
        "url":         "https://www.youtube.com/watch?v=XNkRdc_4yXo",
        "video_id":    "XNkRdc_4yXo",
        "title":       "Gaming Addiction — Regaining Balance",
        "thumbnail":   yt_thumb("XNkRdc_4yXo"),
        "description": "How to build a healthier relationship with gaming",
    },
    "addiction_social_media": {
        "url":         "https://www.youtube.com/watch?v=PmEDAzqswh8",
        "video_id":    "PmEDAzqswh8",
        "title":       "Social Media and Mental Health",
        "thumbnail":   yt_thumb("PmEDAzqswh8"),
        "description": "Understanding social media's impact and how to manage it",
    },
    "addiction_nicotine": {
        "url":         "https://www.youtube.com/watch?v=vkPbCDuNSo0",
        "video_id":    "vkPbCDuNSo0",
        "title":       "Quitting Smoking — Evidence-Based Strategies",
        "thumbnail":   yt_thumb("vkPbCDuNSo0"),
        "description": "Practical approaches to nicotine cessation",
    },
    "addiction_gambling": {
        "url":         "https://www.youtube.com/watch?v=1GJpBnHhZ44",
        "video_id":    "1GJpBnHhZ44",
        "title":       "Problem Gambling — Getting Help",
        "thumbnail":   yt_thumb("1GJpBnHhZ44"),
        "description": "Understanding problem gambling and recovery pathways",
    },
    "addiction_work": {
        "url":         "https://www.youtube.com/watch?v=PJSiEDnxQFQ",
        "video_id":    "PJSiEDnxQFQ",
        "title":       "Work-Life Balance — Preventing Burnout",
        "thumbnail":   yt_thumb("PJSiEDnxQFQ"),
        "description": "Strategies to restore balance and prevent burnout",
    },

    # ── Triggers ─────────────────────────────────────────────────
    "trigger_stress": {
        "url":         "https://www.youtube.com/watch?v=hnpQrMqDoqE",
        "video_id":    "hnpQrMqDoqE",
        "title":       "Stress Management Techniques",
        "thumbnail":   yt_thumb("hnpQrMqDoqE"),
        "description": "Simple daily techniques to manage stress",
    },
    "trigger_trauma": {
        "url":         "https://www.youtube.com/watch?v=wkHB82bJKAI",
        "video_id":    "wkHB82bJKAI",
        "title":       "Understanding Trauma and Healing",
        "thumbnail":   yt_thumb("wkHB82bJKAI"),
        "description": "What trauma does to the brain and how healing happens",
    },
    "trigger_grief": {
        "url":         "https://www.youtube.com/watch?v=Forj3r_av1s",
        "video_id":    "Forj3r_av1s",
        "title":       "Grief and Loss — Moving Through Pain",
        "thumbnail":   yt_thumb("Forj3r_av1s"),
        "description": "Understanding the grief process and finding support",
    },
    "trigger_relationship": {
        "url":         "https://www.youtube.com/watch?v=sa0Ks5CU4Tc",
        "video_id":    "sa0Ks5CU4Tc",
        "title":       "Healthy Relationships — Communication Skills",
        "thumbnail":   yt_thumb("sa0Ks5CU4Tc"),
        "description": "Building healthier communication and connection",
    },
    "trigger_financial": {
        "url":         "https://www.youtube.com/watch?v=xelO4ZnFDkc",
        "video_id":    "xelO4ZnFDkc",
        "title":       "Financial Stress and Mental Health",
        "thumbnail":   yt_thumb("xelO4ZnFDkc"),
        "description": "Managing the mental health impact of financial stress",
    },

    # ── Severe distress / crisis adjacent ────────────────────────
    "severe_distress": {
        "url":         "https://www.youtube.com/watch?v=jDTBTMHzFjQ",
        "video_id":    "jDTBTMHzFjQ",
        "title":       "When Everything Feels Overwhelming",
        "thumbnail":   yt_thumb("jDTBTMHzFjQ"),
        "description": "Grounding techniques for moments of intense distress",
    },
    # ── Venting / Implicit Distress ─────────────────────────────────
    # Emotional regulation: grounding / breathing — no advice, no solutions
    "venting": {
        "url":         "https://www.youtube.com/watch?v=WWloIAQpMkQ",
        "video_id":    "WWloIAQpMkQ",
        "title":       "5-Minute Breathing Exercise to Calm Your Nervous System",
        "thumbnail":   yt_thumb("WWloIAQpMkQ"),
        "description": "A simple breathing technique to ease overwhelm and emotional fatigue",
    },
    # ── Fallback / General Support ───────────────────────────────
    "rag_query": {
        "url":         "https://www.youtube.com/watch?v=POPpLzKxFww",
        "video_id":    "POPpLzKxFww",
        "title":       "Mental Health Support — You're Not Alone",
        "thumbnail":   yt_thumb("POPpLzKxFww"),
        "description": "General mental health support and recovery resources",
    },
    "greeting": {
        "url":         "https://www.youtube.com/watch?v=POPpLzKxFww",
        "video_id":    "POPpLzKxFww",
        "title":       "Mental Health Support — You're Not Alone",
        "thumbnail":   yt_thumb("POPpLzKxFww"),
        "description": "General mental health support and recovery resources",
    },
    "farewell": {
        "url":         "https://www.youtube.com/watch?v=gGJNq-2cjAI",
        "video_id":    "gGJNq-2cjAI",
        "title":       "Keep Going — Self-Care and Resilience",
        "thumbnail":   yt_thumb("gGJNq-2cjAI"),
        "description": "Building lasting resilience and sustainable self-care",
    },
    "gratitude": {
        "url":         "https://www.youtube.com/watch?v=gGJNq-2cjAI",
        "video_id":    "gGJNq-2cjAI",
        "title":       "Keep Going — Self-Care and Resilience",
        "thumbnail":   yt_thumb("gGJNq-2cjAI"),
        "description": "Building lasting resilience and sustainable self-care",
    },
    "unclear": {
        "url":         "https://www.youtube.com/watch?v=POPpLzKxFww",
        "video_id":    "POPpLzKxFww",
        "title":       "Mental Health Support — You're Not Alone",
        "thumbnail":   yt_thumb("POPpLzKxFww"),
        "description": "General mental health support and recovery resources",
    },
    "medication_request": {
        "url":         "https://www.youtube.com/watch?v=hnpQrMqDoqE",
        "video_id":    "hnpQrMqDoqE",
        "title":       "Stress Management Techniques",
        "thumbnail":   yt_thumb("hnpQrMqDoqE"),
        "description": "Simple daily techniques to manage stress and anxiety",
    },
    "error": {
        "url":         "https://www.youtube.com/watch?v=POPpLzKxFww",
        "video_id":    "POPpLzKxFww",
        "title":       "Mental Health Support — You're Not Alone",
        "thumbnail":   yt_thumb("POPpLzKxFww"),
        "description": "General mental health support and recovery resources",
    },
}

# Score label shown on the slider per intent group
SCORE_LABELS = {
    "mood":      "How is your mood right now?",
    "addiction": "How strong is the urge today?",
    "triggers":  "How intense is this feeling?",
    "sleep":     "How well did you sleep last night?",
}

# Which intent tag belongs to which score group
SCORE_GROUPS = {
    "mood_sad":              "mood",
    "mood_anxious":          "mood",
    "mood_angry":            "mood",
    "mood_lonely":           "mood",
    "mood_guilty":           "mood",
    "behaviour_sleep":       "sleep",
    "behaviour_isolation":   "mood",
    "behaviour_eating":      "mood",
    "behaviour_aggression":  "mood",
    "addiction_alcohol":     "addiction",
    "addiction_drugs":       "addiction",
    "addiction_gaming":      "addiction",
    "addiction_social_media":"addiction",
    "addiction_gambling":    "addiction",
    "addiction_food":        "addiction",
    "addiction_work":        "addiction",
    "addiction_shopping":    "addiction",
    "addiction_nicotine":    "addiction",
    "addiction_pornography": "addiction",
    "trigger_stress":        "triggers",
    "trigger_trauma":        "triggers",
    "trigger_relationship":  "triggers",
    "trigger_grief":         "triggers",
    "trigger_financial":     "triggers",
    "severe_distress":       "mood",
}


# ── Alternative videos per intent (backup pool to avoid repetition) ──────────
# When a patient has already seen the primary video for an intent, these
# alternatives are offered instead, in order, before cycling back.
VIDEO_ALTERNATIVES = {
    "mood_sad": [
        {
            "url":         "https://www.youtube.com/watch?v=5CJPA8ahuRc",
            "video_id":    "5CJPA8ahuRc",
            "title":       "How to Deal with Sadness — Dr. Tracey Marks",
            "thumbnail":   yt_thumb("5CJPA8ahuRc"),
            "description": "Clinical guidance on processing and moving through sadness",
        },
        {
            "url":         "https://www.youtube.com/watch?v=RHqTe9KZm-0",
            "video_id":    "RHqTe9KZm-0",
            "title":       "Self-Care When You're Feeling Low",
            "thumbnail":   yt_thumb("RHqTe9KZm-0"),
            "description": "Practical self-care routines to lift your mood",
        },
    ],
    "mood_anxious": [
        {
            "url":         "https://www.youtube.com/watch?v=tybOi4hjZFQ",
            "video_id":    "tybOi4hjZFQ",
            "title":       "How to Stop Anxiety — Therapy in a Nutshell",
            "thumbnail":   yt_thumb("tybOi4hjZFQ"),
            "description": "Evidence-based techniques to reduce anxiety",
        },
        {
            "url":         "https://www.youtube.com/watch?v=aXItOY0sLRY",
            "video_id":    "aXItOY0sLRY",
            "title":       "Grounding Techniques for Anxiety",
            "thumbnail":   yt_thumb("aXItOY0sLRY"),
            "description": "Quick grounding exercises to calm your nervous system",
        },
    ],
    "mood_angry": [
        {
            "url":         "https://www.youtube.com/watch?v=BKBToGMToXQ",
            "video_id":    "BKBToGMToXQ",
            "title":       "Anger and the Brain — Why We Get Angry",
            "thumbnail":   yt_thumb("BKBToGMToXQ"),
            "description": "Understanding the neuroscience of anger",
        },
    ],
    "mood_lonely": [
        {
            "url":         "https://www.youtube.com/watch?v=I71TZO_ZQMU",
            "video_id":    "I71TZO_ZQMU",
            "title":       "The Loneliness Epidemic — Finding Connection",
            "thumbnail":   yt_thumb("I71TZO_ZQMU"),
            "description": "Why loneliness is rising and what to do about it",
        },
    ],
    "mood_guilty": [
        {
            "url":         "https://www.youtube.com/watch?v=IvtZBUSplr4",
            "video_id":    "IvtZBUSplr4",
            "title":       "How to Forgive Yourself",
            "thumbnail":   yt_thumb("IvtZBUSplr4"),
            "description": "Steps toward self-forgiveness and moving forward",
        },
    ],
    "behaviour_sleep": [
        {
            "url":         "https://www.youtube.com/watch?v=t0kACis_dJE",
            "video_id":    "t0kACis_dJE",
            "title":       "Sleep and Mental Health — The Connection",
            "thumbnail":   yt_thumb("t0kACis_dJE"),
            "description": "How sleep affects mood, anxiety and recovery",
        },
    ],
    "behaviour_eating": [
        {
            "url":         "https://www.youtube.com/watch?v=0pS50j-ScEk",
            "video_id":    "0pS50j-ScEk",
            "title":       "Mindful Eating — Rebuilding Your Relationship with Food",
            "thumbnail":   yt_thumb("0pS50j-ScEk"),
            "description": "Mindfulness practices for healthier eating habits",
        },
    ],
    "addiction_alcohol": [
        {
            "url":         "https://www.youtube.com/watch?v=vOBJNv0DmAg",
            "video_id":    "vOBJNv0DmAg",
            "title":       "Life in Recovery from Alcohol — Real Stories",
            "thumbnail":   yt_thumb("vOBJNv0DmAg"),
            "description": "Personal experiences of building a sober life",
        },
        {
            "url":         "https://www.youtube.com/watch?v=T4dJBNBNEVA",
            "video_id":    "T4dJBNBNEVA",
            "title":       "Craving Management — Surfing the Urge",
            "thumbnail":   yt_thumb("T4dJBNBNEVA"),
            "description": "Urge surfing technique to ride out alcohol cravings",
        },
    ],
    "addiction_drugs": [
        {
            "url":         "https://www.youtube.com/watch?v=ao8L-0nSYzg",
            "video_id":    "ao8L-0nSYzg",
            "title":       "The Science of Addiction and Recovery",
            "thumbnail":   yt_thumb("ao8L-0nSYzg"),
            "description": "How addiction changes the brain and how recovery works",
        },
    ],
    "addiction_gambling": [
        {
            "url":         "https://www.youtube.com/watch?v=jEpE37F2q_M",
            "video_id":    "jEpE37F2q_M",
            "title":       "Gambling Disorder — How to Break the Cycle",
            "thumbnail":   yt_thumb("jEpE37F2q_M"),
            "description": "Understanding gambling disorder triggers and recovery steps",
        },
    ],
    "addiction_nicotine": [
        {
            "url":         "https://www.youtube.com/watch?v=2VKCgUHkKW8",
            "video_id":    "2VKCgUHkKW8",
            "title":       "Managing Nicotine Withdrawal",
            "thumbnail":   yt_thumb("2VKCgUHkKW8"),
            "description": "What to expect and how to cope with withdrawal symptoms",
        },
    ],
    "trigger_stress": [
        {
            "url":         "https://www.youtube.com/watch?v=0fL-pn80s-c",
            "video_id":    "0fL-pn80s-c",
            "title":       "How Stress Affects Your Body",
            "thumbnail":   yt_thumb("0fL-pn80s-c"),
            "description": "The physiology of stress and practical relief strategies",
        },
        {
            "url":         "https://www.youtube.com/watch?v=15o4a4yPBDE",
            "video_id":    "15o4a4yPBDE",
            "title":       "Progressive Muscle Relaxation for Stress",
            "thumbnail":   yt_thumb("15o4a4yPBDE"),
            "description": "Guided PMR technique to physically release stress",
        },
    ],
    "trigger_trauma": [
        {
            "url":         "https://www.youtube.com/watch?v=YSjpPe7kGdQ",
            "video_id":    "YSjpPe7kGdQ",
            "title":       "PTSD Explained — Symptoms and Recovery",
            "thumbnail":   yt_thumb("YSjpPe7kGdQ"),
            "description": "What PTSD is, how it develops, and evidence-based treatments",
        },
    ],
    "trigger_grief": [
        {
            "url":         "https://www.youtube.com/watch?v=khkJkR-ipfw",
            "video_id":    "khkJkR-ipfw",
            "title":       "The Stages of Grief — What to Expect",
            "thumbnail":   yt_thumb("khkJkR-ipfw"),
            "description": "Understanding the grief process and finding your way through",
        },
    ],
    "trigger_relationship": [
        {
            "url":         "https://www.youtube.com/watch?v=PHQ1qqbPSl4",
            "video_id":    "PHQ1qqbPSl4",
            "title":       "Setting Healthy Boundaries in Relationships",
            "thumbnail":   yt_thumb("PHQ1qqbPSl4"),
            "description": "How to communicate and enforce healthy boundaries",
        },
    ],
    "trigger_financial": [
        {
            "url":         "https://www.youtube.com/watch?v=GqpB6Y7jBGA",
            "video_id":    "GqpB6Y7jBGA",
            "title":       "Reducing Money Anxiety — Practical Steps",
            "thumbnail":   yt_thumb("GqpB6Y7jBGA"),
            "description": "Actionable ways to reduce anxiety around financial stress",
        },
    ],
    "severe_distress": [
        {
            "url":         "https://www.youtube.com/watch?v=5P-_OvYIGZ4",
            "video_id":    "5P-_OvYIGZ4",
            "title":       "Getting Through a Mental Health Crisis",
            "thumbnail":   yt_thumb("5P-_OvYIGZ4"),
            "description": "Step-by-step guide to navigating a crisis moment",
        },
    ],
}


def get_video(intent: str) -> dict | None:
    """
    Returns video data for a given intent, or a fallback video if not mapped.
    Ensures every message gets a supportive video resource.
    NOTE: Prefer get_video_for_patient() to avoid showing the same video repeatedly.
    """
    # Try specific intent first
    if intent in VIDEO_MAP:
        return VIDEO_MAP.get(intent)

    # Fallback: Always return a general support video
    return VIDEO_MAP.get("rag_query")  # Default general support video


def get_video_for_patient(intent: str, watched_video_ids: set = None) -> dict | None:
    """
    Returns the best unwatched video for the given intent.

    Builds a candidate list: [primary video] + [alternatives].
    Returns the first video whose video_id is not in watched_video_ids.
    If all candidates have been watched, returns the primary video
    (least disruptive fallback — repetition is better than no content).

    Args:
        intent:           The classified intent for this turn.
        watched_video_ids: Set of video_id strings the patient has already seen
                          (across all sessions). Pass an empty set or None when
                          no history is available.

    Returns:
        A video dict with url / video_id / title / thumbnail / description,
        or None if no video is mapped for this intent.
    """
    if watched_video_ids is None:
        watched_video_ids = set()

    # Build ordered candidate list: primary first, then alternatives
    primary = VIDEO_MAP.get(intent) or VIDEO_MAP.get("rag_query")
    if primary is None:
        return None

    candidates = [primary] + VIDEO_ALTERNATIVES.get(intent, [])

    # Return first unwatched candidate
    for video in candidates:
        if video["video_id"] not in watched_video_ids:
            return video

    # All candidates already watched — return the primary (graceful repeat)
    return primary


def get_score_group(intent: str) -> str | None:
    """Returns the score group for an intent, or None if not applicable."""
    return SCORE_GROUPS.get(intent)


def get_score_label(intent: str) -> str:
    """Returns the slider label for the intent's score group."""
    group = SCORE_GROUPS.get(intent)
    return SCORE_LABELS.get(group, "How are you feeling right now?")
