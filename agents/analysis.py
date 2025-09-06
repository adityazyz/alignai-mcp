# ./agents/analysis.py
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from tools.sse_tools import send_sse
from tools.database_tools import create_meeting_summary
import logging
from typing import Dict, Any, Optional
import os
from datetime import datetime
from pydantic import BaseModel
from models import MeetingSummary

load_dotenv()
llm = ChatNVIDIA(model=os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct"), temperature=0)
logger = logging.getLogger(__name__)

class ContentDetails(BaseModel):
    type: str
    recipient: str
    subject: Optional[str] = None

class AnalysisOutput(BaseModel):
    generate_summary: bool = True
    tasks_detected: bool
    content_detected: bool
    content_details: ContentDetails

async def analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        logger.debug("Entering analysis_node")
        transcription = state.get("transcription", "")
        attendees = state.get("attendees", [])
        participants = state.get("participants", [])
        organization_id = state.get("organizationId", "")
        department_id = state.get("departmentId")
        meeting_date = state.get("meeting_data", {}).get("meeting_date", datetime.utcnow().isoformat())
        
        logger.debug(f"State: {state}")

        # Match attendees to participants by name to get email/ID
        def match_attendee_to_participant(attendee_name: str) -> Optional[str]:
            for participant in participants:
                if isinstance(participant, dict):
                    if 'firstName' in participant and 'lastName' in participant:
                        full_name = f"{participant['firstName']} {participant['lastName']}".lower()
                    elif 'name' in participant:
                        full_name = participant['name'].lower()
                    else:
                        continue
                    
                    if attendee_name.lower() == full_name:
                        return participant.get("email", participant.get("id", ""))
            return ""

        # Define prompt for analysis
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Analyze the meeting transcription to determine if a summary, tasks, or content (e.g., email, document) should be generated. Identify tasks (e.g., 'John, please follow up on X') and content needs (e.g., 'Draft an email to client about Y'). Match attendee names to participant emails/IDs for assignees/recipients. Return a JSON object with:
- generate_summary: boolean (always true)
- tasks_detected: boolean (true if tasks like 'follow up' or 'assign' are detected for a particular member of the department or organization, whether in the meeting or not)
- content_detected: boolean (true if content like 'draft/create email', "draft/create message" or 'create document' is said to a particular participant of the meeting is detected)
- content_details: object with type (string, 'email' or 'document'), recipient (string, email or empty), subject (string, optional for email)
Ensure the response is valid JSON."""),
            ("user", "Transcription: {transcription}\nAttendees: {attendees}\nParticipants: {participants}")
        ])
        
        chain = prompt | llm.with_structured_output(AnalysisOutput)
        logger.debug("Invoking LLM chain")
        analysis: AnalysisOutput = await chain.ainvoke({
            "transcription": transcription,
            "attendees": attendees,
            "participants": participants
        })
        logger.debug(f"Parsed analysis: {analysis.model_dump()}")

        # Fallback for tasks_detected and content_detected
        if not analysis.tasks_detected:
            analysis.tasks_detected = "follow up" in transcription.lower() or "assign" in transcription.lower() or "action" in transcription.lower()
        if not analysis.content_detected:
            analysis.content_detected = "draft email" in transcription.lower() or "create document" in transcription.lower() or "send email" in transcription.lower()
            if analysis.content_detected:
                content_type = "email" if "email" in transcription.lower() else "document"
                recipient = next((p.get("email", "") for p in participants if p.get("email")), "")
                subject = "Meeting Follow-Up" if content_type == "email" else ""
                analysis.content_details = ContentDetails(type=content_type, recipient=recipient, subject=subject)

        # Set default content_details if not set
        if not analysis.content_details and analysis.content_detected:
            recipient = next((p.get("email", "") for p in participants if p.get("email")), "")
            analysis.content_details = ContentDetails(
                type="email",
                recipient=recipient,
                subject="Meeting Follow-Up"
            )

        # CREATE DUMMY SUMMARY IMMEDIATELY AFTER ANALYSIS
        dummy_summary_id = ""
        if analysis.generate_summary:
            try:
                dummy_summary = MeetingSummary(
                    organizationId=organization_id,
                    departmentId=department_id,
                    createdById="ai",
                    title="Processing Meeting Summary...",
                    summary="Meeting content is being processed. Summary will be updated shortly with detailed analysis, key points, decisions, and action items...",
                    meetingDate=meeting_date,
                    attendees=attendees,
                    actionItems=[]
                )
                
                dummy_summary_id = await create_meeting_summary(dummy_summary)
                # // set id to state for storage node to pick up
                state["initial_ids"]["summary_id"] = dummy_summary_id;
                logger.info(f"Created dummy summary with ID: {dummy_summary_id}")
                
                if not dummy_summary_id:
                    logger.error("Failed to create dummy summary - got empty ID")
                else:
                    logger.debug(f"Successfully created dummy summary: {dummy_summary_id}")
                
            except Exception as dummy_error:
                logger.error(f"Failed to create dummy summary: {dummy_error}")
                # Continue without failing the entire analysis - parallel coordinator will create new one

        # Update state with analysis results AND dummy summary ID
        state["messages"] = state.get("messages", []) + ["Analysis completed"]
        logger.info("Analysis node completed successfully")
        
        return {
            **state,
            **analysis.model_dump(),
            "dummy_summary_id": dummy_summary_id,
            "status": "pending"
        }
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        state["status"] = "failure"
        state["messages"] = state.get("messages", []) + [f"Analysis failed: {str(e)}"]
        send_sse({
            "success": False,
            "message": f"Analysis failed: {str(e)}",
            "status": "failure",
            "data": {}
        }, event="error")
        raise