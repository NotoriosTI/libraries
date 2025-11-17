"""Test optional source in variable definitions."""

import tempfile
from pathlib import Path
from env_manager import ConfigManager


def test_variable_with_only_default():
    """Test that a variable can be defined with only a default, no source."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML with only default, no source
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  LOG_LEVEL:
    type: str
    default: "INFO"
  
  DEBUG_MODE:
    type: bool
    default: false

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
        
        # Verify defaults are used
        assert manager.get("LOG_LEVEL") == "INFO"
        assert manager.get("DEBUG_MODE") is False


def test_variable_with_source_and_default():
    """Test that a variable with both source and default uses source when available."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  PORT:
    source: PORT
    type: int
    default: 8080

validation:
  strict: false
""")
        
        # Create .env with PORT value
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("PORT=9000\n")
        
        # Create ConfigManager
        manager = ConfigManager(
            str(config_yaml),
            dotenv_path=str(dotenv_file),
            auto_load=True
        )
        
        # Should use value from .env, not default
        assert manager.get("PORT") == 9000


def test_variable_with_source_and_default_fallback():
    """Test that default is used when source is not found."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  PORT:
    source: PORT
    type: int
    default: 8080

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
        
        # Should use default since PORT not in .env
        assert manager.get("PORT") == 8080


def test_variable_with_neither_source_nor_default_raises():
    """Test that variable without source or default raises error."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML with neither source nor default
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  INVALID_VAR:
    type: str

validation:
  strict: false
""")
        
        # Create empty .env
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("")
        
        # Should raise ValueError when calling load()
        try:
            manager = ConfigManager(
                str(config_yaml),
                dotenv_path=str(dotenv_file),
                auto_load=True  # This calls load()
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "must define either 'source' or 'default'" in str(e)


def test_variable_with_empty_source_but_with_default():
    """Test that variable with empty source but with default uses default."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  TIMEOUT:
    type: int
    default: 30

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
        
        # Should use default
        assert manager.get("TIMEOUT") == 30
