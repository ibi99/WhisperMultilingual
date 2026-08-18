#!/usr/bin/env python3

from pathlib import Path

import config

from language_detector import (
    create_model,
    analyse_audio,
    build_raw_markers,
    remove_short_language_segments,
    remove_redundant_markers,
    save_language_file,
    get_video_duration,
    seconds_to_time,
    SUPPORTED,
)

from faster_whisper.audio import decode_audio


SUPPORTED_VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".webm",
}


REPORT_FILE = (
    config.OUTPUT_DIR /
    "language_batch_test_report.txt"
)


def find_manual_language_file(video: Path) -> Path | None:
    """
    Sucht zuerst neben dem Video, danach in LANGUAGE_DIR.
    """

    # 1. Sprachdatei neben dem Video
    candidate = video.with_suffix(
        ".languages.txt"
    )

    if candidate.exists():
        return candidate

    # 2. Sprachdatei im konfigurierten Language-Verzeichnis
    candidate = (
        config.LANGUAGE_DIR /
        f"{video.stem}.languages.txt"
    )

    if candidate.exists():
        return candidate

    return None


def read_language_file(filename: Path):
    """
    Liest eine vorhandene manuelle .languages.txt.
    """

    LANGUAGE_MAP = {
        "de": "de",
        "deutsch": "de",
        "german": "de",

        "en": "en",
        "englisch": "en",
        "english": "en",

        "ar": "ar",
        "arabic": "ar",

        "it": "it",
        "italian": "it",
        "italienisch": "it",
    }

    markers = []

    with open(
        filename,
        "r",
        encoding="utf-8",
    ) as f:

        for line in f:

            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            parts = line.split()

            if len(parts) < 2:
                continue

            time_str = parts[0]
            language = parts[1].lower()

            if ":" in time_str:

                parts_time = time_str.split(":")

                if len(parts_time) == 2:

                    minutes, seconds = map(
                        int,
                        parts_time,
                    )

                    start = (
                        minutes * 60
                        + seconds
                    )

                elif len(parts_time) == 3:

                    hours, minutes, seconds = map(
                        int,
                        parts_time,
                    )

                    start = (
                        hours * 3600
                        + minutes * 60
                        + seconds
                    )

                else:
                    continue

            else:
                continue

            language = LANGUAGE_MAP.get(
                language
            )

            if language is None:
                continue

            markers.append(
                (
                    start,
                    language,
                )
            )

    return markers


def format_marker(
    marker,
):
    start, language = marker

    return (
        f"{seconds_to_time(start):>8} "
        f"{language.upper()}"
    )


def compare_markers(
    manual,
    auto,
):
    """
    Vergleicht die Marker anhand ihrer Reihenfolge
    und Sprache.

    Auto-Marker werden jeweils dem nächsten noch nicht
    verwendeten manuellen Marker gleicher Sprache
    zugeordnet.
    """

    used_manual = set()
    matches = []

    for auto_index, (
        auto_start,
        auto_language,
    ) in enumerate(auto):

        best_index = None
        best_distance = None

        for manual_index, (
            manual_start,
            manual_language,
        ) in enumerate(manual):

            if manual_index in used_manual:
                continue

            if manual_language != auto_language:
                continue

            distance = abs(
                auto_start
                - manual_start
            )

            if (
                best_distance is None
                or distance < best_distance
            ):

                best_distance = distance
                best_index = manual_index

        if best_index is not None:

            used_manual.add(
                best_index
            )

            manual_start, manual_language = (
                manual[best_index]
            )

            matches.append(
                {
                    "manual": (
                        manual_start,
                        manual_language,
                    ),
                    "auto": (
                        auto_start,
                        auto_language,
                    ),
                    "difference": (
                        auto_start
                        - manual_start
                    ),
                }
            )

    unmatched_manual = [
        marker
        for index, marker in enumerate(manual)
        if index not in used_manual
    ]

    matched_auto = {
        (
            match["auto"][0],
            match["auto"][1],
        )
        for match in matches
    }

    unmatched_auto = [
        marker
        for marker in auto
        if marker not in matched_auto
    ]

    return (
        matches,
        unmatched_manual,
        unmatched_auto,
    )


def detect_for_video(
    model,
    video: Path,
):
    """
    Führt die automatische Spracherkennung für
    genau ein Video aus.
    """

    duration = get_video_duration(
        video
    )

    print()
    print(
        f"Video: {video.name}"
    )

    print(
        f"Länge: "
        f"{seconds_to_time(duration)}"
    )

    print(
        "Lade Audio..."
    )

    audio = decode_audio(
        str(video),
        sampling_rate=16000,
    )

    print(
        "Analyse..."
    )

    observations = analyse_audio(
        model,
        audio,
        duration,
    )

    raw_markers = build_raw_markers(
        observations
    )

    filtered_markers = (
        remove_short_language_segments(
            raw_markers,
            config.MIN_LANGUAGE_DURATION,
        )
    )

    filtered_markers = (
        remove_redundant_markers(
            filtered_markers
        )
    )

    filtered_markers.sort(
        key=lambda item: item[0]
    )

    return filtered_markers


