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

    def _add_reaction(self, channel, timestamp, emoji="white_check_mark"):
        """
        Agrega una reacción a un mensaje específico.
        
        Args:
            channel (str): ID del canal donde está el mensaje.
            timestamp (str): Timestamp del mensaje.
            emoji (str): Emoji a usar como reacción (default: ✅).
        """
        try:
            if self.debug:
                logging.info(f"Intentando agregar reacción {emoji} al mensaje en canal {channel}, timestamp {timestamp}")
            
            # Verificar que tenemos los datos necesarios
            if not channel:
                logging.error("No se puede agregar reacción: channel es None")
                return
            if not timestamp:
                logging.error("No se puede agregar reacción: timestamp es None")
                return
            
            # Intentar agregar la reacción
            response = self.app.client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=emoji
            )
            
            if self.debug:
                logging.info(f"✅ Reacción {emoji} agregada exitosamente al mensaje en {channel}")
                logging.info(f"Respuesta de la API: {response}")
                
        except Exception as e:
            logging.error(f"Error agregando reacción {emoji}: {e}")
            if self.debug:
                logging.error(f"Error detallado: {str(e)}", exc_info=True)
                logging.error(f"Channel: {channel}, Timestamp: {timestamp}, Emoji: {emoji}")

    def _process_audio_file(self, file, user_id, say):
        """
        Procesa un archivo de audio, lo transcribe y agrega el texto a la cola.
        
        Args:
            file (dict): Información del archivo de Slack.
            user_id (str): ID del usuario que envió el archivo.
            say (function): Función para responder en Slack.
        """
        if self.debug:
            logging.info(f"🎧 _process_audio_file llamado para archivo: {file.get('name')}")
        
        if not self.openai_client:
            logging.warning("No se puede procesar audio: OpenAI API key no configurada")
            if self.debug:
                say("❌ Transcripción de audio no disponible (OpenAI API key no configurada)")
            return

        try:
            file_id = file.get("id")
            file_private_download_url = file.get("url_private_download")
            
            if self.debug:
                logging.info(f"Datos del archivo - ID: {file_id}, URL: {file_private_download_url}")
            
            logging.info(f"Procesando archivo de audio '{file.get('name')}' del usuario {user_id}.")
            
            if self.debug:
                say(text="🎧 Procesando archivo de audio...", thread_ts=None)
            
            # Verificar si tenemos ID del archivo
            if not file_id:
                raise ValueError("No se encontró ID del archivo")
            
            # Obtener información del archivo desde la API de Slack
            if self.debug:
                logging.info(f"Obteniendo información del archivo con ID: {file_id}")
            
            file_info_response = self.app.client.files_info(file=file_id)
            file_info = file_info_response['file']
            download_url = file_info.get('url_private_download', file_private_download_url)
            
            if self.debug:
                logging.info(f"URL de descarga obtenida: {download_url}")
            
            # Verificar que tenemos URL de descarga
            if not download_url:
                raise ValueError("No se pudo obtener URL de descarga del archivo")
            
            # Descargar el archivo
            if self.debug:
                logging.info("Descargando archivo...")
            
            file_content = self._download_file(download_url)
            
            if self.debug:
                logging.info(f"Archivo descargado - tamaño: {len(file_content)} bytes")
            
            # Detectar formato actual y preparar para OpenAI
            actual_format = self._detect_audio_format(file_content, file.get("filetype"), download_url)
            original_name = file.get("name", "audio_file")
            base_name = original_name.split('.')[0] if '.' in original_name else original_name
            
            if self.debug:
                logging.info(f"Formato detectado: {actual_format}, nombre base: {base_name}")
            
            audio_file_data = BytesIO(file_content)
            audio_file_data.name = f"{base_name}.{actual_format}"
            audio_file_data.seek(0)
            
            # Transcribir con OpenAI Whisper
            if self.debug:
                logging.info("Iniciando transcripción con OpenAI...")
            
            transcript_data = self.openai_client.audio.transcriptions.create(
                file=audio_file_data,
                model="whisper-1"
            )
            
            if self.debug:
                logging.info(f"Transcripción completada: {transcript_data.text[:100]}...")
            
            # Agregar la transcripción a la cola como si fuera un mensaje de texto
            self.message_queue.put({
                'user_id': user_id,
                'text': transcript_data.text,
                'say': say,
                'audio_file': True,  # Flag para identificar que viene de audio
                'channel': file.get('channels', [None])[0] if file.get('channels') else None,
                'timestamp': file.get('timestamp')
            })
            
            if self.debug:
                say(f"🎧 Audio transcrito exitosamente: {transcript_data.text}")
                
        except Exception as e:
            logging.error(f"Error procesando archivo de audio: {e}")
            if self.debug:
                logging.error(f"Error detallado: {str(e)}", exc_info=True)
                say(f"❌ No pude transcribir el archivo de audio: {str(e)}")

    def _register_events(self):
        """
        Registra los manejadores de eventos para el bot.
        """
        @self.app.event("message")
        def handle_message_events(event, say, logger=None):
            # IMPORTANTE: Usar 'event' en lugar de 'message' como en slack_audio.py
            message = event  # Para mantener compatibilidad con código existente
            
            # DEBUG: Imprimir mensaje completo para debugging
            if self.debug:
                logging.info(f"Evento recibido: {event}")
            
            # Ignorar mensajes de bots o ciertos subtipos específicos (NO file_share)
            if 'bot_id' in event:
                if self.debug:
                    logging.info(f"Mensaje ignorado - es de bot")
                return
            
            # Solo ignorar subtipos específicos que no queremos procesar, pero PERMITIR file_share
            unwanted_subtypes = {
                'bot_add', 'bot_remove', 'channel_join', 'channel_leave', 
                'channel_topic', 'channel_purpose', 'channel_name',
                'group_join', 'group_leave', 'channel_archive', 'channel_unarchive'
            }
            
            if 'subtype' in event and event.get('subtype') in unwanted_subtypes:
                if self.debug:
                    logging.info(f"Mensaje ignorado - subtype no deseado: {event.get('subtype')}")
                return

            if event.get('text') == "clear_screen":
                for _ in range(30):
                    say(text="-")
                return

            user_id = event.get('user')
            channel = event.get('channel')
            timestamp = event.get('ts')
            
            if self.debug:
                logging.info(f"Datos del mensaje - user_id: {user_id}, channel: {channel}, timestamp: {timestamp}")
            
            # DEBUG: Verificar si el mensaje contiene archivos
            if self.debug:
                logging.info(f"Verificando archivos en evento. 'files' presente: {'files' in event}")
                if 'files' in event:
                    logging.info(f"Archivos encontrados: {len(event['files'])}")
                    for i, file in enumerate(event['files']):
                        logging.info(f"Archivo {i}: tipo='{file.get('filetype')}', nombre='{file.get('name')}'")
            
            # Verificar si el mensaje contiene archivos
            if "files" in event:
                # Tipos de archivos de audio que Slack reconoce
                audio_filetypes = {"m4a", "mp3", "mp4", "ogg", "wav"}
                
                audio_files_found = False
                for file in event["files"]:
                    filetype = file.get("filetype")
                    
                    if self.debug:
                        logging.info(f"Procesando archivo: {file.get('name')} - tipo: {filetype}")
                    
                    # Verificar si es un archivo de audio
                    if filetype in audio_filetypes:
                        audio_files_found = True
                        if self.debug:
                            logging.info(f"¡Archivo de audio detectado! Procesando: {file.get('name')}")
                        
                        # Agregar reacción ✅ al mensaje de audio
                        if channel and timestamp:
                            if self.debug:
                                logging.info(f"Agregando reacción a archivo de audio en canal {channel}")
                            self._add_reaction(channel, timestamp)
                        else:
                            if self.debug:
                                logging.warning(f"No se puede agregar reacción: channel={channel}, timestamp={timestamp}")
                        
                        self._process_audio_file(file, user_id, say)
                    else:
                        if self.debug:
                            logging.info(f"Archivo no es de audio: {filetype}")
                
                if self.debug:
                    logging.info(f"Archivos de audio encontrados: {audio_files_found}")
                
                # Si solo había archivos de audio, no procesar como mensaje de texto
                audio_files_only = all(file.get("filetype") in audio_filetypes for file in event["files"])
                if audio_files_only:
                    if self.debug:
                        logging.info("Solo archivos de audio encontrados, terminando procesamiento")
                    return

            # Procesar mensaje de texto
            text = event.get('text')
            if user_id and text:
                if self.debug:
                    logging.info(f"Procesando mensaje de texto: '{text}' del usuario: {user_id}")
                
                # Agregar reacción ✅ al mensaje de texto
                if channel and timestamp:
                    if self.debug:
                        logging.info(f"Agregando reacción a mensaje de texto en canal {channel}")
                    self._add_reaction(channel, timestamp)
                else:
                    if self.debug:
                        logging.warning(f"No se puede agregar reacción a texto: channel={channel}, timestamp={timestamp}")
                
                # --- INICIO DE LA MODIFICACION ---
                # Enviar un acuse de recibo inmediato para mostrar que el bot esta "escribiendo".
                # Esto mejora la experiencia del usuario al darle feedback instantaneo.
                if self.debug:
                    try:
                        say(text="Procesando tu solicitud...", thread_ts=event.get("ts"))
                    except Exception as e:
                        logging.error(f"No se pudo enviar el mensaje de acuse de recibo: {e}")
                # --- FIN DE LA MODIFICACION ---
                
                # Empaquetar la informacion relevante y ponerla en la cola
                # para que el proceso principal la consuma.
                self.message_queue.put({
                    'user_id': user_id,
                    'text': text,
                    'say': say,  # La funcion para responder en el canal correcto
                    'audio_file': False,  # Flag para identificar que es texto normal
                    'channel': channel,
                    'timestamp': timestamp
                })
            else:
                if self.debug:
                    logging.info(f"Mensaje sin texto válido - user_id: {user_id}, text: {text}")

        # Agregar también event handler para file_shared si los archivos llegan por separado
        @self.app.event("file_shared")
        def handle_file_shared(event, say):
            if self.debug:
                logging.info(f"Evento file_shared recibido: {event}")
            
            file_id = event.get("file_id")
            user_id = event.get("user_id")
            channel = event.get("channel_id")
            timestamp = event.get("message_ts")
            
            if self.debug:
                logging.info(f"Datos del archivo compartido - file_id: {file_id}, user_id: {user_id}, channel: {channel}, timestamp: {timestamp}")
            
            if file_id and user_id:
                try:
                    # Obtener información del archivo
                    file_info_response = self.app.client.files_info(file=file_id)
                    file_info = file_info_response['file']
                    
                    filetype = file_info.get('filetype')
                    audio_filetypes = {"m4a", "mp3", "mp4", "ogg", "wav"}
                    
                    if self.debug:
                        logging.info(f"Archivo compartido: {file_info.get('name')} - tipo: {filetype}")
                    
                    if filetype in audio_filetypes:
                        if self.debug:
                            logging.info(f"Procesando archivo de audio compartido: {file_info.get('name')}")
                        
                        # Agregar reacción ✅ al mensaje de archivo compartido
                        if channel and timestamp:
                            if self.debug:
                                logging.info(f"Agregando reacción a archivo compartido en canal {channel}")
                            self._add_reaction(channel, timestamp)
                        else:
                            if self.debug:
                                logging.warning(f"No se puede agregar reacción a archivo compartido: channel={channel}, timestamp={timestamp}")
                        
                        self._process_audio_file(file_info, user_id, say)
                
                except Exception as e:
                    logging.error(f"Error procesando archivo compartido: {e}")
                    if self.debug:
                        say(f"❌ Error procesando archivo compartido: {str(e)}")

    def start(self):
        """
        Inicia el bot en un hilo separado para no bloquear la ejecucion principal.
        """
        handler = SocketModeHandler(self.app, self.socket_token)
        thread = threading.Thread(target=handler.start)
        thread.daemon = True
        thread.start()

    def send_maintenance_message(self, user_ids: set[str], message: str = None):
        """
        Envia un mensaje de mantenimiento a los usuarios especificados.
        """
        if message is None:
            message = "Juan se encontrará en mantenimiento temporalmente. Avisaremos cuando vuelva a estar disponible."

        # Enviar mensaje de mantenimiento a cada usuario    
        logging.info(f"Enviando mensaje de mantenimiento {message} a {len(user_ids)} usuarios")
        for user_id in user_ids:
            try:
                im_channel = self.app.client.conversations_open(users=user_id)
            except Exception as e:
                logging.error(f"Error al abrir canal de usuario {user_id}: {e}")
                continue
            
            try:
                channel_id = im_channel['channel']['id']
                self.app.client.chat_postMessage(channel=channel_id, text=message)
                logging.info(f"Mensaje de mantenimiento enviado a {user_id}")
            except Exception as e:
                logging.error(f"Error al enviar mensaje de mantenimiento a {user_id}: {e}")
            

    def send_message(self, user_ids: set[str], message: str):
        """
        Envia un mensaje a los usuarios especificados.
        """
        for user_id in user_ids:
            self.app.client.chat_postMessage(channel=user_id, text=message)