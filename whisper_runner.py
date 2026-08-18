from pathlib import Path
import subprocess

import config


def run_whisper(
    command: list[str],
    expected_output: Path | None = None,
) -> int:

    print("\nStarte Faster-Whisper...\n")

    result = subprocess.run(command)

    print(
        f"\nExit-Code: {result.returncode}\n"
    )

    # Normal beendet
    if result.returncode == 0:
        return result.returncode

    # Purfview kann nach erfolgreicher Ausgabe mit einem
    # Windows-Fast-Fail-Code beendet werden. Wenn die
    # erwartete SRT bereits existiert, können wir trotzdem
    # mit dem erzeugten Ergebnis weiterarbeiten.
    if (
        expected_output is not None
        and expected_output.exists()
    ):
        print(
            "Warnung: Faster-Whisper meldete einen "
            f"Fehlercode {result.returncode}, aber die "
            "erwartete SRT-Datei wurde erzeugt."
        )

        return result.returncode

    raise RuntimeError(
        "Faster-Whisper-XXL ist mit einem Fehler "
        f"beendet worden (Exit-Code {result.returncode})."
    )


def build_whisper_command(
    wav_file: Path,
    language: str,
) -> list[str]:

    return [
        str(config.WHISPER_EXE),
        str(wav_file),
        "--language", language,
        "--model", config.MODEL,
        "--beam_size", str(config.BEAM_SIZE),
        "--condition_on_previous_text",
        str(config.CONDITION_ON_PREVIOUS_TEXT),
        "--initial_prompt",
        config.INITIAL_PROMPT,
        "--output_dir",
        str(config.TEMP_DIR),
        "--output_format",
        "srt",
    ]
