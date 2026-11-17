"""Subida a YouTube con la Data API v3 (OAuth con refresh token)."""
from __future__ import annotations

import os
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def _service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(
    video: Path,
    title: str,
    description: str,
    tags: list[str],
    cfg: dict,
    thumbnail: Path | None = None,
    playlist_id: str = "",
) -> str:
    yt = _service()
    ycfg = cfg["youtube"]
    # YouTube limita las etiquetas a 500 caracteres en total.
    kept, total = [], 0
    for tag in dict.fromkeys(t.strip() for t in tags if t.strip()):
        if total + len(tag) + 2 > 480:
            break
        kept.append(tag)
        total += len(tag) + 2

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": kept,
            "categoryId": ycfg["category_id"],
            "defaultLanguage": ycfg["default_language"],
            "defaultAudioLanguage": ycfg["default_language"],
        },
        "status": {
            "privacyStatus": ycfg["privacy_status"],
            "selfDeclaredMadeForKids": ycfg["made_for_kids"],
            "containsSyntheticMedia": ycfg["contains_synthetic_media"],
        },
    }
    media = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=16 * 1024 * 1024, resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response, retries = None, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"  subida: {int(status.progress() * 100)}%")
        except HttpError as err:
            if err.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                time.sleep(2 ** retries)
                continue
            raise
    video_id = response["id"]

    if thumbnail:
        try:
            yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail))).execute()
        except HttpError as err:
            # Las miniaturas personalizadas requieren un canal verificado por teléfono.
            print(f"  aviso: no se pudo poner la miniatura ({err.resp.status})")

    if playlist_id:
        yt.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
        ).execute()
    return video_id
