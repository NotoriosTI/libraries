# env-manager

Un gestor de configuración simple y consciente del entorno que unifica secretos desde archivos `.env` locales y Google Cloud Secret Manager. Maneja la conversión de tipos, validación, enmascaramiento de secretos y carga automáticamente las variables a `os.environ` para que las bibliotecas externas funcionen sin problemas.

## Instalación

Agrega a tu `pyproject.toml`:

```toml
[project]
dependencies = [
    "env-manager @ git+https://github.com/NotoriosTI/libraries.git@main#subdirectory=env-manager",
]
```

Luego instala con Poetry o pip.

## Inicio Rápido

### Uso Básico (Recomendado)

El patrón singleton es la forma más simple de usar env-manager:

```python
# main.py - Inicializa una vez al inicio
from env_manager import init_config, get_config

init_config("config/config_vars.yaml")

# Ahora úsalo en cualquier parte de tu código
db_password = get_config("DB_PASSWORD")
api_timeout = get_config("API_TIMEOUT", 30)  # con valor por defecto
```

**Qué sucede automáticamente:**
- Las variables se cargan desde `.env` o GCP Secret Manager
- Se aplica conversión de tipos (strings → int/float/bool según configuración)
- Los valores se validan (requeridos vs opcionales)
- Todo se asigna a `os.environ`
- Las bibliotecas externas (LangChain, LangGraph, etc.) funcionan automáticamente

**Ejemplo:**
```python
# config_vars.yaml define PORT como type: int
init_config("config/config_vars.yaml")

port = get_config("PORT")  # → 8080 (int real, no string)
# os.environ["PORT"] ahora es "8080" (string, para bibliotecas externas)
```

### Fuentes de Secretos

Por defecto, los secretos se cargan desde archivos `.env`. Para usar Google Cloud Secret Manager, establece `SECRET_ORIGIN=gcp`.

**Orden de prioridad:**
1. Parámetro explícito: `init_config(..., secret_origin="gcp")`
2. Variable de entorno: `export SECRET_ORIGIN=gcp`
3. Archivo `.env`: `SECRET_ORIGIN=gcp`
4. Por defecto: `"local"`

## Archivo de Configuración

Crea un archivo YAML (ej. `config_vars.yaml`) con esta estructura:

```yaml
variables:
  # Secreto requerido (debe existir en .env o GCP)
  DB_PASSWORD:
    source: DB_PASSWORD
    type: str

  # Opcional con valor de respaldo
  PORT:
    source: PORT
    type: int
    default: 8080

  # Constante (no necesita fuente externa)
  LOG_LEVEL:
    type: str
    default: "INFO"

validation:
  strict: false
  required:
    - DB_PASSWORD    # Error si falta
  optional:
    - DEBUG_MODE     # Advertencia si falta
```

### Reglas de Definición de Variables

Cada variable debe tener **al menos uno** de:
- `source`: Nombre del secreto en `.env` o GCP Secret Manager
- `default`: Valor de respaldo si no se encuentra

**Conversión de tipos** (campo `type`):
- `str` (por defecto): Sin conversión
- `int`: Convierte a entero
- `float`: Convierte a decimal
- `bool`: Acepta solo `"true"`, `"True"`, `"1"`, `"false"`, `"False"`, `"0"`

**Validación** (sección `validation`):
- `required`: Lanza error si la variable falta
- `optional`: Registra advertencia si la variable falta
- `strict: true`: Obliga a que todas las variables tengan valores (ignora defaults)

## Referencia Completa de la API

### API Singleton (Recomendada)

```python
from env_manager import init_config, get_config, require_config

# Inicializa una vez
init_config(
    "config/config_vars.yaml",
    secret_origin=None,      # "local" o "gcp" (auto-detectado si es None)
    gcp_project_id=None,     # Requerido si secret_origin="gcp"
    strict=None,             # Sobrescribe configuración strict del YAML
    dotenv_path=None,        # Ruta personalizada de .env (auto-detectado si es None)
    debug=False,             # Muestra secretos sin enmascarar en logs (NUNCA en producción)
)

# Úsalo en cualquier lugar
value = get_config("KEY")                  # Retorna valor o None
value = get_config("KEY", "default")       # Retorna valor o default provisto
value = require_config("REQUIRED_KEY")     # Lanza RuntimeError si falta
```

### API de Instancia (Avanzado)

**Cuándo usar ConfigManager directamente:**
- Múltiples configuraciones simultáneamente
- Pruebas avanzadas con inyección de dependencias
- Arquitecturas de microservicios complejas

```python
from env_manager import ConfigManager

manager = ConfigManager(
    "config/config_vars.yaml",
    secret_origin="gcp",
    gcp_project_id="my-project",
    auto_load=True,
)

manager.get("DB_PASSWORD")        # Retorna valor o None
manager.get("PORT", 8080)         # Retorna valor o default provisto
manager.require("API_KEY")        # Lanza RuntimeError si falta
manager.values                    # Dict de todos los valores cargados
```

**Ejemplo: Múltiples configuraciones**
```python
prod_config = ConfigManager("config/prod.yaml", secret_origin="gcp")
dev_config = ConfigManager("config/dev.yaml", secret_origin="local")

prod_db = prod_config.get("DB_PASSWORD")
dev_db = dev_config.get("DB_PASSWORD")
```

