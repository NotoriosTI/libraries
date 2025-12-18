from env_manager import init_config
from pathlib import Path

PROJECT_ROOT = Path.cwd()
DOTENV_PATH = PROJECT_ROOT / ".env"
CONFIG_PATH = PROJECT_ROOT / "tests" / "supply" / "test_vars.yaml"

init_config(config_path=CONFIG_PATH, dotenv_path=DOTENV_PATH)
