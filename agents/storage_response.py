# ./agents/storage_response.py
from tools.database_tools import update_meeting_summary, update_tasks, update_generated_content
import logging
from typing import Dict, Any, Optional, Union, List
from models import MeetingSummary, Task, GeneratedContent

logger = logging.getLogger(__name__)

async def storage_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        logger.debug("Entering storage_response_node")
        initial_ids = state.get("initial_ids", {})

        success = True
        message = "Pipeline completed successfully"
        failed_operations = []

        # Since parallel_coordinator handles all database operations,
        # we just need to validate that operations were successful
        
        # Check if summary was created/updated successfully
        summary_id = initial_ids.get("summary_id", "")
        if not summary_id:
            success = False
            failed_operations.append("meeting summary")
            logger.error("Meeting summary creation/update failed - no summary ID")
        else:
            logger.debug(f"Meeting summary successfully handled with ID: {summary_id}")
        
        # Check if tasks were created successfully (if they were supposed to be)
        task_ids = initial_ids.get("task_ids", [])
        tasks_detected = state.get("tasks_detected", False)
        if tasks_detected and not task_ids:
            success = False
            failed_operations.append("tasks")
            logger.error("Task creation failed - tasks were detected but no task IDs returned")
        elif tasks_detected and task_ids:
            logger.debug(f"Tasks successfully created with IDs: {task_ids}")
        
        # Check if content was created successfully (if it was supposed to be)
        content_ids = initial_ids.get("content_ids", [])
        content_detected = state.get("content_detected", False)
        if content_detected and not content_ids:
            success = False
            failed_operations.append("generated content")
            logger.error("Content creation failed - content was detected but no content IDs returned")
        elif content_detected and content_ids:
            logger.debug(f"Generated content successfully created with IDs: {content_ids}")

        # Generate appropriate response message
        if success:
            message = "Pipeline completed successfully - all operations succeeded"
            if summary_id:
                message += f". Summary updated with ID: {summary_id}"
            if task_ids:
                message += f". {len(task_ids)} tasks created"
            if content_ids:
                message += f". {len(content_ids)} content items created"
        else:
            if len(failed_operations) == 1:
                message = f"Pipeline partially completed - failed to process {failed_operations[0]}"
            else:
                message = f"Pipeline partially completed - failed to process: {', '.join(failed_operations)}"

        # Prepare final response
        response = {
            "success": success,
            "message": message,
            "status": "success" if success else "partial_failure",
            "data": {
                "summary_id": summary_id,
                "task_ids": task_ids,
                "content_ids": content_ids,
                "failed_operations": failed_operations,
                "operations_performed": {
                    "summary": "updated" if summary_id else "failed",
                    "tasks": "created" if task_ids else ("not_needed" if not tasks_detected else "failed"),
                    "content": "created" if content_ids else ("not_needed" if not content_detected else "failed")
                }
            }
        }
        
        logger.info(f"Storage response completed: success={success}, summary_id={summary_id}, task_count={len(task_ids)}, content_count={len(content_ids)}")

        # Update state with final response
        updated_state = state.copy()
        updated_state["messages"] = state.get("messages", []) + [message]
        updated_state["final_response"] = response
        updated_state["status"] = response["status"]
        
        return updated_state
        
    except Exception as e:
        logger.error(f"Storage response processing failed: {str(e)}")
        
        # Create error response
        response = {
            "success": False,
            "message": f"Storage response processing failed: {str(e)}",
            "status": "failure",
            "data": {
                "summary_id": initial_ids.get("summary_id", ""),
                "task_ids": initial_ids.get("task_ids", []),
                "content_ids": initial_ids.get("content_ids", []),
                "failed_operations": ["storage_response"],
                "error": str(e)
            }
        }
        
        error_state = state.copy()
        error_state["status"] = "failure"
        error_state["messages"] = state.get("messages", []) + [f"Storage response failed: {str(e)}"]
        error_state["final_response"] = response
        
        return error_state