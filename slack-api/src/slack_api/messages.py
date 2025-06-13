from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import os

class SlackMessages:
    def __init__(self, dotenv_path:str = None):
        # Cargar variables de entorno
        dotenv_path = dotenv_path or '/home/snparada/Spacionatural/Libraries/slack_lib/.env'
        load_dotenv()

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
            print(token_info)
            current_scopes = token_info.get("scope", "").split(",")
            print(required_scopes)
            
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
