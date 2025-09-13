from tools.transcription_tools import transcribe_audio
from models import MeetingSummary
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def transcription_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        audio_data = state.get("audioUrl")
        if not audio_data:
            raise ValueError("No audio data provided")

        transcription = transcribe_audio(audio_data)
        state["transcription"] = transcription;

        if not transcription:
            meeting_data = state.get("meeting_data", {}) 
            meeting_id = state.get("meetingId", "")  # Get meetingId from state
            from tools.database_tools import create_meeting_summary
            
            # Pass meetingId when creating error summary
            summary_id = await create_meeting_summary({
                "organizationId": meeting_data.get("organization_id", ""),
                "departmentId": meeting_data.get("department_id"),
                "createdById": "ai",
                "title": "Error: Transcription failed",
                "summary": "Transcription failed",
                "meetingDate": meeting_data.get("meetingDate"),
                "attendees": state.get("participants", []),
                "actionItems": []
            }, meeting_id)
            raise ValueError(f"Transcription failed, created empty summary: {summary_id}")

        return {
            **state,
            "transcription": transcription
        }
    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        raise