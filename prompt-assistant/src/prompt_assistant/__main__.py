from .graph_reasoner import app
from .reasoner_state import ReasonerState
from langchain_core.messages import HumanMessage
import queue
import threading
import logging

from slack_api import SlackBot
from config_manager import secrets

Loc_flag = True

def main():
    """
    Punto de entrada principal para el asistente de prompt
    """
    print("=" * 50)
    print("\n🤖 Iniciando Agente de Generación de Prompts...")

    # Inicializar el estado
    state = ReasonerState()
    
    if Loc_flag:
        print("🔄 Iniciando Agente de Generación de Prompts en modo local...\n")
        print("=" * 50)
        
        thread_id = threading.get_ident()
        config = {"configurable": {"thread_id": thread_id}}

        while True:
            try:
                # Ejecutar el grafo hasta el próximo interrupt
                state = app.invoke(state, config=config)

                # Si se generó un prompt, mostrarlo y terminar
                if state.get("generated_prompt"):
                    print(f"🎯 Prompt generado:\n{state.get('generated_prompt')}")
                    break

                
                # Mostrar el último mensaje del razonador si existe
                messages = state.get("messages")
                if messages and len(messages) > 0:
                    last_message = messages[-1]
                    if hasattr(last_message, 'content'):
                        print(f"\nAsistente: {last_message.content} \n")
                        print("=" * 50)

                # Obtener el input del usuario después del interrupt
                user_input = input("\nTú: ").strip()
                print("=" * 50)

                # Si el input está vacío, pedir nuevo input
                if not user_input:
                    print("\nPor favor, escribe algo.")
                    user_input = input("\nTú: ").strip()
                    print("\n")
                    print("=" * 50)
                    continue

                # Actualizar el estado con el mensaje del usuario
                # Mantener el historial de mensajes y el estado de generación
                new_messages = messages + [HumanMessage(content=user_input)]
                state = ReasonerState(
                    messages=new_messages,
                    should_generate_prompt=state.get("should_generate_prompt")
                )
            except KeyboardInterrupt:
                print("\n\n👋 Saliendo del asistente...")
                break
            except Exception as e:
                print(f"\n❌ Error inesperado: {e}")
                logging.error(f"Error detallado: {str(e)}", exc_info=True)
                raise  # Re-raise para ver el traceback completo en desarrollo

    else:
        print("🔄 Iniciando Agente de Generación de Prompts en modo Slack...\n")
        print("=" * 50)
        
        # Inicializar la cola de mensajes (corregido: message_queue en lugar de messages_queue)
        message_queue = queue.Queue()
        active_conversations = {}

        # Inicializar el bot de Slack
        try:
            slack_bot = SlackBot(
                message_queue=message_queue,
                bot_token=secrets.SLACK_BOT_TOKEN,
                app_token=secrets.SLACK_APP_TOKEN,
                openai_api_key=secrets.OPENAI_API_KEY,
            )
            slack_bot.start()
            print("✅ Slack bot iniciado correctamente")
            print("🔄 Esperando mensajes...")
        except Exception as e:
            print(f"❌ Error al iniciar el bot de Slack: {e}")
            return

        while True:
            try:
                print("⏳ Esperando mensaje de la cola...")
                slack_message = message_queue.get()
                print(f"📨 Mensaje recibido: {slack_message}")

                user_id = slack_message['user_id']
                text = slack_message['text']
                say = slack_message['say']

                # Manejar conversaciones activas
                if user_id not in active_conversations:
                    thread_id = threading.get_ident()
                    active_conversations[user_id] = thread_id
                    print(f"🆕 Nueva conversación iniciada para el usuario {user_id}")

                thread_id = active_conversations[user_id]
                config = {"configurable": {"thread_id": thread_id}}

                # Ejecutar el grafo
                state = app.invoke(state, config=config)

                # Si se generó un prompt, mostrarlo y terminar
                if state.get("generated_prompt"):
                    say(f"🎯 Prompt generado:\n{state.get('generated_prompt')}")
                    if user_id in active_conversations:
                        del active_conversations[user_id]
                    print("✅ Generación de prompt completada")
                    break
                
                # Mostrar el último mensaje del razonador si existe
                messages = state.get("messages")
                if messages and len(messages) > 0:
                    last_message = messages[-1]
                    if hasattr(last_message, 'content'):
                        say(last_message.content)

                # Actualizar el estado con el mensaje del usuario
                # Mantener el historial de mensajes y el estado de generación
                new_messages = messages + [HumanMessage(content=text)]
                state = ReasonerState(
                    messages=new_messages,
                    should_generate_prompt=state.get("should_generate_prompt")
                )
                print("🔄 State actualizado con el mensaje del usuario")

            except KeyboardInterrupt:
                print("\n\n👋 Saliendo del asistente...")
                break
            except Exception as e:
                print(f"\n❌ Error inesperado: {e}")
                logging.error(f"Error detallado: {str(e)}", exc_info=True)
                raise  # Re-raise para ver el traceback completo en desarrollo

if __name__ == "__main__":
    main()
        