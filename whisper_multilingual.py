#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
from pathlib import Path

import config
from system_check import check_system
from pymediainfo import MediaInfo

from audio_segmenter import extract_audio_segment
from whisper_runner import (
    build_whisper_command,
    run_whisper,
)
from subtitle import (
    load_srt,
    shift_subtitles,
    save_srt,
)
from srt_merge import merge_subtitles
from language_detector import detect_language_file


SUPPORTED_LANGUAGES = config.DETECTION_LANGUAGES



SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
}


@dataclass
class Marker:
    start: int
    language: str


@dataclass
class Segment:
    index: int
    start: int
    end: int | None
    language: str


def time_to_seconds(time_str: str) -> int:
    """
    Wandelt MM:SS oder HH:MM:SS in Sekunden um.
    """

    parts = time_str.split(":")

    if len(parts) == 2:
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds

    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds

    raise ValueError(
        f"Ungültige Zeit: {time_str}"
    )


def seconds_to_time(seconds: int) -> str:

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if h:
        return f"{h:02}:{m:02}:{s:02}"

    return f"{m:02}:{s:02}"


def read_language_file(filename: Path):

    LANGUAGE_MAP = {
        code.lower(): code.lower()
        for code in config.DETECTION_LANGUAGES
    }

    aliases = {
        "deutsch": "de",
        "german": "de",
        "englisch": "en",
        "english": "en",
        "arabic": "ar",
        "arabisch": "ar",
        "italian": "it",
        "italienisch": "it",
        "francais": "fr",
        "français": "fr",
        "french": "fr",
        "spanish": "es",
        "español": "es",
        "turkish": "tr",
        "türkçe": "tr",
    }

    for alias, code in aliases.items():
        if code in config.DETECTION_LANGUAGES:
            LANGUAGE_MAP[alias] = code

    markers = []

    with open(
        filename,
        "r",
        encoding="utf-8",
    ) as f:

        for line_number, line in enumerate(
            f,
            start=1,
        ):

            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            parts = line.split()

            if len(parts) < 2:
                raise ValueError(
                    f"Zeile {line_number}: "
                    "Erwartet 'Zeit Sprache'"
                )

            time_str = parts[0]
            language = parts[1].lower()

            try:
                language = LANGUAGE_MAP[language]

            except KeyError:
                raise ValueError(
                    f"Zeile {line_number}: "
                    f"Unbekannte Sprache '{language}'"
                )

            start = time_to_seconds(time_str)

            markers.append(
                Marker(
                    start,
                    language,
                )
            )

    if not markers:
        raise ValueError(
            "Keine Marker gefunden."
        )

    if markers[0].start != 0:
        raise ValueError(
            "Erster Marker muss bei 00:00 beginnen."
        )

    previous = -1

    for marker in markers:

        if marker.start <= previous:
            raise ValueError(
                "Zeiten müssen streng aufsteigend sein."
            )

        previous = marker.start

    return markers


def build_segments(
    markers: list[Marker],
) -> list[Segment]:

    segments: list[Segment] = []

    for i, marker in enumerate(markers):

        end = (
            markers[i + 1].start
            if i < len(markers) - 1
            else None
        )

        segments.append(
            Segment(
                index=i + 1,
                start=marker.start,
                end=end,
                language=marker.language,
            )
        )

    return segments


def print_segments(
    video_file: Path,
    language_file: Path,
    segments: list[Segment],
) -> None:

    print()
    print("=" * 60)
    print("WhisperMultilingual")
    print("=" * 60)
    print()

    print(
        f"Video      : {video_file}"
    )

    print(
        f"Sprachdatei: {language_file}"
    )

    print(
        f"Segmente   : {len(segments)}"
    )

    print()

    for segment in segments:

        print("-" * 60)

        print(
            f"Segment {segment.index}"
        )

        print(
            "Start :",
            seconds_to_time(
                segment.start
            )
        )

        if segment.end is None:
            end = "Videoende"
        else:
            end = seconds_to_time(
                segment.end
            )

        print(
            "Ende  :",
            end
        )

        print(
            "Sprache:",
            segment.language,
            f"({SUPPORTED_LANGUAGES[segment.language]})",
        )

    print("-" * 60)


