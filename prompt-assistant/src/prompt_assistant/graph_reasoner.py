from langgraph.graph import StateGraph
from typing import Annotated, Sequence, TypeVar

from .nodes_reasoner import reasoner_node, human_node, route_node, prompt_generator_node
from .reasoner_state import ReasonerState

# Crear el grafo
workflow = StateGraph(ReasonerState)

# Agregar nodos
workflow.add_node("reasoner", reasoner_node)
workflow.add_node("human", human_node)
workflow.add_node("prompt_generator", prompt_generator_node)

# Configurar el flujo
workflow.set_entry_point("reasoner")

# Del router, basado en la condición:
# - Si should_generate_prompt es False: ir a human
# - Si should_generate_prompt es True: ir a prompt_generator
workflow.add_conditional_edges(
    "reasoner",
    route_node,
    {
        True: "prompt_generator",
        False: "human"
    }
)

# Del human de vuelta al reasoner
workflow.add_edge("human", "reasoner")

# Configurar el nodo final
workflow.set_finish_point("prompt_generator")

# Compilar el grafo
app = workflow.compile()