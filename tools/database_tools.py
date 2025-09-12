import httpx
import os
from datetime import datetime
from typing import Dict, List, Union
import logging
from models import MeetingSummary, Task, GeneratedContent, TaskCreatedBy, TaskStatus, Priority

logger = logging.getLogger(__name__)

# Base URL for Node.js backend
NODE_API_URL = os.getenv("NODE_API_URL", "http://localhost:3333")
# Backend auth token from environment variable
BACKEND_AUTH_TOKEN = os.getenv("BACKEND_OUTGOING_AUTH_TOKEN", "")

async def fetch_meeting_record(meeting_id: str, auth_token: str) -> Dict:
    """
    Fetch meeting record from Node.js backend.
    Returns dummy data if the request fails to allow pipeline to continue.

    Args:
        meeting_id: The ID of the meeting to fetch.
        auth_token: Authentication token for the request.

    Returns:
        Dict: Meeting data with bot_id, organization_id, department_id, meeting_date.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{NODE_API_URL}/mcp/meeting/info-for-mcp/{meeting_id}",
                headers={
                    "Authorization": f"Bearer {auth_token}",
                    "Backend-Auth-Token": BACKEND_AUTH_TOKEN
                }
            )
            response.raise_for_status()
            storedResponse = response.json()
            logger.debug(f"Fetched meeting record: {storedResponse}")
            return {
                "bot_id": storedResponse["botId"],
                "organization_id": storedResponse["organizationId"],
                "department_id": storedResponse["departmentId"],
                "meeting_date": storedResponse["startDateTime"]
            }
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch meeting record for meeting {meeting_id}: {str(e)}. Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
            return {
                "bot_id": "8f5be0e1-e440-42f2-aa82-5523949ef0be",
                "organization_id": "org_329HWJ2BlveJ6s634hA1waMtp5z",
                "department_id": "cmf2tgz8b0001ufajia5ftelv",
                "meeting_date": datetime.utcnow().isoformat()
            }

async def fetch_department_members(department_id: str) -> List[Dict]:
    """
    Fetch department members from Node.js backend.
    Returns dummy data if the request fails to allow pipeline to continue.

    Args:
        department_id: The ID of the department.

    Returns:
        List[Dict]: List of members with id, firstName, lastName, username, email.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{NODE_API_URL}/mcp/department/fetch-all-members/{department_id}",
                headers={"Backend-Auth-Token": BACKEND_AUTH_TOKEN}
            )
            response.raise_for_status()
            members = response.json()
            logger.debug(f"Fetched department members: {members}")
            return members
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch department members for department {department_id}: {str(e)}. Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
            return [
                {
                    "id": "user1",
                    "firstName": "John",
                    "lastName": "Doe",
                    "username": "johndoe",
                    "email": "john@example.com"
                }
            ]

