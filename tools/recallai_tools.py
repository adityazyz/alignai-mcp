import httpx
import os
import logging
from typing import Dict, Any, List
import json # For JSON handling, null -> None

logger = logging.getLogger(__name__)

RECALLAI_API_URL = os.getenv("RECALLAI_API_URL", "https://api.recall.ai")
RECALLAI_API_KEY = os.getenv("RECALLAI_API_KEY")

# function to transform participants data into easy and desired format 
def transform_participants(data):
    """
    Transforms an array of participant objects into a simplified structure.

    Args:
        data (list): List of participant objects.

    Returns:
        list: Transformed list with name, is_host, and static_participant_id fields.
    """
    transformed = []
    for item in data:
        transformed.append({
            "name": item.get("name"),
            "is_host": item.get("is_host", False),
            "static_participant_id": (
                item.get("extra_data", {})
                    .get("google_meet", {})
                    .get("static_participant_id")
            )
        })
    return transformed
    
# function to transform participants eveents data into easy and desired format 
def transform_events(events):
    transformed = []
    for event in events:
        participant = event.get("participant", {})
        extra_data = participant.get("extra_data", {})
        google_meet = extra_data.get("google_meet", {})
        
        transformed.append({
            "id": event.get("id"),
            "action": event.get("action"),
            "timestamp": event.get("timestamp"),
            "name": participant.get("name"),
            "is_host": participant.get("is_host"),
            "static_participant_id": google_meet.get("static_participant_id")
        })
    return transformed


