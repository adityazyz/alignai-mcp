from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from tools.sse_tools import send_sse
import logging
from typing import Dict, Any, Optional, List
import os
from models import Task, TaskCreatedBy, TaskStatus, Priority, Subtask
import json
import re

load_dotenv()
llm = ChatNVIDIA(model=os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct"), temperature=0)
logger = logging.getLogger(__name__)

def smart_match_participant_id(name: str, participants: list) -> str:
    """
    Intelligently match a name from transcription to a participant ID.
    Returns the best matching participant ID or default fallback.
    """
    if not name or not participants:
        logger.warning(f"No name or participants provided for matching. Name: '{name}', Participants: {participants}")
        return get_default_participant_id(participants)
    
    name_lower = name.lower().strip()
    
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
            
            if 'name' in participant:
                participant_name = participant['name'].lower().strip()
                # Check if the name is contained in the participant name or vice versa
                if name_lower in participant_name or participant_name in name_lower:
                    participant_id = participant.get("id", participant.get("email", ""))
                    logger.debug(f"Partial name containment match: '{name}' -> ID: '{participant_id}'")
                    return participant_id
    
    logger.warning(f"No match found for name '{name}'. Using default ID.")
    return get_default_participant_id(participants)

def get_default_participant_id(participants: list) -> str:
    """Get a default valid participant ID for fallback cases."""
    if not participants:
        logger.warning("No participants available for default ID. Returning 'ai'.")
        return "ai"
    
    for participant in participants:
        if isinstance(participant, dict):
            participant_id = participant.get("id")
            if participant_id and participant_id != "ai":
                logger.debug(f"Using default participant ID: '{participant_id}'")
                return participant_id
            email = participant.get("email")
            if email and email != "ai":
                logger.debug(f"Using default participant email as ID: '{email}'")
                return email
    
    logger.warning("No valid default participant ID found. Returning 'ai'.")
    return "ai"

def is_professional_task(task_data: Dict[str, Any]) -> bool:
    """
    Validate if a task is work-related and professional.
    Returns True if the task is professional, False otherwise.
    """
    unprofessional_keywords = [
        "lunch", "coffee", "party", "celebration", "birthday", "personal",
        "hangout", "social", "drinks", "outing", "gift", "fun", "team building"
    ]
    
    title = task_data.get("title", "").lower()
    description = task_data.get("description", "").lower()
    subtasks = [subtask.get("content", "").lower() for subtask in task_data.get("subtasks", [])]
    
    # Check if the task contains unprofessional keywords
    for keyword in unprofessional_keywords:
        if keyword in title or keyword in description or any(keyword in subtask for subtask in subtasks):
            logger.warning(f"Task '{title}' rejected: contains unprofessional keyword '{keyword}'")
            return False
    
    # Basic check for work-related context (e.g., presence of business-related terms)
    work_related_keywords = [
        "project", "report", "meeting", "deadline", "deliverable", "client",
        "development", "analysis", "review", "document", "strategy", "task",
        "action item", "follow-up", "implementation", "research"
    ]
    
    has_work_context = any(keyword in title or keyword in description or any(keyword in subtask for subtask in subtasks) for keyword in work_related_keywords)
    
    if not has_work_context:
        logger.warning(f"Task '{title}' rejected: lacks work-related context")
        return False
    
    return True

async def generate_tasks(transcription: str, attendees: list, participants: list, organization_id: str, department_id: str) -> List[Task]:
    """
    Core task generation logic with smart participant ID matching and professional task filtering.
    ALWAYS returns a list, even if empty or single task.
    """
    try:
        # Generate tasks with structured output - return as JSON first
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert task identification system. Analyze the meeting transcription and identify actionable, professional, work-related tasks, action items, and follow-ups. Exclude any unprofessional or non-work-related tasks (e.g., planning social events, personal errands, or informal activities like 'organize a team lunch' or 'pick up coffee').

For each task you identify:
1. Extract a clear, actionable title (required)
2. Provide a detailed description (required)
3. Identify who should be assigned to this task based on the context - look for names mentioned in the transcription like "John, please follow up on X" or "Sarah will handle Y"
4. Break down complex tasks into subtasks if needed
5. Ensure tasks are professional and related to business activities (e.g., project work, reports, client follow-ups)

Return your response as a JSON array of task objects. Each task must have:
- title: string (clear, actionable title)
- description: string (detailed description) 
- assignedToName: string (name of the person who should do this task - extract from transcription context, think carefully about who is mentioned, use "default" if unclear)
- subtasks: array of objects with 'content' field for each subtask

Focus on concrete, actionable, work-related items mentioned in the meeting. Ignore general discussions or non-professional tasks.
Only return the JSON array, no other text."""),
            ("user", """Please analyze this meeting transcription and identify all actionable, professional, work-related tasks:

Transcription: {transcription}

Available attendees: {attendees}
Available participants: {participants}

Extract all actionable, work-related tasks, action items, and follow-ups from this meeting. Pay special attention to who is mentioned as responsible for each task. Exclude unprofessional or non-work-related tasks. Return only JSON.""")
        ])

        chain = prompt | llm
        
        response = await chain.ainvoke({
            "transcription": transcription,
            "attendees": attendees,
            "participants": participants
        })

        # Parse JSON response
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        try:
            # Try to extract JSON array from response
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            
            tasks_data = json.loads(response_text)
            
            # Ensure we have a list - CRITICAL for single tasks
            if not isinstance(tasks_data, list):
                if tasks_data:
                    tasks_data = [tasks_data]  # Convert single object to list
                else:
                    tasks_data = []
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}. Response: {response_text}")
            tasks_data = []

        # Convert to Task objects with smart ID matching and professional filtering
        tasks = []
        default_assignee = get_default_participant_id(participants)
        
        logger.debug(f"Processing {len(tasks_data)} raw tasks")
        
        for task_data in tasks_data:
            try:
                # Validate task professionalism
                if not is_professional_task(task_data):
                    continue

                # Handle subtasks
                subtasks = []
                if task_data.get("subtasks"):
                    for subtask_data in task_data["subtasks"]:
                        if isinstance(subtask_data, dict) and subtask_data.get("content"):
                            subtasks.append(Subtask(content=subtask_data["content"], isDone=False))
                        elif isinstance(subtask_data, str):
                            subtasks.append(Subtask(content=subtask_data, isDone=False))

                # Smart assignment - match name to participant ID
                assigned_to_name = task_data.get("assignedToName", "default")

                logger.debug(f"assigned_to_name: {assigned_to_name}")

                if assigned_to_name and assigned_to_name.lower() != "default":
                    assigned_to_id = smart_match_participant_id(assigned_to_name, participants)
                else:
                    assigned_to_id = default_assignee
                
                # Ensure we never use "ai" if we have valid participants
                if assigned_to_id == "ai" and participants:
                    assigned_to_id = default_assignee
                
                logger.debug(f"Task '{task_data.get('title', 'Unknown')}' assigned to name: '{assigned_to_name}' -> ID: '{assigned_to_id}'")
                
                task = Task(
                    organizationId=organization_id,
                    departmentId=department_id,
                    createdBy=TaskCreatedBy.AI,
                    title=task_data.get("title", "Generated Task"),
                    description=task_data.get("description", ""),
                    assignedToId=assigned_to_id,
                    reportToId=None,
                    status=TaskStatus.TODO,
                    priority=Priority.MEDIUM,
                    highQualityCompletion=False,
                    subtasks=subtasks
                )
                tasks.append(task)
                
            except Exception as task_error:
                logger.error(f"Error creating task from data {task_data}: {task_error}")
                continue

        # ALWAYS return a list (even if empty)
        logger.info(f"Generated {len(tasks)} professional tasks with proper participant IDs")
        return tasks
        
    except Exception as e:
        logger.error(f"Task generation failed: {str(e)}")
        return []

async def task_identification_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Legacy node wrapper for backward compatibility"""
    try:
        if not state.get("tasks_detected"):
            logger.debug("No tasks detected, skipping task_identification_node")
            return state

        logger.debug("Entering task_identification_node")
        transcription = state.get("transcription", "")
        attendees = state.get("attendees", [])
        participants = state.get("participants", [])
        organization_id = state.get("organizationId", "")
        department_id = state.get("departmentId")

        tasks = await generate_tasks(transcription, attendees, participants, organization_id, department_id)

        # Update state - ensure tasks is always a list
        updated_state = state.copy()
        updated_state["tasks"] = [task.model_dump() for task in tasks] if tasks else []
        updated_state["messages"] = state.get("messages", []) + ["Professional tasks identified and refined"]
        updated_state["status"] = "pending"
        
        logger.info(f"Successfully identified {len(tasks)} professional tasks")
        return updated_state
        
    except Exception as e:
        logger.error(f"Task identification failed: {str(e)}")
        error_state = state.copy()
        error_state["status"] = "failure"
        error_state["messages"] = state.get("messages", []) + [f"Task identification failed: {str(e)}"]
        
        # Send SSE error notification
        try:
            send_sse({
                "success": False,
                "message": f"Task identification failed: {str(e)}",
                "status": "failure",
                "data": {}
            }, event="error")
        except Exception as sse_error:
            logger.warning(f"Failed to send SSE error: {sse_error}")
        
        return error_state