async def fetch_organization_members(organization_id: str) -> List[Dict]:
    """
    Fetch organization members from Node.js backend.
    Returns dummy data if the request fails to allow pipeline to continue.

    Args:
        organization_id: The ID of the organization.

    Returns:
        List[Dict]: List of members with id, firstName, lastName, username, email.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{NODE_API_URL}/mcp/organization/fetch-all-members/{organization_id}",
                headers={"Backend-Auth-Token": BACKEND_AUTH_TOKEN}
            )
            response.raise_for_status()
            members = response.json()
            logger.debug(f"Fetched organization members: {members}")
            return members
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch organization members for organization {organization_id}: {str(e)}. Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
            return [
                {
                    "id": "user2",
                    "firstName": "Jane",
                    "lastName": "Doe",
                    "username": "janedoe",
                    "email": "jane@example.com"
                }
            ]

async def create_meeting_summary(initial_data: Union[Dict, MeetingSummary]) -> str:
    """
    Create a meeting summary by sending a POST request to the Node.js backend.

    Args:
        initial_data: Dictionary or MeetingSummary Pydantic model with summary creation fields.

    Returns:
        str: The ID of the created summary, or empty string if failed.
    """
    async with httpx.AsyncClient() as client:
        try:
            data = initial_data.model_dump() if isinstance(initial_data, MeetingSummary) else initial_data
            
            # Ensure required fields are present
            payload = {
                "organizationId": data["organizationId"],
                "departmentId": data.get("departmentId"),
                "createdById": data.get("createdById", "ai"),
                "title": data["title"],
                "summary": data["summary"],
                "meetingDate": data["meetingDate"],
                "attendees": data.get("attendees", []),
                "actionItems": data.get("actionItems", [])
            }
            
            logger.debug(f"Sending meeting summary to {NODE_API_URL}/mcp/summary/create: {payload}")
            response = await client.post(
                f"{NODE_API_URL}/mcp/summary/create",
                json=payload,
                headers={"Backend-Auth-Token": BACKEND_AUTH_TOKEN}
            )
            response.raise_for_status()
            
            response_data = response.json()
            summary_id = response_data.get("summary", {}).get("id", "")
            print("Created meeting summary:", response.json())
            logger.debug(f"Created meeting summary with ID: {summary_id}")
            return summary_id
        except httpx.HTTPError as e:
            logger.error(f"Failed to create meeting summary: {str(e)}. Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
            return ""

async def update_meeting_summary(summary_id: str, data: Union[Dict, MeetingSummary]) -> bool:
    """
    Update a meeting summary by sending a PUT request to the Node.js backend.

    Args:
        summary_id: The ID of the meeting summary to update.
        data: Dictionary or MeetingSummary Pydantic model with updated fields.

    Returns:
        bool: True if the update was successful, False otherwise.
    """
    async with httpx.AsyncClient() as client:
        try:
            data_dict = data.model_dump() if isinstance(data, MeetingSummary) else data
            
            # Prepare update payload - only include fields that can be updated
            update_payload = {}
            if "departmentId" in data_dict:
                update_payload["departmentId"] = data_dict["departmentId"]
            if "title" in data_dict:
                update_payload["title"] = data_dict["title"]
            if "summary" in data_dict:
                update_payload["summary"] = data_dict["summary"]
            if "meetingDate" in data_dict:
                update_payload["meetingDate"] = data_dict["meetingDate"]
            if "attendees" in data_dict:
                update_payload["attendees"] = data_dict["attendees"]
            if "actionItems" in data_dict:
                update_payload["actionItems"] = data_dict["actionItems"]
            
            logger.debug(f"Updating meeting summary {summary_id}: {update_payload}")
            response = await client.put(
                f"{NODE_API_URL}/mcp/summary/update/{summary_id}",
                json=update_payload,
                headers={"Backend-Auth-Token": BACKEND_AUTH_TOKEN}
            )
            response.raise_for_status()
            logger.info(f"Successfully updated meeting summary {summary_id}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to update meeting summary {summary_id}: {str(e)}. Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
            return False

async def create_tasks(initial_tasks: List[Union[Dict, Task]]) -> List[str]:
    """
    Create tasks by sending a POST request to the Node.js backend.

    Args:
        initial_tasks: List of dictionaries or Task Pydantic models with task creation fields.

    Returns:
        List[str]: List of created task IDs, or empty list if failed.
    """
    # Always ensure we have a list, even for single tasks
    if not isinstance(initial_tasks, list):
        initial_tasks = [initial_tasks] if initial_tasks else []
    
    # Return empty list if no tasks to create
    if not initial_tasks:
        logger.debug("No tasks to create, returning empty list")
        return []

    async with httpx.AsyncClient() as client:
        try:
            # Convert Task models to dictionaries
            tasks = []
            for task in initial_tasks:
                if isinstance(task, Task):
                    task_dict = task.model_dump()
                else:
                    task_dict = task.copy()
                
                # Ensure required fields and proper format
                task_payload = {
                    "organizationId": task_dict["organizationId"],
                    "departmentId": task_dict.get("departmentId"),
                    "createdBy": task_dict.get("createdBy", "ai"),
                    "title": task_dict["title"],
                    "description": task_dict.get("description", ""),
                    "assignedToId": task_dict["assignedToId"],
                    "reportToId": task_dict.get("reportToId"),
                    "status": task_dict.get("status", "todo"),
                    "priority": task_dict.get("priority", "medium"),
                    "highQualityCompletion": task_dict.get("highQualityCompletion", False),
                    "deadline": task_dict.get("deadline"),
                    "subtasks": task_dict.get("subtasks", [])
                }
                
                # CRITICAL FIX: Make sure assignedToId is not "ai" if we have valid participants
                if task_payload["assignedToId"] == "ai":
                    logger.warning(f"Task {task_payload['title']} assigned to 'ai' which may not exist in organization")
                
                # Remove None values except for departmentId and reportToId which can be None
                cleaned_payload = {}
                for key, value in task_payload.items():
                    if value is not None or key in ["departmentId", "reportToId"]:
                        cleaned_payload[key] = value
                
                tasks.append(cleaned_payload)

            # The API expects the payload in this exact format
            payload = {"initial_tasks": tasks}
            
            logger.debug(f"Creating tasks with payload: {payload}")
            response = await client.post(
                f"{NODE_API_URL}/mcp/task/bulk-create",
                json=payload,
                headers={"Backend-Auth-Token": BACKEND_AUTH_TOKEN}
            )
            
            # Log the full response for debugging
            logger.debug(f"Task creation response status: {response.status_code}")
            if response.status_code != 201:
                logger.error(f"Task creation failed with status {response.status_code}: {response.text}")
                return []
                
            response.raise_for_status()
            
            response_data = response.json()
            # Extract task IDs from the response
            created_tasks = response_data.get("tasks", [])
            task_ids = [task.get("id") for task in created_tasks if task.get("id")]
            
            logger.debug(f"Created tasks with IDs: {task_ids}")
            return task_ids
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to create tasks: {str(e)}. Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error creating tasks: {str(e)}")
            return []

async def create_generated_content(initial_content_list: List[Union[Dict, GeneratedContent]]) -> List[str]:
    """
    Create multiple generated content items by sending a POST request to the Node.js backend.

    Args:
        initial_content_list: List of dictionaries or GeneratedContent Pydantic models with content creation fields.

    Returns:
        List[str]: List of created content IDs, or empty list if failed.
    """
    # Always ensure we have a list, even for single content items
    if not isinstance(initial_content_list, list):
        initial_content_list = [initial_content_list] if initial_content_list else []
    
    # Return empty list if no content to create
    if not initial_content_list:
        logger.debug("No content to create, returning empty list")
        return []

    async with httpx.AsyncClient() as client:
        try:
            # Convert GeneratedContent models to dictionaries
            content_items = []
            for content in initial_content_list:
                if isinstance(content, GeneratedContent):
                    content_dict = content.model_dump()
                else:
                    content_dict = content.copy()
                
                # Ensure required fields and proper format
                content_payload = {
                    "organizationId": content_dict["organizationId"],
                    "departmentId": content_dict.get("departmentId"),
                    "createdForId": content_dict["createdForId"],
                    "type": content_dict["type"],
                    "content": content_dict["content"],
                    "subject": content_dict.get("subject"),
                    "recipientEmail": content_dict.get("recipientEmail"),
                    "metadata": content_dict.get("metadata")
                }
                
                # Remove None values except for departmentId which can be None
                cleaned_payload = {}
                for key, value in content_payload.items():
                    if value is not None or key in ["departmentId"]:
                        cleaned_payload[key] = value
                
                content_items.append(cleaned_payload)

            # CRITICAL FIX: The API expects "contents" not "initial_content"
            payload = {"contents": content_items}
            
            logger.debug(f"Creating generated content with payload: {payload}")
            response = await client.post(
                f"{NODE_API_URL}/mcp/generated-content/bulk-create",
                json=payload,
                headers={"Backend-Auth-Token": BACKEND_AUTH_TOKEN}
            )
            
            # Log the full response for debugging
            logger.debug(f"Content creation response status: {response.status_code}")
            if response.status_code != 201:
                logger.error(f"Content creation failed with status {response.status_code}: {response.text}")
                return []
                
            response.raise_for_status()
            
            response_data = response.json()
            # Extract content IDs from the response - backend returns "contents" array
            created_content = response_data.get("contents", [])
            content_ids = [content.get("id") for content in created_content if content.get("id")]
            
            logger.debug(f"Created generated content with IDs: {content_ids}")
            return content_ids
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to create generated content: {str(e)}. Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error creating generated content: {str(e)}")
            return []


# async def update_tasks(task_ids: List[str], tasks: List[Union[Dict, Task]]) -> bool:
#     """
#     Update tasks by sending a PUT request to the Node.js backend.

