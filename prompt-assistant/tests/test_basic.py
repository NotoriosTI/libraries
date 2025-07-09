import pytest
from src.reasoner_state import ReasonerState, PromptRequirements
from langchain_core.messages import HumanMessage, AIMessage


class TestReasonerState:
    """Pruebas para el estado del reasoner."""
    
    def test_reasoner_state_creation(self):
        """Prueba que se puede crear un estado del reasoner."""
        state = ReasonerState()
        assert state.messages == []
        assert state.summary == ""
        assert state.last_human_input is None
        assert isinstance(state.prompt_requirements, PromptRequirements)
        assert state.current_phase == "gathering_requirements"
        assert state.generated_prompt is None
        assert state.conversation_round == 0
    
    def test_prompt_requirements_creation(self):
        """Prueba que se puede crear requerimientos de prompt."""
        requirements = PromptRequirements()
        assert requirements.objective == ""
        assert requirements.context == ""
        assert requirements.target_audience == ""
        assert requirements.constraints == []
        assert requirements.requirements == []
        assert requirements.examples == []
        assert requirements.tone == ""
        assert requirements.length_preference == ""
        assert requirements.additional_notes == ""
        assert requirements.is_complete is False
    
    def test_state_with_messages(self):
        """Prueba que el estado puede manejar mensajes."""
        messages = [
            HumanMessage(content="Hola"),
            AIMessage(content="¡Hola! ¿En qué puedo ayudarte?")
        ]
        state = ReasonerState(messages=messages)
        assert len(state.messages) == 2
        assert state.messages[0].content == "Hola"
        assert state.messages[1].content == "¡Hola! ¿En qué puedo ayudarte?"
    
    def test_prompt_requirements_update(self):
        """Prueba que se pueden actualizar los requerimientos."""
        requirements = PromptRequirements(
            objective="Crear un prompt para análisis de datos",
            target_audience="Analistas de datos",
            tone="Técnico",
            is_complete=True
        )
        assert requirements.objective == "Crear un prompt para análisis de datos"
        assert requirements.target_audience == "Analistas de datos"
        assert requirements.tone == "Técnico"
        assert requirements.is_complete is True


class TestPromptRequirements:
    """Pruebas específicas para PromptRequirements."""
    
    def test_requirements_validation(self):
        """Prueba que los requerimientos se validan correctamente."""
        requirements = PromptRequirements(
            constraints=["Máximo 500 palabras"],
            requirements=["Incluir ejemplos", "Ser claro"],
            examples=["Ejemplo 1", "Ejemplo 2"]
        )
        assert len(requirements.constraints) == 1
        assert len(requirements.requirements) == 2
        assert len(requirements.examples) == 2
        assert "Máximo 500 palabras" in requirements.constraints
        assert "Incluir ejemplos" in requirements.requirements
        assert "Ejemplo 1" in requirements.examples 