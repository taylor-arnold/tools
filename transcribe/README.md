# Transcribe

This is a simple CLI tool that I vibe-coded using Claude to access the
speech-to-text functionality on macOS from the command-line. It required
writing swift code, which I have absolutely no experience with.

To install the software, simply run the following:

```bash
swiftc transcribe.swift -o transcribe
sudo mv transcribe /usr/local/bin/
```

To see all of the options run:

```bash
transcribe --help
```

## Output Formants

**1. Detailed Word-Level Timing**

```bash
./transcribe --detailed audio.wav
```

Shows each word/phrase with:
- Start and end timestamps
- Duration
- Individual text segments

**2. SRT Subtitle Format**

```bash
./transcribe --srt presentation.wav > subtitles.srt
```

Perfect for creating subtitle files for videos!

**3. JSON Format**

```bash
./transcribe --json meeting.wav > transcript.json
```

Machine-readable format with all timing and confidence data.

**4. Confidence Scores**

```bash
./transcribe --detailed --confidence audio.wav
```

Shows how confident the AI is about each word (0-100%).

**5. Alternative Interpretations**
```bash
./transcribe --detailed --alternatives audio.wav
```
Shows other possible transcriptions for ambiguous audio.

## Example Outputs

**Detailed Format:**
```
=== DETAILED TRANSCRIPT ===
Full Text: Hello world, this is a test recording.

Word-Level Breakdown:
================================================================================

[1] 0.50s - 0.85s
Text: "Hello"
Confidence: 98.5%

[2] 0.85s - 1.20s
Text: "world,"
Confidence: 95.2%
Alternatives: world, word
```

**SRT Format:**
```
1
00:00:00,500 --> 00:00:00,850
Hello

2
00:00:00,850 --> 00:00:01,200
world,
```

**JSON Format:**
```json
{
  "transcript": "Hello world, this is a test recording.",
  "segments": [
    {
      "text": "Hello",
      "startTime": 0.5,
      "endTime": 0.85,
      "duration": 0.35,
      "confidence": 0.985,
      "alternatives": []
    }
  ],
  "totalDuration": 3.45,
  "averageConfidence": 0.942
}
```