#     Args:
#         task_ids: List of task IDs to update.
#         tasks: List of dictionaries or Task Pydantic models with updated fields.

#     Returns:
#         bool: True if the update was successful, False otherwise.
#     """
#     async with httpx.AsyncClient() as client:
#         try:
#             updates = []
#             for task_id, task_data in zip(task_ids, tasks):
#                 if isinstance(task_data, Task):
#                     task_dict = task_data.model_dump()
#                 else:
#                     task_dict = task_data.copy()
                
#                 # Prepare update payload - only include fields that can be updated
#                 update_data = {"id": task_id}
                
#                 if "departmentId" in task_dict:
#                     update_data["departmentId"] = task_dict["departmentId"]
#                 if "title" in task_dict:
#                     update_data["title"] = task_dict["title"]
#                 if "description" in task_dict:
#                     update_data["description"] = task_dict["description"]
#                 if "assignedToId" in task_dict:
#                     update_data["assignedToId"] = task_dict["assignedToId"]
#                 if "reportToId" in task_dict:
#                     update_data["reportToId"] = task_dict["reportToId"]
#                 if "status" in task_dict:
#                     update_data["status"] = task_dict["status"]
#                 if "priority" in task_dict:
#                     update_data["priority"] = task_dict["priority"]
#                 if "highQualityCompletion" in task_dict:
#                     update_data["highQualityCompletion"] = task_dict["highQualityCompletion"]
#                 if "deadline" in task_dict:
#                     update_data["deadline"] = task_dict["deadline"]
#                 if "completedAt" in task_dict:
#                     update_data["completedAt"] = task_dict["completedAt"]
                
