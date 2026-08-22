"""
Configuration management for the device authorization grant client.
Loads all settings from environment variables with sensible defaults.
"""

import logging
from pydantic_settings import BaseSettings
from pydantic import Field


class Config(BaseSettings):
    """Application configuration from environment variables."""
    
    # Keycloak configuration
    keycloak_realm: str = Field(default="device-grant-demo", alias="KEYCLOAK_REALM")
    keycloak_client_id: str = Field(default="device-client", alias="KEYCLOAK_CLIENT_ID")
    keycloak_url: str = Field(default="http://keycloak:8080", alias="KEYCLOAK_URL")
    
    # Device flow configuration
    device_code_lifetime: int = Field(default=600, alias="DEVICE_CODE_LIFETIME")
    poll_timeout: int = Field(default=30, alias="POLL_TIMEOUT")
    polling_interval_min: int = Field(default=2, alias="POLLING_INTERVAL_MIN")
    polling_interval_max: int = Field(default=120, alias="POLLING_INTERVAL_MAX")
    
    # Token storage
    token_storage_path: str = Field(default="/data/tokens.json", alias="TOKEN_STORAGE_PATH")
    
    # Web UI configuration
    web_ui_port: int = Field(default=8000, alias="WEB_UI_PORT")
    web_ui_host: str = Field(default="0.0.0.0", alias="WEB_UI_HOST")
    
    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def device_auth_endpoint(self) -> str:
        """Construct the device authorization endpoint URL."""
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/auth/device"
    
    @property
    def token_endpoint(self) -> str:
        """Construct the token endpoint URL."""
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/token"
    
    @property
    def revoke_endpoint(self) -> str:
        """Construct the token revocation endpoint URL."""
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/revoke"
    
    @property
    def userinfo_endpoint(self) -> str:
        """Construct the userinfo endpoint URL."""
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/userinfo"


def get_config() -> Config:
    """Get or create application configuration."""
    return Config()


def setup_logging(config: Config) -> None:
    """Configure logging based on config settings."""
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
