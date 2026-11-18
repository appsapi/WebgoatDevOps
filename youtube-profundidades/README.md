# Abisal: canal de YouTube automatizado sobre las profundidades marinas

Tubería que investiga, escribe, narra, monta y publica vídeos en español sobre el océano profundo,
sin intervención manual. GitHub Actions la ejecuta con una programación fija.

```
Claude + búsqueda web ──► notas verificadas con fuentes
        │
Claude (salida JSON) ──► guion: título, descripción, etiquetas, segmentos, búsquedas de metraje
        │
edge-tts / ElevenLabs ──► narración MP3 + tiempos de frase
        │
Pexels API ──► clips de stock (o fondo «nieve marina» generado si no hay resultados)
        │
ffmpeg ──► vídeo 1080p (o Short vertical 1080x1920) con subtítulos quemados, música y fundidos
        │
Pillow ──► miniatura 1280x720
        │
YouTube Data API v3 ──► subida, miniatura, lista de reproducción, historial de temas
```

## Calendario por defecto

| Formato | Días (UTC) | Duración |
|---|---|---|
| Vídeo largo (16:9) | lunes y jueves, 16:07 | ~8 min |
| Short (9:16) | martes, miércoles, viernes y sábado, 17:13 | ~50 s |

Se cambia en `.github/workflows/canal-profundidades.yml`; la duración y el estilo, en `config.yaml`.

## Puesta en marcha

### 1. Claves de servicios

| Secreto de GitHub | De dónde sale |
|---|---|
| `ANTHROPIC_API_KEY` | https://platform.claude.com → API keys |
| `PEXELS_API_KEY` | https://www.pexels.com/api/ (gratis) |
| `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | paso 2 |
| `ELEVENLABS_API_KEY` (opcional) | solo si `voice.provider: elevenlabs` |

Añádelos en el repositorio: **Settings → Secrets and variables → Actions → New repository secret**.
O, más rápido, cuando tengas las dos claves y el JSON del paso 2, un único comando en tu ordenador
pide las claves, abre la autorización de YouTube, guarda los cinco secretos y lanza la prueba:

```bash
gh auth login        # solo la primera vez
bash youtube-profundidades/tools/configurar_secretos.sh client_secret.json
```

### 2. Acceso a YouTube

1. Crea el canal en YouTube y verifícalo por teléfono (https://www.youtube.com/verify); sin eso no se
   pueden poner miniaturas personalizadas ni subir vídeos de más de 15 minutos.
2. En https://console.cloud.google.com crea un proyecto, activa **YouTube Data API v3** y configura la
   pantalla de consentimiento OAuth (tipo «Externo», añade tu cuenta como usuario de prueba).
   **Publica la app** (estado «En producción»): en modo prueba el refresh token caduca a los 7 días.
3. Crea credenciales **ID de cliente OAuth → Aplicación de escritorio** y descarga el JSON.
4. En tu ordenador:
   ```bash
   pip install google-auth-oauthlib
   python tools/get_refresh_token.py client_secret.json
   ```
   Copia los tres valores impresos a los secretos de GitHub.
5. **Solicita la auditoría de la API** (formulario «YouTube API Services – Audit and Quota Extension»).
   Hasta que Google la apruebe, los vídeos subidos desde proyectos de API no verificados quedan
   bloqueados como **privados**, aunque `privacy_status` diga `public`.

### 3. Primera ejecución

`python tools/check_setup.py` comprueba todas las claves (Claude, Pexels, voz y YouTube) sin publicar
nada. El workflow «Canal Abisal - prueba» lo ejecuta en GitHub y además genera un Short sin subirlo.

En GitHub: **Actions → Canal Abisal → Run workflow**, con `upload` desactivado para revisar el
resultado. El vídeo, la miniatura, el guion y las notas quedan como artefacto descargable 7 días.
Cuando te guste, deja que la programación siga sola.

## Uso local

```bash
cd youtube-profundidades
pip install -r requirements.txt        # requiere ffmpeg instalado
python run.py --mock                   # prueba del montaje sin claves ni red
python run.py --format short --no-upload
python run.py --format long            # ciclo completo, incluida la subida
python run.py --script output/<carpeta>/script.json --no-upload   # rehacer el vídeo con un guion ya generado
```

## Personalización

- **Nombre, textos y voz**: `config.yaml` (`channel`, `voice.edge_voice`; otras voces en español:
  `es-ES-ElviraNeural`, `es-MX-JorgeNeural`, `es-MX-DaliaNeural`).
- **Música**: deja MP3 libres de derechos en `assets/music/`.
- **Tono y temas**: los prompts están en `abisal/llm.py`.
- **Modelo**: `claude.model` en `config.yaml`; el esfuerzo de razonamiento, en `research_effort` y
  `script_effort`. Las peticiones activan el respaldo automático de modelo (`fallbacks: "default"`)
  por si el modelo principal rechaza una petición.

## Costes aproximados

- Claude: una investigación con búsqueda web y un guion por vídeo; del orden de céntimos a pocas
  decenas de céntimos por vídeo (más las búsquedas web, que se facturan aparte).
- Pexels, edge-tts, GitHub Actions (repositorio público o dentro de los minutos gratis): 0 €.
- Cuota de YouTube: 10.000 unidades/día por defecto; sobra para una subida diaria.

## Avisos importantes

- **Monetización**: YouTube no monetiza el «contenido no auténtico» (producido en masa o repetitivo).
  Un canal 100 % automatizado corre ese riesgo. Para el Programa de Partners conviene revisar los
  guiones, variar formatos y aportar valor propio. Si quieres un paso de revisión, pon
  `privacy_status: private` y publica a mano tras revisar.
- **Contenido sintético**: los vídeos se suben con `containsSyntheticMedia: true` y la descripción
  indica que la voz es sintética y el guion está hecho con ayuda de IA.
- **Exactitud**: el guion se basa en notas con fuentes, que se listan en la descripción, pero un
  modelo puede equivocarse. Revisa de vez en cuando los vídeos publicados.
- **edge-tts** usa el servicio de voz de Microsoft Edge sin API oficial; puede dejar de funcionar
  o tener restricciones de uso comercial. Para un canal monetizado, usa ElevenLabs u otro proveedor
  con licencia comercial (`voice.provider`).
- **Pexels** permite uso comercial sin atribución obligatoria; aun así la descripción da crédito a
  los autores.
