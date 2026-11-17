"""Investigación y guion con Claude.

Dos llamadas:
1. Investigación: Claude elige un tema que el canal no haya tratado y lo documenta
   con búsqueda web, devolviendo notas y fuentes.
2. Guion: a partir de esas notas, Claude escribe el guion estructurado (JSON)
   con la narración por segmentos y términos de búsqueda de metraje.
"""
from __future__ import annotations

import json
from typing import Literal

import anthropic
from pydantic import BaseModel

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class Segment(BaseModel):
    chapter_title: str
    narration: str
    visual_queries: list[str]


class Source(BaseModel):
    title: str
    url: str


class Script(BaseModel):
    topic: str
    title: str
    description: str
    tags: list[str]
    thumbnail_text: str
    segments: list[Segment]
    sources: list[Source]


SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "thumbnail_text": {"type": "string"},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chapter_title": {"type": "string"},
                    "narration": {"type": "string"},
                    "visual_queries": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["chapter_title", "narration", "visual_queries"],
                "additionalProperties": False,
            },
        },
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
                "required": ["title", "url"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["topic", "title", "description", "tags", "thumbnail_text", "segments", "sources"],
    "additionalProperties": False,
}

RESEARCH_SYSTEM = """Eres el documentalista de «{channel}», un canal de divulgación en español sobre las \
profundidades del océano: zonas mesopelágica, batial, abisal y hadal, sus criaturas, fosas, fuentes \
hidrotermales, exploración submarina, naufragios profundos, geología del fondo marino y misterios sin resolver.

Tu trabajo es elegir el tema del próximo vídeo y documentarlo con rigor. Usa la búsqueda web para \
contrastar cada dato (profundidades, tamaños, fechas, nombres científicos, expediciones) en fuentes \
fiables: instituciones científicas, revistas, NOAA, MBARI, Schmidt Ocean Institute, museos, prensa \
científica. Si un dato es dudoso o está discutido, dilo en las notas."""

RESEARCH_PROMPT = """Formato del próximo vídeo: {format_desc}.

Temas ya publicados (no los repitas ni hagas variaciones evidentes):
{history}

Elige un tema concreto y con gancho (una criatura, un lugar, una expedición, un fenómeno o una pregunta), \
investígalo y entrega:
- Primera línea: «TEMA: <tema>»
- Notas de investigación con los datos verificados más sorprendentes, cada uno con su fuente.
- Lista final de fuentes (título + URL)."""

SCRIPT_SYSTEM = """Eres el guionista de «{channel}», canal de divulgación en español (castellano neutro) \
sobre las profundidades marinas. Escribes narraciones para voz en off: frases claras, ritmo de documental, \
asombro sin sensacionalismo, y solo datos respaldados por las notas de investigación. Si las notas marcan \
algo como incierto, la narración también lo presenta como incierto."""

SCRIPT_PROMPT = """Escribe el guion del vídeo a partir de estas notas de investigación.

<notas>
{notes}
</notas>

Formato: {format_desc}
- Narración total: unas {words} palabras, repartidas en {segments} segmentos aproximadamente.
- El primer segmento es el gancho: una pregunta o imagen potente en las dos primeras frases.
- {ending}
- Escribe los números como se pronuncian cuando haya riesgo de mala lectura (p. ej. «once mil metros»).
- chapter_title: título breve del segmento (3-6 palabras); se usa para los capítulos de YouTube.
- visual_queries: 2-4 búsquedas cortas EN INGLÉS para bancos de vídeo de stock (p. ej. "deep sea jellyfish", \
"underwater darkness", "submarine lights"). Piensa en metraje que realmente existe en bancos gratuitos; \
evita nombres de especies raras y usa descripciones visuales genéricas.
- title: máximo 90 caracteres, atractivo y honesto (sin promesas falsas){title_extra}.
- description: 2-3 párrafos que resuman el vídeo, sin hashtags ni enlaces (se añaden después).
- tags: 10-15 etiquetas en español.
- thumbnail_text: 2-4 palabras en mayúsculas para la miniatura.
- sources: las fuentes de las notas que respaldan el guion."""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(max_retries=4)


def _check(response) -> None:
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude rechazó la petición: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("La respuesta de Claude se cortó por max_tokens")


def _format_desc(fmt: Literal["long", "short"], cfg: dict) -> str:
    if fmt == "short":
        return f"YouTube Short vertical de unos {cfg['formats']['short']['target_seconds']} segundos"
    return f"vídeo documental horizontal de unos {cfg['formats']['long']['target_minutes']} minutos"


def research(cfg: dict, fmt: Literal["long", "short"], history: list[dict]) -> str:
    client = _client()
    past = "\n".join(f"- {h['topic']}" for h in history[-200:]) or "- (ninguno todavía)"
    messages: list = [
        {
            "role": "user",
            "content": RESEARCH_PROMPT.format(format_desc=_format_desc(fmt, cfg), history=past),
        }
    ]
    # Bucle para pause_turn: la búsqueda web puede pausar el turno en búsquedas largas.
    for _ in range(6):
        with client.beta.messages.stream(
            model=cfg["claude"]["model"],
            max_tokens=32000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=RESEARCH_SYSTEM.format(channel=cfg["channel"]["name"]),
            output_config={"effort": cfg["claude"]["research_effort"]},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 10}],
            messages=messages,
        ) as stream:
            response = stream.get_final_message()
        _check(response)
        if response.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": response.content})
    else:
        raise RuntimeError("La investigación no terminó tras varios pause_turn")

    notes = "\n".join(b.text for b in response.content if b.type == "text").strip()
    if not notes:
        raise RuntimeError("La investigación no devolvió texto")
    return notes


def write_script(cfg: dict, fmt: Literal["long", "short"], notes: str) -> Script:
    client = _client()
    if fmt == "short":
        secs = cfg["formats"]["short"]["target_seconds"]
        words, segments = int(secs * 2.5), 4
        ending = "Termina con una frase que invite a ver el canal o a comentar; nada de despedidas largas."
        title_extra = "; añade #shorts al final"
    else:
        mins = cfg["formats"]["long"]["target_minutes"]
        words, segments = int(mins * 150), max(6, mins + 2)
        ending = "Cierra con una reflexión breve y una invitación a suscribirse en una sola frase."
        title_extra = ""

    with client.beta.messages.stream(
        model=cfg["claude"]["model"],
        max_tokens=64000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        system=SCRIPT_SYSTEM.format(channel=cfg["channel"]["name"]),
        output_config={
            "effort": cfg["claude"]["script_effort"],
            "format": {"type": "json_schema", "schema": SCRIPT_SCHEMA},
        },
        messages=[
            {
                "role": "user",
                "content": SCRIPT_PROMPT.format(
                    notes=notes,
                    format_desc=_format_desc(fmt, cfg),
                    words=words,
                    segments=segments,
                    ending=ending,
                    title_extra=title_extra,
                ),
            }
        ],
    ) as stream:
        response = stream.get_final_message()
    _check(response)
    text = next(b.text for b in response.content if b.type == "text")
    script = Script.model_validate(json.loads(text))
    if not script.segments:
        raise RuntimeError("El guion no tiene segmentos")
    script.title = script.title.strip()[:100]
    return script
