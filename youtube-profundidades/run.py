#!/usr/bin/env python3
"""Genera (y opcionalmente publica) un vídeo del canal.

Ejemplos:
    python run.py --format long             # investigación + guion + vídeo + subida
    python run.py --format short --no-upload
    python run.py --mock                    # prueba local sin claves ni red
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from abisal.config import load_config
from abisal.pipeline import run_pipeline


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--format", choices=["long", "short"], default="long")
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--script", type=Path, default=None, help="reutilizar un script.json existente")
    ap.add_argument("--no-upload", action="store_true", help="generar el vídeo sin subirlo")
    ap.add_argument("--mock", action="store_true", help="sin Claude, voz, Pexels ni subida (prueba del montaje)")
    ap.add_argument("--out", type=Path, default=None, help="carpeta de salida (por defecto ./output)")
    args = ap.parse_args()

    result = run_pipeline(
        load_config(args.config), args.format,
        mock=args.mock, upload=not args.no_upload, script_path=args.script, out_root=args.out,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
