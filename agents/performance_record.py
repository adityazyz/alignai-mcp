from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from tools.sse_tools import send_sse
from tools.database_tools import bulk_create_performance_records
import logging
from typing import Dict, Any, List
import os
import json
import re

load_dotenv()
llm = ChatNVIDIA(model=os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct"), temperature=0)
logger = logging.getLogger(__name__)

points_awarding_instructions = """

Evaluate the performance of meeting members based on the following criteria and awards them points acccordingly:

// Positive scoring types (in Meetings decided by ai, to be evaluated based on meeting transcription and atendees events list)
1 "attendance" - (+1) points for attending meetings [type : attendance]
2 "active_participation" - (+2) points for active participation in meetings [type : meeting_performance]
3 "collaboration" - (+2) points for collaborating on tasks or meetings [type : meeting_performance]
4 "initiative" - (+2) points for taking initiative in tasks or meetings [type : meeting_performance]
5 "feedback" - (+2) points for providing constructive feedback in meetings [type : meeting_performance]
6 "innovation" - (+2) points for suggesting innovative ideas in meetings or tasks [type : meeting_performance]
7 "leadership" - (+2) points for leading meetings or tasks [type : meeting_performance]
8 "teamwork" - (+2) points for effective teamwork in tasks or meetings [type : meeting_performance]
9 "communication" -(+1) points for clear communication in tasks or meetings [type : meeting_performance]
10 "problem_solving" -(+2) points for effective problem-solving in tasks or meetings [type : meeting_performance]
11 "creativity" -(+2) points for creative contributions in tasks or meetings [type : meeting_performance]
12 "adaptability" -(+2) points for adapting to changes in tasks or meetings [type : meeting_performance]
13 "professionalism" -(+2) points for maintaining professionalism in tasks or meetings [type : meeting_performance]
14 "customer_focus" -(+2) points for focusing on customer needs in tasks or meetings [type : meeting_performance]
15 "attention_to_detail" -(+2) points for attention to detail in tasks or meetings [type : meeting_performance]
16 "goal_achievement" -(+2) points for achieving goals in tasks or meetings [type : meeting_performance]

// Negative scoring types (in Meetings decided by ai, ( to be evaluated based on transcription and atendees events list) )
1 "poor_communication" - (-1) points deducted for poor communication in tasks or meetings [type : meeting_performance]
2 "late_joining" - (-1) points deducted for joining meetings late [type : meeting_performance]
3 "early_leaving" - (-1) points deducted for leaving meetings early
4 "disengagement" - (-2) points deducted for lack of engagement in tasks or meetings [type : meeting_performance]
5 "conflict" -(-2) points deducted for conflicts in tasks or meetings [type : meeting_performance]
6 "unprofessionalism" -(-2) points deducted for unprofessional behavior in tasks or meetings  [type : meeting_performance]
7 "lack_of_participation" - (-2)  points deducted for not participating for tasks and dodging them in meetings [type : meeting_performance]

--Calculate the scorings based on 4 things from states--
transcription of the meeting 
participants list ( list of objects all members of department / organisation with id (used to award performance score in the backend), email, firstName, lastName etc), 
attendees list ( list of objects of all members with fields like static_participant_id, name and is_host ) and
attendees events list ( list of objects of events of the actions performed by all attendees in the meeting with fields like id, static_participant_id, name, action, timpstamp.absolute, timestamp.relative, is_host )

[use transcription and attendees events list ( to identify what positive or negative things they did) and then map attendee name from attendees list to the name in participants list and identify their id to be used when performing database actions]
"""

def extract_json_from_response(response_text: str) -> List[Dict]:
    """
    Extract JSON array from LLM response text with better error handling.
    """
    try:
        # Clean the response text
        response_text = response_text.strip()
        
        # Try to find JSON array using regex
        json_pattern = r'\[[\s\S]*\]'
        json_matches = re.findall(json_pattern, response_text)
        
        if json_matches:
            # Take the first (and likely only) JSON array match
            json_text = json_matches[0]
            logger.debug(f"Extracted JSON text: {json_text[:200]}...")
            return json.loads(json_text)
        
        # Fallback: try to parse the entire response as JSON
        if response_text.startswith('[') and response_text.endswith(']'):
            return json.loads(response_text)
        
        # Another fallback: look for text between code blocks
        if '```json' in response_text:
            start_idx = response_text.find('```json') + 7
            end_idx = response_text.find('```', start_idx)
            if end_idx != -1:
                json_text = response_text[start_idx:end_idx].strip()
                return json.loads(json_text)
        
        # Final fallback: try to find array bounds manually
        start_bracket = response_text.find('[')
        end_bracket = response_text.rfind(']')
        
        if start_bracket != -1 and end_bracket != -1 and start_bracket < end_bracket:
            json_text = response_text[start_bracket:end_bracket + 1]
            return json.loads(json_text)
        
        logger.warning("No valid JSON array found in response")
        return []
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        logger.debug(f"Problematic text: {response_text}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error extracting JSON: {e}")
        return []

def smart_match_participant_id(name: str, participants: list) -> str:
    """
    Intelligently match a name to a participant ID.
    Returns the best matching participant ID or default fallback.
    """
    if not name or not participants:
        logger.warning(f"No name or participants provided for matching. Name: '{name}', Participants: {len(participants) if participants else 0}")
        return get_default_participant_id(participants)
    
    name_lower = name.lower().strip()
    logger.debug(f"Attempting to match name: '{name}' (normalized: '{name_lower}')")
    
    # Try exact matches first
    for participant in participants:
        if isinstance(participant, dict):
            # Try full name match
            if 'firstName' in participant and 'lastName' in participant:
                full_name = f"{participant['firstName']} {participant['lastName']}".lower().strip()
                if name_lower == full_name:
                    participant_id = participant.get("id", participant.get("email", ""))
                    logger.debug(f"Exact full name match: '{name}' -> ID: '{participant_id}'")
                    return participant_id
            
            # Try userName match
            if 'userName' in participant:
                user_name = participant['userName'].lower().strip()
                if name_lower == user_name:
                    participant_id = participant.get("id", participant.get("email", ""))
                    logger.debug(f"Exact username match: '{name}' -> ID: '{participant_id}'")
                    return participant_id
            
            # Try single name field match
            if 'name' in participant:
                participant_name = participant['name'].lower().strip()
                if name_lower == participant_name:
                    participant_id = participant.get("id", participant.get("email", ""))
                    logger.debug(f"Exact single name match: '{name}' -> ID: '{participant_id}'")
                    return participant_id
    
    # Try partial matches (first name or last name)
    for participant in participants:
        if isinstance(participant, dict):
            if 'firstName' in participant and 'lastName' in participant:
                first_name = participant['firstName'].lower().strip()
                last_name = participant['lastName'].lower().strip()
                if name_lower == first_name or name_lower == last_name:
                    participant_id = participant.get("id", participant.get("email", ""))
                    logger.debug(f"Partial name match: '{name}' -> ID: '{participant_id}'")
                    return participant_id
            
            # Try contains matching
            if 'firstName' in participant:
                first_name = participant['firstName'].lower().strip()
                if first_name in name_lower or name_lower in first_name:
                    participant_id = participant.get("id", participant.get("email", ""))
                    logger.debug(f"First name containment match: '{name}' -> ID: '{participant_id}'")
                    return participant_id
    
    logger.warning(f"No match found for name '{name}'. Using default ID.")
    return get_default_participant_id(participants)

def get_default_participant_id(participants: list) -> str:
    """Get a default valid participant ID for fallback cases."""
    if not participants:
        logger.warning("No participants available for default ID. Returning 'user_329HS70oiTIrXPaoVmDkYwHgMp7'.")
        return "user_329HS70oiTIrXPaoVmDkYwHgMp7"  # Use the admin user from your logs as fallback
    
    for participant in participants:
        if isinstance(participant, dict):
            participant_id = participant.get("id")
            if participant_id and participant_id.startswith("user_"):
                logger.debug(f"Using default participant ID: '{participant_id}'")
                return participant_id
    
    # If no user_ ID found, use the first available ID
    for participant in participants:
        if isinstance(participant, dict):
            participant_id = participant.get("id")
            if participant_id:
                logger.debug(f"Using fallback participant ID: '{participant_id}'")
                return participant_id
    
    logger.warning("No valid default participant ID found. Using fallback.")
    return "user_329HS70oiTIrXPaoVmDkYwHgMp7"

async def generate_performance_records(transcription: str, participants: list, attendees: list, attendees_events: list, organization_id: str, department_id: str, meeting_id: str) -> List[Dict]:
    """
    Generate performance records based on meeting data.
    Returns a list of performance record dictionaries ready for bulk creation.
    """
    try:
        logger.info(f"Starting performance record generation for meeting {meeting_id}")
        logger.debug(f"Input data - Participants: {len(participants)}, Attendees: {len(attendees)}, Events: {len(attendees_events)}")
        
        # Generate performance records with structured output
        prompt = ChatPromptTemplate.from_messages([
            ("system", points_awarding_instructions + """

CRITICAL: Return ONLY a valid JSON array. No additional text, explanations, or formatting.

For attendance: Award +1 point (scoreType: "attendance") to each user who attended the meeting (present in attendees list). Comment: "Attended the meeting".

For late_joining: If a user joined more than 5 minutes (300 seconds) after the first join event, award -1 point (scoreType: "meeting_performance"). Comment: "Joined the meeting late".

For early_leaving: If a user left more than 5 minutes (300 seconds) before the last leave event, award -1 point (scoreType: "meeting_performance"). Comment: "Left the meeting early".

For other criteria: Analyze the transcription to identify who performed positive or negative actions. Award points accordingly with scoreType: "meeting_performance" for all non-attendance criteria.

Use user names exactly as they appear in attendees or participants lists for matching.

Return format example:
[
  {{
    "userName": "Wayne Haber",
    "scoreType": "attendance",
    "points": 1,
    "comment": "Attended the meeting"
  }},
  {{
    "userName": "Wayne Haber", 
    "scoreType": "meeting_performance",
    "points": 2,
    "comment": "Led the meeting and provided clear communication"
  }}
]

IMPORTANT: Return ONLY the JSON array, nothing else."""),
            ("user", """Analyze this meeting and generate performance records:

Transcription: {transcription}

Participants: {participants}

Attendees: {attendees}

Attendees Events: {attendees_events}""")
        ])

        chain = prompt | llm
        
        response = await chain.ainvoke({
            "transcription": transcription[:5000],  # Limit transcription to avoid token limits
            "participants": json.dumps(participants),
            "attendees": json.dumps(attendees),
            "attendees_events": json.dumps(attendees_events)
        })

        logger.info("Generate records response received")
        logger.debug(f"Raw response: {response}")

        # Parse JSON response
        response_text = response.content if hasattr(response, 'content') else str(response)
        logger.debug(f"Response text length: {len(response_text)}")
        
        # Extract JSON from response
        records_data = extract_json_from_response(response_text)
        
        if not records_data:
            logger.error("No valid performance records extracted from LLM response")
            logger.debug(f"Full response text: {response_text}")
            return []

        logger.info(f"Successfully extracted {len(records_data)} performance records from LLM")

        # Map to database-ready records
        performance_records = []
        default_user_id = get_default_participant_id(participants)
        
        logger.debug(f"Processing {len(records_data)} raw performance records")
        logger.debug(f"Default participant ID: {default_user_id}")
        
        for i, record_data in enumerate(records_data):
            try:
                if not isinstance(record_data, dict):
                    logger.warning(f"Skipping invalid record {i}: not a dictionary - {record_data}")
                    continue
                
                user_name = record_data.get("userName", "").strip()
                
                if not user_name:
                    logger.warning(f"Skipping record {i}: missing userName")
                    continue
                
                # Find matching participant ID
                user_id = smart_match_participant_id(user_name, participants)
                
                # Validate user_id
                if not user_id or user_id == "ai":
                    logger.warning(f"Skipping record for '{user_name}': invalid user_id '{user_id}'")
                    continue
                
                score_type = record_data.get("scoreType", "meeting_performance")
                points = record_data.get("points", 0)
                comment = record_data.get("comment", "")
                
                # Validate record data
                if not isinstance(points, (int, float)):
                    logger.warning(f"Invalid points value for '{user_name}': {points}")
                    points = 0
                
                logger.debug(f"Creating performance record: '{user_name}' -> ID: '{user_id}', Points: {points}, Type: {score_type}")
                
                record = {
                    "organizationId": organization_id,
                    "userId": user_id,
                    "meetingId": meeting_id,
                    "scoreType": score_type,
                    "points": int(points),
                    "comment": comment[:500]  # Limit comment length
                }
                performance_records.append(record)
                
            except Exception as record_error:
                logger.error(f"Error creating performance record from data {record_data}: {record_error}")
                continue

        logger.info(f"Generated {len(performance_records)} valid performance records")
        return performance_records
        
    except Exception as e:
        logger.error(f"Performance records generation failed: {str(e)}")
        logger.exception("Full error traceback:")
        return []

async def performance_records_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Node to generate and create performance records."""
    try:
        logger.debug("Entering performance_records_node")
        transcription = state.get("transcription", "")
        participants = state.get("participants", [])
        attendees = state.get("attendees", [])
        attendees_events = state.get("attendees_events", [])
        organization_id = state.get("organizationId", "")
        department_id = state.get("departmentId")
        meeting_id = state.get("meetingId", "")

        logger.info(f"Processing performance records for meeting: {meeting_id}")
        logger.debug(f"State data: transcription={len(transcription)} chars, participants={len(participants)}, attendees={len(attendees)}, events={len(attendees_events)}")

        if not all([transcription, participants, organization_id, meeting_id]):
            raise ValueError("Missing required data: transcription, participants, organization_id, or meeting_id")

        performance_records = await generate_performance_records(
            transcription, 
            participants, 
            attendees, 
            attendees_events, 
            organization_id, 
            department_id, 
            meeting_id
        )

        if not performance_records:
            logger.warning("No performance records generated")
            # Still return success state but with empty records
            updated_state = state.copy()
            updated_state["initial_ids"] = state.get("initial_ids", {})
            updated_state["initial_ids"]["performance_record_ids"] = []
            updated_state["messages"] = state.get("messages", []) + ["No performance records generated"]
            updated_state["status"] = "pending"
            return updated_state

        # Bulk create the records
        created_ids = await bulk_create_performance_records(performance_records)

        # Update state
        updated_state = state.copy()
        updated_state["initial_ids"] = state.get("initial_ids", {})
        updated_state["initial_ids"]["performance_record_ids"] = created_ids
        updated_state["messages"] = state.get("messages", []) + [f"Performance records created: {len(created_ids)} records"]
        updated_state["status"] = "pending"
        
        logger.info(f"Successfully created {len(created_ids)} performance records")
        return updated_state
        
    except Exception as e:
        logger.error(f"Performance records node failed: {str(e)}")
        logger.exception("Full error traceback:")
        error_state = state.copy()
        error_state["status"] = "failure"
        error_state["messages"] = state.get("messages", []) + [f"Performance records failed: {str(e)}"]
        
        # Send SSE error notification
        try:
            send_sse({
                "success": False,
                "message": f"Performance records failed: {str(e)}",
                "status": "failure",
                "data": {}
            }, event="error")
        except Exception as sse_error:
            logger.warning(f"Failed to send SSE error: {sse_error}")
        
        return error_state