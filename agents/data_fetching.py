from langchain_nvidia_ai_endpoints import ChatNVIDIA
from dotenv import load_dotenv
from tools.database_tools import fetch_meeting_record, fetch_department_members, fetch_organization_members
from tools.recallai_tools import fetch_recallai_bot_data
from tools.audio_tools import convert_video_to_mp3
from tools.sse_tools import send_sse
import logging
from typing import Dict, Any, Optional
import os
from datetime import datetime


load_dotenv()
llm = ChatNVIDIA(model=os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct"), temperature=0)
logger = logging.getLogger(__name__)

def extract_department_users(data: dict) -> list:
    """
    Extracts the 'user' objects from all members in the given data.

    Args:
        data (dict): The input dictionary containing a 'members' list.

    Returns:
        list: A list of 'user' dictionaries.
    """
    if "members" not in data:
        return []

    return [member["user"] for member in data["members"] if "user" in member]



async def data_fetching_node(state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        meeting_id = state["meetingId"]
        auth_token = state["auth_token"]
        
        # Fetch meeting record from Node.js backend
        meeting_data = await fetch_meeting_record(meeting_id, auth_token)
        if not meeting_data:
            state["status"] = "failure"
            state["messages"] = state.get("messages", []) + ["Meeting not found or invalid auth token"]
            send_sse({"success": False, "message": "Meeting not found or invalid auth token", "status": "failure", "data": {}}, event="error")
            raise ValueError("Meeting not found or invalid auth token")

        print("meeting data fetchedd successfully",meeting_data)
        state["meeting_data"] = meeting_data;
        # Fetch attendees from RecallAI bot
        bot_data = await fetch_recallai_bot_data(meeting_data.get("bot_id", ""))
        attendees = bot_data.get("participants", [])
        audio_url = bot_data.get("audio_mixed")
        video_url = bot_data.get("video_mixed")

        # state["status"] = "failure"
        state["audioUrl"] = bot_data.get("audio_mixed")



        # Fetch participants (for task/content assignment) from Node.js backend
        participants = []
        if meeting_data.get("department_id"):
            participants = await fetch_department_members(meeting_data["department_id"])
            participants = extract_department_users(participants)
        else:
            participants = await fetch_organization_members(meeting_data["organization_id"])
            participants = participants.get("members", []);

        print("participants fetched successfully",participants);


        

        # Fallback for attendees if bot list is empty, mapping names to participants
        if not attendees:
            attendees = [
                {"name": f"{p['firstName']} {p['lastName']}"}
                for p in participants
            ]

        state["messages"] = state.get("messages", []) + ["Data fetched successfully"]
        return {
            **state,
            "organizationId": meeting_data["organization_id"],
            "departmentId": meeting_data.get("department_id"),
            "attendees": attendees,
            "participants": participants,
            "audioUrl": audio_url,
            "videoUrl": video_url,
            "status": "pending"
        }
    except Exception as e:
        logger.error(f"Data fetching failed: {str(e)}")
        state["status"] = "failure"
        state["messages"] = state.get("messages", []) + [f"Data fetching failed: {str(e)}"]
        raise