def get_video_duration(
    filename: Path,
) -> float:

    media_info = MediaInfo.parse(
        str(filename)
    )

    for track in media_info.tracks:

        if track.track_type == "Video":
            return float(
                track.duration
            ) / 1000

    raise RuntimeError(
        "Keine Videospur gefunden."
    )


def get_language_file(
    video: Path,
) -> Path:
    """
    Ermittelt die Sprachdatei für ein Video.

    Priorität:
    1. manuelle .languages.txt neben dem Video
    2. vorhandene .languages.auto.txt
    3. automatische Spracherkennung
    """

    manual_candidates = [
        video.with_suffix(".languages.txt"),
        config.LANGUAGE_DIR / f"{video.stem}.languages.txt",
    ]

    for manual_file in manual_candidates:

        if manual_file.exists():

            print()
            print(
                "Verwende vorhandene manuelle "
                "Sprachdatei:"
            )
            print(manual_file)

            return manual_file

    auto_file = (
        config.OUTPUT_DIR /
        f"{video.stem}.languages.auto.txt"
    )

    if auto_file.exists():

        print()
        print(
            "Keine manuelle Sprachdatei gefunden."
        )

        print(
            "Verwende vorhandene automatische "
            "Sprachdatei:"
        )

        print(
            auto_file
        )

        return auto_file

    print()
    print(
        "Keine Sprachdatei gefunden."
    )

    print(
        "Starte automatische Spracherkennung..."
    )

    return detect_language_file(
        video
    )


def process_video(
    video: Path,
    language_file: Path | None = None,
) -> Path:
    """
    Verarbeitet genau ein Video.
    Wird sowohl im Einzel- als auch im Batch-Modus verwendet.
    """

    print()
    print("#" * 60)
    print(
        f"VIDEO: {video.name}"
    )
    print("#" * 60)

    # ------------------------------------------------------
    # Sprachdatei
    # ------------------------------------------------------

    if language_file is None:

        language_file = get_language_file(
            video
        )

    else:

        if not language_file.is_absolute():
            language_file = (
                config.LANGUAGE_DIR /
                language_file
            )

        if not language_file.exists():
            raise FileNotFoundError(
                language_file
            )

    # ------------------------------------------------------
    # Sprachmarker
    # ------------------------------------------------------

    markers = read_language_file(
        language_file
    )

    segments = build_segments(
        markers
    )

    duration = int(
        get_video_duration(video)
    )

    segments[-1].end = duration

    print_segments(
        video,
        language_file,
        segments,
    )

    # ------------------------------------------------------
    # Transkription
    # ------------------------------------------------------

    subtitle_files = []

    for segment in segments:

        wav_file = (
            config.TEMP_DIR /
            f"{video.stem}_"
            f"{segment.index:03}_"
            f"{segment.language}.wav"
        )

        print()
        print("=" * 60)

        print(
            f"Segment "
            f"{segment.index}/"
            f"{len(segments)} "
            f"({segment.language})"
        )

        print("=" * 60)

        extract_audio_segment(
            video,
            wav_file,
            segment.start,
            segment.end,
        )

        command = build_whisper_command(
            wav_file,
            segment.language,
        )

        srt_file = (
            config.TEMP_DIR /
            f"{video.stem}_"
            f"{segment.index:03}_"
            f"{segment.language}.srt"
        )

        run_whisper(
            command,
            expected_output=srt_file,
        )

        subs = load_srt(
            srt_file
        )

        shift_subtitles(
            subs,
            segment.start * 1000,
        )

        subtitle_files.append(
            subs
        )

    # ------------------------------------------------------
    # Zusammenführen
    # ------------------------------------------------------

    merged = merge_subtitles(
        subtitle_files
    )

    base_name = video.stem

    output_srt = (
        config.OUTPUT_DIR /
        f"{base_name}.subtitles.srt"
    )

    save_srt(
        merged,
        output_srt,
    )

    print()
    print(
        f"Fertig: {video.name}"
    )

    print(
        output_srt
    )

    return output_srt


