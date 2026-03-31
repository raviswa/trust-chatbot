"""
SUPABASE INTEGRATION FOR PATIENT CONTEXT SYSTEM
================================================

This module provides integration between Supabase tables and patient_context.py.
It bridges the gap between storing data in Supabase and building real-time context
for the chatbot.

Usage:
    from supabase_integration import SupabaseContextManager
    
    manager = SupabaseContextManager(supabase_client)
    patient_context = await manager.build_patient_context(patient_id, session_id)
    
    # Later, update after message
    await manager.update_session_with_message(session_id, role, message, intent, severity)
    await manager.update_risk_with_checkin(patient_id, checkin_data)
"""

from typing import Dict, Optional, List, Any
from datetime import date, datetime
from dataclasses import asdict
import logging

from patient_context import (
    PatientContext,
    OnboardingProfile,
    DailyCheckin,
    ContentEngagement,
    RiskAssessment,
    build_context,
    compute_risk_score,
)

logger = logging.getLogger(__name__)


class SupabaseContextManager:
    """
    Manages reading from and writing to Supabase for patient context.
    
    Integrates Supabase tables with patient_context.py dataclasses.
    """
    
    def __init__(self, supabase_client):
        """
        Initialize with Supabase client.
        
        Args:
            supabase_client: Instance of supabase.client.Client
        """
        self.db = supabase_client
        
    async def build_patient_context(
        self, 
        patient_id: str, 
        session_id: Optional[str] = None
    ) -> PatientContext:
        """
        Assemble full patient context from Supabase (4 context sources).
        
        Steps:
        1. Fetch onboarding_profile (static)
        2. Fetch today's daily_checkin (latest)
        3. Fetch content_engagement from current session
        4. Fetch/compute latest risk_assessment
        
        Args:
            patient_id: UUID of patient
            session_id: Current session UUID (optional)
            
        Returns:
            PatientContext object with all 4 sources populated
        """
        
        logger.info(f"Building context for patient {patient_id}, session {session_id}")
        
        # 1. Get onboarding profile
        try:
            profile_response = self.db.table('onboarding_profiles').select(
                'addiction_type, baseline_mood, primary_triggers, support_network, '
                'work_status, diagnosed_conditions, communication_preference'
            ).eq('patient_id', patient_id).single().execute()
            
            onboarding = profile_response.data if profile_response.data else {}
        except Exception as e:
            logger.warning(f"Could not fetch onboarding profile: {e}")
            onboarding = {}
        
        # 2. Get today's check-in
        try:
            checkin_response = self.db.table('daily_checkins').select(
                'todays_mood, sleep_quality, craving_intensity, medication_taken, '
                'triggers_today, emotional_notes, exercise_done, sleep_hours'
            ).eq('patient_id', patient_id).eq(
                'checkin_date', date.today().isoformat()
            ).order('created_at', desc=True).limit(1).execute()
            
            checkin = checkin_response.data[0] if checkin_response.data else {}
        except Exception as e:
            logger.warning(f"Could not fetch today's checkin: {e}")
            checkin = {}
        
        # 3. Get content engagement from this session (if session_id provided)
        content_engagement_list = []
        if session_id:
            try:
                content_response = self.db.table('content_engagement').select(
                    'content_id, content_title, content_type, content_category, '
                    'completion_pct, was_helpful, user_rating, shown_at'
                ).eq('session_id', session_id).order('shown_at', desc=True).execute()
                
                content_engagement_list = content_response.data if content_response.data else []
            except Exception as e:
                logger.warning(f"Could not fetch content engagement: {e}")
        
        # 4. Get latest risk assessment
        try:
            risk_response = self.db.table('risk_assessments').select(
                'live_risk_score, risk_level, key_risk_drivers, crisis_flag'
            ).eq('patient_id', patient_id).order(
                'computed_at', desc=True
            ).limit(1).execute()
            
            risk_data = risk_response.data[0] if risk_response.data else {}
        except Exception as e:
            logger.warning(f"Could not fetch risk assessment: {e}")
            risk_data = {}
        
        # Build session dict for patient_context.build_context()
        session = {
            'session_id': session_id,
            'patient_id': patient_id,
            'intake_profile': onboarding,
            'checkin_data': checkin,
            'content_engagement': content_engagement_list,
            'message_count': 0,
        }
        
        # Use patient_context.py to build full context
        patient_context = build_context(session)
        
        return patient_context
    
    async def get_patient_snapshot(self, patient_id: str) -> Dict[str, Any]:
        """
        Get quick snapshot of patient's current state.
        
        Args:
            patient_id: UUID of patient
            
        Returns:
            Dict with: patient_code, name, risk_level, last_checkin, last_session
        """
        
        try:
            snapshot = self.db.rpc(
                'get_patient_snapshot',
                {'p_patient_id': patient_id}
            ).execute()
            
            return snapshot.data if snapshot.data else {}
        except Exception as e:
            logger.error(f"Could not fetch snapshot: {e}")
            return {}
    
    async def create_session(self, patient_id: str, patient_code: str) -> str:
        """
        Create new conversation session.
        
        Args:
            patient_id: UUID of patient
            patient_code: Human-readable code (PAT-001)
            
        Returns:
            session_id (UUID)
        """
        
        try:
            response = self.db.table('sessions').insert({
                'patient_id': patient_id,
                'patient_code': patient_code,
                'started_at': datetime.now().isoformat(),
                'message_count': 0,
            }).execute()
            
            session_id = response.data[0]['session_id']
            logger.info(f"Created session {session_id} for patient {patient_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Could not create session: {e}")
            raise
    
    async def insert_message(
        self,
        session_id: str,
        patient_id: str,
        role: str,  # 'user' or 'assistant'
        content: str,
        intent: Optional[str] = None,
        severity: Optional[str] = None,
        detected_emotions: Optional[List[str]] = None,
        response_tone: Optional[str] = None,
        response_includes_video: bool = False,
        video_title: Optional[str] = None,
    ) -> str:
        """
        Insert a message (user or bot) into conversation history.
        
        Args:
            session_id: UUID of session
            patient_id: UUID of patient
            role: 'user' or 'assistant'
            content: Message text
            intent: Detected intent (from intent classifier)
            severity: 'low', 'medium', 'high', or 'critical'
            detected_emotions: Array of emotion tags
            response_tone: For bot messages: 'warm', 'calm', 'direct', etc.
            response_includes_video: Did bot suggest a video?
            video_title: If yes, which video?
            
        Returns:
            message_id
        """
        
        try:
            response = self.db.table('messages').insert({
                'session_id': session_id,
                'patient_id': patient_id,
                'role': role,
                'content': content,
                'intent': intent,
                'severity': severity,
                'detected_emotions': detected_emotions,
                'response_tone': response_tone,
                'response_includes_video': response_includes_video,
                'video_title': video_title,
                'has_crisis_indicators': severity == 'critical' if severity else False,
            }).execute()
            
            message_id = response.data[0]['message_id']
            logger.info(f"Inserted message {message_id} for session {session_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Could not insert message: {e}")
            raise
    
    async def increment_session_messages(self, session_id: str):
        """Increment message count on session."""
        try:
            self.db.table('sessions').update({
                'message_count': self.db.sql(
                    "message_count + 1"
                )
            }).eq('session_id', session_id).execute()
        except Exception as e:
            logger.warning(f"Could not increment session messages: {e}")
    
    async def close_session(
        self,
        session_id: str,
        summary: Optional[str] = None,
        action_items: Optional[List[str]] = None,
        satisfaction_score: Optional[int] = None,
    ):
        """
        Close out a session.
        
        Args:
            session_id: UUID of session
            summary: Conversation summary
            action_items: List of follow-ups identified
            satisfaction_score: 1-5 rating from patient (if asked)
        """
        
        try:
            conversation_duration = self.db.sql(
                "(EXTRACT(EPOCH FROM (now() - started_at)) / 60)::INTEGER"
            )
            
            self.db.table('sessions').update({
                'ended_at': datetime.now().isoformat(),
                'conversation_summary': summary,
                'action_items': action_items,
                'user_satisfaction_score': satisfaction_score,
            }).eq('session_id', session_id).execute()
            
            logger.info(f"Closed session {session_id}")
            
        except Exception as e:
            logger.error(f"Could not close session: {e}")
    
    async def insert_daily_checkin(
        self,
        patient_id: str,
        todays_mood: Optional[str] = None,
        sleep_quality: Optional[int] = None,
        sleep_hours: Optional[float] = None,
        craving_intensity: Optional[int] = None,
        medication_taken: Optional[bool] = None,
        triggers_today: Optional[List[str]] = None,
        exercise_done: Optional[bool] = None,
        exercise_duration_minutes: Optional[int] = None,
        social_contact: Optional[bool] = None,
        session_id: Optional[str] = None,
    ):
        """
        Insert or update today's daily check-in.
        
        Args:
            patient_id: UUID of patient
            todays_mood: Current mood state
            sleep_quality: 0-10 score
            sleep_hours: How many hours slept
            craving_intensity: 0-10 scale
            medication_taken: Bool
            triggers_today: List of triggers encountered
            exercise_done: Bool
            exercise_duration_minutes: Minutes exercised
            social_contact: Bool - had support contact?
            session_id: If during active session
        """
        
        try:
            # Check if checkin already exists for today
            existing = self.db.table('daily_checkins').select('checkin_id').eq(
                'patient_id', patient_id
            ).eq(
                'checkin_date', date.today().isoformat()
            ).execute()
            
            checkin_data = {
                'patient_id': patient_id,
                'checkin_date': date.today().isoformat(),
                'todays_mood': todays_mood,
                'sleep_quality': sleep_quality,
                'sleep_hours': sleep_hours,
                'craving_intensity': craving_intensity,
                'medication_taken': medication_taken,
                'triggers_today': triggers_today,
                'exercise_done': exercise_done,
                'exercise_duration_minutes': exercise_duration_minutes,
                'social_contact': social_contact,
                'session_id': session_id,
            }
            
            if existing.data and len(existing.data) > 0:
                # Update existing
                response = self.db.table('daily_checkins').update(
                    checkin_data
                ).eq('patient_id', patient_id).eq(
                    'checkin_date', date.today().isoformat()
                ).execute()
                logger.info(f"Updated checkin for {patient_id}")
            else:
                # Insert new
                response = self.db.table('daily_checkins').insert(
                    checkin_data
                ).execute()
                logger.info(f"Created checkin for {patient_id}")
            
            return response.data[0] if response.data else None
            
        except Exception as e:
            logger.error(f"Could not insert/update checkin: {e}")
            raise
    
    async def update_risk_assessment(
        self,
        patient_id: str,
        session_id: Optional[str] = None,
    ):
        """
        Recompute and update risk assessment based on latest checkin.
        
        This is called after a new checkin is recorded or during session.
        
        Args:
            patient_id: UUID of patient
            session_id: Current session (optional)
        """
        
        try:
            # Fetch today's checkin
            checkin_response = self.db.table('daily_checkins').select(
                '*'
            ).eq('patient_id', patient_id).eq(
                'checkin_date', date.today().isoformat()
            ).order('created_at', desc=True).limit(1).execute()
            
            if not checkin_response.data:
                logger.warning(f"No checkin found for {patient_id}")
                return
            
            checkin_dict = checkin_response.data[0]
            
            # Convert to DailyCheckin dataclass for compute_risk_score
            checkin = DailyCheckin(
                todays_mood=checkin_dict.get('todays_mood'),
                sleep_quality=checkin_dict.get('sleep_quality'),
                craving_intensity=checkin_dict.get('craving_intensity'),
                medication_taken=checkin_dict.get('medication_taken', True),
                triggers_today=checkin_dict.get('triggers_today', []),
            )
            
            # Use patient_context.py to compute risk
            risk_assessment = compute_risk_score(checkin)
            
            # Insert into Supabase
            self.db.table('risk_assessments').insert({
                'patient_id': patient_id,
                'session_id': session_id,
                'live_risk_score': risk_assessment.live_risk_score,
                'risk_level': risk_assessment.risk_level,
                'key_risk_drivers': risk_assessment.key_risk_drivers,
                'crisis_flag': risk_assessment.crisis_flag,
                'sleep_quality_score': checkin.sleep_quality,
                'craving_intensity_score': checkin.craving_intensity,
                'computed_at': datetime.now().isoformat(),
            }).execute()
            
            logger.info(
                f"Updated risk for {patient_id}: "
                f"{risk_assessment.risk_level} ({risk_assessment.live_risk_score})"
            )
            
            return risk_assessment
            
        except Exception as e:
            logger.error(f"Could not update risk assessment: {e}")
            raise
    
    async def record_crisis_event(
        self,
        patient_id: str,
        event_type: str,
        severity: str,
        user_message: str,
        bot_response: str,
        session_id: Optional[str] = None,
        resources_provided: Optional[List[str]] = None,
    ):
        """
        Record a crisis event for monitoring and follow-up.
        
        Args:
            patient_id: UUID of patient
            event_type: 'suicidal_ideation', 'self_harm', 'relapse_urge', etc.
            severity: 'critical' or 'high'
            user_message: What patient said
            bot_response: How chatbot responded
            session_id: Current session
            resources_provided: List of resources shared (hotlines, etc.)
        """
        
        try:
            response = self.db.table('crisis_events').insert({
                'patient_id': patient_id,
                'session_id': session_id,
                'event_type': event_type,
                'severity': severity,
                'user_message': user_message,
                'bot_response': bot_response,
                'resources_provided': resources_provided or [],
                'crisis_protocol_triggered': True,
                'requires_followup': True,
            }).execute()
            
            logger.info(f"Recorded crisis event for {patient_id}: {event_type}")
            
            # TODO: Trigger notification to clinical team
            
            return response.data[0] if response.data else None
            
        except Exception as e:
            logger.error(f"Could not record crisis event: {e}")
            raise
    
    async def log_content_engagement(
        self,
        patient_id: str,
        session_id: str,
        content_id: str,
        content_title: str,
        content_type: str,
        content_category: str,
        shown_due_to_risk_level: str,
    ):
        """
        Log that content was shown to patient.
        
        Args:
            patient_id: UUID of patient
            session_id: Current session
            content_id: Unique ID of content
            content_title: Human-readable title
            content_type: 'video', 'article', 'meditation', etc.
            content_category: 'breathing', 'sleep', 'motivation', etc.
            shown_due_to_risk_level: Why was it shown? ('Low', 'Medium', 'High', etc.)
        """
        
        try:
            response = self.db.table('content_engagement').insert({
                'patient_id': patient_id,
                'session_id': session_id,
                'content_id': content_id,
                'content_title': content_title,
                'content_type': content_type,
                'content_category': content_category,
                'shown_at': datetime.now().isoformat(),
                'shown_due_to_risk_level': shown_due_to_risk_level,
            }).execute()
            
            logger.info(f"Logged content engagement: {content_title}")
            
            return response.data[0] if response.data else None
            
        except Exception as e:
            logger.error(f"Could not log content engagement: {e}")
            raise
    
    async def get_recommended_content(
        self,
        patient_id: str,
        risk_level: str,
    ) -> Optional[Dict]:
        """
        Get recommended content based on patient's risk level and preferences.
        
        Queries videos that:
        - Match content_category for this risk level
        - Patient has rated highly (4-5 stars) in past
        - Patient hasn't seen recently
        
        Args:
            patient_id: UUID of patient
            risk_level: 'Low', 'Medium', 'High', 'Critical'
            
        Returns:
            Single content dict with id, title, url, or None
        """
        
        try:
            # Map risk level to typical content needs
            category_map = {
                'Low': ['motivation', 'recovery_story'],
                'Medium': ['coping_strategies', 'sleep'],
                'High': ['crisis_support', 'immediate_coping'],
                'Critical': ['crisis_hotline', 'emergency_resources'],
            }
            
            categories = category_map.get(risk_level, [])
            
            # Get highly-rated content in these categories that patient hasn't seen
            response = self.db.rpc(
                'get_recommended_content',
                {
                    'p_patient_id': patient_id,
                    'p_categories': categories,
                }
            ).execute()
            
            content = response.data if response.data else None
            return content[0] if isinstance(content, list) and len(content) > 0 else content
            
        except Exception as e:
            logger.warning(f"Could not get recommended content: {e}")
            return None