async def fetch_recallai_bot_data(bot_id: str) -> Dict[str, Any]:
    """
    Fetch bot data from RecallAI API, including participants and audio URL.
    Returns dummy data if the request fails to allow pipeline to continue.

    Args:
        bot_id: The ID of the bot to fetch data for.

    Returns:
        Dict: Bot data with participants (name only) and audio_mixed download URL.
    """
    async with httpx.AsyncClient() as client:
        try:
            # response = await client.get(
            #     f"{RECALLAI_API_URL}//bots/{bot_id}",
            #     headers={"Authorization": f"Token {RECALLAI_API_KEY}"}
            # )
            # response.raise_for_status()
            # bot_data = response.json()

            ## convers to python friendly response format
            # parsed = json.loads(response.text, strict=False) 

            # # Extract participants from participants_download_url
            # participants = []
            # participant_url = bot_data.get("recordings", [{}])[0] \
            #     .get("media_shortcuts", {}) \
            #     .get("participant_events", {}) \
            #     .get("data", {}) \
            #     .get("participants_download_url", "")
            # if participant_url:
            #     participant_response = await client.get(participant_url)
            #     participant_response.raise_for_status()
            #     # Transform to [{name: str}]
            #     participants = [{"name": p["name"]} for p in participant_response.json()]  # Expect: [{id, name, is_host, platform, extra_data}]

            # # Extract audio URL
            # audio_url = bot_data.get("recordings", [{}])[0] \
            #     .get("media_shortcuts", {}) \
            #     .get("audio_mixed", {}) \
            #     .get("data", {}) \
            #     .get("download_url", "")

            # # Extract video URL
            # video_url = bot_data.get("recordings", [{}])[0] \
            #     .get("media_shortcuts", {}) \
            #     .get("video_mixed", {}) \
            #     .get("data", {}) \
            #     .get("download_url", "")

            # return {
            #     "participants": participants,
            #     "audio_mixed": audio_url,
            #     "video_mixed": video_url
            # }
            
            return {
                    # { "name": "Ali Raza" },
                    # { "name": "Sana Tariq" },
                    # { "name": "Bilal Ahmed" },
                    # { "name": "Farah Khan" },
                    # { "name": "Imran Bashir" },

                "participants": [{'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'name': 'Thomas Woodham', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'name': 'Jay Swain', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'name': 'Amar Patel', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'name': 'Neil McCorrison', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'name': 'Fernando Diaz', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'name': 'Seth Berger', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'name': 'Phil Calder', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'name': 'Mon Ray', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'name': 'Alan', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}],
                
                "participants_events": [{'id': '1', 'action': 'join', 'timestamp': {'absolute': '2025-09-14T08:00:00.000000Z', 'relative': 0}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '2', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:00:00.500000Z', 'relative': 0.5}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '3', 'action': 'join', 'timestamp': {'absolute': '2025-09-14T08:00:30.000000Z', 'relative': 30.0}, 'name': 'Alan', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '4', 'action': 'join', 'timestamp': {'absolute': '2025-09-14T08:01:00.000000Z', 'relative': 60.0}, 'name': 'Phil Calder', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '5', 'action': 'join', 'timestamp': {'absolute': '2025-09-14T08:02:00.000000Z', 'relative': 120.0}, 'name': 'Mon Ray', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '6', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:04:30.000000Z', 'relative': 270.0}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '7', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:04:30.100000Z', 'relative': 270.1}, 'name': 'Mon Ray', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '8', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:05:00.000000Z', 'relative': 300.0}, 'name': 'Mon Ray', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '9', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:05:00.100000Z', 'relative': 300.1}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '10', 'action': 'join', 'timestamp': {'absolute': '2025-09-14T08:06:00.000000Z', 'relative': 360.0}, 'name': 'Neil McCorrison', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '11', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:08:00.000000Z', 'relative': 480.0}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '12', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:08:00.100000Z', 'relative': 480.1}, 'name': 'Neil McCorrison', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '13', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:09:30.000000Z', 'relative': 570.0}, 'name': 'Neil McCorrison', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '14', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:09:30.100000Z', 'relative': 570.1}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '15', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:10:30.000000Z', 'relative': 630.0}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '16', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:10:30.100000Z', 'relative': 630.1}, 'name': 'Phil Calder', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '17', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:12:30.000000Z', 'relative': 750.0}, 'name': 'Phil Calder', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '18', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:12:30.100000Z', 'relative': 750.1}, 'name': 'Thomas Woodham', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '19', 'action': 'join', 'timestamp': {'absolute': '2025-09-14T08:13:00.000000Z', 'relative': 780.0}, 'name': 'Thomas Woodham', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '20', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:15:00.000000Z', 'relative': 900.0}, 'name': 'Thomas Woodham', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '21', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:15:00.100000Z', 'relative': 900.1}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '22', 'action': 'join', 'timestamp': {'absolute': '2025-09-14T08:18:00.000000Z', 'relative': 1080.0}, 'name': 'Jay Swain', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '23', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:20:00.000000Z', 'relative': 1200.0}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '24', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:20:00.100000Z', 'relative': 1200.1}, 'name': 'Jay Swain', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '25', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:21:30.000000Z', 'relative': 1290.0}, 'name': 'Jay Swain', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '26', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:21:30.100000Z', 'relative': 1290.1}, 'name': 'Neil McCorrison', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '27', 'action': 'join', 'timestamp': {'absolute': '2025-09-14T08:22:00.000000Z', 'relative': 1320.0}, 'name': 'Amar Patel', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '28', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:23:00.000000Z', 'relative': 1380.0}, 'name': 'Neil McCorrison', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '29', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:23:00.100000Z', 'relative': 1380.1}, 'name': 'Amar Patel', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '30', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:24:30.000000Z', 'relative': 1470.0}, 'name': 'Amar Patel', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '31', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:24:30.100000Z', 'relative': 1470.1}, 'name': 'Thomas Woodham', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '32', 'action': 'join', 'timestamp': {'absolute': '2025-09-14T08:35:00.000000Z', 'relative': 2100.0}, 'name': 'Fernando Diaz', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '33', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:35:30.000000Z', 'relative': 2130.0}, 'name': 'Thomas Woodham', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '34', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:35:30.100000Z', 'relative': 2130.1}, 'name': 'Fernando Diaz', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '35', 'action': 'join', 'timestamp': {'absolute': '2025-09-14T08:40:00.000000Z', 'relative': 2400.0}, 'name': 'Seth Berger', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '36', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:42:00.000000Z', 'relative': 2520.0}, 'name': 'Fernando Diaz', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '37', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:42:00.100000Z', 'relative': 2520.1}, 'name': 'Seth Berger', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '38', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:45:00.000000Z', 'relative': 2700.0}, 'name': 'Seth Berger', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '39', 'action': 'speech_on', 'timestamp': {'absolute': '2025-09-14T08:45:00.100000Z', 'relative': 2700.1}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '40', 'action': 'speech_off', 'timestamp': {'absolute': '2025-09-14T08:50:00.000000Z', 'relative': 3000.0}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '41', 'action': 'leave', 'timestamp': {'absolute': '2025-09-14T08:50:30.000000Z', 'relative': 3030.0}, 'name': 'Wayne Haber', 'is_host': True, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '42', 'action': 'leave', 'timestamp': {'absolute': '2025-09-14T08:51:00.000000Z', 'relative': 3060.0}, 'name': 'Alan', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '43', 'action': 'leave', 'timestamp': {'absolute': '2025-09-14T08:51:30.000000Z', 'relative': 3090.0}, 'name': 'Phil Calder', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '44', 'action': 'leave', 'timestamp': {'absolute': '2025-09-14T08:52:00.000000Z', 'relative': 3120.0}, 'name': 'Mon Ray', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '45', 'action': 'leave', 'timestamp': {'absolute': '2025-09-14T08:52:30.000000Z', 'relative': 3150.0}, 'name': 'Neil McCorrison', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '46', 'action': 'leave', 'timestamp': {'absolute': '2025-09-14T08:53:00.000000Z', 'relative': 3180.0}, 'name': 'Thomas Woodham', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '47', 'action': 'leave', 'timestamp': {'absolute': '2025-09-14T08:53:30.000000Z', 'relative': 3210.0}, 'name': 'Jay Swain', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}, {'id': '48', 'action': 'leave', 'timestamp': {'absolute': '2025-09-14T08:54:00.000000Z', 'relative': 3240.0}, 'name': 'Amar Patel', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '49', 'action': 'leave', 'timestamp': {'absolute': '2025-09-14T08:54:30.000000Z', 'relative': 3270.0}, 'name': 'Fernando Diaz', 'is_host': False, 'static_participant_id': 'cf3v3UGX24UVwXWZ4buVb-gOfl0GdLD_679YAFAGqpw='}, {'id': '50', 'action': 'leave', 'timestamp': {'absolute': '2025-09-14T08:55:00.000000Z', 'relative': 3300.0}, 'name': 'Seth Berger', 'is_host': False, 'static_participant_id': 'uyzXC7wF9AlhqPsbdmPXyPrkNpjvitVSyBM_D2rgEZk='}],

                "audio_mixed": "https://khcwoblulpdrjwmucceb.supabase.co/storage/v1/object/public/email-attachments/logo/Sec-Growth-DataScience-staff-meet2.mp3",
                "video_mixed": "https://dummy-video-url.com/video.mp4"
            }
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch RecallAI bot data for bot {bot_id}: {str(e)}")
            # Dummy data fallback
            return {
                "participants": [
                    # { "name": "Ali Raza" },
                    # { "name": "Sana Tariq" },
                    # { "name": "Bilal Ahmed" },
                    # { "name": "Farah Khan" },
                    # { "name": "Imran Bashir" },

                    { "name": "Thomas Woodham" },
                    { "name": "Jay Swain" },
                    { "name": "Amar Patel" },
                    { "name": "Wayne Haber" },
                    { "name": "Neil McCorrison" },
                    { "name": "Fernando Diaz" },
                    { "name": "Seth Berger" },
                    { "name": "Phil Calder" },
                    { "name": "Mon Ray" },
                    { "name": "Alan" }
                ]
,
                "audio_mixed": "https://khcwoblulpdrjwmucceb.supabase.co/storage/v1/object/public/email-attachments/logo/Sec-Growth-DataScience-staff-meet2.mp3",
                "video_mixed": "https://dummy-video-url.com/video.mp4"
            }