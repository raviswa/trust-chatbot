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
    "trigger_financial": {
        "url":         "https://www.youtube.com/watch?v=xelO4ZnFDkc",
        "video_id":    "xelO4ZnFDkc",
        "title":       "Financial Stress and Mental Health",
        "thumbnail":   yt_thumb("xelO4ZnFDkc"),
        "description": "Managing the mental health impact of financial stress",
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


def get_video(intent: str) -> dict | None:
    """Returns video data for a given intent, or None if not mapped."""
    return VIDEO_MAP.get(intent)


def get_score_group(intent: str) -> str | None:
    """Returns the score group for an intent, or None if not applicable."""
    return SCORE_GROUPS.get(intent)


def get_score_label(intent: str) -> str:
    """Returns the slider label for the intent's score group."""
    group = SCORE_GROUPS.get(intent)
    return SCORE_LABELS.get(group, "How are you feeling right now?")
