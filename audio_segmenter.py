from pathlib import Path
import subprocess

import config


def extract_audio_segment(
    video_file: Path,
    output_file: Path,
    start: int,
    end: int | None,
) -> None:

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        str(config.FFMPEG_EXE),
        "-y",
        "-ss", str(start),
    ]

    if end is not None:
        command.extend(["-to", str(end)])

    command.extend([
        "-i", str(video_file),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(output_file),
    ])

    subprocess.run(command, check=True)