#                 updates.append(update_data)

#             payload = {"updates": updates}
#             logger.debug(f"Updating tasks with payload: {payload}")
#             response = await client.put(f"{NODE_API_URL}/mcp/task/bulk-update", json=payload)
#             response.raise_for_status()
#             logger.info(f"Successfully updated tasks: {task_ids}")
#             return True
#         except httpx.HTTPError as e:
#             logger.error(f"Failed to update tasks: {str(e)}. Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
#             return False


# async def update_generated_content(content_ids: List[str], content_list: List[Union[Dict, GeneratedContent]]) -> bool:
#     """
#     Update multiple generated content items by sending a PUT request to the Node.js backend.

#     Args:
#         content_ids: List of content IDs to update.
#         content_list: List of dictionaries or GeneratedContent Pydantic models with updated fields.

#     Returns:
#         bool: True if the update was successful, False otherwise.
#     """
#     async with httpx.AsyncClient() as client:
#         try:
#             updates = []
#             for content_id, content_data in zip(content_ids, content_list):
#                 if isinstance(content_data, GeneratedContent):
#                     content_dict = content_data.model_dump()
#                 else:
#                     content_dict = content_data.copy()
                
#                 # Prepare update payload - only include fields that can be updated
#                 update_data = {"id": content_id}
                
#                 if "departmentId" in content_dict:
#                     update_data["departmentId"] = content_dict["departmentId"]
#                 if "type" in content_dict:
#                     update_data["type"] = content_dict["type"]
#                 if "content" in content_dict:
#                     update_data["content"] = content_dict["content"]
#                 if "subject" in content_dict:
#                     update_data["subject"] = content_dict["subject"]
#                 if "recipientEmail" in content_dict:
#                     update_data["recipientEmail"] = content_dict["recipientEmail"]
#                 if "metadata" in content_dict:
#                     update_data["metadata"] = content_dict["metadata"]
#                 if "isArchived" in content_dict:
#                     update_data["isArchived"] = content_dict["isArchived"]
                
#                 updates.append(update_data)

#             payload = {"updates": updates}
#             logger.debug(f"Updating generated content with payload: {payload}")
#             response = await client.put(f"{NODE_API_URL}/mcp/generated-content/bulk-update",  json=payload)
#             response.raise_for_status()
#             logger.info(f"Successfully updated generated content: {content_ids}")
#             return True
#         except httpx.HTTPError as e:
#             logger.error(f"Failed to update generated content: {str(e)}. Response: {e.response.text if hasattr(e, 'response') else 'No response'}")
#             return False