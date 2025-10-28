# env-manager

Environment-aware configuration loader that unifies secrets from local `.env` files and Google Cloud Secret Manager. It provides consistent type coercion, validation, secret masking, and both singleton and instance-based APIs so teams can share configuration logic across services.

## Installation

Add the dependency to your `pyproject.toml`:

```toml
[project]
dependencies = [
    "env-manager @ git+https://github.com/NotoriosTI/libraries.git@main#subdirectory=env-manager",
]
```

After updating, install with Poetry or pip as usual.

## Quickstart

For most applications, use the **singleton API** with `init_config` and `get_config`:

```python
# main.py or application startup
from env_manager import init_config, get_config

# Initialize once at application startup
init_config("config/config_vars.yaml")

# Use get_config anywhere in your code
db_password = get_config("DB_PASSWORD")
api_timeout = get_config("API_TIMEOUT", 30)  # with default
```

**Key points:**

- Call `init_config()` **once** during application startup (e.g., in `main.py` or application factory).
- Use `get_config(key, default)` throughout your code to retrieve configuration values.
- Variables are automatically loaded, validated, type-coerced, and assigned to `os.environ`.
- External libraries (LangChain, LangGraph, etc.) automatically detect variables in `os.environ` without requiring additional imports.
- Type coercion is applied: `PORT` defined as `int` in YAML becomes an actual integer, not a string.

### Configuring Secret Origin

By default, `SECRET_ORIGIN` falls back to `local` and reads from `.env`. To use Google Cloud Secret Manager, set `SECRET_ORIGIN=gcp`.

**Priority order for `SECRET_ORIGIN`:**

1. Explicit parameter: `init_config(..., secret_origin="gcp")`
2. Environment variable: `export SECRET_ORIGIN=gcp`
3. `.env` file: `SECRET_ORIGIN=gcp` (automatically detected)
4. Default: `"local"`

The `.env` file is read without loading the entire file to `os.environ`, so only `SECRET_ORIGIN` and `GCP_PROJECT_ID` are detected from `.env` for configuration resolution.

## Configuration Schema

Create a YAML file matching the structure below:

```yaml
variables:
  DB_PASSWORD:
    source: DB_PASSWORD       # secret name in .env or GCP
    type: str                 # str (default), int, float, bool
    default: "optional"       # fallback if secret missing

  LOG_LEVEL:
    type: str                 # no source needed if default is always used
    default: "INFO"

validation:
  strict: false               # validate all variables before loading
  required:                   # raise immediately when missing
    - DB_PASSWORD
  optional:                   # log warning when missing
    - DEBUG_MODE
```

Guidelines:

- `variables` is a mapping of configuration keys to their source definitions.
- **`source` and `default` requirements**: Each variable must define **at least one** of `source` or `default`:
  - `source` specifies where to load the variable (from `.env` or GCP Secret Manager)
  - `default` provides a fallback value if the variable is not found
  - Both can be specified together: the variable is loaded from `source`, and `default` is used if not found
  - Variables with neither `source` nor `default` will raise a `ValueError` during initialization
- `type` controls coercion (`str`, `int`, `float`, `bool`). Defaults to `str`.
- `default` values are coerced just like loaded secrets.
- `validation.strict` enforces that every variable is present (ignores defaults).
- `validation.required` raises an error if the variable cannot be loaded.
- `validation.optional` logs a warning when the variable is absent.

## API Reference

### Singleton API (Recommended for most cases)

```python
from env_manager import init_config, get_config, require_config

# Initialize once at application startup
init_config("config/config_vars.yaml")

# Use anywhere in your code
value = get_config("VARIABLE_NAME")                    # -> value or None
value = get_config("VARIABLE_NAME", "default_value")  # -> value or provided default
value = require_config("REQUIRED_VARIABLE")            # -> raises RuntimeError if missing
```

**Why use this?**
- Simple and direct for most applications
- No wrapper or factory pattern needed
- Built-in singleton management
- Type coercion and validation included

Calling `init_config` multiple times replaces the existing singleton and emits a warning.

### Instance API (ConfigManager)

