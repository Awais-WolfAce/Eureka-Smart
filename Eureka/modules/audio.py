import queue, pyaudio, wave, threading
from modules.tts import TTS
import os

class AudioInterface:
    def __init__(self, rate=16000, chunk=1024):
        self.rate    = rate
        self.chunk   = chunk
        self.format  = pyaudio.paInt16
        self.audio   = pyaudio.PyAudio()
        self.stream  = None
        self.frames  = queue.Queue()
        self.speaking_stream = None
        self.tts = TTS()
        self.speaking_flag = False  # Add a flag to track speaking state

    def start_recording(self):
        def cb(in_data, frame_count, t, status):
            self.frames.put(in_data)
            return (None, pyaudio.paContinue)
        self.stream = self.audio.open(format=self.format,
                                       channels=1,
                                       rate=self.rate,
                                       input=True,
                                       frames_per_buffer=self.chunk,
                                       stream_callback=cb)
        self.stream.start_stream()

    def stop_recording(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

    def read_audio(self):
        data = b''
        while not self.frames.empty():
            data += self.frames.get()
        return data

    def stop_speaking(self):
        self.speaking_flag = False  # Clear speaking flag
        if self.speaking_stream:
            self.speaking_stream.stop_stream()
            self.speaking_stream.close()
            self.speaking_stream = None

    def is_speaking(self):
        # Use the speaking flag for more reliable state tracking
        return self.speaking_flag

    def _speak_thread(self, text, lang):
        tts_file = None
        try:
            self.speaking_flag = True  # Set speaking flag
            tts_file = self.tts.synthesize(text, lang)
            if not tts_file or not os.path.exists(tts_file):
                return

            with wave.open(tts_file, 'rb') as wf:
                self.speaking_stream = self.audio.open(
                    format=self.audio.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True
                )

                data = wf.readframes(self.chunk)
                while data and self.speaking_stream:
                    try:
                        self.speaking_stream.write(data)
                        data = wf.readframes(self.chunk)
                    except OSError:
                        # This can happen if the stream is closed by another thread.
                        # It's safe to just break the loop.
                        break

        finally:
            self.speaking_flag = False  # Clear speaking flag
            if self.speaking_stream:
                self.speaking_stream.stop_stream()
                self.speaking_stream.close()
            if tts_file and os.path.exists(tts_file):
                try:
                    os.remove(tts_file)
                except OSError as e:
                    print(f"Error removing TTS file: {e}")

    def speak(self, text, lang='en'):
        self.stop_speaking() # Stop any previous speech
        thread = threading.Thread(target=self._speak_thread, args=(text, lang))
        thread.daemon = True
        thread.start()

    def __del__(self):
        self.stop_speaking()
        self.audio.terminate()
