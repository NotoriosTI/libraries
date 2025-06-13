import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import threading
from queue import Queue

class SlackBot:
    def __init__(self, message_queue: Queue, dotenv_path: str = None):
        """
        Inicializa el Slack bot.

        Args:
            message_queue (Queue): La cola compartida para enviar mensajes al agente consumidor.
            dotenv_path (str, optional): Ruta al archivo .env.
        """
        if not dotenv_path:
            dotenv_path = '/Users/bastianibanez/work/libraries/.env'
        load_dotenv(dotenv_path)

        self.app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
        self.socket_token = os.environ.get("SLACK_APP_TOKEN")
        self.message_queue = message_queue
        self._register_events()

    def _register_events(self):
        """
        Registra los manejadores de eventos para el bot.
        """
        @self.app.event("message")
        def handle_message_events(message, say):
            # Ignorar mensajes de bots o subtipos de mensajes (ej. uniones a canal)
            if 'bot_id' in message or 'subtype' in message:
                return

            user_id = message.get('user')
            text = message.get('text')
            
            if user_id and text:
                # Empaquetar la información relevante y ponerla en la cola
                self.message_queue.put({
                    'user_id': user_id,
                    'text': text,
                    'say': say  # La función para responder en el canal correcto
                })

    def start(self):
        """
        Inicia el bot en un hilo separado para no bloquear la ejecución principal.
        """
        handler = SocketModeHandler(self.app, self.socket_token)
        thread = threading.Thread(target=handler.start)
        thread.daemon = True
        thread.start()