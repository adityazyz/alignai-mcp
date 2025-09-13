# ./agents/parallel_coordinator.py
import asyncio
import logging
from typing import Dict, Any
from tools.database_tools import create_tasks, create_generated_content
from agents.task_identification import generate_tasks
from agents.content_generation import generate_content
from agents.summary_generation import generate_summary
from agents.performance_record import generate_performance_records
from models import MeetingSummary, Task
from datetime import datetime

logger = logging.getLogger(__name__)

def smart_match_participant_id(name: str, participants: list) -> str:
    """
    Intelligently match a name from transcription/attendees to a participant ID.
    Returns the best matching participant ID or "ai" as fallback.
    """
    if not name or not participants:
        return "ai"
    
    name_lower = name.lower().strip()
    
    # Try exact matches first
    for participant in participants:
        if isinstance(participant, dict):
            # Try full name match
            if 'firstName' in participant and 'lastName' in participant:
                full_name = f"{participant['firstName']} {participant['lastName']}".lower().strip()
                if name_lower == full_name:
                    return participant.get("id", participant.get("email", "ai"))
            
            # Try single name field match
            if 'name' in participant:
                participant_name = participant['name'].lower().strip()
                if name_lower == participant_name:
                    return participant.get("id", participant.get("email", "ai"))
    
    # Try partial matches (first name or last name)
    for participant in participants:
        if isinstance(participant, dict):
            if 'firstName' in participant and 'lastName' in participant:
                first_name = participant['firstName'].lower().strip()
                last_name = participant['lastName'].lower().strip()
                if name_lower == first_name or name_lower == last_name:
                    return participant.get("id", participant.get("email", "ai"))
            
            if 'name' in participant:
                participant_name = participant['name'].lower().strip()
                # Check if the name is contained in the participant name or vice versa
                if name_lower in participant_name or participant_name in name_lower:
                    return participant.get("id", participant.get("email", "ai"))
    
    # Fallback: return first valid participant ID if available
    for participant in participants:
        if isinstance(participant, dict):
            participant_id = participant.get("id")
            if participant_id and participant_id != "ai":
                return participant_id
            email = participant.get("email")
            if email and email != "ai":
                return email
    
    return "ai"

def get_default_participant_id(participants: list) -> str:
    """Get a default valid participant ID for fallback cases."""
    if not participants:
        return "ai"
    
    for participant in participants:
        if isinstance(participant, dict):
            participant_id = participant.get("id")
            if participant_id and participant_id != "ai":
                return participant_id
            email = participant.get("email")
            if email and email != "ai":
                return email
    
    return "ai"

def validate_subtasks(task: Task) -> Task:
    """
    Validate and clean up subtasks for a task.
    """
    if not hasattr(task, 'subtasks') or not task.subtasks:
        return task
    
    # Remove empty or invalid subtasks
    valid_subtasks = []
    for subtask in task.subtasks:
        if hasattr(subtask, 'content') and subtask.content and subtask.content.strip():
            # Ensure the subtask content is professional and actionable
            content = subtask.content.strip()
            if len(content) > 5:  # Basic length check
                valid_subtasks.append(subtask)
    
    task.subtasks = valid_subtasks
    logger.debug(f"Task '{task.title}' validated with {len(valid_subtasks)} subtasks")
    return task

