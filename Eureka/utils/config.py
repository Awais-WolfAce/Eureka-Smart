import os
from dotenv import load_dotenv

load_dotenv()   # <-- reads .env into os.environ

class Config:
    SPEECH_KEY      = os.getenv('AZURE_SPEECH_KEY')
    SPEECH_REGION   = os.getenv('AZURE_SPEECH_REGION')
    SPEAKER_KEY     = os.getenv('AZURE_SPEAKER_KEY')
    SPEAKER_REGION  = os.getenv('AZURE_SPEAKER_REGION')
    OPENAI_API_KEY  = os.getenv('AZURE_OPENAI_KEY')
    OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
    OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
    EMAIL_USER      = os.getenv('EMAIL_USER')
    EMAIL_PASS      = os.getenv('EMAIL_PASS')
    DEFAULT_LANG    = 'en-US'
    URDU_LANG       = 'ur-PK'
    OPENWEATHERMAP_API_KEY = os.getenv('OPENWEATHERMAP_API_KEY')

    @classmethod
    def debug_print(cls):
        print("=== Config Values ===")
        print("SPEECH_KEY:    ", cls.SPEECH_KEY)
        print("SPEECH_REGION: ", cls.SPEECH_REGION)
        print("SPEAKER_KEY:   ", cls.SPEAKER_KEY)
        print("SPEAKER_REGION:", cls.SPEAKER_REGION)
        print("OPENAI_API_KEY:", cls.OPENAI_API_KEY)
        print("OPENAI_ENDPOINT:", cls.OPENAI_ENDPOINT)
        print("OPENAI_DEPLOYMENT_NAME:", cls.OPENAI_DEPLOYMENT_NAME)
        print("EMAIL_USER:    ", cls.EMAIL_USER)
        print("=====================")