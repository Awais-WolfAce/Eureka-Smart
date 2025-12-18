import azure.cognitiveservices.speech as speechsdk
import uuid
from utils.config import Config

class TTS:
    def __init__(self):
        self.cfg = speechsdk.SpeechConfig(
            subscription=Config.SPEECH_KEY,
            region=Config.SPEECH_REGION
        )

    def synthesize(self, text, lang='en'):
        voices = {
            'en': 'en-US-JennyNeural',
            'ur': 'ur-PK-UzmaNeural',
            'hi': 'hi-IN-MadhurNeural'
        }
        voice = voices.get(lang[:2], voices['en'])
        self.cfg.speech_synthesis_voice_name = voice
        # generate and store output filename
        filename = f"tts_{uuid.uuid4()}.wav"
        audio_cfg = speechsdk.audio.AudioOutputConfig(filename=filename)
        # perform synthesis
        synth = speechsdk.SpeechSynthesizer(speech_config=self.cfg, audio_config=audio_cfg)
        result = synth.speak_text(text)
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return filename
        else:
            details = speechsdk.CancellationDetails.from_result(result)
            raise RuntimeError(f"TTS failed: {details.error_details}")