def find_test_videos():
    """
    Findet alle Videos im Videoverzeichnis,
    für die eine manuelle Language-Datei existiert.
    """

    videos = []

    for video in sorted(
        config.VIDEO_DIR.iterdir(),
        key=lambda p: p.name.lower(),
    ):

        if not video.is_file():
            continue

        if (
            video.suffix.lower()
            not in SUPPORTED_VIDEO_EXTENSIONS
        ):
            continue

        manual = find_manual_language_file(
            video
        )

        if manual is not None:

            videos.append(
                (
                    video,
                    manual,
                )
            )

    return videos


def main():

    config.OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    videos = find_test_videos()

    if not videos:

        print(
            "Keine Videos mit manueller "
            ".languages.txt gefunden."
        )

        return

    print()
    print("=" * 60)
    print("LANGUAGE BATCH TEST")
    print("=" * 60)
    print()

    print(
        f"{len(videos)} Videos gefunden."
    )

    print()

    print(
        "Lade Faster-Whisper large-v3 einmal..."
    )

    model = create_model()

    report_lines = []

    report_lines.append(
        "WHISPERMULTILINGUAL – LANGUAGE BATCH TEST"
    )

    report_lines.append(
        "=" * 60
    )

    report_lines.append("")

    successful = 0
    failed = 0

    for index, (
        video,
        manual_file,
    ) in enumerate(
        videos,
        start=1,
    ):

        print()
        print("#" * 60)

        print(
            f"VIDEO {index}/{len(videos)}"
        )

        print(
            video.name
        )

        print("#" * 60)

        report_lines.append("")
        report_lines.append(
            "#" * 60
        )
        report_lines.append(
            f"VIDEO {index}/{len(videos)}: "
            f"{video.name}"
        )
        report_lines.append(
            "#" * 60
        )

        try:

            manual = read_language_file(
                manual_file
            )

            auto = detect_for_video(
                model,
                video,
            )

            auto_file = (
                config.OUTPUT_DIR /
                f"{video.stem}.languages.auto.txt"
            )

            save_language_file(
                auto_file,
                auto,
            )

            (
                matches,
                unmatched_manual,
                unmatched_auto,
            ) = compare_markers(
                manual,
                auto,
            )

            successful += 1

            # --------------------------------------------------
            # Report
            # --------------------------------------------------

            report_lines.append("")
            report_lines.append(
                f"Manuell: {manual_file}"
            )

            report_lines.append(
                f"Auto   : {auto_file}"
            )

            report_lines.append("")
            report_lines.append(
                "VERGLEICH"
            )

            report_lines.append(
                "-" * 60
            )

            for match in matches:

                manual_start, language = (
                    match["manual"]
                )

                auto_start, _ = (
                    match["auto"]
                )

                difference = (
                    match["difference"]
                )

                sign = (
                    "+"
                    if difference > 0
                    else ""
                )

                report_lines.append(
                    f"{seconds_to_time(manual_start):>8} "
                    f"{language.upper():<3}  "
                    f"→ "
                    f"{seconds_to_time(auto_start):>8} "
                    f"{sign}{difference:>4}s"
                )

            if unmatched_manual:

                report_lines.append("")
                report_lines.append(
                    "FEHLENDE AUTO-MARKER:"
                )

                for marker in (
                    unmatched_manual
                ):

                    report_lines.append(
                        "  "
                        + format_marker(marker)
                    )

            if unmatched_auto:

                report_lines.append("")
                report_lines.append(
                    "ZUSÄTZLICHE AUTO-MARKER:"
                )

                for marker in (
                    unmatched_auto
                ):

                    report_lines.append(
                        "  "
                        + format_marker(marker)
                    )

            print()
            print(
                "Manuelle Marker:",
                len(manual)
            )

            print(
                "Auto-Marker:",
                len(auto)
            )

            print(
                "Auto-Datei:",
                auto_file
            )

            if unmatched_manual:

                print(
                    "FEHLENDE AUTO-MARKER:",
                    len(unmatched_manual)
                )

            if unmatched_auto:

                print(
                    "ZUSÄTZLICHE AUTO-MARKER:",
                    len(unmatched_auto)
                )

            if (
                not unmatched_manual
                and not unmatched_auto
            ):

                print(
                    "✓ Gleiche Anzahl / "
                    "keine zusätzlichen Marker"
                )

        except Exception as exc:

            failed += 1

            print()
            print(
                f"FEHLER: "
                f"{type(exc).__name__}: {exc}"
            )

            report_lines.append("")
            report_lines.append(
                f"FEHLER: "
                f"{type(exc).__name__}: {exc}"
            )

    # ======================================================
    # Report speichern
    # ======================================================

    report_lines.append("")
    report_lines.append(
        "=" * 60
    )

    report_lines.append(
        f"Erfolgreich: {successful}"
    )

    report_lines.append(
        f"Fehler: {failed}"
    )

    with open(
        REPORT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            "\n".join(report_lines)
        )

    print()
    print("=" * 60)
    print("TEST ABGESCHLOSSEN")
    print("=" * 60)

    print()
    print(
        f"Erfolgreich: {successful}"
    )

    print(
        f"Fehler: {failed}"
    )

    print()
    print(
        f"Report: {REPORT_FILE}"
    )


if __name__ == "__main__":
    main()