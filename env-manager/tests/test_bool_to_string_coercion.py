"""Test boolean to string coercion when type is str."""

import tempfile
from pathlib import Path
from env_manager import ConfigManager


def test_bool_yaml_to_string_true():
    """Test that YAML boolean true is converted to string 'true' when type is str."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML with boolean true (no quotes)
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  DEBUG_MODE:
    default: true
    type: str

validation:
  strict: false
""")
        
        # Create empty .env
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("")
        
        # Create ConfigManager
        manager = ConfigManager(
            str(config_yaml),
            dotenv_path=str(dotenv_file),
            auto_load=True
        )
        
        # Should be string "true", not "True" or boolean True
        result = manager.get("DEBUG_MODE")
        assert result == "true"
        assert isinstance(result, str)


def test_bool_yaml_to_string_false():
    """Test that YAML boolean false is converted to string 'false' when type is str."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML with boolean false (no quotes)
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  TRACING:
    default: false
    type: str

validation:
  strict: false
""")
        
        # Create empty .env
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("")
        
        # Create ConfigManager
        manager = ConfigManager(
            str(config_yaml),
            dotenv_path=str(dotenv_file),
            auto_load=True
        )
        
        # Should be string "false", not "False" or boolean False
        result = manager.get("TRACING")
        assert result == "false"
        assert isinstance(result, str)


def test_bool_yaml_with_bool_type():
    """Test that YAML boolean is preserved as bool when type is bool."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML with boolean and type: bool
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  ENABLED:
    default: true
    type: bool

validation:
  strict: false
""")
        
        # Create empty .env
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("")
        
        # Create ConfigManager
        manager = ConfigManager(
            str(config_yaml),
            dotenv_path=str(dotenv_file),
            auto_load=True
        )
        
        # Should be boolean True
        result = manager.get("ENABLED")
        assert result is True
        assert isinstance(result, bool)


def test_string_true_to_string():
    """Test that YAML string 'true' stays as string when type is str."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML with quoted "true"
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  VALUE:
    default: "true"
    type: str

validation:
  strict: false
""")
        
        # Create empty .env
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("")
        
        # Create ConfigManager
        manager = ConfigManager(
            str(config_yaml),
            dotenv_path=str(dotenv_file),
            auto_load=True
        )
        
        # Should be string "true"
        result = manager.get("VALUE")
        assert result == "true"
        assert isinstance(result, str)


def test_number_to_string():
    """Test that YAML numbers are converted to string when type is str."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML with number
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  PORT:
    default: 8080
    type: str

validation:
  strict: false
""")
        
        # Create empty .env
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("")
        
        # Create ConfigManager
        manager = ConfigManager(
            str(config_yaml),
            dotenv_path=str(dotenv_file),
            auto_load=True
        )
        
        # Should be string "8080"
        result = manager.get("PORT")
        assert result == "8080"
        assert isinstance(result, str)
