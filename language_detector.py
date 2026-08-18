from pathlib import Path
import os

import config
from pymediainfo import MediaInfo


# ==========================================================
# Purfview / CUDA
# ==========================================================

def configure_purfview_cuda() -> None:
    """Configure DLL search paths for the Purfview runtime."""

    whisper_exe = Path(config.WHISPER_EXE)

    if not whisper_exe.exists():
        raise FileNotFoundError(
            "Faster-Whisper-XXL nicht gefunden:\n"
            f"{whisper_exe}\n\n"
            "Bitte WHISPER_EXE in config.py anpassen."
        )

    purfview_dir = whisper_exe.parent
    torch_lib = purfview_dir / "_xxl_data" / "torch" / "lib"
    torchvision_lib = purfview_dir / "_xxl_data" / "torchvision"

    if not torch_lib.exists():
        raise FileNotFoundError(
            "Purfview Torch/CUDA-Verzeichnis nicht gefunden:\n"
            f"{torch_lib}"
        )

    os.add_dll_directory(str(torch_lib))

    if torchvision_lib.exists():
        os.add_dll_directory(str(torchvision_lib))

    os.environ["PATH"] = (
        str(torch_lib)
        + os.pathsep
        + (
            str(torchvision_lib) + os.pathsep
            if torchvision_lib.exists()
            else ""
        )
        + os.environ["PATH"]
    )


# ==========================================================
# Detection settings
# ==========================================================

SUPPORTED = set(
    config.DETECTION_LANGUAGES.keys()
)

LANGUAGE_WINDOW = config.LANGUAGE_WINDOW
LANGUAGE_STEP = config.LANGUAGE_STEP
LANGUAGE_CONFIRM_WINDOWS = config.LANGUAGE_CONFIRM_WINDOWS


# ==========================================================
# Helper
# ==========================================================

def seconds_to_time(
    seconds: float,
) -> str:

    seconds = int(round(seconds))

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours:
        return (
            f"{hours:02}:"
            f"{minutes:02}:"
            f"{secs:02}"
        )

    return (
        f"{minutes}:"
        f"{secs:02}"
    )


def get_video_duration(
    filename: Path,
) -> float:

    media_info = MediaInfo.parse(
        str(filename)
    )

    for track in media_info.tracks:

        if track.track_type == "Video":

            return (
                float(track.duration)
                / 1000
            )

    raise RuntimeError(
        "Keine Videospur gefunden."
    )


# ==========================================================
# Whisper
# ==========================================================

def create_model():

    configure_purfview_cuda()

    from faster_whisper import WhisperModel

    print()
    print(
        "Lade Faster-Whisper large-v3..."
    )
    print()

    model = WhisperModel(
        config.MODEL,
        device=config.DEVICE,
        compute_type="float16",
    )

    print(
        "Modell geladen."
    )
    print()

    return model


def detect_language(
    model,
    audio,
):

    language, probability, all_probs = (
        model.detect_language(
            audio,
            language_detection_segments=1,
            language_detection_threshold=0.5,
        )
    )

    # ------------------------------------------------------
    # Nur konfigurierte Sprachen berücksichtigen.
    #
    # Beispiel:
    # Whisper erkennt UR mit 0.70,
    # EN hat aber 0.61.
    #
    # Wenn UR nicht konfiguriert ist, betrachten wir
    # stattdessen EN.
    # ------------------------------------------------------

    supported_probs = [
        (
            lang,
            prob,
        )
        for lang, prob in all_probs
        if lang in SUPPORTED
    ]

    if not supported_probs:

        return None, 0.0

    language, probability = max(
        supported_probs,
        key=lambda item: item[1],
    )

    if (
        probability
        < config.LANGUAGE_THRESHOLD
    ):

        return None, probability

    return (
        language,
        probability,
    )


# ==========================================================
# Sliding Window
# ==========================================================