async def parallel_coordinator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced coordinator that handles parallel processing with summary and performance nodes
    always running, and task/content generation running conditionally.
    """
    try:
        logger.debug("Entering enhanced parallel_coordinator_node with summary and performance support")
        
        # Extract required data from state
        transcription = state.get("transcription", "")
        attendees = state.get("attendees", [])
        participants = state.get("participants", [])
        attendees_events = state.get("attendees_events", [])
        organization_id = state.get("organizationId", "") 
        department_id = state.get("departmentId")
        meeting_date = state.get("meeting_data", {}).get("meeting_date", datetime.utcnow().isoformat())
        meeting_id = state.get("meetingId", "")  # Get meetingId from state
        
        # Analysis results
        generate_summary_flag = state.get("generate_summary", True)
        tasks_detected = state.get("tasks_detected", False)
        content_detected = state.get("content_detected", False)
        content_details = state.get("content_details", {})
        
        # Get existing initial_ids from state (includes dummy_summary_id from analysis)
        initial_ids = state.get("initial_ids", {})
        
        # Step 1: Generate all content in parallel (summary and performance always run)
        processing_tasks = []
        task_names = []
        
        # Summary generation - ALWAYS runs
        processing_tasks.append(generate_summary_task(
            transcription, attendees, participants, organization_id, department_id, meeting_date
        ))
        task_names.append("summary")
        
        # Performance records - ALWAYS runs
        processing_tasks.append(generate_performance_records_task(
            transcription, participants, attendees, attendees_events, organization_id, department_id, meeting_id
        ))
        task_names.append("performance")
        
        # Task generation - runs conditionally
        if tasks_detected:
            processing_tasks.append(generate_tasks_task(
                transcription, attendees, participants, organization_id, department_id
            ))
            task_names.append("tasks")
            
        # Content generation - runs conditionally
        if content_detected and content_details:
            processing_tasks.append(generate_content_task(
                transcription, content_details, attendees, participants, organization_id, department_id
            ))
            task_names.append("content")
        
        # Execute content generation in parallel
        logger.debug("Starting parallel processing of all nodes")
        final_summary = None
        final_performance_records = []
        final_tasks = []
        final_content = []
        
        if processing_tasks:
            processing_results = await asyncio.gather(*processing_tasks, return_exceptions=True)
            
            # Process results
            for i, (task_name, result) in enumerate(zip(task_names, processing_results)):
                if isinstance(result, Exception):
                    logger.error(f"{task_name.capitalize()} generation failed: {result}")
                    if task_name == "summary":
                        final_summary = create_error_summary(organization_id, department_id, attendees, meeting_date)
                    elif task_name == "performance":
                        final_performance_records = []
                    elif task_name == "tasks":
                        final_tasks = []
                    elif task_name == "content":
                        final_content = []
                else:
                    if task_name == "summary":
                        final_summary = result
                    elif task_name == "performance":
                        final_performance_records = result if isinstance(result, list) else [result] if result else []
                    elif task_name == "tasks":
                        final_tasks = result if isinstance(result, list) else [result] if result else []
                        # Validate subtasks for each task
                        final_tasks = [validate_subtasks(task) for task in final_tasks]
                        
                        # Log subtask statistics
                        total_subtasks = sum(len(task.subtasks) for task in final_tasks)
                        logger.info(f"Generated {len(final_tasks)} tasks with {total_subtasks} total subtasks")
                        
                    elif task_name == "content":
                        final_content = result if isinstance(result, list) else [result] if result else []
        
        # Step 2: Fix assignee/creator IDs using smart matching
        if final_tasks:
            for task in final_tasks:
                if hasattr(task, 'assignedToId') and task.assignedToId == "ai":
                    # Try to find a better assignee from the task content or attendees
                    better_assignee = get_default_participant_id(participants)
                    task.assignedToId = better_assignee
                    logger.debug(f"Updated task '{task.title}' assignee from 'ai' to '{better_assignee}'")
        
        if final_content:
            for content in final_content:
                if hasattr(content, 'createdForId') and content.createdForId == "ai":
                    # Try to find a better creator from the content or attendees
                    better_creator = get_default_participant_id(participants)
                    content.createdForId = better_creator
                    logger.debug(f"Updated content creator from 'ai' to '{better_creator}'")
                
                if hasattr(content, 'recipientEmail') and content.recipientEmail == "ai":
                    # Try to find a better recipient
                    better_recipient = get_default_participant_id(participants)
                    content.recipientEmail = better_recipient
        
        # Step 3: Create database records for all generated content
        creation_tasks = []
        creation_names = []
        
        # Update summary record (using existing dummy summary ID)
        if final_summary and initial_ids.get("summary_id"):
            creation_tasks.append(update_summary_task(initial_ids["summary_id"], final_summary))
            creation_names.append("summary")
        
        # Create performance records
        if final_performance_records:
            creation_tasks.append(create_performance_records_task(final_performance_records))
            creation_names.append("performance")
        
        # Create task records
        if final_tasks and tasks_detected:
            tasks_to_create = final_tasks if isinstance(final_tasks, list) else [final_tasks]
            
            # Log detailed subtask information before database creation
            for i, task in enumerate(tasks_to_create):
                logger.debug(f"Task {i+1}: '{task.title}' has {len(task.subtasks)} subtasks:")
                for j, subtask in enumerate(task.subtasks):
                    logger.debug(f"  Subtask {j+1}: {subtask.content}")
            
            # Pass meetingId when creating tasks
            creation_tasks.append(create_tasks(tasks_to_create, meeting_id))
            creation_names.append("tasks")
        
        # Create content records
        if final_content and content_detected:
            content_to_create = final_content if isinstance(final_content, list) else [final_content]
            # Pass meetingId when creating content
            creation_tasks.append(create_generated_content(content_to_create, meeting_id))
            creation_names.append("content")
        
        # Execute database operations in parallel
        if creation_tasks:
            creation_results = await asyncio.gather(*creation_tasks, return_exceptions=True)
            
            # Process creation results
            for i, (creation_name, result) in enumerate(zip(creation_names, creation_results)):
                if isinstance(result, Exception):
                    logger.error(f"Failed to {creation_name}: {result}")
                    if creation_name == "summary":
                        initial_ids["summary_updated"] = False
                    elif creation_name == "performance":
                        initial_ids["performance_record_ids"] = []
                    elif creation_name == "tasks":
                        initial_ids["task_ids"] = []
                    elif creation_name == "content":
                        initial_ids["content_ids"] = []
                else:
                    if creation_name == "summary":
                        initial_ids["summary_updated"] = result
                        logger.info(f"Successfully updated summary {initial_ids.get('summary_id', '')}")
                    elif creation_name == "performance":
                        initial_ids["performance_record_ids"] = result if isinstance(result, list) else [result] if result else []
                        logger.info(f"Successfully created {len(initial_ids['performance_record_ids'])} performance records")
                    elif creation_name == "tasks":
                        initial_ids["task_ids"] = result if isinstance(result, list) else [result] if result else []
                        logger.info(f"Successfully created {len(initial_ids['task_ids'])} tasks with subtasks in database")
                    elif creation_name == "content":
                        initial_ids["content_ids"] = result if isinstance(result, list) else [result] if result else []
                        logger.info(f"Successfully created {len(initial_ids['content_ids'])} content items in database")
        
        logger.debug(f"Enhanced parallel coordinator completed. Summary updated: {initial_ids.get('summary_updated', False)}, Task IDs: {initial_ids.get('task_ids', [])}, Content IDs: {initial_ids.get('content_ids', [])}, Performance IDs: {len(initial_ids.get('performance_record_ids', []))}")
        
        # Update state with results
        updated_state = state.copy()
        updated_state["initial_ids"] = initial_ids
        updated_state["meetingSummary"] = final_summary.model_dump() if final_summary else {}
        updated_state["tasks"] = [task.model_dump() for task in final_tasks] if final_tasks else []
        updated_state["generatedContent"] = [content.model_dump() for content in final_content] if final_content else []
        updated_state["performanceRecords"] = final_performance_records
        updated_state["messages"] = state.get("messages", []) + ["Enhanced parallel processing with all nodes completed"]
        updated_state["status"] = "pending"
        
        # Add statistics to the message
        stats_parts = []
        if final_summary:
            stats_parts.append("summary generated")
        if final_tasks:
            total_subtasks = sum(len(task.subtasks) for task in final_tasks)
            stats_parts.append(f"{len(final_tasks)} tasks with {total_subtasks} subtasks")
        if final_content:
            stats_parts.append(f"{len(final_content)} content items")
        if final_performance_records:
            stats_parts.append(f"{len(final_performance_records)} performance records")
            
        if stats_parts:
            updated_state["messages"][-1] += f" ({', '.join(stats_parts)})"
        
        logger.info(f"Enhanced parallel processing completed successfully for meeting {meeting_id}")
        return updated_state
        
    except Exception as e:
        logger.error(f"Enhanced parallel processing failed: {str(e)}")
        error_state = state.copy()
        error_state["status"] = "failure"
        error_state["messages"] = state.get("messages", []) + [f"Enhanced parallel processing failed: {str(e)}"]
        return error_state

async def generate_summary_task(transcription: str, attendees: list, participants: list, organization_id: str, department_id: str, meeting_date: str):
    """Generate summary in a separate task"""
    return await generate_summary(transcription, attendees, participants, organization_id, department_id, meeting_date)

async def generate_performance_records_task(transcription: str, participants: list, attendees: list, attendees_events: list, organization_id: str, department_id: str, meeting_id: str):
    """Generate performance records in a separate task"""
    return await generate_performance_records(transcription, participants, attendees, attendees_events, organization_id, department_id, meeting_id)

async def generate_tasks_task(transcription: str, attendees: list, participants: list, organization_id: str, department_id: str):
    """Generate enhanced tasks with subtasks in a separate task"""
    return await generate_tasks(transcription, attendees, participants, organization_id, department_id)

async def generate_content_task(transcription: str, content_details: dict, attendees: list, participants: list, organization_id: str, department_id: str):
    """Generate content in a separate task"""
    return await generate_content(transcription, content_details, attendees, participants, organization_id, department_id)

async def update_summary_task(summary_id: str, summary_data):
    """Update summary in a separate task"""
    from tools.database_tools import update_meeting_summary
    return await update_meeting_summary(summary_id, summary_data)

async def create_performance_records_task(performance_records):
    """Create performance records in a separate task"""
    from tools.database_tools import bulk_create_performance_records
    return await bulk_create_performance_records(performance_records)

def create_error_summary(organization_id: str, department_id: str, attendees: list, meeting_date: str):
    """Create an error summary when processing fails"""
    return MeetingSummary(
        organizationId=organization_id,
        departmentId=department_id,
        createdById="ai",
        title="Processing Error",
        summary="An error occurred while processing the meeting summary.",
        meetingDate=meeting_date,
        attendees=attendees,
        actionItems=[]
    )