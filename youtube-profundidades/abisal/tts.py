"""Síntesis de voz: un MP3 por segmento más los tiempos de cada frase para subtítulos."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests

from .media import probe_duration


@dataclass
class Cue:
    start: float  # segundos, relativos al inicio del segmento
    end: float
    text: str


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p for p in parts if p]


def proportional_cues(text: str, duration: float) -> list[Cue]:
    """Reparte la duración entre frases de forma proporcional a su longitud."""
    sentences = _split_sentences(text) or [text]
    total = sum(len(s) for s in sentences) or 1
    cues, t = [], 0.0
    for s in sentences:
        d = duration * len(s) / total
        cues.append(Cue(t, t + d, s))
        t += d
    return cues


def _edge(text: str, out: Path, cfg: dict) -> list[Cue]:
    import edge_tts

    comm = edge_tts.Communicate(
        text, cfg["voice"]["edge_voice"], rate=cfg["voice"]["edge_rate"], boundary="SentenceBoundary"
    )
    cues: list[Cue] = []
    with open(out, "wb") as fh:
        for chunk in comm.stream_sync():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] in ("SentenceBoundary", "WordBoundary"):
                start = chunk["offset"] / 1e7
                cues.append(Cue(start, start + chunk["duration"] / 1e7, chunk["text"]))
    return cues


def _elevenlabs(text: str, out: Path, cfg: dict) -> list[Cue]:
    voice_id = cfg["voice"]["elevenlabs_voice_id"]
    if not voice_id:
        raise RuntimeError("voice.elevenlabs_voice_id no está configurado")
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "accept": "audio/mpeg"},
        json={"text": text, "model_id": cfg["voice"]["elevenlabs_model"]},
        timeout=300,
    )
    resp.raise_for_status()
    out.write_bytes(resp.content)
    return []


def _mock(text: str, out: Path, cfg: dict) -> list[Cue]:
    """Audio silencioso con la duración estimada (≈2,5 palabras/s). Solo para pruebas."""
    seconds = max(2.0, len(text.split()) / 2.5)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", f"{seconds:.2f}", "-c:a", "libmp3lame", "-q:a", "4", str(out)],
        check=True,
    )
    return []


def synthesize(text: str, out: Path, cfg: dict, mock: bool = False) -> tuple[float, list[Cue]]:
    provider = "mock" if mock else cfg["voice"]["provider"]
    fn = {"edge": _edge, "elevenlabs": _elevenlabs, "mock": _mock}[provider]
    cues = fn(text, out, cfg)
    duration = probe_duration(out)
    if not cues:
        cues = proportional_cues(text, duration)
    return duration, cues
