from pathlib import Path

# ==========================================================
# WhisperMultilingual configuration
# ==========================================================

VERSION = "1.0.0"

# ----------------------------------------------------------
# Directories
# ----------------------------------------------------------
# Edit these paths for your system.

VIDEO_DIR = Path(r"C:\Path\to\Videos")
LANGUAGE_DIR = Path(r"C:\Path\to\LanguageFiles")

# TEMP_DIR and OUTPUT_DIR may stay relative to the project.
PROJECT_DIR = Path(__file__).resolve().parent
TEMP_DIR = PROJECT_DIR / "temp"
OUTPUT_DIR = PROJECT_DIR / "output"


# ----------------------------------------------------------
# External programs
# ----------------------------------------------------------
# Edit these paths for your system.

FFMPEG_EXE = Path(
    r"C:\Path\to\ffmpeg.exe"
)

WHISPER_EXE = Path(
    r"C:\Path\to\Purfview-Faster-Whisper-XXL\faster-whisper-xxl.exe"
)


# ----------------------------------------------------------
# Whisper transcription
# ----------------------------------------------------------

MODEL = "large-v3"
DEVICE = "cuda"
BEAM_SIZE = 5
CONDITION_ON_PREVIOUS_TEXT = True

# Optional vocabulary to help Whisper recognize
# domain-specific terms. Adapt this list to the
# subject of your videos.
INITIAL_PROMPT = (
    "spirituality, meditation, mindfulness, consciousness, "
    "psychology, inner peace, spiritual development, "
    "Achtsamkeit, Bewusstsein, Meditation, Spiritualität, "
    "Selbstentwicklung, innere Ruhe, Persönlichkeit"
)

VAD = True
WORD_TIMESTAMPS = False


# ----------------------------------------------------------
# Automatic language detection
# ----------------------------------------------------------
# Add or remove languages as required.
# The codes are Whisper language codes.
#
# German and English are the languages used for testing.
# Additional languages can be enabled as needed.

DETECTION_LANGUAGES = {
    "de": "Deutsch",
    "en": "English",

    # Optional: additional languages
    # "fr": "Français",
    # "es": "Español",
    # "it": "Italiano",
    # "ar": "Arabic",
}

# Minimum probability for a configured language to be
# considered a valid observation.
LANGUAGE_THRESHOLD = 0.60

# Short language insertions below this duration are ignored.
MIN_LANGUAGE_DURATION = 15

# Sliding-window settings used by the detector.
LANGUAGE_WINDOW = 5
LANGUAGE_STEP = 2
LANGUAGE_CONFIRM_WINDOWS = 3