Use `ConfigManager` directly **only if** you need multiple configurations, advanced testing, or dependency injection:

```python
from env_manager import ConfigManager

manager = ConfigManager(
    config_path="config/config_vars.yaml",
    secret_origin=None,      # "local" or "gcp" (falls back to env var)
    gcp_project_id=None,     # overrides discovery from env/.env
    strict=None,             # overrides YAML strict flag
    auto_load=True,          # eagerly load and validate
    debug=False,             # set True to log raw secret values
)

manager.get("DB_PASSWORD")            # -> value or None
manager.get("DEBUG_MODE", False)      # -> value or provided default
manager.require("API_KEY")            # -> raises RuntimeError if missing
manager.values                        # -> dict of coerced values
```

## When to Use ConfigManager

**You probably don't need ConfigManager.** The singleton API (`init_config` + `get_config`) is sufficient for 90% of applications.

Use `ConfigManager` directly only in these scenarios:

### 1. Multiple Configurations Simultaneously

```python
# Load different configs for different environments
prod_config = ConfigManager("config/prod.yaml")
dev_config = ConfigManager("config/dev.yaml")

prod_db = prod_config.get("DB_PASSWORD")
dev_db = dev_config.get("DB_PASSWORD")
```

### 2. Advanced Testing with Dependency Injection

```python
class DatabaseService:
    def __init__(self, config: ConfigManager = None):
        self.config = config or ConfigManager("config/config_vars.yaml")
        self.host = self.config.get("DB_HOST")

# Easy to test with a custom config
def test_database_service():
    test_config = ConfigManager("config/test.yaml")
    service = DatabaseService(config=test_config)
    # Test in isolation
```

### 3. Complex Microservices Architecture

If you're building a large system with multiple services that need their own configurations, create a factory:

```python
# config.py
_config = None

def get_manager():
    global _config
    if _config is None:
        _config = ConfigManager("config/config_vars.yaml")
    return _config

# In your services
from config import get_manager

class MyService:
    def __init__(self):
        self.config = get_manager()
        self.db_host = self.config.get("DB_HOST")
```

**For simple applications, skip this pattern entirely and just use `init_config + get_config`.**

## Type Coercion

## Type Coercion

env-manager applies type coercion according to your YAML configuration:

- `str`: leaves values untouched.
- `int`: uses `int(value)` and raises when conversion fails.
- `float`: uses `float(value)` with failure raising `ValueError`.
- `bool`: accepts only `"true"`, `"True"`, `"1"`, `"false"`, `"False"`, `"0"`.

Both loaded values and defaults go through the same coercion path so you can rely on consistent types.

### Important: Type Coercion with get_config vs os.environ

When you use `get_config()` or `ConfigManager.get()`, you receive properly coerced types:

```python
from env_manager import init_config, get_config

init_config("config/config_vars.yaml")

# Assuming PORT is defined as type: int in YAML
port = get_config("PORT")       # → 8080 (actual int)
debug = get_config("DEBUG")     # → False (actual bool)
timeout = get_config("TIMEOUT") # → 30.5 (actual float)
```

However, variables are also assigned to `os.environ` for external libraries. Since `os.environ` only stores strings, accessing them directly returns strings:

```python
import os

# This is assigned to os.environ internally
os.environ["PORT"]   # → "8080" (string)
os.environ["DEBUG"]  # → "false" (string)

# External libraries (LangChain, LangGraph) read from os.environ
# They typically handle string parsing correctly
```

**Best practice:** Use `get_config()` for your application logic and let external libraries read from `os.environ` automatically.

## Resolving Configuration Variables

## Resolving Configuration Variables

### Variable Definition Flexibility

Each variable must define **at least one** of `source` or `default`. This provides flexibility for different use cases:

#### 1. Constants (default only)

For constant values that never change:

```yaml
variables:
  LOG_LEVEL:
    type: str
    default: "INFO"
  
  TIMEOUT:
    type: int
    default: 30
```

```python
init_config("config/config_vars.yaml")
log_level = get_config("LOG_LEVEL")   # → "INFO"
timeout = get_config("TIMEOUT")       # → 30
```

