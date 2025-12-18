import customtkinter
import queue
import threading
import string
import os
import glob
import time
import dotenv
import re

from modules.audio import AudioInterface
from modules.stt import SpeechRecognizer
from modules.nlu import NLU
from modules.database import Database

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)

def cleanup_temp_files():
    temp_files = glob.glob("tts_*.wav")
    for f in temp_files:
        try:
            os.remove(f)
        except OSError:
            pass

dotenv.load_dotenv()

class VoiceAssistantThread(threading.Thread):
    def __init__(self, ui_queue):
        super().__init__()
        self.ui_queue = ui_queue
        self.daemon = True
        self.ignore_recognition = False

    def run(self):
        try:
            # --- Initialization ---
            audio = AudioInterface()
            stt = SpeechRecognizer()
            nlu = NLU()
            database = Database()
            text_queue = queue.Queue()

            def update_ui(log_msg=None, status_msg=None):
                if log_msg: 
                    self.ui_queue.put(("log", log_msg))
                if status_msg: 
                    self.ui_queue.put(("status", status_msg))

            def stt_callback(text):
                if self.ignore_recognition:
                    print("[DEBUG] Ignoring audio during speech period")
                    return
                if audio.is_speaking():
                    print("[DEBUG] Eureka is speaking, ignoring input")
                    return
                cleaned_text = text.lower().strip().translate(str.maketrans('', '', string.punctuation))
                if cleaned_text in ['stop', 'hold on', 'wait', 'shut up']:
                    if audio.is_speaking():
                        print("[DEBUG] Interruption detected, stopping speech")
                        audio.stop_speaking()
                        time.sleep(0.5)
                        update_ui(status_msg="Listening resumed after interruption...")
                else:
                    if cleaned_text:
                        update_ui(log_msg=f"You: {text}")
                        text_queue.put(text)
            
            cleanup_temp_files()
            stt.start_continuous(stt_callback)
            update_ui(status_msg="Listening...")

            # --- Main Loop ---
            while True:
                text = text_queue.get()
                intent = nlu.parse(text)
                reply = "I can only answer questions about the database. Please ask me something about the AdventureWorks database."
                
                # Only handle database queries
                if intent.name == 'query_database':
                    user_query = intent.entities.get('query', text)
                    update_ui(status_msg="Querying database...")
                    reply = database.auto_query(user_query)
                else:
                    # If not a database query, inform the user
                    update_ui(status_msg="Waiting for database query...")

                # --- Final Reply Handling ---
                # Ensure reply is a single line
                reply_for_speech = EMOJI_PATTERN.sub(r'', reply)
                reply_for_speech = ' '.join(reply_for_speech.splitlines()).strip()
                reply = ' '.join(reply.splitlines()).strip()
                update_ui(log_msg=f"Eureka: {reply}", status_msg="Speaking...")
                
                # --- Start of Critical Section ---
                stt.pause_recognition()
                audio.speak(reply_for_speech)

                while audio.is_speaking():
                    time.sleep(0.1)

                # Extended grace period
                time.sleep(1.2)

                with text_queue.mutex:
                    text_queue.queue.clear()

                stt.resume_recognition()
                # --- End of Critical Section ---

                update_ui(status_msg="Listening...")

        except Exception as e:
            self.ui_queue.put(("log", f"An error occurred in the assistant thread: {e}"))
            self.ui_queue.put(("status", "Error! Restart required."))

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        print("[GUI INIT] Starting App initialization...")

        self.title("Eureka Database Assistant")
        self.geometry("800x600")
        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("blue")
        print("[GUI INIT] Appearance set.")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.textbox = customtkinter.CTkTextbox(self, state="disabled", wrap="word", font=("Arial", 14))
        self.textbox.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        print("[GUI INIT] Textbox created.")

        self.status_label = customtkinter.CTkLabel(self, text="Initializing...", anchor="w")
        self.status_label.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        print("[GUI INIT] Status label created.")
        
        self.ui_queue = queue.Queue()
        self.assistant_thread = VoiceAssistantThread(self.ui_queue)
        self.assistant_thread.start()
        print("[GUI INIT] Assistant thread started.")
        
        self.after(100, self.process_ui_queue)
        print("[GUI INIT] UI queue processing started.")

    def process_ui_queue(self):
        try:
            while not self.ui_queue.empty():
                msg_type, message = self.ui_queue.get_nowait()
                if msg_type == "log":
                    self.textbox.configure(state="normal")
                    self.textbox.insert("end", f"{message}\n\n")
                    self.textbox.configure(state="disabled")
                    self.textbox.see("end")
                elif msg_type == "status":
                    self.status_label.configure(text=message)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_ui_queue)

if __name__ == '__main__':
    print("[MAIN] Starting application.")
    app = App()
    print("[MAIN] App instance created. Starting mainloop.")
    app.mainloop()
    print("[MAIN] Mainloop finished.")
