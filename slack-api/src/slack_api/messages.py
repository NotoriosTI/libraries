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
            required_scopes = {
                'read': [
                    "channels:history",  # For reading messages and threads
                    "groups:history",    # For reading in private channels
                    "channels:read"      # For basic channel info
                ],
                'write': [
                    "chat:write"        # For sending messages
                ]
            }
            
            token_info = self.client.auth_test()
            current_scopes = token_info.get("scope", "").split(",")
            print(current_scopes)
            
        except SlackApiError as e:
            print(f"Error checking authentication: {e.response['error']}")

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
            print(f"Error creando mensaje: {e.response['error']}")
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
            print(f"Error creando mensaje en hilo: {e.response['error']}")
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
            print(f"Error obteniendo conversaciones: {e.response['error']}")
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

    def get_conversations_summary(self) -> dict:
        """
        Obtiene un resumen organizado de todas las conversaciones del bot
        
        Returns:
            dict: Resumen organizado por tipo de conversación
        """
        try:
            all_conversations = self.get_bot_conversations()
            
            summary = {
                'public_channels': [],
                'private_channels': [],
                'direct_messages': [],
                'group_messages': [],
                'total_count': len(all_conversations)
            }
            
            for conv in all_conversations:
                conv_info = {
                    'id': conv.get('id'),
                    'name': conv.get('name', 'Sin nombre'),
                    'is_member': conv.get('is_member', False),
                    'is_archived': conv.get('is_archived', False),
                    'member_count': conv.get('num_members', 0)
                }
                
                if conv.get('is_channel') and not conv.get('is_private'):
                    summary['public_channels'].append(conv_info)
                elif conv.get('is_group') or (conv.get('is_private') and conv.get('is_channel')):
                    summary['private_channels'].append(conv_info)
                elif conv.get('is_im'):
                    # Para DMs, obtener info del usuario
                    conv_info['user_id'] = conv.get('user')
                    summary['direct_messages'].append(conv_info)
                elif conv.get('is_mpim'):
                    summary['group_messages'].append(conv_info)
                    
            return summary
            
        except SlackApiError as e:
            print(f"Error obteniendo resumen de conversaciones: {e.response['error']}")
            return {}

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
