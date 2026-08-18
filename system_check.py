import config


def check_system() -> None:
    """Check required external programs and create work directories."""

    print("Systemprüfung...\n")

    if not config.WHISPER_EXE.exists():
        raise FileNotFoundError(
            "Faster-Whisper-XXL nicht gefunden:\n"
            f"{config.WHISPER_EXE}\n\n"
            "Bitte WHISPER_EXE in config.py anpassen."
        )

    if not config.FFMPEG_EXE.exists():
        raise FileNotFoundError(
            "FFmpeg nicht gefunden:\n"
            f"{config.FFMPEG_EXE}\n\n"
            "Bitte FFMPEG_EXE in config.py anpassen."
        )

    if not config.VIDEO_DIR.exists():
        raise FileNotFoundError(
            "VIDEO_DIR nicht gefunden:\n"
            f"{config.VIDEO_DIR}\n\n"
            "Bitte VIDEO_DIR in config.py anpassen."
        )

    config.TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    config.OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("✓ Faster-Whisper gefunden")
    print("✓ FFmpeg gefunden")
    print("✓ Video-Verzeichnis gefunden")
    print("✓ Arbeitsverzeichnisse bereit")
