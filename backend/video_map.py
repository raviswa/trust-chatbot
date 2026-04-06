"""
video_map.py
─────────────────────────────────────────────────────────────────
Maps intent tags to curated YouTube videos.
Temporary solution until a proper video CMS is in place.
Each entry has: url, title, thumbnail, description.
─────────────────────────────────────────────────────────────────
"""

# Placeholder helper — returns intent key wrapped in double braces.
# YouTube URLs will be replaced with real video URLs when the
# mobile app integration is complete.
def yt_thumb(intent_key):
    return f"{{{{ {intent_key} }}}}"

VIDEO_MAP = {
    # ── Mood ─────────────────────────────────────────────────────
    "mood_sad": {
        "url":         "{{mood_sad}}",
        "video_id":    "{{mood_sad}}",
        "title":       "Understanding and Coping with Low Mood",
        "thumbnail":   "{{mood_sad}}",
        "description": "Practical techniques for managing feelings of sadness",
        "tags":        ["mood_sad"],
    },
    "mood_anxious": {
        "url":         "{{mood_anxious}}",
        "video_id":    "{{mood_anxious}}",
        "title":       "5-Minute Anxiety Relief — Breathing Exercise",
        "thumbnail":   "{{mood_anxious}}",
        "description": "A simple breathing technique to calm anxiety",
        "tags":        ["mood_anxious", "trigger_stress"],
    },
    "mood_angry": {
        "url":         "{{mood_angry}}",
        "video_id":    "{{mood_angry}}",
        "title":       "Managing Anger — Healthy Coping Strategies",
        "thumbnail":   "{{mood_angry}}",
        "description": "Evidence-based techniques for managing anger",
        "tags":        ["mood_angry"],
    },
    "mood_lonely": {
        "url":         "{{mood_lonely}}",
        "video_id":    "{{mood_lonely}}",
        "title":       "Overcoming Loneliness — Building Connection",
        "thumbnail":   "{{mood_lonely}}",
        "description": "Steps to rebuild social connection and reduce isolation",
        "tags":        ["mood_lonely", "behaviour_isolation"],
    },
    "mood_guilty": {
        "url":         "{{mood_guilty}}",
        "video_id":    "{{mood_guilty}}",
        "title":       "Self-Compassion — Letting Go of Guilt",
        "thumbnail":   "{{mood_guilty}}",
        "description": "Developing self-compassion and processing guilt",
        "tags":        ["mood_guilty"],
    },

    # ── Behaviour ────────────────────────────────────────────────
    "behaviour_sleep": {
        "url":         "{{behaviour_sleep}}",
        "video_id":    "{{behaviour_sleep}}",
        "title":       "Better Sleep — Science-Backed Tips",
        "thumbnail":   "{{behaviour_sleep}}",
        "description": "Practical sleep hygiene strategies",
        "tags":        ["behaviour_sleep", "mood_anxious"],
    },
    "behaviour_fatigue": {
        "url":         "{{behaviour_fatigue}}",
        "video_id":    "{{behaviour_fatigue}}",
        "title":       "Managing Fatigue in Recovery",
        "thumbnail":   "{{behaviour_fatigue}}",
        "description": "Understanding tiredness and rebuilding energy",
        "tags":        ["behaviour_fatigue", "behaviour_sleep", "mood_sad"],
    },
    "behaviour_isolation": {
        "url":         "{{behaviour_isolation}}",
        "video_id":    "{{behaviour_isolation}}",
        "title":       "Overcoming Social Withdrawal",
        "thumbnail":   "{{behaviour_isolation}}",
        "description": "Steps to re-engage with others at your own pace",
        "tags":        ["behaviour_isolation", "mood_lonely"],
    },
    "behaviour_eating": {
        "url":         "{{behaviour_eating}}",
        "video_id":    "{{behaviour_eating}}",
        "title":       "Emotional Eating — Breaking the Cycle",
        "thumbnail":   "{{behaviour_eating}}",
        "description": "Understanding and addressing emotional eating patterns",
        "tags":        ["behaviour_eating", "mood_sad"],
    },

    # ── Addiction ────────────────────────────────────────────────
    "addiction_alcohol": {
        "url":         "{{addiction_alcohol}}",
        "video_id":    "{{addiction_alcohol}}",
        "title":       "Understanding Alcohol Use Disorder — Recovery",
        "thumbnail":   "{{addiction_alcohol}}",
        "description": "What recovery looks like and how to start",
        "tags":        ["addiction_alcohol", "addiction_drugs", "relapse_disclosure"],
    },
    "addiction_drugs": {
        "url":         "{{addiction_drugs}}",
        "video_id":    "{{addiction_drugs}}",
        "title":       "Substance Use Recovery — First Steps",
        "thumbnail":   "{{addiction_drugs}}",
        "description": "Practical first steps toward recovery",
        "tags":        ["addiction_drugs", "relapse_disclosure"],
    },
    "addiction_gaming": {
        "url":         "{{addiction_gaming}}",
        "video_id":    "{{addiction_gaming}}",
        "title":       "Gaming Addiction — Regaining Balance",
        "thumbnail":   "{{addiction_gaming}}",
        "description": "How to build a healthier relationship with gaming",
        "tags":        ["addiction_gaming", "behaviour_sleep"],
    },
    "addiction_social_media": {
        "url":         "{{addiction_social_media}}",
        "video_id":    "{{addiction_social_media}}",
        "title":       "Social Media and Mental Health",
        "thumbnail":   "{{addiction_social_media}}",
        "description": "Understanding social media's impact and how to manage it",
        "tags":        ["addiction_social_media", "mood_anxious", "behaviour_sleep"],
    },
    "addiction_nicotine": {
        "url":         "{{addiction_nicotine}}",
        "video_id":    "{{addiction_nicotine}}",
        "title":       "Quitting Smoking — Evidence-Based Strategies",
        "thumbnail":   "{{addiction_nicotine}}",
        "description": "Practical approaches to nicotine cessation",
        "tags":        ["addiction_nicotine", "trigger_stress"],
    },
    "addiction_gambling": {
        "url":         "{{addiction_gambling}}",
        "video_id":    "{{addiction_gambling}}",
        "title":       "Problem Gambling — Getting Help",
        "thumbnail":   "{{addiction_gambling}}",
        "description": "Understanding problem gambling and recovery pathways",
        "tags":        ["addiction_gambling", "trigger_financial", "trigger_stress"],
    },
    "addiction_food": {
        "url":         "{{addiction_food}}",
        "video_id":    "{{addiction_food}}",
        "title":       "Emotional Eating — Understanding the Cycle",
        "thumbnail":   "{{addiction_food}}",
        "description": "How emotions, urges, and food become linked and how to interrupt the pattern",
        "tags":        ["addiction_food", "behaviour_eating", "mood_guilty"],
    },
    "addiction_work": {
        "url":         "{{addiction_work}}",
        "video_id":    "{{addiction_work}}",
        "title":       "Work-Life Balance — Preventing Burnout",
        "thumbnail":   "{{addiction_work}}",
        "description": "Strategies to restore balance and prevent burnout",
        "tags":        ["addiction_work", "trigger_stress", "behaviour_sleep"],
    },
    "addiction_shopping": {
        "url":         "{{addiction_shopping}}",
        "video_id":    "{{addiction_shopping}}",
        "title":       "Compulsive Shopping — Regaining Control",
        "thumbnail":   "{{addiction_shopping}}",
        "description": "Understanding spending urges and creating space before acting on them",
        "tags":        ["addiction_shopping", "trigger_stress", "mood_guilty"],
    },
    "addiction_pornography": {
        "url":         "{{addiction_pornography}}",
        "video_id":    "{{addiction_pornography}}",
        "title":       "Compulsive Pornography Use — Breaking the Shame Cycle",
        "thumbnail":   "{{addiction_pornography}}",
        "description": "A recovery-focused look at shame, urges, and building healthier patterns",
        "tags":        ["addiction_pornography", "mood_guilty", "trigger_relationship"],
    },

    # ── Triggers ─────────────────────────────────────────────────
    "trigger_stress": {
        "url":         "{{trigger_stress}}",
        "video_id":    "{{trigger_stress}}",
        "title":       "Stress Management Techniques",
        "thumbnail":   "{{trigger_stress}}",
        "description": "Simple daily techniques to manage stress",
        "tags":        ["trigger_stress", "mood_anxious", "behaviour_sleep"],
    },
    "trigger_trauma": {
        "url":         "{{trigger_trauma}}",
        "video_id":    "{{trigger_trauma}}",
        "title":       "Understanding Trauma and Healing",
        "thumbnail":   "{{trigger_trauma}}",
        "description": "What trauma does to the brain and how healing happens",
        "tags":        ["trigger_trauma", "mood_anxious", "mood_sad"],
    },
    "trigger_grief": {
        "url":         "{{trigger_grief}}",
        "video_id":    "{{trigger_grief}}",
        "title":       "Grief and Loss — Moving Through Pain",
        "thumbnail":   "{{trigger_grief}}",
        "description": "Understanding the grief process and finding support",
        "tags":        ["trigger_grief", "mood_sad", "mood_lonely"],
    },
    "trigger_relationship": {
        "url":         "{{trigger_relationship}}",
        "video_id":    "{{trigger_relationship}}",
        "title":       "Healthy Relationships — Communication Skills",
        "thumbnail":   "{{trigger_relationship}}",
        "description": "Building healthier communication and connection",
        "tags":        ["trigger_relationship", "mood_lonely", "mood_angry"],
    },
    "trigger_financial": {
        "url":         "{{trigger_financial}}",
        "video_id":    "{{trigger_financial}}",
        "title":       "Financial Stress and Mental Health",
        "thumbnail":   "{{trigger_financial}}",
        "description": "Managing the mental health impact of financial stress",
        "tags":        ["trigger_financial", "trigger_stress", "mood_anxious"],
    },

    # ── Severe distress / crisis adjacent ────────────────────────
    "severe_distress": {
        "url":         "{{severe_distress}}",
        "video_id":    "{{severe_distress}}",
        "title":       "When Everything Feels Overwhelming",
        "thumbnail":   "{{severe_distress}}",
        "description": "Grounding techniques for moments of intense distress",
        "tags":        ["severe_distress", "mood_anxious", "venting"],
    },
    # ── Venting / Implicit Distress ─────────────────────────────────
    # Emotional regulation: grounding / breathing — no advice, no solutions
    "venting": {
        "url":         "{{venting}}",
        "video_id":    "{{venting}}",
        "title":       "5-Minute Breathing Exercise to Calm Your Nervous System",
        "thumbnail":   "{{venting}}",
        "description": "A simple breathing technique to ease overwhelm and emotional fatigue",
        "tags":        ["venting", "mood_anxious", "severe_distress"],
    },
    # ── Fallback / General Support ───────────────────────────────
    "rag_query": {
        "url":         "{{rag_query}}",
        "video_id":    "{{rag_query}}",
        "title":       "Mental Health Support — You're Not Alone",
        "thumbnail":   "{{rag_query}}",
        "description": "General mental health support and recovery resources",
        "tags":        ["rag_query"],
    },
    "greeting": {
        "url":         "{{greeting}}",
        "video_id":    "{{greeting}}",
        "title":       "Mental Health Support — You're Not Alone",
        "thumbnail":   "{{greeting}}",
        "description": "General mental health support and recovery resources",
        "tags":        ["greeting"],
    },
    "farewell": {
        "url":         "{{farewell}}",
        "video_id":    "{{farewell}}",
        "title":       "Keep Going — Self-Care and Resilience",
        "thumbnail":   "{{farewell}}",
        "description": "Building lasting resilience and sustainable self-care",
        "tags":        ["farewell", "gratitude"],
    },
    "gratitude": {
        "url":         "{{gratitude}}",
        "video_id":    "{{gratitude}}",
        "title":       "Keep Going — Self-Care and Resilience",
        "thumbnail":   "{{gratitude}}",
        "tags":        ["gratitude", "farewell"],
        "description": "Building lasting resilience and sustainable self-care",
    },
    "unclear": {
        "url":         "{{unclear}}",
        "video_id":    "{{unclear}}",
        "title":       "Mental Health Support — You're Not Alone",
        "thumbnail":   "{{unclear}}",
        "description": "General mental health support and recovery resources",
        "tags":        ["unclear", "rag_query"],
    },
    "medication_request": {
        "url":         "{{medication_request}}",
        "video_id":    "{{medication_request}}",
        "title":       "Stress Management Techniques",
        "thumbnail":   "{{medication_request}}",
        "description": "Simple daily techniques to manage stress and anxiety",
        "tags":        ["medication_request", "trigger_stress"],
    },
    "error": {
        "url":         "{{error}}",
        "video_id":    "{{error}}",
        "title":       "Mental Health Support — You're Not Alone",
        "thumbnail":   "{{error}}",
        "description": "General mental health support and recovery resources",
        "tags":        ["error", "rag_query"],
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
            "url":         "{{mood_sad_alt_1}}",
            "video_id":    "{{mood_sad_alt_1}}",
            "title":       "How to Deal with Sadness — Dr. Tracey Marks",
            "thumbnail":   "{{mood_sad_alt_1}}",
            "description": "Clinical guidance on processing and moving through sadness",
        },
        {
            "url":         "{{mood_sad_alt_2}}",
            "video_id":    "{{mood_sad_alt_2}}",
            "title":       "Self-Care When You're Feeling Low",
            "thumbnail":   "{{mood_sad_alt_2}}",
            "description": "Practical self-care routines to lift your mood",
        },
    ],
    "mood_anxious": [
        {
            "url":         "{{mood_anxious_alt_1}}",
            "video_id":    "{{mood_anxious_alt_1}}",
            "title":       "How to Stop Anxiety — Therapy in a Nutshell",
            "thumbnail":   "{{mood_anxious_alt_1}}",
            "description": "Evidence-based techniques to reduce anxiety",
        },
        {
            "url":         "{{mood_anxious_alt_2}}",
            "video_id":    "{{mood_anxious_alt_2}}",
            "title":       "Grounding Techniques for Anxiety",
            "thumbnail":   "{{mood_anxious_alt_2}}",
            "description": "Quick grounding exercises to calm your nervous system",
        },
    ],
    "mood_angry": [
        {
            "url":         "{{mood_angry_alt_1}}",
            "video_id":    "{{mood_angry_alt_1}}",
            "title":       "Anger and the Brain — Why We Get Angry",
            "thumbnail":   "{{mood_angry_alt_1}}",
            "description": "Understanding the neuroscience of anger",
        },
    ],
    "mood_lonely": [
        {
            "url":         "{{mood_lonely_alt_1}}",
            "video_id":    "{{mood_lonely_alt_1}}",
            "title":       "The Loneliness Epidemic — Finding Connection",
            "thumbnail":   "{{mood_lonely_alt_1}}",
            "description": "Why loneliness is rising and what to do about it",
        },
    ],
    "mood_guilty": [
        {
            "url":         "{{mood_guilty_alt_1}}",
            "video_id":    "{{mood_guilty_alt_1}}",
            "title":       "How to Forgive Yourself",
            "thumbnail":   "{{mood_guilty_alt_1}}",
            "description": "Steps toward self-forgiveness and moving forward",
        },
    ],
    "behaviour_sleep": [
        {
            "url":         "{{behaviour_sleep_alt_1}}",
            "video_id":    "{{behaviour_sleep_alt_1}}",
            "title":       "Sleep and Mental Health — The Connection",
            "thumbnail":   "{{behaviour_sleep_alt_1}}",
            "description": "How sleep affects mood, anxiety and recovery",
        },
    ],
    "behaviour_eating": [
        {
            "url":         "{{behaviour_eating_alt_1}}",
            "video_id":    "{{behaviour_eating_alt_1}}",
            "title":       "Mindful Eating — Rebuilding Your Relationship with Food",
            "thumbnail":   "{{behaviour_eating_alt_1}}",
            "description": "Mindfulness practices for healthier eating habits",
        },
    ],
    "addiction_alcohol": [
        {
            "url":         "{{addiction_alcohol_alt_1}}",
            "video_id":    "{{addiction_alcohol_alt_1}}",
            "title":       "Life in Recovery from Alcohol — Real Stories",
            "thumbnail":   "{{addiction_alcohol_alt_1}}",
            "description": "Personal experiences of building a sober life",
        },
        {
            "url":         "{{addiction_alcohol_alt_2}}",
            "video_id":    "{{addiction_alcohol_alt_2}}",
            "title":       "Craving Management — Surfing the Urge",
            "thumbnail":   "{{addiction_alcohol_alt_2}}",
            "description": "Urge surfing technique to ride out alcohol cravings",
        },
    ],
    "addiction_drugs": [
        {
            "url":         "{{addiction_drugs_alt_1}}",
            "video_id":    "{{addiction_drugs_alt_1}}",
            "title":       "The Science of Addiction and Recovery",
            "thumbnail":   "{{addiction_drugs_alt_1}}",
            "description": "How addiction changes the brain and how recovery works",
        },
    ],
    "addiction_gambling": [
        {
            "url":         "{{addiction_gambling_alt_1}}",
            "video_id":    "{{addiction_gambling_alt_1}}",
            "title":       "Gambling Disorder — How to Break the Cycle",
            "thumbnail":   "{{addiction_gambling_alt_1}}",
            "description": "Understanding gambling disorder triggers and recovery steps",
        },
    ],
    "addiction_food": [
        {
            "url":         "{{addiction_food_alt_1}}",
            "video_id":    "{{addiction_food_alt_1}}",
            "title":       "Emotional Eating and Self-Regulation",
            "thumbnail":   "{{addiction_food_alt_1}}",
            "description": "Tools for noticing urges earlier and responding with more choice",
        },
    ],
    "addiction_nicotine": [
        {
            "url":         "{{addiction_nicotine_alt_1}}",
            "video_id":    "{{addiction_nicotine_alt_1}}",
            "title":       "Managing Nicotine Withdrawal",
            "thumbnail":   "{{addiction_nicotine_alt_1}}",
            "description": "What to expect and how to cope with withdrawal symptoms",
        },
    ],
    "addiction_work": [
        {
            "url":         "{{addiction_work_alt_1}}",
            "video_id":    "{{addiction_work_alt_1}}",
            "title":       "Burnout Recovery — Learning to Slow Down",
            "thumbnail":   "{{addiction_work_alt_1}}",
            "description": "How to recognize overwork patterns and rebuild sustainable pace",
        },
    ],
    "addiction_shopping": [
        {
            "url":         "{{addiction_shopping_alt_1}}",
            "video_id":    "{{addiction_shopping_alt_1}}",
            "title":       "Why We Stress Spend — And How to Stop",
            "thumbnail":   "{{addiction_shopping_alt_1}}",
            "description": "A practical breakdown of emotional spending triggers and pauses",
        },
    ],
    "addiction_pornography": [
        {
            "url":         "{{addiction_pornography_alt_1}}",
            "video_id":    "{{addiction_pornography_alt_1}}",
            "title":       "Compulsive Sexual Content Use — Recovery Skills",
            "thumbnail":   "{{addiction_pornography_alt_1}}",
            "description": "Recovery-oriented skills for shame reduction and urge interruption",
        },
    ],
    "trigger_stress": [
        {
            "url":         "{{trigger_stress_alt_1}}",
            "video_id":    "{{trigger_stress_alt_1}}",
            "title":       "How Stress Affects Your Body",
            "thumbnail":   "{{trigger_stress_alt_1}}",
            "description": "The physiology of stress and practical relief strategies",
        },
        {
            "url":         "{{trigger_stress_alt_2}}",
            "video_id":    "{{trigger_stress_alt_2}}",
            "title":       "Progressive Muscle Relaxation for Stress",
            "thumbnail":   "{{trigger_stress_alt_2}}",
            "description": "Guided PMR technique to physically release stress",
        },
    ],
    "trigger_trauma": [
        {
            "url":         "{{trigger_trauma_alt_1}}",
            "video_id":    "{{trigger_trauma_alt_1}}",
            "title":       "PTSD Explained — Symptoms and Recovery",
            "thumbnail":   "{{trigger_trauma_alt_1}}",
            "description": "What PTSD is, how it develops, and evidence-based treatments",
        },
    ],
    "trigger_grief": [
        {
            "url":         "{{trigger_grief_alt_1}}",
            "video_id":    "{{trigger_grief_alt_1}}",
            "title":       "The Stages of Grief — What to Expect",
            "thumbnail":   "{{trigger_grief_alt_1}}",
            "description": "Understanding the grief process and finding your way through",
        },
    ],
    "trigger_relationship": [
        {
            "url":         "{{trigger_relationship_alt_1}}",
            "video_id":    "{{trigger_relationship_alt_1}}",
            "title":       "Setting Healthy Boundaries in Relationships",
            "thumbnail":   "{{trigger_relationship_alt_1}}",
            "description": "How to communicate and enforce healthy boundaries",
        },
    ],
    "trigger_financial": [
        {
            "url":         "{{trigger_financial_alt_1}}",
            "video_id":    "{{trigger_financial_alt_1}}",
            "title":       "Reducing Money Anxiety — Practical Steps",
            "thumbnail":   "{{trigger_financial_alt_1}}",
            "description": "Actionable ways to reduce anxiety around financial stress",
        },
    ],
    "severe_distress": [
        {
            "url":         "{{severe_distress_alt_1}}",
            "video_id":    "{{severe_distress_alt_1}}",
            "title":       "Getting Through a Mental Health Crisis",
            "thumbnail":   "{{severe_distress_alt_1}}",
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


def get_video_for_intents(active_intents: list, watched_video_ids: set = None) -> dict | None:
    """
    Returns the best-matching video for a set of co-present intents.

    Each video in VIDEO_MAP has a `tags` list declaring which intents it covers.
    This function scores every video by the number of its tags that overlap with
    `active_intents`, preferring unwatched videos at equal score.

    Use case: when a patient message signals multiple concerns
    (e.g. alcohol craving + sleeplessness), the video that tags both
    intents ranks higher than one that tags only one.

    Args:
        active_intents:   Ordered list — primary intent first, then secondary.
        watched_video_ids: Set of video_id strings already seen by this patient.

    Returns:
        Best-matching video dict, or falls back to get_video_for_patient(primary).
    """
    if not active_intents:
        return None
    if watched_video_ids is None:
        watched_video_ids = set()

    primary_intent = active_intents[0]
    active_set = set(active_intents)
    # Position map: lower index = higher priority (primary intent = highest)
    intent_position = {intent: i for i, intent in enumerate(active_intents)}

    best: dict | None = None
    best_overlap = 0
    best_position = float('inf')   # lower is better
    best_unwatched = False

    for key, vid in VIDEO_MAP.items():
        overlap = len(set(vid.get("tags", [])) & active_set)
        if overlap == 0:
            continue
        unwatched = vid.get("video_id", "") not in watched_video_ids
        # Position score: best (lowest) position of any matching tag in active_intents
        matching_tags = set(vid.get("tags", [])) & active_set
        position = min(intent_position[t] for t in matching_tags)
        # Prefer: 1) higher overlap  2) earlier position in active_intents  3) unwatched
        better = (
            overlap > best_overlap
            or (overlap == best_overlap and position < best_position)
            or (overlap == best_overlap and position == best_position and unwatched and not best_unwatched)
        )
        if better:
            best = vid
            best_overlap = overlap
            best_position = position
            best_unwatched = unwatched

    return best if best else get_video_for_patient(primary_intent, watched_video_ids)


def get_score_group(intent: str) -> str | None:
    """Returns the score group for an intent, or None if not applicable."""
    return SCORE_GROUPS.get(intent)


def get_score_label(intent: str) -> str:
    """Returns the slider label for the intent's score group."""
    group = SCORE_GROUPS.get(intent)
    return SCORE_LABELS.get(group, "How are you feeling right now?")
