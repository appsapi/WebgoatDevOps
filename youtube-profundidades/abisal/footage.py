"""Metraje de stock desde Pexels (licencia gratuita, uso comercial permitido)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import requests

from .media import run

PEXELS_SEARCH = "https://api.pexels.com/videos/search"
# Búsquedas genéricas de reserva cuando una búsqueda concreta no da resultados.
FALLBACK_QUERIES = ["deep sea", "underwater dark", "ocean depths", "jellyfish dark", "underwater particles"]


@dataclass
class Clip:
    path: Path
    author: str = ""
    page_url: str = ""


@dataclass
class FootageLibrary:
    workdir: Path
    width: int
    height: int
    mock: bool = False
    used_ids: set[int] = field(default_factory=set)
    credits: dict[str, str] = field(default_factory=dict)  # autor -> url
    _cache: dict[str, list[dict]] = field(default_factory=dict)
    _counter: int = 0

    @property
    def orientation(self) -> str:
        return "portrait" if self.height > self.width else "landscape"

    def _search(self, query: str) -> list[dict]:
        if query not in self._cache:
            resp = requests.get(
                PEXELS_SEARCH,
                headers={"Authorization": os.environ["PEXELS_API_KEY"]},
                params={"query": query, "orientation": self.orientation, "per_page": 30, "size": "medium"},
                timeout=60,
            )
            resp.raise_for_status()
            self._cache[query] = resp.json().get("videos", [])
        return self._cache[query]

    def _best_file(self, video: dict) -> dict | None:
        short_side = min(self.width, self.height)
        files = [
            f for f in video.get("video_files", [])
            if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")
        ]
        if not files:
            return None
        # La resolución más pequeña que cubra el lado corto del formato; si no hay, la mayor disponible.
        ok = [f for f in files if min(f["width"], f["height"]) >= short_side]
        return min(ok, key=lambda f: f["width"] * f["height"]) if ok else max(files, key=lambda f: f["width"] * f["height"])

    def _placeholder(self) -> Clip:
        """Fondo azul abisal con partículas («nieve marina») generado con ffmpeg.

        Se generan como mucho 3 variantes y se reutilizan.
        """
        self._counter += 1
        out = self.workdir / f"placeholder_{self._counter % 3}.mp4"
        if out.exists():
            return Clip(out)
        run([
            "-f", "lavfi", "-i", f"color=c=0x02101f:s={self.width}x{self.height}:d=12:r=30",
            "-vf", "noise=alls=18:allf=t,gblur=sigma=1.2,vignette",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out),
        ])
        return Clip(out)

    def get(self, queries: list[str]) -> Clip:
        if self.mock or not os.environ.get("PEXELS_API_KEY"):
            return self._placeholder()
        for query in [*queries, *FALLBACK_QUERIES]:
            for video in self._search(query):
                if video["id"] in self.used_ids:
                    continue
                f = self._best_file(video)
                if not f:
                    continue
                self.used_ids.add(video["id"])
                out = self.workdir / f"pexels_{video['id']}.mp4"
                if not out.exists():
                    with requests.get(f["link"], stream=True, timeout=300) as r:
                        r.raise_for_status()
                        with open(out, "wb") as fh:
                            for chunk in r.iter_content(1 << 20):
                                fh.write(chunk)
                user = video.get("user", {})
                if user.get("name"):
                    self.credits[user["name"]] = user.get("url", "")
                return Clip(out, user.get("name", ""), video.get("url", ""))
        return self._placeholder()
