"""Test SECRET_ORIGIN detection from .env file."""

import os
import tempfile
from pathlib import Path
from env_manager import ConfigManager


def test_secret_origin_from_dotenv():
    """Test that SECRET_ORIGIN is detected from .env without explicit parameter."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  TEST_VAR:
    source: TEST_VAR
    type: str
    default: "test_value"

validation:
  strict: false
""")
        
        # Create .env with SECRET_ORIGIN
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("SECRET_ORIGIN=gcp\nGCP_PROJECT_ID=test-project\n")
        
        # Create ConfigManager without explicit secret_origin
        manager = ConfigManager(
            str(config_yaml),
            dotenv_path=str(dotenv_file),
            auto_load=False  # Don't try to connect to GCP
        )
        
        # Verify that SECRET_ORIGIN was detected from .env
        assert manager.secret_origin == "gcp"
        assert manager.gcp_project_id == "test-project"


def test_secret_origin_parameter_overrides_dotenv():
    """Test that explicit parameter overrides .env value."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  TEST_VAR:
    source: TEST_VAR
    type: str
    default: "test_value"

validation:
  strict: false
""")
        
        # Create .env with SECRET_ORIGIN=gcp
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("SECRET_ORIGIN=gcp\n")
        
        # Create ConfigManager with explicit secret_origin="local"
        manager = ConfigManager(
            str(config_yaml),
            dotenv_path=str(dotenv_file),
            secret_origin="local",  # Override .env
            auto_load=False
        )
        
        # Verify that parameter overrides .env
        assert manager.secret_origin == "local"


def test_secret_origin_env_var_overrides_dotenv():
    """Test that environment variable overrides .env value."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  TEST_VAR:
    source: TEST_VAR
    type: str
    default: "test_value"

validation:
  strict: false
""")
        
        # Create .env with SECRET_ORIGIN=gcp
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("SECRET_ORIGIN=gcp\n")
        
        # Set environment variable
        os.environ["SECRET_ORIGIN"] = "local"
        
        try:
            # Create ConfigManager without explicit parameter
            manager = ConfigManager(
                str(config_yaml),
                dotenv_path=str(dotenv_file),
                auto_load=False
            )
            
            # Verify that env var overrides .env
            assert manager.secret_origin == "local"
        finally:
            # Clean up
            del os.environ["SECRET_ORIGIN"]


def test_secret_origin_defaults_to_local():
    """Test that SECRET_ORIGIN defaults to 'local' when not specified."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create config YAML
        config_yaml = tmpdir / "config.yaml"
        config_yaml.write_text("""
variables:
  TEST_VAR:
    source: TEST_VAR
    type: str
    default: "test_value"

validation:
  strict: false
""")
        
        # Create .env without SECRET_ORIGIN
        dotenv_file = tmpdir / ".env"
        dotenv_file.write_text("SOME_VAR=value\n")
        
        # Create ConfigManager without any specification
        manager = ConfigManager(
            str(config_yaml),
            dotenv_path=str(dotenv_file),
            auto_load=False
        )
        
        # Verify default
        assert manager.secret_origin == "local"
