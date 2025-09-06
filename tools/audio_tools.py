from moviepy.editor import VideoFileClip
import requests
import os
from io import BytesIO

def convert_video_to_mp3(video_url: str) -> str:
    try:
        response = requests.get(video_url)
        response.raise_for_status()
        video_data = BytesIO(response.content)
        video = VideoFileClip(video_data)
        audio_path = "temp_audio.mp3"
        video.audio.write_audiofile(audio_path)
        video.close()
        return audio_path
    except Exception as e:
        return ""