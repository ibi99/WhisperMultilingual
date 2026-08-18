from subtitle import SubtitleFile


def merge_subtitles(
    subtitle_files: list[SubtitleFile],
) -> SubtitleFile:

    merged = []

    for subtitle_file in subtitle_files:
        merged.extend(subtitle_file.subtitles)

    merged.sort(key=lambda s: s.start_ms)

    for i, subtitle in enumerate(merged, start=1):
        subtitle.number = i

    return SubtitleFile(merged)