#!/usr/bin/env python3
"""Obtiene el refresh token de YouTube (se ejecuta UNA vez, en tu ordenador).

1. En Google Cloud Console crea un proyecto, activa «YouTube Data API v3» y crea
   credenciales OAuth de tipo «Aplicación de escritorio». Descarga el JSON.
2. python tools/get_refresh_token.py ruta/al/client_secret.json
3. Inicia sesión con la cuenta Google propietaria del canal y acepta los permisos.
4. Copia los tres valores que se imprimen a los secretos del repositorio en GitHub.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

if len(sys.argv) != 2:
    sys.exit(__doc__)

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
info = json.load(open(sys.argv[1]))
client = info.get("installed") or info.get("web")
print("\nYOUTUBE_CLIENT_ID=" + client["client_id"])
print("YOUTUBE_CLIENT_SECRET=" + client["client_secret"])
print("YOUTUBE_REFRESH_TOKEN=" + creds.refresh_token)