def find_batch_videos() -> list[Path]:
    """
    Findet alle unterstützten Videos in VIDEO_DIR.
    """

    if not config.VIDEO_DIR.exists():
        raise FileNotFoundError(
            config.VIDEO_DIR
        )

    videos = sorted(
        (
            path
            for path in config.VIDEO_DIR.iterdir()
            if (
                path.is_file()
                and path.suffix.lower()
                in SUPPORTED_VIDEO_EXTENSIONS
            )
        ),
        key=lambda path: path.name.lower(),
    )

    return videos


def run_batch(
    videos: list[Path],
) -> None:
    """
    Verarbeitet mehrere Videos nacheinander.
    Fehler bei einem Video stoppen den Batch nicht.
    """

    successful = []
    failed = []

    print()
    print("=" * 60)
    print("BATCH-VERARBEITUNG")
    print("=" * 60)
    print()

    print(
        f"Verzeichnis: {config.VIDEO_DIR}"
    )

    print(
        f"Videos: {len(videos)}"
    )

    print()

    for index, video in enumerate(
        videos,
        start=1,
    ):

        print()
        print("#" * 60)
        print(
            f"BATCH {index}/{len(videos)}"
        )
        print(
            video.name
        )
        print("#" * 60)

        try:

            output = process_video(
                video
            )

            successful.append(
                (
                    video,
                    output,
                )
            )

        except Exception as exc:

            failed.append(
                (
                    video,
                    exc,
                )
            )

            print()
            print(
                f"FEHLER bei {video.name}:"
            )

            print(
                f"{type(exc).__name__}: {exc}"
            )

            print()
            print(
                "Batch wird mit dem "
                "nächsten Video fortgesetzt."
            )

    # ------------------------------------------------------
    # Ergebnis
    # ------------------------------------------------------

    print()
    print("=" * 60)
    print("BATCH-ERGEBNIS")
    print("=" * 60)
    print()

    for video, output in successful:

        print(
            f"✓ {video.name}"
        )

        print(
            f"  → {output}"
        )

    for video, error in failed:

        print(
            f"✗ {video.name}"
        )

        print(
            f"  → {type(error).__name__}: {error}"
        )

    print()
    print(
        f"Videos gesamt : {len(videos)}"
    )

    print(
        f"Erfolgreich   : {len(successful)}"
    )

    print(
        f"Fehler        : {len(failed)}"
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "WhisperMultilingual – automatische "
            "Spracherkennung und SRT-Transkription"
        )
    )

    parser.add_argument(
        "--version",
        action="version",
        version=config.VERSION,
    )

    parser.add_argument(
        "video",
        nargs="?",
        help="Ein einzelnes Video",
    )

    parser.add_argument(
        "languages",
        nargs="?",
        default=None,
        help=(
            "Optionale manuelle Sprachdatei "
            "für ein einzelnes Video"
        ),
    )

    parser.add_argument(
        "--batch",
        action="store_true",
        help=(
            "Alle Videos aus VIDEO_DIR "
            "verarbeiten"
        ),
    )

    args = parser.parse_args()

    # ------------------------------------------------------
    # Systemprüfung einmalig
    # ------------------------------------------------------

    check_system()
    print()

    # ------------------------------------------------------
    # Batch-Modus
    # ------------------------------------------------------

    if args.batch:

        if args.video is not None:
            parser.error(
                "--batch darf nicht zusammen "
                "mit einem Video verwendet werden."
            )

        if args.languages is not None:
            parser.error(
                "--batch darf nicht zusammen "
                "mit einer Sprachdatei verwendet werden."
            )

        videos = find_batch_videos()

        if not videos:

            print()
            print(
                "Keine unterstützten Videos gefunden:"
            )

            print(
                config.VIDEO_DIR
            )

            return

        run_batch(
            videos
        )

        return

    # ------------------------------------------------------
    # Einzelvideo
    # ------------------------------------------------------

    if args.video is None:

        parser.error(
            "Bitte ein Video angeben "
            "oder --batch verwenden."
        )

    video = Path(
        args.video
    )

    if not video.is_absolute():
        video = (
            config.VIDEO_DIR /
            video
        )

    if not video.exists():
        raise FileNotFoundError(
            video
        )

    language_file = None

    if args.languages is not None:
        language_file = Path(
            args.languages
        )

    process_video(
        video,
        language_file,
    )


if __name__ == "__main__":
    main()