**Ejemplo: Pruebas con inyección de dependencias**
```python
class DatabaseService:
    def __init__(self, config: ConfigManager = None):
        self.config = config or ConfigManager("config/config_vars.yaml")
        self.host = self.config.get("DB_HOST")

def test_database_service():
    test_config = ConfigManager("config/test.yaml")
    service = DatabaseService(config=test_config)
    # Prueba de forma aislada
```

## Cómo Funciona

### Carga Automática al Entorno

Cuando llamas a `init_config()` o creas un `ConfigManager`:

1. **Se analiza la configuración** desde el YAML
2. **Se obtienen los secretos** desde `.env` o GCP Secret Manager
3. **Se convierten los tipos** según las definiciones del YAML
4. **Se validan los valores** (verificaciones required/optional)
5. **Las variables se asignan a `os.environ`** automáticamente
6. **Los secretos se enmascaran** en toda la salida de logs

Esto significa que las bibliotecas externas que leen de `os.environ` (como LangChain, LangGraph, etc.) funcionan automáticamente sin configuración adicional.

### Detalles de Conversión de Tipos

**Cuando usas `get_config()`:** Obtienes el valor con el tipo correcto
```python
port = get_config("PORT")  # → 8080 (int)
debug = get_config("DEBUG")  # → False (bool)
```

**Cuando bibliotecas externas leen `os.environ`:** Obtienen strings
```python
os.environ["PORT"]   # → "8080" (string)
os.environ["DEBUG"]  # → "false" (string)
```

Esto es intencional - `os.environ` solo almacena strings, pero las bibliotecas externas manejan el parseo de strings correctamente.

### Resolución de SECRET_ORIGIN

El `SECRET_ORIGIN` determina de dónde cargar los secretos:

**Prioridad (de mayor a menor):**
1. Parámetro explícito: `init_config(..., secret_origin="gcp")`
2. Variable de entorno: `export SECRET_ORIGIN=gcp`
3. Archivo `.env`: `SECRET_ORIGIN=gcp` (leído sin cargar todo el archivo)
4. Por defecto: `"local"`

**Ejemplo:**
```bash
# Archivo .env
SECRET_ORIGIN=gcp
GCP_PROJECT_ID=my-project
```

```python
# Automáticamente usa GCP desde .env
init_config("config/config_vars.yaml")
```

### Resolución de GCP_PROJECT_ID

Al usar `secret_origin="gcp"`, el ID del proyecto GCP se resuelve con:

1. Parámetro explícito: `init_config(..., gcp_project_id="my-project")`
2. Variable de entorno: `export GCP_PROJECT_ID=my-project`
3. Archivo `.env`: `GCP_PROJECT_ID=my-project`
4. Sin establecer (se registra advertencia)

## Enmascaramiento de Secretos

Todos los secretos se enmascaran automáticamente en los logs por seguridad:

- **Secretos cortos** (< 10 caracteres): `**********`
- **Secretos largos**: `ab****1234` (se muestran primeros 2 + últimos 4 caracteres)

Establece `debug=True` para ver temporalmente valores sin enmascarar (nunca en producción):

```python
init_config("config/config_vars.yaml", debug=True)
```

## Guía de Migración

Si estás migrando desde `python-dotenv` o uso manual de `os.environ`:

1. **Copia** `config_vars.yaml.example` a tu proyecto
2. **Personaliza** el YAML con tus variables
3. **Instala** env-manager en tus dependencias
4. **Reemplaza** `load_dotenv()` con `init_config("config/config_vars.yaml")`
5. **Reemplaza** `os.environ["KEY"]` con `get_config("KEY")`
6. **Configura** `SECRET_ORIGIN=gcp` y `GCP_PROJECT_ID` para producción

**Antes:**
```python
from dotenv import load_dotenv
import os

load_dotenv()
db_password = os.environ["DB_PASSWORD"]
port = int(os.environ.get("PORT", "8080"))
```

**Después:**
```python
from env_manager import init_config, get_config

init_config("config/config_vars.yaml")
db_password = get_config("DB_PASSWORD")
port = get_config("PORT")  # Ya es un int, con default 8080
```

## Solución de Problemas

**`Configuration manager not initialised`**
- Llama a `init_config()` antes de usar `get_config()` o `require_config()`

**`Missing GCP project ID`**
- Establece `GCP_PROJECT_ID` vía parámetro, variable de entorno o archivo `.env`

**`Type coercion failed`**
- Verifica que el campo `type` del YAML coincida con el formato de tu valor
- Asegúrate de que los valores booleanos sean exactamente `"true"`, `"false"`, `"1"` o `"0"`

**`Required variable not found`**
- Verifica que el secreto exista en `.env` o GCP Secret Manager
- Verifica que el nombre del secreto coincida con el campo `source` del YAML
- Asegúrate de que las credenciales GCP tengan acceso al proyecto

**Variables no cargadas**
- Confirma que `init_config()` se ejecutó exitosamente
- Revisa los logs para advertencias o errores
- Verifica que el archivo `.env` exista y esté en la ubicación correcta

## Desarrollo

```bash
# Instalar dependencias
poetry install

# Ejecutar pruebas
pytest -v

# Ejecutar con cobertura
pytest --cov=env_manager --cov-report=html
```

El proyecto usa Python 3.12+, Poetry para gestión de dependencias y pytest para pruebas.

## Licencia

Biblioteca interna de NotoriosTI.