#### 2. Optional with fallback (source + default)

For variables that may or may not be present:

```yaml
variables:
  PORT:
    source: PORT
    type: int
    default: 8080
```

The loader attempts to fetch `PORT` from `.env` or GCP. If not found, it uses the `default`.

#### 3. Required from external source (source only)

For variables that must come from an external source:

```yaml
variables:
  API_KEY:
    source: API_KEY
    type: str
```

If `API_KEY` is not found, an error is raised (unless it's marked as `optional`).

### SECRET_ORIGIN Resolution

`SECRET_ORIGIN` determines whether to load secrets from local `.env` files or Google Cloud Secret Manager. It's resolved using this priority:

1. **Explicit parameter**: `init_config(..., secret_origin="gcp")`
2. **Environment variable**: `export SECRET_ORIGIN=gcp`
3. **`.env` file**: `SECRET_ORIGIN=gcp` (automatically detected without loading entire file)
4. **Default**: `"local"`

Example with `.env`:

```bash
# .env
SECRET_ORIGIN=gcp
GCP_PROJECT_ID=my-project
```

```python
from env_manager import init_config

# Automatically detects SECRET_ORIGIN=gcp from .env
init_config("config/config_vars.yaml")
```

**Priority order in action:**

```bash
# .env contains SECRET_ORIGIN=gcp

# Option 1: Uses .env value
python main.py
# Result: SECRET_ORIGIN=gcp

# Option 2: Environment variable overrides .env
export SECRET_ORIGIN=local
python main.py
# Result: SECRET_ORIGIN=local

# Option 3: Parameter overrides everything
# In code: init_config(..., secret_origin="local")
# Result: SECRET_ORIGIN=local
```

### GCP_PROJECT_ID Resolution

Similarly, `GCP_PROJECT_ID` is resolved with this priority:

1. **Explicit parameter**: `init_config(..., gcp_project_id="my-project")`
2. **Environment variable**: `export GCP_PROJECT_ID=my-project`
3. **`.env` file**: `GCP_PROJECT_ID=my-project` (automatically detected)
4. **Not set** (logs warning if needed for GCP origin)

## Validation Controls

- **Required variables**: log an error and raise immediately if absent.
- **Optional variables**: log a warning when missing but continue.
- **Strict mode**: if enabled (in YAML or via `strict=True`), the manager raises as soon as any variable lacks a value, regardless of optional/required classification.

## Secret Masking

All log statements mask secret values before emitting them:

- Secrets shorter than 10 characters render as `**********`.
- Longer secrets show the first two characters, four asterisks, and the final four characters (e.g., `ab****1234`).

This keeps logs actionable without leaking sensitive data.

Set `debug=True` when constructing `ConfigManager` (or `init_config`) to temporarily disable masking and print raw values for troubleshooting. Remember to keep this disabled in production environments.

## Migration Guide

1. Copy `config_vars.yaml.example` to your project and tailor it to your secrets.
2. Install `env-manager` and declare it in your dependencies.
3. Replace existing `python-dotenv` usage with `env_manager.init_config(...)` during service startup.
4. Swap direct `os.environ[...]` access with `get_config`/`require_config` to take advantage of validation and coercion.
5. Configure `SECRET_ORIGIN=gcp` and `GCP_PROJECT_ID` for environments that rely on Google Secret Manager.

## Troubleshooting

- **`Configuration manager not initialised`**: call `init_config` before `get_config`.
- **Missing GCP project ID**: ensure `GCP_PROJECT_ID` is supplied via init parameter, environment variable, or `.env` file.
- **Type coercion errors**: check the YAML `type` field and confirm values are parseable.
- **Secrets not found in GCP**: verify the secret name matches the YAML `source` and that credentials grant access to the project.

## Development

- Install dependencies: `poetry install` or `pip install -e .`.
- Run the test suite: `pytest -v`.
- Add new fixtures under `tests/fixtures/` as needed.

The project follows PEP 621 with Poetry, uses pytest for testing, and expects Python 3.12+.
