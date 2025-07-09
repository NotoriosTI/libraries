from pydantic import BaseModel, Field
from typing import Annotated, Optional, List
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class ReasonerState(BaseModel):
    """
    Estado del agente reasoner para recopilar requerimientos y generar prompts.
    """

    messages: Annotated[List[BaseMessage], add_messages] = Field(
        default_factory=list,
        description="Historial de mensajes de la conversación"
    )

    should_generate_prompt: bool = Field(
        default=False,
        description="Indica si se debe generar un prompt"
    )

    generated_prompt: Optional[str] = Field(
        default=None,
        description="Prompt generado por el agente especializado"
    )
