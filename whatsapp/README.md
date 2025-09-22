# WhatsApp Library

Cliente sencillo para integrar bots y utilidades con la API de WhatsApp (meta) vía HTTP. Incluye clientes de mensajes y media, modelos de datos tipados y helpers listos para usar.

## Características

- Envío de mensajes de texto e imágenes
- Descarga/gestión de media
- Modelos Pydantic para requests/responses
- API de alto nivel: `whatsapp_client`, `whatsapp_messages`, `whatsapp_media`

## Instalación

```bash
cd whatsapp
poetry install
```

Como dependencia desde el monorepo:

```bash
pip install -e whatsapp/
```

## Configuración

Variables esperadas (define con tu sistema de secretos preferido):

```env
WHATSAPP_API_URL=https://graph.facebook.com/v19.0
WHATSAPP_PHONE_NUMBER_ID=1234567890
WHATSAPP_ACCESS_TOKEN=your_long_lived_token
```

## Uso

### Enviar texto

```python
from whatsapp import whatsapp_messages

whatsapp_messages.send_text(
    to="+56912345678",
    body="Hola!"
)
```

### Enviar imagen desde URL

```python
from whatsapp import whatsapp_media, whatsapp_messages

media_id = whatsapp_media.upload_from_url("https://example.com/picture.jpg")
whatsapp_messages.send_image(to="+56912345678", media_id=media_id, caption="Foto")
```

## API pública

- `whatsapp.WhatsAppClient` y `whatsapp_client`: Cliente HTTP base
- `whatsapp.WhatsAppMessages` y `whatsapp_messages`: Envío de mensajes
- `whatsapp.WhatsAppMedia` y `whatsapp_media`: Subida/descarga de media
- Modelos: `WhatsAppTextMessage`, `WhatsAppImageMessage`, `WhatsAppMediaResponse`, `WhatsAppMessageResponse`

```python
from whatsapp import (
  WhatsAppClient, whatsapp_client,
  WhatsAppMessages, whatsapp_messages,
  WhatsAppMedia, whatsapp_media,
)
```

## Tests

```bash
poetry run pytest
```

## Requisitos

- Python >= 3.12


