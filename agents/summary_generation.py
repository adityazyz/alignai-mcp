# ./agents/summary_generation.py
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from tools.sse_tools import send_sse
from tools.database_tools import update_meeting_summary
import logging
import os
import json
import re
from datetime import datetime
from models import MeetingSummary
from difflib import SequenceMatcher

load_dotenv()
llm = ChatNVIDIA(model=os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct"), temperature=0)
logger = logging.getLogger(__name__)

class AttendeeMatch(BaseModel):
    """Model for structured attendee matching output"""
    attendee_name: str = Field(description="Name mentioned in meeting")
    matched_participant: Optional[Dict[str, Any]] = Field(description="Matched participant data or None if no match")
    confidence: float = Field(description="Match confidence score (0-1)")

class AttendeeMatchingResult(BaseModel):
    """Model for attendee matching result"""
    matches: List[AttendeeMatch] = Field(description="List of attendee matches")

def similarity_score(name1: str, name2: str) -> float:
    """Calculate similarity score between two names"""
    if not name1 or not name2:
        return 0.0
    
    name1_clean = name1.lower().strip()
    name2_clean = name2.lower().strip()
    
    # Exact match
    if name1_clean == name2_clean:
        return 1.0
    
    # Check if one name is contained in the other
    if name1_clean in name2_clean or name2_clean in name1_clean:
        return 0.9
    
    # Use sequence matcher for similarity
    return SequenceMatcher(None, name1_clean, name2_clean).ratio()

def fuzzy_match_attendees(attendees: List[str], participants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Match attendee names to participant data using fuzzy matching
    """
    matched_attendees = []
    
    for attendee_name in attendees:
        best_match = None
        best_score = 0.0
        
        for participant in participants:
            # Try different name combinations
            participant_names = []
            
            # Full name combinations
            if participant.get('firstName') and participant.get('lastName'):
                full_name = f"{participant['firstName']} {participant['lastName']}"
                participant_names.append(full_name)
            
            # Individual names
            if participant.get('firstName'):
                participant_names.append(participant['firstName'])
            if participant.get('lastName'):
                participant_names.append(participant['lastName'])
            if participant.get('userName'):
                participant_names.append(participant['userName'])
            
            # Find best match for this participant
            for p_name in participant_names:
                score = similarity_score(attendee_name, p_name)
                if score > best_score and score >= 0.7:  # Minimum confidence threshold
                    best_score = score
                    best_match = participant
        
        if best_match:
            # Include full participant data - FIXED: Handle None values properly
            attendee_data = {
                "name": attendee_name,
                "id": best_match.get("id"),
                "userName": best_match.get("userName"),
                "firstName": best_match.get("firstName"),
                "lastName": best_match.get("lastName"),
                "email": best_match.get("email"),
                "role": best_match.get("role", ""),  # Default to empty string instead of None
                "department": best_match.get("department", ""),  # Default to empty string instead of None
                "matchConfidence": str(best_score)  # Convert float to string
            }
        else:
            # No match found, keep basic info - FIXED: Use empty strings instead of None
            attendee_data = {
                "name": attendee_name,
                "id": None,
                "userName": None,
                "firstName": None,
                "lastName": None,
                "email": None,
                "role": "",  # Empty string instead of None
                "department": "",  # Empty string instead of None
                "matchConfidence": "0.0"  # String instead of float
            }
        
        matched_attendees.append(attendee_data)
    
    return matched_attendees

async def llm_match_attendees(attendees: List[str], participants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Use LLM with structured output to match attendees to participants
    """
    try:
        # Prepare participant data for LLM
        participant_info = []
        for p in participants:
            info = {
                "id": p.get("id"),
                "userName": p.get("userName"),
                "firstName": p.get("firstName"),
                "lastName": p.get("lastName"),
                "email": p.get("email"),
                "fullName": f"{p.get('firstName', '')} {p.get('lastName', '')}".strip()
            }
            participant_info.append(info)
        
        # Create structured output parser
        parser = JsonOutputParser(pydantic_object=AttendeeMatchingResult)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at matching meeting attendee names to participant records. 
            
            Your task is to match each attendee name from the meeting to the most likely participant from the provided list.
            
            Matching rules:
            1. Look for exact matches first
            2. Consider partial matches (first name only, last name only)
            3. Account for common nicknames (Bob->Robert, Mike->Michael, etc.)
            4. Consider variations in name order
            5. Assign confidence scores (0-1) where 1.0 is perfect match, 0.7+ is good match, below 0.7 is poor match
            
            Return a JSON object with the matches array containing attendee matches.
            
            {format_instructions}"""),
            ("user", """Match these attendees to participants:

Attendees mentioned in meeting: {attendees}

Available participants:
{participants}

For each attendee, find the best matching participant and provide the full participant data along with confidence score.""")
        ])
        
        chain = prompt | llm | parser
        
        result = await chain.ainvoke({
            "attendees": attendees,
            "participants": json.dumps(participant_info, indent=2),
            "format_instructions": parser.get_format_instructions()
        })
        
        # Process LLM results and create final attendee list
        matched_attendees = []
        for match in result.matches:
            if match.matched_participant and match.confidence >= 0.7:
                attendee_data = {
                    "name": match.attendee_name,
                    "id": match.matched_participant.get("id"),
                    "userName": match.matched_participant.get("userName"),
                    "firstName": match.matched_participant.get("firstName"),
                    "lastName": match.matched_participant.get("lastName"),
                    "email": match.matched_participant.get("email"),
                    "role": match.matched_participant.get("role", ""),  # Default to empty string
                    "department": match.matched_participant.get("department", ""),  # Default to empty string
                    "matchConfidence": str(match.confidence)  # Convert to string
                }
            else:
                attendee_data = {
                    "name": match.attendee_name,
                    "id": None,
                    "userName": None,
                    "firstName": None,
                    "lastName": None,
                    "email": None,
                    "role": "",  # Empty string instead of None
                    "department": "",  # Empty string instead of None
                    "matchConfidence": str(match.confidence) if match.matched_participant else "0.0"
                }
            
            matched_attendees.append(attendee_data)
        
        return matched_attendees
        
    except Exception as e:
        logger.warning(f"LLM matching failed: {str(e)}, falling back to fuzzy matching")
        # Fallback to fuzzy matching
        attendee_names = [name.get("name", name) if isinstance(name, dict) else name for name in attendees]
        return fuzzy_match_attendees(attendee_names, participants)

def process_attendees_with_participants(attendees: List[Any], participants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process attendees list and match with participants data
    FIXED: Handle organization-level meetings with no department_id properly
    """
    if not participants:
        logger.warning("No participants data provided for matching")
        # Convert attendees to standard format if they're just names
        processed_attendees = []
        for att in attendees:
            if isinstance(att, dict):
                att_copy = att.copy()
                # Ensure required fields are not None
                if att_copy.get('role') is None:
                    att_copy['role'] = ""
                if att_copy.get('department') is None:
                    att_copy['department'] = ""
                if att_copy.get('matchConfidence') is not None:
                    att_copy['matchConfidence'] = str(att_copy['matchConfidence'])
                processed_attendees.append(att_copy)
            else:
                processed_attendees.append({
                    "name": str(att),
                    "role": "",
                    "department": "",
                    "matchConfidence": "0.0"
                })
        return processed_attendees
    
    # Extract attendee names
    attendee_names = []
    for attendee in attendees:
        if isinstance(attendee, dict):
            attendee_names.append(attendee.get("name", "Unknown"))
        else:
            attendee_names.append(str(attendee))
    
    # Use fuzzy matching as primary method (faster and more reliable for most cases)
    matched_attendees = fuzzy_match_attendees(attendee_names, participants)
    
    # CRITICAL FIX: Ensure all attendee data has proper types and no None values
    for attendee in matched_attendees:
        # Fix role and department None values
        if attendee.get('role') is None:
            attendee['role'] = ""
        if attendee.get('department') is None:
            attendee['department'] = ""
        # Ensure matchConfidence is a string
        if isinstance(attendee.get('matchConfidence'), (int, float)):
            attendee['matchConfidence'] = str(attendee['matchConfidence'])
        elif attendee.get('matchConfidence') is None:
            attendee['matchConfidence'] = "0.0"
    
    logger.info(f"Matched {len(matched_attendees)} attendees with participant data (organization-level meeting support)")
    return matched_attendees

async def generate_summary(transcription: str, attendees: list, participants: list, organization_id: str, department_id: str, meeting_date: str) -> MeetingSummary:
    """Core summary generation logic with enhanced attendee matching and improved length controls"""
    try:
        # Process attendees with participant data - FIXED for organization-level meetings
        enhanced_attendees = process_attendees_with_participants(attendees, participants)
        
        # Create attendee string for prompt (just names for context)
        attendees_str = ", ".join([att["name"] for att in enhanced_attendees])
        
        # Generate summary with improved prompting for length control
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Generate a comprehensive meeting summary based on the transcription. Follow these requirements:

TITLE: Create a concise, specific title (3-6 words max) that captures the main topic or purpose of the meeting.

SUMMARY: Write a detailed summary of 100-200 words that includes:
- Brief overview of the meeting purpose and context
- Key topics discussed with specific details
- Important decisions made and their rationale
- Significant insights, concerns, or outcomes
- Next steps or follow-up actions mentioned

ACTION ITEMS: Extract specific, actionable tasks with clear assignees when mentioned.

Return ONLY a JSON object with fields: organizationId (str), departmentId (str or null), createdById (str), title (str), summary (str), meetingDate (str), attendees (array of attendee objects), actionItems ([{{description: str, assignee: str}}]). 

Keep the title concise but the summary comprehensive and within 100-200 words. Do NOT include any additional text, markdown, or explanations outside the JSON object."""),
            ("user", "Transcription: {transcription}\nAttendees: {attendees_str}\nOrganizationId: {organization_id}")
        ])
        chain = prompt | llm
        
        input_data = {
            "transcription": transcription,
            "attendees_str": attendees_str,
            "organization_id": organization_id
        }
        
        raw_output = await chain.ainvoke(input_data)
        
        # Extract JSON from output if wrapped in markdown
        output_text = raw_output.content if hasattr(raw_output, 'content') else raw_output
        json_match = re.search(r'```(?:json)?\n([\s\S]*?)\n```', output_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = output_text

        # Parse JSON output
        try:
            summary_data_dict = json.loads(json_str)
            summary_data = MeetingSummary(**summary_data_dict)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to parse LLM output: {str(e)}")
            # Create fallback summary
            summary_data = MeetingSummary(
                organizationId=organization_id,
                departmentId=department_id,
                createdById="ai",
                title="Meeting Summary",
                summary="Summary generated from meeting transcription.",
                meetingDate=meeting_date,
                attendees=enhanced_attendees,
                actionItems=[]
            )

        # Ensure required fields are set and use enhanced attendees
        summary_data.organizationId = organization_id
        summary_data.departmentId = department_id
        summary_data.createdById = "ai"
        summary_data.meetingDate = meeting_date
        summary_data.attendees = enhanced_attendees  # Use enhanced attendees with full participant data

        # Iterative refinement (2 iterations for speed) with improved length control
        for i in range(2):
            try:
                # Critique with length considerations
                critique_prompt = ChatPromptTemplate.from_messages([
                    ("system", """Critique the meeting summary for:
                    1. Title conciseness (should be 3-6 words, specific to meeting topic)
                    2. Summary completeness and length (should be 100-200 words with key details)
                    3. Accuracy of information from transcription
                    4. Clarity and professional tone
                    5. Action items relevance and specificity
                    
                    Suggest specific improvements for length, detail, and accuracy."""),
                    ("user", "Summary to critique:\nTitle: {title}\nSummary: {summary}\nAction Items: {action_items}")
                ])
                critique_chain = critique_prompt | llm
                critique = await critique_chain.ainvoke({
                    "title": summary_data.title,
                    "summary": summary_data.summary,
                    "action_items": json.dumps([item.__dict__ if hasattr(item, '__dict__') else item for item in summary_data.actionItems])
                })

                # Refine with specific length requirements
                refine_prompt = ChatPromptTemplate.from_messages([
                    ("system", """Refine the meeting summary based on the critique. Requirements:

TITLE: Make it concise (3-6 words) and specific to the main meeting topic or purpose.

SUMMARY: Expand to 100-200 words covering:
- Meeting context and purpose
- Key discussion points with details
- Decisions made and reasoning
- Important insights or concerns raised
- Next steps or outcomes

ACTION ITEMS: Keep specific and actionable with clear assignees.

Return ONLY a JSON object with fields: organizationId (str), departmentId (str or null), createdById (str), title (str), summary (str), meetingDate (str), attendees (array of attendee objects), actionItems ([{{description: str, assignee: str}}]). 

Ensure the summary is comprehensive within 100-200 words while keeping the title brief. Do NOT include any additional text, markdown, or explanations outside the JSON object."""),
                    ("user", "Original transcription: {transcription}\nAttendees: {attendees_str}\nOrganizationId: {organization_id}\nCritique: {critique}")
                ])
                refine_chain = refine_prompt | llm
                
                refine_input_data = {
                    "transcription": transcription,
                    "attendees_str": attendees_str,
                    "organization_id": organization_id,
                    "critique": critique.content if hasattr(critique, 'content') else critique
                }
                
                raw_refine_output = await refine_chain.ainvoke(refine_input_data)

                # Extract JSON from refine output
                refine_output_text = raw_refine_output.content if hasattr(raw_refine_output, 'content') else raw_refine_output
                json_match = re.search(r'```(?:json)?\n([\s\S]*?)\n```', refine_output_text)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = refine_output_text

                # Parse refine JSON output
                try:
                    summary_data_dict = json.loads(json_str)
                    refined_summary = MeetingSummary(**summary_data_dict)
                    
                    # Validate word count for summary (100-200 words)
                    word_count = len(refined_summary.summary.split())
                    if 100 <= word_count <= 200:
                        summary_data = refined_summary
                    else:
                        logger.info(f"Summary word count ({word_count}) outside target range, keeping previous version")
                    
                    # Reapply required fields and enhanced attendees
                    summary_data.organizationId = organization_id
                    summary_data.departmentId = department_id
                    summary_data.createdById = "ai"
                    summary_data.meetingDate = meeting_date
                    summary_data.attendees = enhanced_attendees  # Preserve enhanced attendees
                    
                except (json.JSONDecodeError, Exception) as refinement_error:
                    logger.warning(f"Refinement iteration {i+1} failed: {refinement_error}. Using previous version.")
                    break
                    
            except Exception as refinement_error:
                logger.warning(f"Refinement iteration {i+1} failed: {refinement_error}. Continuing with current summary.")
                break

        # Final validation and logging
        final_word_count = len(summary_data.summary.split())
        logger.info(f"Final summary: {len(summary_data.title.split())} words in title, {final_word_count} words in summary")
        
        # CRITICAL: Final validation of attendee data before returning
        for attendee in summary_data.attendees:
            if isinstance(attendee, dict):
                if attendee.get('role') is None:
                    attendee['role'] = ""
                if attendee.get('department') is None:
                    attendee['department'] = ""
                if isinstance(attendee.get('matchConfidence'), (int, float)):
                    attendee['matchConfidence'] = str(attendee['matchConfidence'])
                elif attendee.get('matchConfidence') is None:
                    attendee['matchConfidence'] = "0.0"
        
        return summary_data
        
    except Exception as e:
        logger.error(f"Summary generation failed: {str(e)}")
        # Return fallback summary with enhanced attendees if possible
        try:
            enhanced_attendees = process_attendees_with_participants(attendees, participants)
        except:
            enhanced_attendees = []
            for att in attendees:
                if isinstance(att, dict):
                    att_copy = att.copy()
                    att_copy['role'] = att_copy.get('role', "")
                    att_copy['department'] = att_copy.get('department', "")
                    att_copy['matchConfidence'] = str(att_copy.get('matchConfidence', 0.0))
                    enhanced_attendees.append(att_copy)
                else:
                    enhanced_attendees.append({
                        "name": str(att),
                        "role": "",
                        "department": "",
                        "matchConfidence": "0.0"
                    })
            
        return MeetingSummary(
            organizationId=organization_id,
            departmentId=department_id,
            createdById="ai",
            title="Meeting Summary Error",
            summary=f"Error generating summary: {str(e)}",
            meetingDate=meeting_date,
            attendees=enhanced_attendees,
            actionItems=[]
        )

async def summary_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Updated node that generates final summary with enhanced attendee data and improved length controls"""
    try:
        logger.debug("Entering summary_generation_node")
        transcription = state.get("transcription", "")
        attendees = state.get("attendees", [])
        participants = state.get("participants", [])  # Get participants list
        organization_id = state.get("organizationId", "")
        department_id = state.get("departmentId")
        meeting_date = state.get("meeting_data", {}).get("meeting_date", datetime.utcnow().isoformat())
        
        # Get the summary_id from initial_ids that was created in analysis node
        initial_ids = state.get("initial_ids", {})
        summary_id = initial_ids.get("summary_id", "")
        
        if not summary_id:
            logger.error("No summary_id found in initial_ids - dummy summary was not created properly")
            raise ValueError("Missing summary_id for updating dummy summary")

        # Generate the final summary content with enhanced attendee matching and length controls
        logger.debug("Generating final summary content with participant matching and improved length control")
        final_summary = await generate_summary(
            transcription, 
            attendees, 
            participants,  # Pass participants for matching
            organization_id, 
            department_id, 
            meeting_date
        )
        
        # Log attendee matching results and summary metrics
        matched_count = sum(1 for att in final_summary.attendees if isinstance(att, dict) and att.get("id"))
        summary_word_count = len(final_summary.summary.split())
        title_word_count = len(final_summary.title.split())
        
        logger.info(f"Successfully matched {matched_count}/{len(final_summary.attendees)} attendees to participant data")
        logger.info(f"Generated summary: {title_word_count} words in title, {summary_word_count} words in human-friendly summary")
        
        # Update the existing dummy summary with the final content
        logger.debug(f"Updating existing summary {summary_id} with final content")
        update_success = await update_meeting_summary(summary_id, final_summary)
        
        if not update_success:
            logger.error(f"Failed to update summary {summary_id} with final content")
            # Don't fail completely - the summary exists, just not updated
            state["messages"] = state.get("messages", []) + [f"Summary generated but update to {summary_id} failed"]
        else:
            logger.info(f"Successfully updated summary {summary_id} with final content")
            state["messages"] = state.get("messages", []) + [f"Summary generated and updated successfully (ID: {summary_id})"]
        
        # Return updated state with the final summary data
        return {
            **state,
            "meetingSummary": final_summary.model_dump(),
            "status": "pending"
        }
        
    except Exception as e:
        logger.error(f"Summary generation failed: {str(e)}", exc_info=True)
        state["status"] = "failure"
        state["messages"] = state.get("messages", []) + [f"Summary generation failed: {str(e)}"]
        send_sse({
            "success": False,
            "message": f"Summary generation failed: {str(e)}",
            "status": "failure",
            "data": {}
        }, event="error")
        raise