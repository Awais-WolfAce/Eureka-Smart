import azure.cognitiveservices.speech as speechsdk
from utils.config import Config
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav

class SpeechRecognizer:
    def __init__(self, lang=Config.DEFAULT_LANG):
        speech_config = speechsdk.SpeechConfig(
            subscription=Config.SPEECH_KEY,
            region=Config.SPEECH_REGION
        )
        speech_config.speech_recognition_language = lang
        self.recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config)

    def recognize_once(self):
        res = self.recognizer.recognize_once()
        if res.reason == speechsdk.ResultReason.RecognizedSpeech:
            return res.text
        return None

    def start_continuous(self, callback):
        def handle(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                callback(evt.result.text)
        self.recognizer.recognized.connect(handle)
        self.recognizer.start_continuous_recognition()
        self._recognition_active = True

    def stop_continuous(self):
        self.recognizer.stop_continuous_recognition()
        self._recognition_active = False

    def pause_recognition(self):
        """Pause continuous speech recognition"""
        try:
            self.recognizer.stop_continuous_recognition()
            self._recognition_active = False
        except Exception as e:
            print(f"Error pausing recognition: {e}")

    def resume_recognition(self):
        """Resume continuous speech recognition"""
        try:
            self.recognizer.start_continuous_recognition()
            self._recognition_active = True
        except Exception as e:
            print(f"Error resuming recognition: {e}")

    def is_recognition_active(self):
        """Check if continuous recognition is currently active"""
        try:
            # This is a simple check - in practice, Azure doesn't provide a direct way
            # to check if recognition is active, so we'll use a flag-based approach
            return hasattr(self, '_recognition_active') and self._recognition_active
        except Exception:
            return False

    def recognize_once_with_lang(self, languages=[Config.DEFAULT_LANG]):
        print(f"[DEBUG] SPEECH_KEY: {Config.SPEECH_KEY}")
        print(f"[DEBUG] SPEECH_REGION: {Config.SPEECH_REGION}")
        print(f"[DEBUG] DEFAULT_LANG: {Config.DEFAULT_LANG}")
        print(f"[DEBUG] Languages for detection: {languages}")
        # Use only the first language for now
        speech_config = speechsdk.SpeechConfig(
            subscription=Config.SPEECH_KEY,
            region=Config.SPEECH_REGION
        )
        speech_config.speech_recognition_language = languages[0]
        audio_config = speechsdk.AudioConfig(use_default_microphone=True)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )
        res = recognizer.recognize_once()
        print(f"[DEBUG] Recognition result reason: {res.reason}")
        print(f"[DEBUG] Recognition result text: {getattr(res, 'text', None)}")
        print(f"[DEBUG] Recognition result JSON: {res.__dict__}")
        if res.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = res.cancellation_details
            print(f"[ERROR] Cancellation reason: {cancellation_details.reason}")
            print(f"[ERROR] Cancellation details: {cancellation_details.error_details}")
        if res.reason == speechsdk.ResultReason.NoMatch:
            print(f"[ERROR] NoMatch details: {res.no_match_details}")
        if res.reason == speechsdk.ResultReason.RecognizedSpeech:
            return res.text, languages[0]
        return None, None

    def test_microphone(self, duration=3, filename='mic_test.wav'):
        print(f"[DEBUG] Recording {duration} seconds of audio to {filename}...")
        fs = 16000
        try:
            audio = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
            sd.wait()
            wav.write(filename, fs, audio)
            print(f"[DEBUG] Audio recorded to {filename}. Play it back to check your mic.")
        except Exception as e:
            print(f"[ERROR] Microphone test failed: {e}")

    def mute_microphone(self):
        """Mute the microphone (stop recognition)."""
        self.pause_recognition()

    def unmute_microphone(self):
        """Unmute the microphone (resume recognition)."""
        self.resume_recognition()