def analyse_audio(
    model,
    audio,
    duration: float,
):
    """
    Analysiert das komplette Audio mit überlappenden
    Zeitfenstern.

    Das Audio wird bereits vollständig im RAM gehalten.
    Dadurch entfällt ein separater FFmpeg-Aufruf
    für jedes einzelne Analysefenster.
    """

    sample_rate = 16000

    window_samples = int(
        LANGUAGE_WINDOW
        * sample_rate
    )

    step_samples = int(
        LANGUAGE_STEP
        * sample_rate
    )

    total_samples = len(audio)

    observations = []

    start_sample = 0

    last_printed_second = -1

    while (
        start_sample < total_samples
    ):

        end_sample = min(
            start_sample
            + window_samples,
            total_samples,
        )

        window_audio = (
            audio[
                start_sample:end_sample
            ]
        )

        if len(window_audio) == 0:
            break

        start_seconds = (
            start_sample
            / sample_rate
        )

        end_seconds = (
            end_sample
            / sample_rate
        )

        language, probability = (
            detect_language(
                model,
                window_audio,
            )
        )

        observations.append(
            (
                start_seconds,
                end_seconds,
                language,
                probability,
            )
        )

        # --------------------------------------------------
        # Fortschritt nur alle 30 Sekunden anzeigen
        # --------------------------------------------------

        current_second = int(
            start_seconds
        )

        if (
            current_second // 30
            != last_printed_second // 30
        ):

            print(
                f"  Analyse: "
                f"{seconds_to_time(start_seconds)}"
            )

            last_printed_second = (
                current_second
            )

        if (
            end_sample
            >= total_samples
        ):
            break

        start_sample += step_samples

    return observations


# ==========================================================
# Sprachwechsel aus den Beobachtungen bestimmen
# ==========================================================

def build_raw_markers(
    observations,
):
    """
    Erstellt vorläufige Sprachmarker.

    Ein Sprachwechsel wird erst akzeptiert,
    wenn die neue Sprache über mehrere
    aufeinanderfolgende Fenster bestätigt wurde.
    """

    markers = []

    stable_language = None

    candidate_language = None
    candidate_start = None
    candidate_count = 0

    for (
        start,
        end,
        language,
        probability,
    ) in observations:

        # --------------------------------------------------
        # Keine relevante Sprache erkannt
        #
        # Ein solches Fenster unterbricht einen bestehenden
        # Sprachabschnitt NICHT.
        # --------------------------------------------------

        if language is None:

            continue

        # --------------------------------------------------
        # Erste Sprache
        # --------------------------------------------------

        if stable_language is None:

            if (
                candidate_language
                == language
            ):

                candidate_count += 1

            else:

                candidate_language = (
                    language
                )

                candidate_start = (
                    start
                )

                candidate_count = 1

            if (
                candidate_count
                >= LANGUAGE_CONFIRM_WINDOWS
            ):

                stable_language = (
                    candidate_language
                )

                markers.append(
                    (
                        0,
                        stable_language,
                    )
                )

                candidate_language = None
                candidate_start = None
                candidate_count = 0

            continue

        # --------------------------------------------------
        # Gleiche Sprache wie bisher
        # --------------------------------------------------

        if language == stable_language:

            candidate_language = None
            candidate_start = None
            candidate_count = 0

            continue

        # --------------------------------------------------
        # Neue mögliche Sprache
        # --------------------------------------------------

        if (
            candidate_language
            == language
        ):

            candidate_count += 1

        else:

            candidate_language = (
                language
            )

            candidate_start = start
            candidate_count = 1

        # --------------------------------------------------
        # Wechsel bestätigen
        # --------------------------------------------------

        if (
            candidate_count
            >= LANGUAGE_CONFIRM_WINDOWS
        ):

            stable_language = (
                candidate_language
            )

            markers.append(
                (
                    candidate_start,
                    stable_language,
                )
            )

            candidate_language = None
            candidate_start = None
            candidate_count = 0

    return markers


# ==========================================================
# Kurze Sprachabschnitte entfernen
# ==========================================================

def remove_short_language_segments(
    markers,
    min_duration,
):
    """
    Entfernt kurze Sprachabschnitte.

    Beispiel:

        17:44 EN
        22:07 DE
        22:15 EN

    Der deutsche Einschub dauert nur 8 Sekunden
    und wird deshalb entfernt.
    """

    if len(markers) < 3:
        return markers

    cleaned = list(markers)

    changed = True

    while changed:

        changed = False
        result = []

        i = 0

        while i < len(cleaned):

            # Letzten Marker behalten
            if (
                i
                == len(cleaned) - 1
            ):

                result.append(
                    cleaned[i]
                )

                i += 1
                continue

            current_start, current_language = (
                cleaned[i]
            )

            next_start, next_language = (
                cleaned[i + 1]
            )

            duration = (
                next_start
                - current_start
            )

            if (
                duration
                < min_duration
                and i > 0
            ):

                # Kurzen Abschnitt verwerfen.
                #
                # Der folgende Marker bleibt erhalten.
                i += 1

                changed = True

                continue

            result.append(
                cleaned[i]
            )

            i += 1

        cleaned = result

    return cleaned


