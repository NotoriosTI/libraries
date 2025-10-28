# env-manager

A simple, environment-aware configuration manager that unifies secrets from local `.env` files and Google Cloud Secret Manager. It handles type coercion, validation, secret masking, and automatically loads variables to `os.environ` so external libraries work seamlessly.

## Installation

Add to your `pyproject.toml`:

```toml
[project]
dependencies = [
    "env-manager @ git+https://github.com/NotoriosTI/libraries.git@main#subdirectory=env-manager",
]
```

Then install with Poetry or pip.

## Quickstart

### Basic Usage (Recommended)

The singleton pattern is the simplest way to use env-manager:

```python
# main.py - Initialize once at startup
from env_manager import init_config, get_config

init_config("config/config_vars.yaml")

# Now use anywhere in your codebase
db_password = get_config("DB_PASSWORD")
api_timeout = get_config("API_TIMEOUT", 30)  # with default
```

**What happens automatically:**
- Variables are loaded from `.env` or GCP Secret Manager
- Type coercion is applied (strings → int/float/bool as configured)
- Values are validated (required vs optional)
- Everything is assigned to `os.environ`
- External libraries (LangChain, LangGraph, etc.) work automatically

**Example:**
```python
# config_vars.yaml defines PORT as type: int
init_config("config/config_vars.yaml")

port = get_config("PORT")  # → 8080 (actual int, not string)
# os.environ["PORT"] is now "8080" (string, for external libraries)
```

### Secret Sources

By default, secrets are loaded from `.env` files. To use Google Cloud Secret Manager, set `SECRET_ORIGIN=gcp`.

**Priority order:**
1. Explicit parameter: `init_config(..., secret_origin="gcp")`
2. Environment variable: `export SECRET_ORIGIN=gcp`
3. `.env` file: `SECRET_ORIGIN=gcp`
4. Default: `"local"`


## Configuration File

Create a YAML file (e.g., `config_vars.yaml`) with this structure:

```yaml
variables:
  # Required secret (must exist in .env or GCP)
  DB_PASSWORD:
    source: DB_PASSWORD
    type: str

  # Optional with fallback
  PORT:
    source: PORT
    type: int
    default: 8080

  # Constant (no external source needed)
  LOG_LEVEL:
    type: str
    default: "INFO"

validation:
  strict: false
  required:
    - DB_PASSWORD    # Error if missing
  optional:
    - DEBUG_MODE     # Warning if missing
```

### Variable Definition Rules

Each variable must have **at least one** of:
- `source`: Name of the secret in `.env` or GCP Secret Manager
- `default`: Fallback value if not found

**Type coercion** (`type` field):
- `str` (default): No conversion
- `int`: Converts to integer
- `float`: Converts to float
- `bool`: Accepts only `"true"`, `"True"`, `"1"`, `"false"`, `"False"`, `"0"`

**Validation** (`validation` section):
- `required`: Raises error if variable is missing
- `optional`: Logs warning if variable is missing
- `strict: true`: Enforces all variables must have values (ignores defaults)

## Complete API Reference

### Singleton API (Recommended)

```python
from env_manager import init_config, get_config, require_config

# Initialize once
init_config(
    "config/config_vars.yaml",
    secret_origin=None,      # "local" or "gcp" (auto-detected if None)
    gcp_project_id=None,     # Required if secret_origin="gcp"
    strict=None,             # Override YAML strict setting
    dotenv_path=None,        # Custom .env path (auto-detected if None)
    debug=False,             # Show raw secrets in logs (NEVER in production)
)

# Use anywhere
value = get_config("KEY")                  # Returns value or None
value = get_config("KEY", "default")       # Returns value or provided default
value = require_config("REQUIRED_KEY")     # Raises RuntimeError if missing
```

### Instance API (Advanced)

**When to use ConfigManager directly:**
- Multiple configurations simultaneously
- Advanced testing with dependency injection
- Complex microservices architectures

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

manager.get("DB_PASSWORD")        # Returns value or None
manager.get("PORT", 8080)         # Returns value or provided default
manager.require("API_KEY")        # Raises RuntimeError if missing
manager.values                    # Dict of all loaded values
```

**Example: Multiple configurations**
```python
prod_config = ConfigManager("config/prod.yaml", secret_origin="gcp")
dev_config = ConfigManager("config/dev.yaml", secret_origin="local")

