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
            self.required_scopes = {
                'conversations': {
                    'public_channel': 'channels:read',
                    'private_channel': 'groups:read',
                    'im': 'im:read',
                    'mpim': 'mpim:read'
                },
                'messages': {
                    'read_history': ['channels:history', 'groups:history'],
                    'write': 'chat:write',
                    'update': 'chat:write',
                    'delete': 'chat:write'
                },
                'basic': {
                    'channel_info': 'channels:read'
                }
            }
            
            token_info = self.client.auth_test()
            current_scopes = token_info.get("scope", "").split(",")
            current_scopes = [scope.strip() for scope in current_scopes if scope.strip()]
            
            # Validar scopes requeridos
            all_required = self._get_all_required_scopes()
            missing_scopes = [scope for scope in all_required if scope not in current_scopes]
            
            if missing_scopes:
                print(f"⚠️  Advertencia: El token no tiene los siguientes scopes requeridos:")
                for scope in missing_scopes:
                    print(f"   - {scope}")
                print("Algunas funcionalidades pueden no funcionar correctamente.")
            else:
                print("✅ Todos los scopes requeridos están presentes.")
                
            # Guardar scopes para referencia
            self.current_scopes = current_scopes
            
        except SlackApiError as e:
            print(f"Error checking authentication: {e.response['error']}")
            self.current_scopes = []

    def _get_all_required_scopes(self) -> list:
        """
        Extrae todos los scopes requeridos de la estructura self.required_scopes
        
        Returns:
            list: Lista única de todos los scopes requeridos
        """
        all_scopes = set()
        
        def extract_scopes(obj):
            if isinstance(obj, str):
                all_scopes.add(obj)
            elif isinstance(obj, list):
                all_scopes.update(obj)
            elif isinstance(obj, dict):
                for value in obj.values():
                    extract_scopes(value)
        
        extract_scopes(self.required_scopes)
        return list(all_scopes)

    def _check_required_scopes(self, functionality: str, sub_functionality: str = None) -> tuple[bool, list]:
        """
        Verifica si los scopes requeridos para una funcionalidad están presentes
        
        Args:
            functionality (str): Categoría principal (ej: 'conversations', 'messages')
            sub_functionality (str): Subcategoría específica (ej: 'public_channel', 'write')
            
        Returns:
            tuple: (tiene_scopes, scopes_faltantes)
        """
        current_scopes = getattr(self, 'current_scopes', [])
        
        if functionality not in self.required_scopes:
            return True, []
        
        func_scopes = self.required_scopes[functionality]
        
        if sub_functionality:
            if sub_functionality not in func_scopes:
                return True, []
            required = func_scopes[sub_functionality]
        else:
            required = func_scopes
        
        # Normalizar required a lista
        if isinstance(required, str):
            required = [required]
        elif isinstance(required, dict):
            required = list(required.values())
        
        # Aplanar lista si contiene sublistas
        flattened_required = []
        for item in required:
            if isinstance(item, list):
                flattened_required.extend(item)
            else:
                flattened_required.append(item)
        
        missing = [scope for scope in flattened_required if scope not in current_scopes]
        
        return len(missing) == 0, missing

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
        has_scope, missing = self._check_required_scopes('messages', 'write')
        if not has_scope:
            print(f"⚠️  Falta scope para escribir mensajes: {', '.join(missing)}")
        
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
        has_scope, missing = self._check_required_scopes('messages', 'write')
        if not has_scope:
            print(f"⚠️  Falta scope para escribir mensajes en hilos: {', '.join(missing)}")
        
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
        # Verificar scopes requeridos según el tipo de conversación
        requested_types = [t.strip() for t in types.split(',')]
        missing_scopes = []
        
        for req_type in requested_types:
            has_scope, missing = self._check_required_scopes('conversations', req_type)
            if not has_scope:
                missing_scopes.extend(missing)
        
        if missing_scopes:
            print(f"⚠️  Faltan scopes para obtener {types}: {', '.join(set(missing_scopes))}")
        
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
                # Usar información centralizada para mostrar scopes necesarios
                needed_scopes = []
                for req_type in requested_types:
                    _, missing = self._check_required_scopes('conversations', req_type)
                    needed_scopes.extend(missing)
                print("Scopes necesarios:", ', '.join(set(needed_scopes)))
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
        try:
            response = self.client.chat_delete(
                channel=channel,
                ts=message_ts
            )
            return response['ok']
        except SlackApiError as e:
            print(f"Error eliminando mensaje: {e.response['error']}")
            return False
