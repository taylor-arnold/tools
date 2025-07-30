import json
import math
import subprocess

from colorama import Fore, Style, init


init(autoreset=True)


def format_time(seconds):
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes:02d}:{secs:04.1f}"


class AudioTranscriber:
    def __init__(self):
        pass

    def transcribe(self, wave_file_path, json_file_path):
        subprocess.run([
            "transcribe",
            "--language",
            "fr-FR",
            "--detailed",
            "--confidence",
            "--alternatives",
            "--json",
            json_file_path,
            wave_file_path
        ], stdout=subprocess.DEVNULL)

    def message(self, json_file_path):
        with open(json_file_path, 'r') as file:
            data = json.load(file)

        # Column headers
        print(f"{Fore.CYAN}{Style.NORMAL}{'Word':<20}{Fore.YELLOW}{'Confidence':<12}{Fore.MAGENTA}{'  Start Time':<14}{'  End Time':<12}{Style.RESET_ALL}")
        print("-" * 60)

        # Iterate through segments and print each line
        for seg in data['segments']:
            word = f"{Fore.CYAN}{seg['text']:<20}"
            conf = f"{Fore.YELLOW}{seg['confidence']:.3f}{'':<5}"
            start = f"{Fore.MAGENTA}  {format_time(seg['startTime']):<12}"
            end = f"  {format_time(seg['endTime']):<12}"
            print(f"{word}{conf}  {start}{end}")

        # Print the full transcript at the end
        print("\n" + Fore.GREEN + "Full Transcript: " + Style.RESET_ALL + data['transcript'])
