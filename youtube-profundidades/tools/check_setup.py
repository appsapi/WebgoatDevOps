#!/usr/bin/env python3
"""Comprueba que todas las claves y servicios del canal funcionan, sin publicar nada.

    python tools/check_setup.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from abisal.config import load_config  # noqa: E402

cfg = load_config()
results: list[tuple[str, bool, str]] = []


def check(name: str):
    def deco(fn):
        try:
            results.append((name, True, fn()))
        except Exception as exc:  # noqa: BLE001
            results.append((name, False, f"{type(exc).__name__}: {exc}"))
            traceback.print_exc()
        return fn
    return deco


@check("Variables de entorno")
def _env():
    needed = ["ANTHROPIC_API_KEY", "PEXELS_API_KEY", "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [n for n in needed if not os.environ.get(n)]
    if missing:
        raise RuntimeError("faltan secretos: " + ", ".join(missing))
    return "todos los secretos están definidos"


@check("Claude API")
def _claude():
    import anthropic

    client = anthropic.Anthropic()
    model = client.models.retrieve(cfg["claude"]["model"])
    resp = client.messages.create(
        model=cfg["claude"]["model"], max_tokens=200, output_config={"effort": "low"},
        messages=[{"role": "user", "content": "Responde solo: ok"}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return f"{model.id} responde «{text[:20]}»"


@check("Pexels API")
def _pexels():
    import requests

    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": os.environ["PEXELS_API_KEY"]},
        params={"query": "deep sea", "per_page": 5}, timeout=30,
    )
    r.raise_for_status()
    return f"{r.json().get('total_results', 0)} vídeos para «deep sea»"


@check("Voz (TTS)")
def _tts():
    from abisal.tts import synthesize

    with tempfile.TemporaryDirectory() as d:
        dur, cues = synthesize("Bienvenidos a las profundidades del océano.", Path(d) / "t.mp3", cfg)
    return f"{cfg['voice']['provider']}: {dur:.1f} s de audio, {len(cues)} frases"


@check("YouTube API")
def _youtube():
    from abisal.youtube import _service

    yt = _service()
    items = yt.channels().list(part="snippet,status", mine=True).execute().get("items", [])
    if not items:
        raise RuntimeError("la cuenta autorizada no tiene canal de YouTube")
    ch = items[0]
    return f"canal «{ch['snippet']['title']}» ({ch['id']}), estado: {ch.get('status', {}).get('privacyStatus', '?')}"


print("\n=== Diagnóstico del canal ===")
for name, ok, detail in results:
    print(f"{'✅' if ok else '❌'} {name}: {detail}")
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a", encoding="utf-8") as fh:
        fh.write("## Diagnóstico del canal\n\n| | Servicio | Detalle |\n|---|---|---|\n")
        for name, ok, detail in results:
            fh.write(f"| {'✅' if ok else '❌'} | {name} | {detail.replace('|', '/')} |\n")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
