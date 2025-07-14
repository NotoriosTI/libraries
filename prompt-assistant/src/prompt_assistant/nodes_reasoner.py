from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.errors import NodeInterrupt
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_core.tools import tool

from .reasoner_state import ReasonerState

# Cargar variables de entorno desde .env
load_dotenv()

# Inicializar el modelo de lenguaje
llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0.2
)

@tool
def set_should_generate_prompt() -> dict:
    """activa el flag should_generate_prompt a True cuando tenga toda la informacion necesaria para generar un prompt o cuando el usuario te indique que ya tienes toda la informacion necesaria"""
    return {"should_generate_prompt": True}

llm_with_tools = llm.bind_tools([set_should_generate_prompt])

def reasoner_node(state: ReasonerState) -> ReasonerState:
    """
    Node que recolecta requerimientos y genera un prompt.
    """

    system_prompt = """
    Eres un asistente experto en recopilar información para generar prompts de IA.
    
    Tu objetivo es interactuar con el humano y recopilar los requerimientos necesarios
    para generar un prompt efectivo. Debes ser proactivo y hacer preguntas específicas para
    recopilar toda la información que encuentres necesaria.

    historial de conversacion:
    {messages}

    Areas importantes a recopilar:
    1. Objetivo del prompt
    2. Contexto y situación
    3. Restricciones y limitaciones

    Analiza la conversación actual y en base a la conversacion:
    - sugiere mejoras o consideraciones
    - si consideras que falta información, haz preguntas específicas
    - si el usuario te especifica directamente que quieres salir de ejecucion, invoca la herramienta `set_should_generate_prompt` con el valor `True`.
    
    Responde de manera clara y estructurada.

    cuando tengas toda la informacion necesaria o si el usuario te indica que ya tienes toda la informacion necesaria invoca la herramienta `set_should_generate_prompt`
    la variable should_generate_prompt por defecto es False, su valor actual es {should_generate}
    la herramienta retorna un diccionario con la clave `should_generate_prompt` y el valor `True` lo que activara el flujo de generacion de prompt y finalizara tu tarea
    """

    system_message = system_prompt.format(messages=state.messages, should_generate=state.should_generate_prompt)
    messages = [SystemMessage(content=system_message)] + state.messages
    
    # Obtener la respuesta del LLM
    response = llm_with_tools.invoke(messages)
    
    # Si la respuesta contiene una llamada a la herramienta, actualizar should_generate_prompt
    if hasattr(response, 'additional_kwargs') and 'tool_calls' in response.additional_kwargs:
        for tool_call in response.additional_kwargs['tool_calls']:
            if tool_call['function']['name'] == 'set_should_generate_prompt':
                return ReasonerState(
                    should_generate_prompt=True
                )

    # Si no se llamó a la herramienta, continuar la conversación normalmente
    return ReasonerState(
        messages=[response]
    )

def human_node(state: ReasonerState) -> ReasonerState:
    """
    Node que proporciona el punto de interrupción para input humano.
    No maneja el input directamente, solo interrumpe el flujo.
    """
    # Usar NodeInterrupt para pausar el flujo y esperar input del usuario
    raise NodeInterrupt("human_input")
    return state


def prompt_generator_node(state: ReasonerState) -> ReasonerState:
    """
    Node que genera un prompt basado en los requerimientos recopilados.
    """

    system_prompt = """
    Eres un agente generador de prompts cuya función es crear prompts claros, coherentes y completos basados exclusivamente en la información proporcionada por un usuario a través de un agente recolector. La información recibida incluye: 
    1) objetivos del prompt, 
    2) contexto y situaciones, 
    3) restricciones y limitaciones, y 
    4) respuestas a preguntas específicas realizadas por el agente recolector para profundizar en el prompt deseado. 

    si el usuario espesifico directamente que quiere salir de ejecucion no genere un prompt, unicamente retorna saliendo de ejecucion.
    
    Tu tarea es generar un prompt que:  
    - Incluya toda la información y contexto proporcionados, sin omitir detalles importantes.  
    - Sea coherente, claro, sin ambigüedades, inconsistencias ni contradicciones.  
    - Utilice el tono y formato más adecuados para maximizar la calidad y funcionalidad del prompt, decidiendo internamente la mejor estructura sin mencionarlo explícitamente.  
    - No incluya información externa, suposiciones propias ni detalles no proporcionados por el usuario.  
    - No tenga límite de longitud y esté listo para ser usado directamente, sin interacción adicional con el usuario.  

    Genera únicamente el prompt final basado en la información recibida, sin añadir explicaciones ni comentarios adicionales.
    """

    messages = [SystemMessage(content=system_prompt)] + state.messages
    response = llm.invoke(messages)
    
    return ReasonerState(
        generated_prompt=response.content
    )

def route_node(state: ReasonerState):
    """
    Node que determina la siguiente acción según el estado actual.
    El estado contiene should_generate_prompt que determina el siguiente nodo.
    """
    should_generate = state.should_generate_prompt
    return should_generate