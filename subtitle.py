from dataclasses import dataclass
from pathlib import Path


@dataclass
class Subtitle:

    number: int
    start_ms: int
    end_ms: int
    text: str
    language: str = ""


@dataclass
class SubtitleFile:

    subtitles: list[Subtitle]


def srt_time_to_ms(time_str: str) -> int:

    hms, ms = time_str.split(",")

    h, m, s = map(int, hms.split(":"))

    return (
        ((h * 60 + m) * 60 + s) * 1000
        + int(ms)
)


def ms_to_srt_time(ms: int) -> str:

    h = ms // 3600000
    ms %= 3600000

    m = ms // 60000
    ms %= 60000

    s = ms // 1000
    ms %= 1000

    return (
        f"{h:02}:{m:02}:{s:02},{ms:03}"
)


def load_srt(filename: Path) -> SubtitleFile:

    subtitles: list[Subtitle] = []

    with open(filename, "r", encoding="utf-8") as f:

        blocks = f.read().strip().split("\n\n")

    for block in blocks:

        lines = block.splitlines()

        if len(lines) < 3:
            continue

        number = int(lines[0])

        start_str, end_str = lines[1].split(" --> ")

        text = "\n".join(lines[2:])

        subtitles.append(
            Subtitle(
                number=number,
                start_ms=srt_time_to_ms(start_str),
                end_ms=srt_time_to_ms(end_str),
                text=text,
            )
        )

    return SubtitleFile(subtitles)


def shift_subtitles(
    subtitle_file: SubtitleFile,
    offset_ms: int,
) -> None:

    for subtitle in subtitle_file.subtitles:
        subtitle.start_ms += offset_ms
        subtitle.end_ms += offset_ms


def save_srt(
    subtitle_file: SubtitleFile,
    filename: Path,
) -> None:

    filename.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(filename, "w", encoding="utf-8", newline="\n") as f:

        for subtitle in subtitle_file.subtitles:

            f.write(f"{subtitle.number}\n")

            f.write(
                f"{ms_to_srt_time(subtitle.start_ms)} --> "
                f"{ms_to_srt_time(subtitle.end_ms)}\n"
            )

            f.write(subtitle.text)

            f.write("\n\n")