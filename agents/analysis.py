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
    hints: Optional[str] = None  # Added hints field

class AnalysisOutput(BaseModel):
    generate_summary: bool = True
    tasks_detected: bool
    content_detected: bool
    content_details: Optional[ContentDetails] = None

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

        # Enhanced prompt for better content detection and hint generation
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Analyze the meeting transcription to determine if a summary, tasks, or content (e.g., email, document) should be generated. 

For CONTENT DETECTION, look for:
1. Direct mentions: "draft an email", "send a message", "create a document", "write a report"
2. Implied needs: "follow up with client", "update the team", "inform stakeholders", "share the results"
3. Communication requirements: "let them know", "reach out to", "notify", "update", "inform"
4. Documentation needs: obvious need for written follow-up, documentation, or formal communication

For content_details, provide:
- type: "email" or "document" 
- recipient: try to identify from context (name/email), use "enteryouremail@gmail.com" as last fallback
- subject: clear subject based on content purpose
- hints: detailed description of WHY this content needs to be created, WHAT it should contain, WHO it's for, and any SPECIFIC CONTEXT from the meeting

Match attendee names to participant emails/IDs for accurate recipients. Return JSON with:
- generate_summary: boolean (always true)
- tasks_detected: boolean (true if tasks are detected)
- content_detected: boolean (true if any content creation is needed)
- content_details: object with type, recipient, subject, and hints (null if no content needed)"""),
            ("user", "Transcription: {transcription}\nAttendees: {attendees}\nParticipants: {participants}")
        ])
        
        chain = prompt | llm.with_structured_output(AnalysisOutput)
        logger.debug("Invoking LLM chain for enhanced analysis")
        analysis: AnalysisOutput = await chain.ainvoke({
            "transcription": transcription,
            "attendees": attendees,
            "participants": participants
        })
        logger.debug(f"Parsed analysis: {analysis.model_dump()}")

        # Enhanced fallback logic for content detection
        if not analysis.content_detected:
            content_keywords = [
                "draft email", "send email", "create document", "write report",
                "follow up", "reach out", "notify", "inform", "update them",
                "let them know", "share with", "communicate", "send message"
            ]
            
            transcription_lower = transcription.lower()
            for keyword in content_keywords:
                if keyword in transcription_lower:
                    analysis.content_detected = True
                    
                    # Try to extract recipient from context
                    recipient_email = "enteryouremail@gmail.com"  # Default fallback
                    
                    # Try to find email from participants first
                    for participant in participants:
                        if isinstance(participant, dict) and participant.get("email"):
                            recipient_email = participant["email"]
                            break
                    
                    # Create content details with hints
                    content_type = "email" if any(word in keyword for word in ["email", "message", "notify", "inform"]) else "document"
                    subject = "Meeting Follow-Up" if content_type == "email" else "Meeting Documentation"
                    hints = f"Content needed based on '{keyword}' mentioned in transcription. Extract relevant context and create appropriate {content_type}."
                    
                    analysis.content_details = ContentDetails(
                        type=content_type,
                        recipient=recipient_email,
                        subject=subject,
                        hints=hints
                    )
                    break

        # Fallback for tasks_detected
        if not analysis.tasks_detected:
            analysis.tasks_detected = any(keyword in transcription.lower() for keyword in [
                "follow up", "assign", "action", "complete", "finish", "deliver", "implement"
            ])

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
                # set id to state for storage node to pick up
                state["initial_ids"]["summary_id"] = dummy_summary_id
                logger.info(f"Created dummy summary with ID: {dummy_summary_id}")
                
                if not dummy_summary_id:
                    logger.error("Failed to create dummy summary - got empty ID")
                else:
                    logger.debug(f"Successfully created dummy summary: {dummy_summary_id}")
                
            except Exception as dummy_error:
                logger.error(f"Failed to create dummy summary: {dummy_error}")

        # Update state with analysis results AND dummy summary ID
        state["messages"] = state.get("messages", []) + ["Enhanced analysis completed"]
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