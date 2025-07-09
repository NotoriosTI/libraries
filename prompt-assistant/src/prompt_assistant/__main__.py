from .graph_reasoner import app
from .reasoner_state import ReasonerState
from langchain_core.messages import HumanMessage
import threading

def main():
    """
    Punto de entrada principal para el asistente de prompt
    """
    print("=" * 50)
    print("\n🤖 Iniciando Agente de Generación de Prompts...")
    print("El asistente te guiará para recopilar la información necesaria.\n")
    print("=" * 50)

    # Inicializar el estado
    state = ReasonerState()
    
    # Configuración del thread para el interrupt
    thread_id = threading.get_ident()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        while True:
            # Ejecutar el grafo hasta el próximo interrupt
            state = app.invoke(state, config=config)
            
            # Si se generó un prompt, mostrarlo y terminar
            if state.get("generated_prompt"):
                print("\nPrompt generado:\n")
                print(state.get("generated_prompt"))
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
        print("\n\nSaliendo del asistente...")
    except Exception as e:
        print(f"\nError inesperado: {e}")
        raise  # Re-raise para ver el traceback completo en desarrollo

if __name__ == "__main__":
    main()
        