from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import os

class SlackMessages:
    def __init__(self, dotenv_path):
        # Cargar variables de entorno
        load_dotenv(dotenv_path)
        
        # Inicializar el cliente de Slack
        self.client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))
        
        # Check required scopes
        try:
            # Lista simple de todos los scopes que la biblioteca necesita
            self.required_scopes = [
                "channels:read",      # Para listar y leer canales públicos
                "groups:read",        # Para listar y leer canales privados  
                "im:read",            # Para listar mensajes directos
                "mpim:read",          # Para listar conversaciones grupales
                "channels:history",   # Para leer historial de canales públicos
                "groups:history",     # Para leer historial de canales privados
                "chat:write"          # Para escribir, actualizar y eliminar mensajes
            ]
            
            token_info = self.client.auth_test()
            current_scopes = token_info.get("scope", "").split(",")
            self.current_scopes = [scope.strip() for scope in current_scopes if scope.strip()]
            
            # Verificar que todos los scopes necesarios estén presentes
            missing_scopes = [scope for scope in self.required_scopes if scope not in self.current_scopes]
            
            if missing_scopes:
                print(f"⚠️  Advertencia: Faltan los siguientes scopes:")
                for scope in missing_scopes:
                    print(f"   - {scope}")
                print("\n🔧 Agrega estos scopes en tu Slack App para usar todas las funcionalidades.")
                self.has_all_scopes = False
            else:
                print("✅ Todos los scopes requeridos están presentes.")
                self.has_all_scopes = True
                
        except SlackApiError as e:
            print(f"Error checking authentication: {e.response['error']}")
            self.current_scopes = []
            self.has_all_scopes = False

    def _check_scopes(self) -> bool:
        """
        Verifica si tenemos todos los scopes necesarios
        
        Returns:
            bool: True si tenemos todos los scopes, False si faltan algunos
        """
        if not hasattr(self, 'has_all_scopes'):
            return False
        
        if not self.has_all_scopes:
            print("⚠️  Operación no disponible. Faltan scopes requeridos.")
            print("Ejecuta el objeto para ver qué scopes necesitas agregar.")
            
        return self.has_all_scopes

    # CREATE operations
    def create_channel_message(self, channel: str, text: str) -> dict:
        """
        Crea un nuevo mensaje en un canal
        
        Args:
            channel (str): ID o nombre del canal
            text (str): Texto del mensaje
            
        Returns:
            dict: Información del mensaje incluyendo ts (timestamp que sirve como ID del mensaje)
        """
        # Verificar scope requerido
        if not self._check_scopes():
            return None
        
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text
            )
            return {
                'message_id': response['ts'],
                'channel': response['channel']
            }
        except SlackApiError as e:
            error_code = e.response['error']
            if error_code == "missing_scope":
                print("Error de scope: El bot no tiene permisos para escribir mensajes.")
                print("Scope necesario: chat:write")
            else:
                print(f"Error creando mensaje: {error_code}")
            return None

    def create_thread_message(self, channel: str, thread_ts: str, text: str) -> dict:
        """
        Crea un nuevo mensaje en un hilo específico
        
        Args:
            channel (str): ID o nombre del canal
            thread_ts (str): ID del mensaje padre del hilo
            text (str): Texto de la respuesta
            
        Returns:
            dict: Información del mensaje enviado
        """
        # Verificar scope requerido
        if not self._check_scopes():
            return None
        
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=text
            )
            return {
                'message_id': response['ts'],
                'channel': response['channel']
            }
        except SlackApiError as e:
            error_code = e.response['error']
            if error_code == "missing_scope":
                print("Error de scope: El bot no tiene permisos para escribir mensajes.")
                print("Scope necesario: chat:write")
            else:
                print(f"Error creando mensaje en hilo: {error_code}")
            return None

    # READ operations
    def get_bot_conversations(self, types: str = "public_channel,private_channel,mpim,im") -> list:
        """
        Obtiene todas las conversaciones donde el bot tiene acceso
        
        Args:
            types (str): Tipos de conversaciones a obtener:
                - public_channel: Canales públicos
                - private_channel: Canales privados  
                - mpim: Conversaciones grupales
                - im: Mensajes directos
                
        Returns:
            list: Lista de conversaciones con información detallada
        """
        if not self._check_scopes():
            return []
        
        try:
            conversations = []
            cursor = None
            
            while True:
                response = self.client.conversations_list(
                    types=types,
                    limit=200,
                    cursor=cursor
                )
                
                conversations.extend(response['channels'])
                
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
                    
            return conversations
            
        except SlackApiError as e:
            error_code = e.response['error']
            if error_code == "missing_scope":
                print(f"Error de scope: El bot no tiene permisos para listar conversaciones de tipo '{types}'")
                print("Revisa que tengas todos los scopes requeridos en tu Slack App.")
            else:
                print(f"Error obteniendo conversaciones: {error_code}")
            return []

    def get_public_channels(self) -> list:
        """
        Obtiene solo los canales públicos donde el bot tiene acceso
        
        Returns:
            list: Lista de canales públicos
        """
        return self.get_bot_conversations(types="public_channel")

    def get_private_channels(self) -> list:
        """
        Obtiene solo los canales privados donde el bot tiene acceso
        
        Returns:
            list: Lista de canales privados
        """
        return self.get_bot_conversations(types="private_channel")

    def get_direct_messages(self) -> list:
        """
        Obtiene las conversaciones de mensajes directos del bot
        
        Returns:
            list: Lista de conversaciones directas
        """
        return self.get_bot_conversations(types="im")

    def get_group_messages(self) -> list:
        """
        Obtiene las conversaciones grupales donde el bot participa
        
        Returns:
            list: Lista de conversaciones grupales
        """
        return self.get_bot_conversations(types="mpim")

    def read_channel_messages(self, channel: str, limit: int = 100) -> list:
        """
        Lee los mensajes de un canal
        
        Args:
            channel (str): ID o nombre del canal
            limit (int): Número máximo de mensajes a recuperar
            
        Returns:
            list: Lista de mensajes
        """
        if not self._check_scopes():
            return []
        
        try:
            response = self.client.conversations_history(
                channel=channel,
                limit=limit
            )
            return response['messages']
        except SlackApiError as e:
            print(f"Error leyendo mensajes: {e.response['error']}")
            return []

    def read_thread_messages(self, channel: str, thread_ts: str) -> list:
        """
        Lee los mensajes de un hilo específico
        
        Args:
            channel (str): ID o nombre del canal
            thread_ts (str): ID del mensaje padre del hilo
            
        Returns:
            list: Lista de mensajes del hilo
        """
        if not self._check_scopes():
            return []
        
        try:
            response = self.client.conversations_replies(
                channel=channel,
                ts=thread_ts
            )
            return response['messages']
        except SlackApiError as e:
            error = e.response['error']
            if error == "missing_scope":
                print("Error: Bot token missing required scopes for reading threads.")
                print("Please add 'channels:history' scope in your Slack App configuration")
            else:
                print(f"Error leyendo hilo: {error}")
            return []

    def read_message(self, channel: str, message_ts: str) -> dict:
        """
        Lee un mensaje específico por su ID
        
        Args:
            channel (str): ID o nombre del canal
            message_ts (str): ID del mensaje
            
        Returns:
            dict: Información del mensaje
        """
        if not self._check_scopes():
            return None
        
        try:
            # Obtenemos el mensaje específico usando conversations_history con latest y limit=1
            response = self.client.conversations_history(
                channel=channel,
                latest=message_ts,
                limit=1,
                inclusive=True
            )
            return response['messages'][0] if response['messages'] else None
        except SlackApiError as e:
            print(f"Error leyendo mensaje: {e.response['error']}")
            return None

    # UPDATE operations
    def update_message(self, channel: str, message_ts: str, new_text: str) -> dict:
        """
        Actualiza el texto de un mensaje existente
        
        Args:
            channel (str): ID o nombre del canal
            message_ts (str): ID del mensaje a actualizar
            new_text (str): Nuevo texto para el mensaje
            
        Returns:
            dict: Información del mensaje actualizado
        """
        if not self._check_scopes():
            return None
        
        try:
            response = self.client.chat_update(
                channel=channel,
                ts=message_ts,
                text=new_text
            )
            return {
                'message_id': response['ts'],
                'channel': response['channel']
            }
        except SlackApiError as e:
            print(f"Error actualizando mensaje: {e.response['error']}")
            return None

    # DELETE operations
    def delete_message(self, channel: str, message_ts: str) -> bool:
        """
        Elimina un mensaje específico
        
        Args:
            channel (str): ID o nombre del canal
            message_ts (str): ID del mensaje a eliminar
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        if not self._check_scopes():
            return False
        
        try:
            response = self.client.chat_delete(
                channel=channel,
                ts=message_ts
            )
            return response['ok']
        except SlackApiError as e:
            print(f"Error eliminando mensaje: {e.response['error']}")
            return False