# ============================================================================
# USAGE IN chatbot_engine.py
# ============================================================================
"""
Example integration with existing chatbot_engine.handle_message():

from supabase_integration import SupabaseContextManager

# In __init__ or setup phase:
supabase_manager = SupabaseContextManager(supabase_client)

# In handle_message() Layer 0 (Input Validation):
async def handle_message(message: str, session_id: str, patient_id: str):
    # Build context from Supabase
    patient_context = await supabase_manager.build_patient_context(
        patient_id, session_id
    )
    
    # Log user message
    await supabase_manager.insert_message(
        session_id, patient_id,
        role='user',
        content=message,
        intent=detected_intent,
        severity=severity_level,
    )
    
    # Increment session counter
    await supabase_manager.increment_session_messages(session_id)
    
    # Layer 1: Use context to greet
    opening_line = get_opening_line(patient_context)
    
    # Layer 4: Generate response with tone
    response = await generate_response(...)
    
    # Log bot response
    await supabase_manager.insert_message(
        session_id, patient_id,
        role='assistant',
        content=response,
        response_tone=tone_used,
        response_includes_video=bool(video_shown),
        video_title=video_title,
    )
    
    # If video shown, log engagement
    if video_shown:
        await supabase_manager.log_content_engagement(
            patient_id, session_id,
            content_id, content_title, content_type, content_category,
            shown_due_to_risk_level=risk_level,
        )
    
    # Detect crisis and log if needed
    if severity_level == 'critical':
        await supabase_manager.record_crisis_event(
            patient_id, event_type, 'critical',
            user_message=message,
            bot_response=response,
            session_id=session_id,
            resources_provided=crisis_resources,
        )
    
    return response
"""
