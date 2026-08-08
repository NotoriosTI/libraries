"""Acceso a configuración vía env-manager.

Reemplaza al `config_manager` de este mismo repo, que quedó deprecado y sólo
sabe leer secretos sueltos de Secret Manager — precisamente los que se
eliminaron al consolidar en un JSON por app.

El entorno activo lo decide `APP_ENV`; ver `config/config_vars.yaml`.
"""

from pathlib import Path

from env_manager import get_config, init_config

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config_vars.yaml"


class _Secrets:
    """Expone las variables como atributos, igual que el `secrets` anterior.

    La inicialización es perezosa y ocurre una sola vez: importar este módulo no
    debe golpear Secret Manager, para que los tests puedan importarlo sin
    credenciales.
    """

    _initialized = False

    def __getattr__(self, name: str):
        if not _Secrets._initialized:
            init_config(str(CONFIG_PATH))
            _Secrets._initialized = True
        return get_config(name)


secrets = _Secrets()
