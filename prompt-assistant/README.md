# Prompt Assistant

Un agente React inteligente para generar prompts de manera estructurada y eficiente utilizando LangGraph y Google Gemini.

## 🎯 Características

- **Agente React**: Utiliza un sistema de razonamiento estructurado para recopilar información
- **Loop Interactivo**: Conversación dinámica entre el reasoner y el usuario
- **Generación Especializada**: Agente dedicado para crear prompts optimizados
- **Estado Persistente**: Mantiene el contexto de la conversación
- **Estructura Clara**: PromptRequirements bien definidos para capturar todos los aspectos necesarios

## 🏗️ Arquitectura

### Componentes Principales

1. **ReasonerState**: Estado principal que contiene:
   - Historial de mensajes
   - PromptRequirements (objetivo, contexto, audiencia, etc.)
   - Fase actual del proceso
   - Prompt generado

2. **PromptRequirements**: Clase estructurada para capturar:
   - Objetivo del prompt
   - Contexto y situación
   - Audiencia objetivo
   - Restricciones y requerimientos
   - Ejemplos deseados
   - Tono y estilo
   - Longitud preferida
   - Notas adicionales

3. **Nodos del Grafo**:
   - `reasoner_node`: Analiza la conversación y actualiza requerimientos
   - `human_node`: Permite entrada del usuario
   - `prompt_generator_node`: Genera el prompt final optimizado

## 🚀 Instalación

1. **Clonar el repositorio**:
```bash
git clone <repository-url>
cd prompt-assistant
```

2. **Instalar dependencias con Poetry**:
```bash
# Instalar Poetry (si no lo tienes)
curl -sSL https://install.python-poetry.org | python3 -

# Instalar dependencias del proyecto
poetry install

# Activar el entorno virtual
poetry shell
```

3. **Configurar variables de entorno**:
```bash
cp .env.example .env
# Editar .env y agregar tu GOOGLE_API_KEY
```

## 📝 Uso

### Ejecución Básica
```bash
# Usando Poetry
poetry run prompt-assistant

# O desde el entorno virtual
python -m prompt_assistant
```

### Flujo de Trabajo

1. **Inicio**: El agente te da la bienvenida y explica el proceso
2. **Recopilación**: El reasoner hace preguntas específicas para completar los requerimientos
3. **Iteración**: Loop entre reasoner y usuario hasta completar la información
4. **Generación**: Cuando estés listo, di "generar" o "listo"
5. **Resultado**: El agente especializado crea tu prompt optimizado

### Comandos Disponibles

- `generar`, `generate`, `listo`, `ready`, `completo`: Generar el prompt
- `exit`, `salir`, `terminar`, `finish`, `done`: Terminar el proceso

## 🔧 Configuración

### Variables de Entorno

```env
GOOGLE_API_KEY=tu_api_key_de_google
```

### Personalización

Puedes modificar los prompts del sistema en:
- `nodes_reasoner.py`: Prompts del reasoner y generador
- `graph_reasoner.py`: Mensaje de bienvenida

## 📁 Estructura del Proyecto

```
prompt-assistant/
├── src/
│   ├── __init__.py
│   ├── __main__.py              # Punto de entrada
│   ├── reasoner_state.py        # Estado y modelos
│   ├── nodes_reasoner.py        # Nodos del grafo
│   ├── graph_reasoner.py        # Configuración del grafo
│   └── expert_reasoner/         # Agentes especializados (futuro)
├── tests/
├── pyproject.toml
└── README.md
```

## 🧪 Pruebas

```bash
# Ejecutar pruebas con Poetry
poetry run pytest

# O con cobertura
poetry run pytest --cov=prompt_assistant
```

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 🆘 Soporte

Si tienes problemas o preguntas:
1. Revisa la documentación
2. Busca en los issues existentes
3. Crea un nuevo issue con detalles del problema

## 🔮 Roadmap

- [ ] Agentes especializados por dominio
- [ ] Interfaz web
- [ ] Templates de prompts predefinidos
- [ ] Análisis de calidad de prompts
- [ ] Integración con múltiples LLMs
