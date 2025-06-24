from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import threading
from queue import Queue
import logging
import requests
from openai import OpenAI
from io import BytesIO

class SlackBot:
    def __init__(
            self,
            message_queue: Queue,
            bot_token: str,
            app_token: str,
            debug: bool = False,
            openai_api_key: str = None,
            ):
        """
        Inicializa el Slack bot.

        Args:
            message_queue (Queue): La cola compartida para enviar mensajes al agente consumidor.
            bot_token (str): El token del bot de Slack.
            app_token (str): El token de la aplicación de Slack.
            debug (bool): Habilitar modo debug para mensajes adicionales.
            openai_api_key (str): API key de OpenAI para transcripción de audio (opcional).
        """

        self.app = App(token=bot_token)
        self.socket_token = app_token
        self.bot_token = bot_token
        self.message_queue = message_queue
        self.debug = debug
        
        # Inicializar cliente OpenAI si se proporciona la API key
        self.openai_client = None
        if openai_api_key:
            self.openai_client = OpenAI(api_key=openai_api_key)
        
        self._register_events()

    def _download_file(self, url):
        """
        Descarga un archivo desde Slack usando el token del bot.
        
        Args:
            url (str): URL del archivo a descargar.
            
        Returns:
            bytes: Contenido del archivo descargado.
        """
        headers = {
            "Authorization": f"Bearer {self.bot_token}"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.content

    def _detect_audio_format(self, content, filetype, url):
        """
        Detecta el formato real del audio desde el contenido del archivo.
        
        Args:
            content (bytes): Contenido del archivo.
            filetype (str): Tipo de archivo reportado por Slack.
            url (str): URL del archivo.
            
        Returns:
            str: Formato de audio detectado.
        """
        if content.startswith(b'\x00\x00\x00\x20ftypM4A'):
            return 'm4a'
        elif content.startswith(b'\x00\x00\x00\x20ftypisom') or content.startswith(b'\x00\x00\x00\x18ftypmp42'):
            return 'mp4'
        elif content.startswith(b'ID3') or content.startswith(b'\xff\xfb'):
            return 'mp3'
        elif content.startswith(b'OggS'):
            return 'ogg'
        elif content.startswith(b'RIFF') and b'WAVE' in content[:12]:
            return 'wav'
        else:
            return filetype  # fallback to what Slack reported

    def _process_audio_file(self, file, user_id, say):
        """
        Procesa un archivo de audio, lo transcribe y agrega el texto a la cola.
        
        Args:
            file (dict): Información del archivo de Slack.
            user_id (str): ID del usuario que envió el archivo.
            say (function): Función para responder en Slack.
        """
        if not self.openai_client:
            logging.warning("No se puede procesar audio: OpenAI API key no configurada")
            if self.debug:
                say("❌ Transcripción de audio no disponible (OpenAI API key no configurada)")
            return

        try:
            file_id = file.get("id")
            file_private_download_url = file.get("url_private_download")
            
            logging.info(f"Procesando archivo de audio '{file.get('name')}' del usuario {user_id}.")
            
            if self.debug:
                say(text="🎧 Procesando archivo de audio...", thread_ts=None)
            
            # Obtener información del archivo desde la API de Slack
            file_info_response = self.app.client.files_info(file=file_id)
            file_info = file_info_response['file']
            download_url = file_info.get('url_private_download', file_private_download_url)
            
            # Descargar el archivo
            file_content = self._download_file(download_url)
            
            # Detectar formato actual y preparar para OpenAI
            actual_format = self._detect_audio_format(file_content, file.get("filetype"), download_url)
            original_name = file.get("name", "audio_file")
            base_name = original_name.split('.')[0] if '.' in original_name else original_name
            
            audio_file_data = BytesIO(file_content)
            audio_file_data.name = f"{base_name}.{actual_format}"
            audio_file_data.seek(0)
            
            # Transcribir con OpenAI Whisper
            transcript_data = self.openai_client.audio.transcriptions.create(
                file=audio_file_data,
                model="whisper-1"
            )
            
            # Agregar la transcripción a la cola como si fuera un mensaje de texto
            self.message_queue.put({
                'user_id': user_id,
                'text': transcript_data.text,
                'say': say,
                'audio_file': True  # Flag para identificar que viene de audio
            })
            
            if self.debug:
                say(f"🎧 Audio transcrito exitosamente")
                
        except Exception as e:
            logging.error(f"Error procesando archivo de audio: {e}")
            if self.debug:
                say(f"❌ No pude transcribir el archivo de audio: {str(e)}")

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

            user_id = message.get('user')
            
            # Verificar si el mensaje contiene archivos
            if "files" in message:
                # Tipos de archivos de audio que Slack reconoce
                audio_filetypes = {"m4a", "mp3", "mp4", "ogg", "wav"}
                
                for file in message["files"]:
                    filetype = file.get("filetype")
                    
                    # Verificar si es un archivo de audio
                    if filetype in audio_filetypes:
                        self._process_audio_file(file, user_id, say)
                
                # Si solo había archivos de audio, no procesar como mensaje de texto
                audio_files_only = all(file.get("filetype") in audio_filetypes for file in message["files"])
                if audio_files_only:
                    return

            # Procesar mensaje de texto
            text = message.get('text')
            if user_id and text:
                # --- INICIO DE LA MODIFICACION ---
                # Enviar un acuse de recibo inmediato para mostrar que el bot esta "escribiendo".
                # Esto mejora la experiencia del usuario al darle feedback instantaneo.
                if self.debug:
                    try:
                        say(text="Procesando tu solicitud...", thread_ts=message.get("ts"))
                    except Exception as e:
                        logging.error(f"No se pudo enviar el mensaje de acuse de recibo: {e}")
                # --- FIN DE LA MODIFICACION ---
                
                # Empaquetar la informacion relevante y ponerla en la cola
                # para que el proceso principal la consuma.
                self.message_queue.put({
                    'user_id': user_id,
                    'text': text,
                    'say': say,  # La funcion para responder en el canal correcto
                    'audio_file': False  # Flag para identificar que es texto normal
                })

    def start(self):
        """
        Inicia el bot en un hilo separado para no bloquear la ejecucion principal.
        """
        handler = SocketModeHandler(self.app, self.socket_token)
        thread = threading.Thread(target=handler.start)
        thread.daemon = True
        thread.start()