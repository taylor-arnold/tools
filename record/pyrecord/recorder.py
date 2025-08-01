import select
import subprocess
import sys
from datetime import datetime
import termios
import threading
import tty
import wave
import json
import os
import shutil
import tempfile
import atexit

from colorama import Fore, Style, init
import numpy as np
import sounddevice as sd


init(autoreset=True)


from .transcribe import AudioTranscriber
from .formant import plot_formats


def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')


class AudioRecorder:
    def __init__(self, save_persistent=False):
        """
        Initialize the recorder with Whisper model loaded once.
        """
        idx_in = sd.default.device[0]
        info   = sd.query_devices(idx_in)
        clear_terminal()
        print(f"{Style.DIM}Recording from: [{idx_in}] {info['name']}")
        self.transcriber = AudioTranscriber()
        self.save_persistent = save_persistent
        
        if not save_persistent:
            # Create temporary directory for non-persistent files
            self.temp_dir = tempfile.mkdtemp()
            self.wav_file = os.path.join(self.temp_dir, "output.wav")
            self.json_file = os.path.join(self.temp_dir, "output.json")
            # Register cleanup function
            atexit.register(self._cleanup_temp_files)
        else:
            self.wav_file = "output.wav"
            self.json_file = "output.json"


    def record_audio(self, sample_rate=44100, channels=1, dtype=np.int16):
        """
        Record audio until any key is pressed.

        Returns:
            bool: True if audio was recorded, False otherwise
        """
        clear_terminal()
        print(f"{Style.DIM}Press any key to stop recording...")

        # Storage for recorded audio
        recorded_audio = []
        recording = True

        def audio_callback(indata, frames, time, status):
            """Callback function to capture audio data"""
            if status:
                print(f"{Style.DIM}Audio status: {status}")
            if recording:
                recorded_audio.append(indata.copy())

        def wait_for_keypress():
            """Wait for any key press (cross-platform)"""
            nonlocal recording

            # Unix/Linux/Mac
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setraw(sys.stdin.fileno())
                select.select([sys.stdin], [], [])
            finally:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            recording = False

        # Start key detection in separate thread
        key_thread = threading.Thread(target=wait_for_keypress, daemon=True)
        key_thread.start()

        # Start recording
        with sd.InputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype=dtype,
            callback=audio_callback,
        ):
            key_thread.join()  # Wait for key press

        # Convert recorded audio to numpy array
        if not recorded_audio:
            print("{Style.DIM}No audio data recorded.")
            return False

        audio_data = np.concatenate(recorded_audio, axis=0)

        # Save as WAV file (overwrite existing)
        with wave.open(self.wav_file, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(np.dtype(dtype).itemsize)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.tobytes())

        duration = len(audio_data) / sample_rate
        print(f"{Style.DIM}Duration: {duration:.2f} seconds")

        return True

    def record_and_transcribe(self):
        if self.record_audio():
            self.transcriber.transcribe(self.wav_file, self.json_file)
            self.transcriber.message(self.json_file)


    def _clear_input_buffer(self):
        """Clear any remaining input in the buffer"""
        import termios
        import sys
        if sys.stdin.isatty():
            termios.tcflush(sys.stdin, termios.TCIFLUSH)

    def run_interactive(self):
        """
        Run the application interactively until user quits.
        """
        print("\n" + "=" * 60)
        print(f"{Style.DIM}AUDIO RECORDER & TRANSCRIBER")
        print("=" * 60)

        while True:
            try:
                user_input = (
                    input(
                        f"\n{Style.DIM}"
                        "record (enter), play (p), save(s), formants (f) "
                        "or quit (q):\n"
                    )
                    .strip()
                    .lower()
                )

                if user_input == "q":
                    print(f"{Style.DIM}Au revoir !")
                    break

                elif user_input == "":
                    self.record_and_transcribe()
                    self._clear_input_buffer()

                elif user_input == "s":
                    stime = datetime.now().strftime('%Y%m%dT%H%M%S')
                    shutil.copy(self.json_file, f'cache/output-{stime}.json')
                    shutil.copy(self.wav_file, f'cache/output-{stime}.wav')
                    clear_terminal()
                    print(f"{Style.DIM}Saved file as cache/output-{stime}.wav")
                    self.transcriber.message(self.json_file)

                elif user_input == "p":
                    try:
                        clear_terminal()
                        self.transcriber.message(self.json_file)
                        subprocess.run(["afplay", self.wav_file], check=True)

                    except subprocess.CalledProcessError:
                        print(f"{Style.DIM}Error: Could not play `{self.wav_file}`")

                    except FileNotFoundError:
                        print(f"{Style.DIM}Error: afplay command not found (macOS required)")

                elif user_input == "f":
                    if self.save_persistent:
                        plot_formats(self.json_file, self.wav_file, "output.pdf")
                        subprocess.run(["open", "output.pdf"], check=True)
                    else:
                        # For temporary files, create PDF in temp directory
                        pdf_file = os.path.join(self.temp_dir, "output.pdf")
                        plot_formats(self.json_file, self.wav_file, pdf_file)
                        subprocess.run(["open", pdf_file], check=True)

                else:
                    clear_terminal()
                    print(f"{Style.DIM}Invalid input.")

            except KeyboardInterrupt:
                print(f"\n\n{Style.DIM}Au revoir!")
                break

            except Exception as e:
                print(f"{Style.DIM}Error: {e}")

    def _cleanup_temp_files(self):
        """Clean up temporary files and directory when not using persistent storage"""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)