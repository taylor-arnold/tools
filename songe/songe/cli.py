from datetime import datetime
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
import mlx_whisper

MODEL = "mlx-community/whisper-large-v3-mlx"
SAMPLE_RATE = 44100


def record_until_enter() -> np.ndarray:
    recorded = []
    recording = True
    stop_timer = threading.Event()

    def show_timer():
        start = time.monotonic()
        while not stop_timer.is_set():
            elapsed = time.monotonic() - start
            m, s = divmod(int(elapsed), 60)
            print(f"\rRecording... {m:02d}:{s:02d}  (Press Enter to stop)", end="", flush=True)
            time.sleep(0.25)

    def callback(indata, frames, t, status):
        if recording:
            recorded.append(indata.copy())

    device_info = sd.query_devices(kind="input")
    print(f"Input: {device_info['name']}")

    timer_thread = threading.Thread(target=show_timer, daemon=True)
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype=np.int16, callback=callback):
        timer_thread.start()
        input()
        stop_timer.set()
        recording = False

    timer_thread.join()
    print()  # newline after the timer line

    if not recorded:
        return np.array([], dtype=np.int16)
    return np.concatenate(recorded, axis=0)


def save_wav(audio: np.ndarray, path: str) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())


def wav_to_mp3(wav_path: str, mp3_path: str) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-q:a", "2", mp3_path],
        check=True,
        capture_output=True,
    )


def main():
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    mp3_name = f"songe-{timestamp}.mp3"
    mp3_path = Path.cwd() / mp3_name

    audio = record_until_enter()

    if len(audio) == 0:
        print("No audio recorded.")
        return

    duration = len(audio) / SAMPLE_RATE
    print(f"Recorded {duration:.2f}s. Saving to {mp3_name}...")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        save_wav(audio, wav_path)
        wav_to_mp3(wav_path, str(mp3_path))
    finally:
        Path(wav_path).unlink(missing_ok=True)

    print(f"Saved: {mp3_name}")
    print("Transcribing...")

    result = mlx_whisper.transcribe(
        str(mp3_path),
        path_or_hf_repo=MODEL,
        language="fr",
        verbose=True,
        condition_on_previous_text=False,
        temperature=0.0,
    )

    text = result.get("text", "").strip()
    print("\n" + "=" * 60)
    print(text)


if __name__ == "__main__":
    main()
