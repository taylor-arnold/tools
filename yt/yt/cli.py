"""Command line interface for ptools."""

import json
from pathlib import Path

import click
import colorama
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI

from . import __version__
from .call_api import transcribe_long_audio
from .rfrance import get_radio_france

colorama.init()
client = OpenAI()


def format_duration(seconds):
    seconds = int(seconds)  # ensure it's an integer

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    else:
        return f"{minutes:02}:{secs:02}"


def create_output(html_path, mp3_path, segments) -> None:

    for i in range(1, len(segments)):
        segments[i]["time"] = format_duration(segments[i]["start"])

    env = Environment(loader=FileSystemLoader("/Users/admin/gh/tools/yt/data/"), autoescape=True)
    template = env.get_template("template.html")
    output = template.render(
        segments=segments,
        mp3=mp3_path
    )
    with open(html_path, "w") as f:
        f.write(output)


def ensure_transcript(mp3_path, transcript_file):
    json_out = Path(transcript_file)

    if not json_out.is_file():
        segment_list = transcribe_long_audio(mp3_path)
        with json_out.open("w", encoding="utf-8") as f:
            json.dump(segment_list, f, ensure_ascii=False, indent=4)


def get_segment_format(json_path):
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    segments = []
    current = {"start": data[0]["start"], "text": data[0]["text"]}

    for i in range(1, len(data)):
        prev = data[i - 1]
        curr = data[i]

        text_ends_cleanly = prev["text"].strip().endswith((".", "!", "?"))
        time_is_continuous = prev["end"] == curr["start"]

        if text_ends_cleanly and time_is_continuous:
            # Start a new segment
            segments.append(current)
            current = {"start": curr["start"], "text": curr["text"]}
        else:
            # Merge with current segment
            current["text"] += " " + curr["text"]

    # Append the last accumulated segment
    segments.append(current)

    return segments


@click.group()
@click.version_option(version=__version__)
@click.pass_context
def main(ctx: click.Context) -> None:
    pass


@main.command()
@click.argument("mp3_path", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def build(ctx: click.Context, mp3_path: Path) -> None:
    """Create transcript website."""
    json_path = mp3_path.with_suffix(".json")
    html_path = mp3_path.with_suffix(".html")

    ensure_transcript(mp3_path, json_path)
    segments = get_segment_format(json_path)
    create_output(html_path, mp3_path, segments)


@main.command()
@click.argument("url_path", type=str)
@click.pass_context
def rfrance(ctx: click.Context, url_path: str) -> None:
    get_radio_france(url_path)


if __name__ == "__main__":
    main()
