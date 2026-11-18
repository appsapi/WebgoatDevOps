"""Orquestación: investigación → guion → voz → montaje → miniatura → subida."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT
from .llm import Script, research, write_script
from .state import append_history, load_history
from .thumbnail import make_thumbnail
from .video import RenderResult, render

SAMPLE_SCRIPT = ROOT / "samples" / "sample_script.json"


def _mmss(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def build_description(script: Script, result: RenderResult, credits: dict[str, str], fmt: str, cfg: dict) -> str:
    parts = [script.description.strip()]

    chapters = result.chapters
    gaps_ok = all(b[0] - a[0] >= 10 for a, b in zip(chapters, chapters[1:])) and result.duration - chapters[-1][0] >= 10
    if fmt == "long" and len(chapters) >= 3 and gaps_ok:
        parts.append("📍 Capítulos\n" + "\n".join(f"{_mmss(t)} {title}" for t, title in chapters))

    if script.sources:
        parts.append("📚 Fuentes\n" + "\n".join(f"• {s.title}: {s.url}" for s in script.sources))
    if credits:
        parts.append("🎥 Vídeos de stock: Pexels — " + ", ".join(credits))

    parts.append(cfg["channel"]["description_footer"].strip())
    hashtags = "#océano #marprofundo #ciencia"
    parts.append(hashtags + (" #shorts" if fmt == "short" else ""))
    return "\n\n".join(parts)


def run_pipeline(cfg: dict, fmt: str, *, mock: bool = False, upload: bool = True,
                 script_path: Path | None = None, out_root: Path | None = None) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    outdir = (out_root or ROOT / "output") / f"{stamp}_{fmt}"
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"▶ Carpeta de trabajo: {outdir}")

    if script_path or mock:
        script = Script.model_validate(json.loads(Path(script_path or SAMPLE_SCRIPT).read_text(encoding="utf-8")))
        print(f"▶ Guion cargado: {script.title}")
    else:
        print("▶ Investigando tema con Claude + búsqueda web…")
        notes = research(cfg, fmt, load_history())
        (outdir / "notes.md").write_text(notes, encoding="utf-8")
        print("▶ Escribiendo guion…")
        script = write_script(cfg, fmt, notes)
    (outdir / "script.json").write_text(script.model_dump_json(indent=2), encoding="utf-8")
    print(f"  tema: {script.topic}\n  título: {script.title}\n  segmentos: {len(script.segments)}")

    print("▶ Generando voz, metraje y montaje…")
    result = render(script, fmt, cfg, outdir / "work", mock=mock)
    credits_file = result.video.with_suffix(".credits.txt")
    credits = dict(
        line.split(": ", 1) for line in credits_file.read_text(encoding="utf-8").splitlines() if ": " in line
    )
    final = outdir / f"{fmt}.mp4"
    result.video.replace(final)
    result.video = final
    print(f"  vídeo: {final} ({result.duration:.1f} s)")

    thumb = None
    if fmt == "long":
        thumb = make_thumbnail(result.first_clip, script.thumbnail_text, cfg["channel"]["name"], outdir / "thumbnail.jpg")
        print(f"  miniatura: {thumb}")

    description = build_description(script, result, credits, fmt, cfg)
    (outdir / "description.txt").write_text(description, encoding="utf-8")
    tags = [*script.tags, *cfg["youtube"]["base_tags"]]

    video_id = ""
    if upload and not mock:
        from .youtube import upload as yt_upload

        print("▶ Subiendo a YouTube…")
        playlist = cfg["youtube"].get(f"playlist_id_{fmt}", "")
        video_id = yt_upload(final, script.title, description, tags, cfg, thumb, playlist)
        print(f"  publicado: https://youtu.be/{video_id}")
        append_history({"format": fmt, "topic": script.topic, "title": script.title, "video_id": video_id})
    else:
        print("▶ Subida omitida (modo prueba o --no-upload)")

    return {"outdir": str(outdir), "video": str(final), "video_id": video_id, "title": script.title}
