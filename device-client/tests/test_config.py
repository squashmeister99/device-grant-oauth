"""
Unit tests for configuration module.
Tests config loading, validation, and defaults.
"""

import pytest
import os
from unittest.mock import patch
from app.config import Config, get_config, setup_logging


class TestConfigDefaults:
    """Test configuration defaults."""
    
    def test_default_values(self):
        """Test that default values are used when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            
            assert config.keycloak_realm == "device-grant-demo"
            assert config.keycloak_client_id == "device-client"
            assert config.keycloak_url == "http://keycloak:8080"
            assert config.device_code_lifetime == 600
            assert config.poll_timeout == 30
            assert config.polling_interval_min == 2
            assert config.polling_interval_max == 120
            assert config.token_storage_path == "/data/tokens.json"
            assert config.web_ui_port == 8000
            assert config.web_ui_host == "0.0.0.0"
            assert config.log_level == "INFO"


class TestConfigEnvVars:
    """Test configuration loading from environment variables."""
    
    def test_load_from_env_vars(self):
        """Test loading config from environment variables."""
        env_vars = {
            'KEYCLOAK_REALM': 'custom-realm',
            'KEYCLOAK_CLIENT_ID': 'custom-client',
            'KEYCLOAK_URL': 'https://auth.example.com',
            'DEVICE_CODE_LIFETIME': '1200',
            'POLL_TIMEOUT': '60',
            'POLLING_INTERVAL_MIN': '5',
            'POLLING_INTERVAL_MAX': '60',
            'TOKEN_STORAGE_PATH': '/custom/path/tokens.json',
            'WEB_UI_PORT': '9000',
            'WEB_UI_HOST': '127.0.0.1',
            'LOG_LEVEL': 'DEBUG'
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config()
            
            assert config.keycloak_realm == 'custom-realm'
            assert config.keycloak_client_id == 'custom-client'
            assert config.keycloak_url == 'https://auth.example.com'
            assert config.device_code_lifetime == 1200
            assert config.poll_timeout == 60
            assert config.polling_interval_min == 5
            assert config.polling_interval_max == 60
            assert config.token_storage_path == '/custom/path/tokens.json'
            assert config.web_ui_port == 9000
            assert config.web_ui_host == '127.0.0.1'
            assert config.log_level == 'DEBUG'


class TestConfigEndpoints:
    """Test computed endpoint properties."""
    
    def test_device_auth_endpoint(self):
        """Test device authorization endpoint construction."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            
            expected = 'http://keycloak:8080/realms/device-grant-demo/protocol/openid-connect/auth/device'
            assert config.device_auth_endpoint == expected
    
    def test_token_endpoint(self):
        """Test token endpoint construction."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            
            expected = 'http://keycloak:8080/realms/device-grant-demo/protocol/openid-connect/token'
            assert config.token_endpoint == expected
    
    def test_revoke_endpoint(self):
        """Test revocation endpoint construction."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            
            expected = 'http://keycloak:8080/realms/device-grant-demo/protocol/openid-connect/revoke'
            assert config.revoke_endpoint == expected
    
    def test_userinfo_endpoint(self):
        """Test userinfo endpoint construction."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            
            expected = 'http://keycloak:8080/realms/device-grant-demo/protocol/openid-connect/userinfo'
            assert config.userinfo_endpoint == expected
    
    def test_endpoints_with_custom_url(self):
        """Test endpoints with custom Keycloak URL."""
        env_vars = {
            'KEYCLOAK_URL': 'https://auth.example.com',
            'KEYCLOAK_REALM': 'production'
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config()
            
            assert config.device_auth_endpoint.startswith('https://auth.example.com')
            assert 'production' in config.device_auth_endpoint
            assert '/protocol/openid-connect/auth/device' in config.device_auth_endpoint


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_invalid_port(self):
        """Test validation of invalid port number."""
        env_vars = {'WEB_UI_PORT': 'not-a-number'}
        
        with patch.dict(os.environ, env_vars):
            with pytest.raises(Exception):  # Pydantic validation error
                Config()
    
    def test_invalid_timeout(self):
        """Test validation of invalid timeout."""
        env_vars = {'POLL_TIMEOUT': 'invalid'}
        
        with patch.dict(os.environ, env_vars):
            with pytest.raises(Exception):  # Pydantic validation error
                Config()


class TestGetConfig:
    """Test the get_config factory function."""
    
    def test_get_config_returns_config_instance(self):
        """Test that get_config returns a Config instance."""
        with patch.dict(os.environ, {}, clear=True):
            config = get_config()
            
            assert isinstance(config, Config)
            assert hasattr(config, 'keycloak_url')
            assert hasattr(config, 'device_code_lifetime')


class TestSetupLogging:
    """Test logging setup."""
    
    def test_setup_logging_info_level(self):
        """Test logging setup with INFO level."""
        with patch.dict(os.environ, {'LOG_LEVEL': 'INFO'}):
            config = Config()
            # Should not raise any errors
            setup_logging(config)
    
    def test_setup_logging_debug_level(self):
        """Test logging setup with DEBUG level."""
        with patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG'}):
            config = Config()
            # Should not raise any errors
            setup_logging(config)
    
    def test_setup_logging_error_level(self):
        """Test logging setup with ERROR level."""
        with patch.dict(os.environ, {'LOG_LEVEL': 'ERROR'}):
            config = Config()
            # Should not raise any errors
            setup_logging(config)
