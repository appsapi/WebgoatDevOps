"""Subtítulos ASS con estilo fijo, listos para quemar en el vídeo con libass."""
from __future__ import annotations

from pathlib import Path

from .tts import Cue


def split_cue(cue: Cue, max_words: int) -> list[Cue]:
    words = cue.text.split()
    if len(words) <= max_words:
        return [cue]
    chunks = [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]
    total = sum(len(c) for c in chunks)
    out, t = [], cue.start
    for c in chunks:
        d = (cue.end - cue.start) * len(c) / total
        out.append(Cue(t, t + d, c))
        t += d
    return out


def _ts(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def write_ass(cues: list[Cue], path: Path, width: int, height: int, font: str) -> None:
    vertical = height > width
    font_size = int(height * (0.042 if vertical else 0.052))
    margin_v = int(height * (0.28 if vertical else 0.065))
    margin_h = int(width * 0.08)
    max_words = 5 if vertical else 12

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
        "Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,"
        f"1,{max(2, font_size // 14)},1,2,{margin_h},{margin_h},{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in cues:
        for c in split_cue(cue, max_words):
            lines.append(f"Dialogue: 0,{_ts(c.start)},{_ts(c.end)},Default,,0,0,0,,{_clean(c.text)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
