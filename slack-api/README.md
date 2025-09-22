# Slack API (`slack-api`)

Cliente para construir bots de Slack en Socket Mode con `slack-bolt`. Incluye soporte para reacciones automáticas, cola de mensajes compartida y transcripción opcional de audio con OpenAI.

## Instalación

```bash
cd slack-api
poetry install
```

## Uso rápido

```python
from queue import Queue
from slack_api import SlackBot

message_queue = Queue()
bot = SlackBot(
    message_queue=message_queue,
    bot_token="xoxb-...",
    app_token="xapp-...",
    debug=True,
    openai_api_key=None,  # o tu key para transcribir audio
)
bot.start()

# Consumidor de la cola en tu app
while True:
    event = message_queue.get()
    text = event["text"]
    say = event["say"]
    # Procesa y responde
    say(f"Recibido: {text}")
```

## Eventos soportados

- Mensajes de texto (agrega reacción y encola el mensaje)
- Archivos de audio (m4a/mp3/mp4/ogg/wav): descarga, detección de formato, transcripción (si `openai_api_key`) y encolado
- Evento `file_shared` para archivos subidos fuera del mensaje

## API

- `SlackBot(message_queue, bot_token, app_token, debug=False, openai_api_key=None)`
  - `.start()`: inicia Socket Mode en un hilo
  - `.send_message(user_ids: set[str], message: str)`
  - `.send_maintenance_message(user_ids: set[str], message: str | None)`

## Notas

- Requiere `SLACK_BOT_TOKEN` y `SLACK_APP_TOKEN` (Socket Mode habilitado)
- Para producción, maneja los tokens vía tu gestor de secretos