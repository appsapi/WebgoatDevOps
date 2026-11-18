#!/usr/bin/env bash
# Configura TODOS los secretos del canal en GitHub con un solo comando.
# Se ejecuta UNA vez en tu ordenador (macOS, Linux, o Windows con Git Bash/WSL).
#
# Necesitas:
#   - GitHub CLI con sesión iniciada:       gh auth login
#   - Python 3.10+                          (python3 --version)
#   - La clave de Anthropic                 https://platform.claude.com/settings/keys
#   - La clave de Pexels                    https://www.pexels.com/api/
#   - El JSON del cliente OAuth de Google   (ver README, sección «Acceso a YouTube»)
#
# Uso:
#   bash youtube-profundidades/tools/configurar_secretos.sh ruta/al/client_secret.json
set -euo pipefail

REPO="${REPO:-appsapi/WebgoatDevOps}"
HERE="$(cd "$(dirname "$0")" && pwd)"
CLIENT_JSON="${1:-}"

if [ -z "$CLIENT_JSON" ] || [ ! -f "$CLIENT_JSON" ]; then
  echo "Uso: bash $0 ruta/al/client_secret.json" >&2
  exit 1
fi
command -v gh >/dev/null || { echo "Instala GitHub CLI: https://cli.github.com" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Inicia sesión primero: gh auth login" >&2; exit 1; }
PY="$(command -v python3 || command -v python)"

echo "== 1/4  Clave de Anthropic =="
read -r -s -p "Pega ANTHROPIC_API_KEY (no se muestra): " ANTHROPIC_API_KEY; echo
echo "== 2/4  Clave de Pexels =="
read -r -s -p "Pega PEXELS_API_KEY (no se muestra): " PEXELS_API_KEY; echo

echo "== 3/4  Autorizar YouTube =="
echo "Se abrirá el navegador: entra con la cuenta Google PROPIETARIA del canal y acepta."
VENV="$(mktemp -d)/venv"
"$PY" -m venv "$VENV"
"$VENV/bin/pip" install -q google-auth-oauthlib 2>/dev/null || "$VENV/Scripts/pip" install -q google-auth-oauthlib
VPY="$VENV/bin/python"; [ -x "$VPY" ] || VPY="$VENV/Scripts/python"
OUT="$("$VPY" "$HERE/get_refresh_token.py" "$CLIENT_JSON")"
YOUTUBE_CLIENT_ID="$(printf '%s\n' "$OUT" | sed -n 's/^YOUTUBE_CLIENT_ID=//p')"
YOUTUBE_CLIENT_SECRET="$(printf '%s\n' "$OUT" | sed -n 's/^YOUTUBE_CLIENT_SECRET=//p')"
YOUTUBE_REFRESH_TOKEN="$(printf '%s\n' "$OUT" | sed -n 's/^YOUTUBE_REFRESH_TOKEN=//p')"
[ -n "$YOUTUBE_REFRESH_TOKEN" ] || { echo "No se obtuvo el refresh token" >&2; exit 1; }

echo "== 4/4  Guardar secretos en $REPO =="
for name in ANTHROPIC_API_KEY PEXELS_API_KEY YOUTUBE_CLIENT_ID YOUTUBE_CLIENT_SECRET YOUTUBE_REFRESH_TOKEN; do
  printf '%s' "${!name}" | gh secret set "$name" --repo "$REPO"
  echo "  ✓ $name"
done

echo
echo "Lanzando la prueba (genera un Short SIN publicarlo)…"
gh workflow run canal-profundidades-prueba.yml --repo "$REPO" --ref main || true
echo "Sigue el resultado en: https://github.com/$REPO/actions"
