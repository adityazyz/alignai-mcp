# from openai import OpenAI
# import os

# def transcribe_audio(audio_data: str) -> str:
#     try:
#         client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#         with open(audio_data, "rb") as audio_file:
#             transcription = client.audio.transcriptions.create(
#                 model="whisper-1",
#                 file=audio_file
#             )
#         return transcription.text
#     except Exception as e:
#         return ""

import requests

def transcribe_audio(audio_url: str, secret: str = "myTranscribeSecretHahahahahaha") -> str:
    try:
        # Send JSON payload to the backend with the audio URL and secret
        response = requests.post(
            "http://0.0.0.0:5001/transcribe",
            json={"audio_url": audio_url, "secret": secret}
        )

        if response.status_code == 200:
            result = response.json()
            return result.get("text", "")
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return ""
    except requests.exceptions.RequestException as e:
        print(f"Request Exception: {str(e)}")
        return ""
    except ValueError as e:
        print(f"JSON Decode Error: {str(e)}")
        return ""

# # # Example usage
# # audio_url = "https://khcwoblulpdrjwmucceb.supabase.co/storage/v1/object/public/email-attachments/logo/yt-vid2.webm"
# # audio_url = "https://khcwoblulpdrjwmucceb.supabase.co/storage/v1/object/public/email-attachments/logo/recording-2025-07-25T18_37_48.265Z.webm"
# audio_url = "https://khcwoblulpdrjwmucceb.supabase.co/storage/v1/object/public/email-attachments/logo/Sec-Growth-DataScience-staff-meet2.mp3"
# transcription = transcribe_audio(audio_url)
# print("Transcription:", transcription)