# ==========================================================
# Redundante Marker entfernen
# ==========================================================

def remove_redundant_markers(
    markers,
):

    cleaned = []

    last_language = None

    for start, language in markers:

        if (
            language
            == last_language
        ):
            continue

        cleaned.append(
            (
                start,
                language,
            )
        )

        last_language = language

    return cleaned


# ==========================================================
# Language-Datei speichern
# ==========================================================

def save_language_file(
    filename: Path,
    markers,
):

    filename.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        filename,
        "w",
        encoding="utf-8",
    ) as f:

        for start, language in markers:

            f.write(
                f"{seconds_to_time(start)} "
                f"{language.upper()}\n"
            )


# ==========================================================
# Öffentliche Funktion für WhisperMultilingual
# ==========================================================

def detect_language_file(
    video: Path,
) -> Path:
    """
    Erkennt automatisch die Sprachwechsel eines Videos
    und erzeugt eine .languages.auto.txt-Datei.
    """

    video = Path(video)

    if not video.exists():

        raise FileNotFoundError(
            video
        )

    duration = get_video_duration(
        video
    )

    output_file = (
        config.OUTPUT_DIR
        / f"{video.stem}.languages.auto.txt"
    )

    print()
    print("=" * 60)
    print(
        "WHISPERMULTILINGUAL – "
        "AUTOMATISCHE SPRACHERKENNUNG"
    )
    print("=" * 60)
    print()

    print(
        f"Video: {video}"
    )

    print(
        f"Länge: "
        f"{seconds_to_time(duration)}"
    )

    print()

    print(
        "Aktivierte Sprachen:"
    )

    for code, name in (
        config.DETECTION_LANGUAGES.items()
    ):

        print(
            f"  {code}: {name}"
        )

    print()

    model = create_model()

    # ------------------------------------------------------
    # Audio EINMAL komplett laden
    # ------------------------------------------------------

    print(
        "Lade Audio einmal komplett..."
    )

    from faster_whisper.audio import decode_audio

    audio = decode_audio(
        str(video),
        sampling_rate=16000,
    )

    print(
        "Audio geladen."
    )

    print()

    # ------------------------------------------------------
    # Sliding Window
    # ------------------------------------------------------

    print("=" * 60)
    print("1. SPRACHERKENNUNG")
    print("=" * 60)
    print()

    observations = analyse_audio(
        model,
        audio,
        duration,
    )

    print()

    print(
        f"{len(observations)} "
        f"Analysefenster ausgewertet."
    )

    # ------------------------------------------------------
    # Rohmarker
    # ------------------------------------------------------

    raw_markers = build_raw_markers(
        observations
    )

    # ------------------------------------------------------
    # Kurze Abschnitte entfernen
    # ------------------------------------------------------

    filtered_markers = (
        remove_short_language_segments(
            raw_markers,
            config.MIN_LANGUAGE_DURATION,
        )
    )

    # ------------------------------------------------------
    # Redundante Marker entfernen
    # ------------------------------------------------------

    filtered_markers = (
        remove_redundant_markers(
            filtered_markers
        )
    )

    # ------------------------------------------------------
    # Sortieren
    # ------------------------------------------------------

    filtered_markers.sort(
        key=lambda item: item[0]
    )

    # ------------------------------------------------------
    # Speichern
    # ------------------------------------------------------

    save_language_file(
        output_file,
        filtered_markers,
    )

    # ------------------------------------------------------
    # Ausgabe
    # ------------------------------------------------------

    print()
    print("=" * 60)
    print(
        "AUTOMATISCHE LANGUAGE-DATEI"
    )
    print("=" * 60)
    print()

    for start, language in (
        filtered_markers
    ):

        print(
            f"{seconds_to_time(start)} "
            f"{language.upper()}"
        )

    print()

    print(
        f"Gespeichert: "
        f"{output_file}"
    )

    print()

    return output_file


# ==========================================================
# Standalone-Aufruf
# ==========================================================

if __name__ == "__main__":

    import sys

    if len(sys.argv) != 2:

        raise SystemExit(
            "Verwendung:\n"
            "python language_detector.py VIDEO"
        )

    video = Path(
        sys.argv[1]
    )

    if not video.is_absolute():

        video = (
            config.VIDEO_DIR
            / video
        )

    detect_language_file(
        video
    )