prod_db = prod_config.get("DB_PASSWORD")
dev_db = dev_config.get("DB_PASSWORD")
```

**Example: Testing with dependency injection**
```python
class DatabaseService:
    def __init__(self, config: ConfigManager = None):
        self.config = config or ConfigManager("config/config_vars.yaml")
        self.host = self.config.get("DB_HOST")

def test_database_service():
    test_config = ConfigManager("config/test.yaml")
    service = DatabaseService(config=test_config)
    # Test in isolation
```

## How It Works

### Automatic Environment Loading

When you call `init_config()` or create a `ConfigManager`:

1. **Configuration is parsed** from YAML
2. **Secrets are fetched** from `.env` or GCP Secret Manager
3. **Types are coerced** according to YAML definitions
4. **Values are validated** (required/optional checks)
5. **Variables are assigned to `os.environ`** automatically
6. **Secrets are masked** in all log output

This means external libraries that read from `os.environ` (like LangChain, LangGraph, etc.) work automatically without any additional setup.

### Type Coercion Details

**When you use `get_config()`:** You get the properly typed value
```python
port = get_config("PORT")  # → 8080 (int)
debug = get_config("DEBUG")  # → False (bool)
```

**When external libraries read `os.environ`:** They get strings
```python
os.environ["PORT"]   # → "8080" (string)
os.environ["DEBUG"]  # → "false" (string)
```

This is intentional - `os.environ` only stores strings, but external libraries handle string parsing correctly.

### SECRET_ORIGIN Resolution

The `SECRET_ORIGIN` determines where to load secrets from:

**Priority (highest to lowest):**
1. Explicit parameter: `init_config(..., secret_origin="gcp")`
2. Environment variable: `export SECRET_ORIGIN=gcp`
3. `.env` file: `SECRET_ORIGIN=gcp` (read without loading entire file)
4. Default: `"local"`

**Example:**
```bash
# .env file
SECRET_ORIGIN=gcp
GCP_PROJECT_ID=my-project
```

```python
# Automatically uses GCP from .env
init_config("config/config_vars.yaml")
```

### GCP_PROJECT_ID Resolution

When using `secret_origin="gcp"`, the GCP project ID is resolved with:

1. Explicit parameter: `init_config(..., gcp_project_id="my-project")`
2. Environment variable: `export GCP_PROJECT_ID=my-project`
3. `.env` file: `GCP_PROJECT_ID=my-project`
4. Not set (warning logged)

## Secret Masking

All secrets are automatically masked in logs for security:

- **Short secrets** (< 10 chars): `**********`
- **Long secrets**: `ab****1234` (first 2 + last 4 chars shown)

Set `debug=True` to temporarily see raw values (never use in production):

```python
init_config("config/config_vars.yaml", debug=True)
```

## Migration Guide

If you're migrating from `python-dotenv` or manual `os.environ` usage:

1. **Copy** `config_vars.yaml.example` to your project
2. **Customize** the YAML with your variables
3. **Install** env-manager in your dependencies
4. **Replace** `load_dotenv()` with `init_config("config/config_vars.yaml")`
5. **Replace** `os.environ["KEY"]` with `get_config("KEY")`
6. **Configure** `SECRET_ORIGIN=gcp` and `GCP_PROJECT_ID` for production

**Before:**
```python
from dotenv import load_dotenv
import os

load_dotenv()
db_password = os.environ["DB_PASSWORD"]
port = int(os.environ.get("PORT", "8080"))
```

**After:**
```python
from env_manager import init_config, get_config

init_config("config/config_vars.yaml")
db_password = get_config("DB_PASSWORD")
port = get_config("PORT")  # Already an int, with default 8080
```

## Troubleshooting

**`Configuration manager not initialised`**
- Call `init_config()` before using `get_config()` or `require_config()`

**`Missing GCP project ID`**
- Set `GCP_PROJECT_ID` via parameter, environment variable, or `.env` file

**`Type coercion failed`**
- Check the YAML `type` field matches your value format
- Ensure boolean values are exactly `"true"`, `"false"`, `"1"`, or `"0"`

**`Required variable not found`**
- Verify the secret exists in `.env` or GCP Secret Manager
- Check the secret name matches the YAML `source` field
- Ensure GCP credentials have access to the project

**Variables not loaded**
- Confirm `init_config()` was called successfully
- Check logs for warnings or errors
- Verify `.env` file exists and is in the correct location

## Development

```bash
# Install dependencies
poetry install

# Run tests
pytest -v

# Run with coverage
pytest --cov=env_manager --cov-report=html
```

The project uses Python 3.12+, Poetry for dependency management, and pytest for testing.

## License

Internal NotoriosTI library.

