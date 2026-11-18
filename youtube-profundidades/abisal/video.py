"""Montaje del vídeo final con ffmpeg."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

from .footage import FootageLibrary
from .llm import Script
from .media import probe_duration, run
from .subtitles import write_ass
from .tts import Cue, synthesize

FONT = "DejaVu Sans"


@dataclass
class RenderResult:
    video: Path
    duration: float
    chapters: list[tuple[float, str]]
    first_clip: Path


def _normalize_piece(src: Path, dst: Path, seconds: float, w: int, h: int, fps: int) -> None:
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        f"fps={fps},setsar=1,format=yuv420p"
    )
    run([
        "-stream_loop", "-1", "-i", str(src), "-t", f"{seconds:.3f}", "-an", "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(fps), str(dst),
    ])


def render(script: Script, fmt: str, cfg: dict, workdir: Path, mock: bool = False) -> RenderResult:
    fcfg = cfg["formats"][fmt]
    vcfg = cfg["video"]
    w, h, fps = fcfg["width"], fcfg["height"], vcfg["fps"]
    pause = vcfg["pause_between_segments"]
    workdir.mkdir(parents=True, exist_ok=True)
    library = FootageLibrary(workdir, w, h, mock=mock)

    pieces: list[Path] = []
    audio_parts: list[Path] = []
    all_cues: list[Cue] = []
    chapters: list[tuple[float, str]] = []
    first_clip: Path | None = None
    t = 0.0

    for i, seg in enumerate(script.segments):
        mp3 = workdir / f"seg{i:02d}.mp3"
        dur, cues = synthesize(seg.narration, mp3, cfg, mock=mock)
        length = dur + pause
        chapters.append((t, seg.chapter_title))
        all_cues.extend(Cue(t + c.start, t + c.end, c.text) for c in cues)

        padded = workdir / f"seg{i:02d}.wav"
        run(["-i", str(mp3), "-af", f"apad=whole_dur={length:.3f}", "-ar", "48000", "-ac", "2", str(padded)])
        audio_parts.append(padded)

        n = max(1, math.ceil(length / fcfg["seconds_per_clip"]))
        piece_len = length / n
        for j in range(n):
            # Rota las búsquedas para variar el metraje dentro del segmento.
            queries = seg.visual_queries[j % max(1, len(seg.visual_queries)):] + seg.visual_queries
            clip = library.get(queries)
            first_clip = first_clip or clip.path
            piece = workdir / f"piece_{i:02d}_{j:02d}.mp4"
            _normalize_piece(clip.path, piece, piece_len, w, h, fps)
            pieces.append(piece)
        t += length

    # Concatenar vídeo y audio.
    vlist = workdir / "pieces.txt"
    vlist.write_text("".join(f"file '{p.name}'\n" for p in pieces))
    silent = workdir / "silent.mp4"
    run(["-f", "concat", "-safe", "0", "-i", str(vlist), "-c", "copy", str(silent)])

    alist = workdir / "audio.txt"
    alist.write_text("".join(f"file '{p.name}'\n" for p in audio_parts))
    narration = workdir / "narration.wav"
    run(["-f", "concat", "-safe", "0", "-i", str(alist), "-c", "copy", str(narration)])

    total = probe_duration(narration)
    out = workdir / f"final_{fmt}.mp4"
    inputs = ["-i", str(silent), "-i", str(narration)]
    music = sorted((Path(__file__).resolve().parent.parent / "assets" / "music").glob("*.mp3"))

    vchain = "[0:v]"
    if vcfg["burn_subtitles"]:
        ass = workdir / "subs.ass"
        write_ass(all_cues, ass, w, h, FONT)
        vchain += f"ass='{ass.as_posix()}',"
    vchain += f"fade=t=in:st=0:d=0.6,fade=t=out:st={max(0, total - 1.2):.2f}:d=1.2[v]"

    if music:
        inputs += ["-stream_loop", "-1", "-i", str(random.choice(music))]
        achain = (
            f"[2:a]volume={vcfg['music_volume']},afade=t=out:st={max(0, total - 3):.2f}:d=3[m];"
            "[1:a][m]amix=inputs=2:duration=first:normalize=0[a]"
        )
    else:
        achain = "[1:a]anull[a]"

    run([
        *inputs, "-filter_complex", f"{vchain};{achain}", "-map", "[v]", "-map", "[a]",
        "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", str(vcfg["crf"]),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out),
    ])
    script_credits = library.credits
    out.with_suffix(".credits.txt").write_text(
        "\n".join(f"{name}: {url}" for name, url in script_credits.items()), encoding="utf-8"
    )
    return RenderResult(out, total, chapters, first_clip or pieces[0])
