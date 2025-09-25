import json
import tempfile
from pathlib import Path

import openai
from pydub import AudioSegment


def transcribe_long_audio(
    mp3_path: Path, language: str = "fr", model: str = "whisper-1"
) -> dict:
    # Load the audio
    audio = AudioSegment.from_file(mp3_path)

    # Constants
    max_chunk_length_ms = 600 * 1000
    chunks = [audio[i:i + max_chunk_length_ms] for i in range(0, len(audio), max_chunk_length_ms)]

    # OpenAI client
    client = openai.OpenAI()

    segment_list = []

    for idx, chunk in enumerate(chunks):
        start_time_ms = idx * max_chunk_length_ms
        start_time_sec = start_time_ms / 1000

        # Save chunk to temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3") as tmpfile:
            chunk.export(tmpfile.name, format="mp3")

            with open(tmpfile.name, "rb") as audio_file:
                result = client.audio.transcriptions.create(
                    file=audio_file,
                    model=model,
                    language=language,
                    response_format="verbose_json"
                )

        # Offset timestamps and add segments
        for segment in result.segments:
            out = json.loads(segment.model_dump_json())
            out["offset"] = start_time_sec
            segment_list.append(out)

    return segment_list
