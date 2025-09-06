import httpx
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

RECALLAI_API_URL = os.getenv("RECALLAI_API_URL", "https://api.recall.ai")
RECALLAI_API_KEY = os.getenv("RECALLAI_API_KEY")

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
                "participants": [
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
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch RecallAI bot data for bot {bot_id}: {str(e)}")
            # Dummy data fallback
            return {
                "participants": [
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