# WhisperMultilingual

WhisperMultilingual is a Windows command-line tool for transcribing videos that switch between multiple spoken languages.

Its main feature is **automatic language-change detection**. The detected language markers are written to a `.languages.auto.txt` file. These markers are then used to split the video into language-specific audio segments, which are transcribed separately with Faster-Whisper-XXL.

## Features

- Automatic detection of language changes
- Configurable detection languages
- Ignores short language insertions below a configurable duration
- Manual `.languages.txt` files can always be used instead
- Existing `.languages.auto.txt` files are reused
- Single-video mode
- Batch processing of all videos in a configured folder
- Separate SRT files are merged into one final subtitle file
- Tested with German/English multilingual Sohbats and Khutbas

## Requirements

WhisperMultilingual is currently designed for **Windows** and a CUDA-capable NVIDIA setup.

You need:

1. Python with the packages in `requirements.txt`
2. FFmpeg
3. Purfview Faster-Whisper-XXL
4. A compatible NVIDIA/CUDA environment for the Faster-Whisper Python language detector

The Purfview executable is **not included** in this repository. Download it separately from:

https://github.com/Purfview/whisper-standalone-win

WhisperMultilingual currently uses the Faster-Whisper-XXL executable for the actual transcription and the Python `faster-whisper` package for language detection.

## Installation

Clone or download the repository and install the Python dependencies:

```bat
python -m pip install -r requirements.txt
```

Install/download FFmpeg and Faster-Whisper-XXL separately.

## Configuration

All machine-specific paths are configured in **`config.py`**. You do not need to change the Python source code for normal setup.

At minimum, edit:

```python
VIDEO_DIR = Path(r"C:\Path\to\Videos")
LANGUAGE_DIR = Path(r"C:\Path\to\LanguageFiles")
FFMPEG_EXE = Path(r"C:\Path\to\ffmpeg.exe")
WHISPER_EXE = Path(
    r"C:\Path\to\Purfview-Faster-Whisper-XXL\faster-whisper-xxl.exe"
)
```

`TEMP_DIR` and `OUTPUT_DIR` default to folders inside the project directory, but they can also be changed in `config.py`.

### Language detection

The languages considered by the automatic detector are configured here:

```python
DETECTION_LANGUAGES = {
    "de": "Deutsch",
    "en": "English",
    "ar": "Arabic",
    "it": "Italiano",
}
```

Add or remove Whisper language codes as needed. The example configuration enables German, English, Arabic and Italian.

Two additional settings control detection:

```python
LANGUAGE_THRESHOLD = 0.60
MIN_LANGUAGE_DURATION = 15
```

`MIN_LANGUAGE_DURATION` is used to ignore short language insertions. For example, a short Arabic prayer passage can be removed manually from the generated language file when it should not be part of the transcription workflow.

## Usage

### Check the command line

```bat
python whisper_multilingual.py --help
```

### Process one video

```bat
python whisper_multilingual.py myvideo.mp4
```

The application looks for a manual language file first: next to the video, then in `LANGUAGE_DIR`. It then looks for an existing automatic language file and only runs automatic language detection when necessary.

### Use a specific language file

```bat
python whisper_multilingual.py myvideo.mp4 myvideo.languages.txt
```

### Batch processing

```bat
python whisper_multilingual.py --batch
```

All supported video files in `VIDEO_DIR` are processed sequentially.

A failure in one video does not stop the remaining batch.

## Language files

A language file contains one language marker per line:

```text
0:00 DE
6:47 EN
8:09 DE
11:46 EN
```

The first marker must be at `0:00`.

Supported language names may be written using the configured language code or common English/German names, for example:

```text
0:00 Deutsch
6:47 English
```

## Generated files

The application writes generated files to `OUTPUT_DIR`.

For example:

```text
myvideo.languages.auto.txt
myvideo.subtitles.srt
```

Temporary segment WAV/SRT files are stored in `TEMP_DIR`.

## Workflow

```text
Video
  |
  v
Automatic language detection
  |
  +--> .languages.auto.txt
  |
  v
Language segments
  |
  v
Faster-Whisper-XXL transcription
  |
  v
Merged SRT
```

If a manually checked `.languages.txt` exists, it takes precedence over automatic detection.

## Notes on automatic detection

The detector analyzes overlapping short audio windows and confirms a language change only after repeated observations. Short interruptions are filtered using `MIN_LANGUAGE_DURATION`.

The detector is intended to find **spoken-language regions**, not to decide whether a given region should be translated. For special cases such as a prayer in Arabic, the generated `.languages.auto.txt` can be edited manually before transcription.

## License

WhisperMultilingual is released under the MIT License. See `LICENSE`.

Third-party software is not bundled with this repository and remains subject to its own licenses. See `THIRD_PARTY.md`.
