from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import threading
from queue import Queue
import logging

class SlackBot:
    def __init__(
            self,
            message_queue: Queue,
            bot_token: str,
            app_token: str,
            debug: bool = False,
            ):
        """
        Inicializa el Slack bot.

        Args:
            message_queue (Queue): La cola compartida para enviar mensajes al agente consumidor.
            bot_token (str): El token del bot de Slack.
            app_token (str): El token de la aplicación de Slack.
        """

        self.app = App(token=bot_token)
        self.socket_token = app_token
        self.message_queue = message_queue
        self._register_events()
        self.debug = debug

    def _register_events(self):
        """
        Registra los manejadores de eventos para el bot.
        """
        @self.app.event("message")
        def handle_message_events(message, say):
            # Ignorar mensajes de bots o subtipos de mensajes (ej. uniones a canal)
            if 'bot_id' in message or 'subtype' in message:
                return

            if message.get('text') == "clear_screen":
                for _ in range(30):
                    say(text="-")
                return

            # --- INICIO DE LA MODIFICACION ---
            # Enviar un acuse de recibo inmediato para mostrar que el bot esta "escribiendo".
            # Esto mejora la experiencia del usuario al darle feedback instantaneo.
            if self.debug:
                try:
                    say(text="Procesando tu solicitud...", thread_ts=message.get("ts"))
                except Exception as e:
                    logging.error(f"No se pudo enviar el mensaje de acuse de recibo: {e}")
            # --- FIN DE LA MODIFICACION ---

            user_id = message.get('user')
            text = message.get('text')
            
            if user_id and text:
                # Empaquetar la informacion relevante y ponerla en la cola
                # para que el proceso principal la consuma.
                self.message_queue.put({
                    'user_id': user_id,
                    'text': text,
                    'say': say  # La funcion para responder en el canal correcto
                })

    def start(self):
        """
        Inicia el bot en un hilo separado para no bloquear la ejecucion principal.
        """
        handler = SocketModeHandler(self.app, self.socket_token)
        thread = threading.Thread(target=handler.start)
        thread.daemon = True
        thread.start()