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

```python
from env_manager import init_config, get_config

init_config("config/config_vars.yaml")
db_password = get_config("DB_PASSWORD")
```

The configuration file defines which secrets to load and how to coerce them. By default, `SECRET_ORIGIN` falls back to `local` and reads from `.env`. Set `SECRET_ORIGIN=gcp` to fetch secrets from Google Secret Manager instead.

## Configuration Schema

Create a YAML file matching the structure below:

```yaml
variables:
  DB_PASSWORD:
    source: DB_PASSWORD       # secret name in .env or GCP
    type: str                 # str (default), int, float, bool
    default: "optional"       # fallback if secret missing

validation:
  strict: false               # validate all variables before loading
  required:                   # raise immediately when missing
    - DB_PASSWORD
  optional:                   # log warning when missing
    - DEBUG_MODE
```

Guidelines:

- `variables` is a mapping of configuration keys to their source definitions.
- `source` names the underlying secret identifier.
- `type` controls coercion (`str`, `int`, `float`, `bool`). Defaults to `str`.
- `default` values are coerced just like loaded secrets.
- `validation.strict` enforces that every variable is present (ignores defaults).
- `validation.required` raises an error if the variable cannot be loaded.
- `validation.optional` logs a warning when the variable is absent.

## API Reference

### Instance API

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
manager.values                          # -> dict of coerced values
```

### Singleton API

```python
from env_manager import init_config, get_config, require_config

init_config("config/config_vars.yaml")
get_config("PORT", 8080)
require_config("DB_PASSWORD")
```

Calling `init_config` multiple times replaces the existing singleton and emits a warning. Use this pattern when you want application-wide access without passing around instances.

## Type Coercion

- `str`: leaves values untouched.
- `int`: uses `int(value)` and raises when conversion fails.
- `float`: uses `float(value)` with failure raising `ValueError`.
- `bool`: accepts only `"true"`, `"True"`, `"1"`, `"false"`, `"False"`, `"0"`.

Both loaded values and defaults go through the same coercion path so you can rely on consistent types.

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
