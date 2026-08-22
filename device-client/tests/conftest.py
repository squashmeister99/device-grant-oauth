"""
Pytest configuration and fixtures for device grant tests.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile


@pytest.fixture
def temp_token_file():
    """Create a temporary token storage file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = Mock()
    config.keycloak_realm = 'test-realm'
    config.keycloak_client_id = 'test-client'
    config.keycloak_url = 'http://localhost:8080'
    config.keycloak_scopes = 'openid profile email'
    config.device_code_lifetime = 600
    config.poll_timeout = 30
    config.polling_interval_min = 2
    config.polling_interval_max = 120
    config.token_storage_path = tempfile.mktemp(suffix='.json')
    config.web_ui_port = 8000
    config.web_ui_host = '0.0.0.0'
    config.log_level = 'INFO'
    
    config.device_auth_endpoint = 'http://localhost:8080/realms/test-realm/protocol/openid-connect/auth/device'
    config.token_endpoint = 'http://localhost:8080/realms/test-realm/protocol/openid-connect/token'
    config.revoke_endpoint = 'http://localhost:8080/realms/test-realm/protocol/openid-connect/revoke'
    config.userinfo_endpoint = 'http://localhost:8080/realms/test-realm/protocol/openid-connect/userinfo'
    
    yield config
    # Cleanup
    Path(config.token_storage_path).unlink(missing_ok=True)


@pytest.fixture
def device_code_response():
    """Create a mock device code response."""
    return {
        'device_code': 'test-device-code-abc123',
        'user_code': 'ABCD1234',
        'verification_uri': 'http://localhost:8080/auth/device',
        'verification_uri_complete': 'http://localhost:8080/auth/device?user_code=ABCD1234',
        'expires_in': 600,
        'interval': 2
    }


@pytest.fixture
def token_response():
    """Create a mock token response."""
    return {
        'access_token': 'eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJrZXkifQ.eyJzdWIiOiJ1c2VyMTIzIiwicHJlZmVycmVkX3VzZXJuYW1lIjoidGVzdHVzZXIiLCJlbWFpbCI6InRlc3R1c2VyQGV4YW1wbGUuY29tIiwiZXhwIjoyMDAwMDAwMDAwfQ.test',
        'token_type': 'Bearer',
        'expires_in': 3600,
        'refresh_token': 'test-refresh-token-xyz789',
        'scope': 'openid profile email'
    }


@pytest.fixture
def error_response_pending():
    """Mock pending authorization response."""
    return {
        'status_code': 400,
        'json': {'error': 'authorization_pending', 'error_description': 'The authorization request is still pending'}
    }


@pytest.fixture
def error_response_slow_down():
    """Mock slow down response."""
    return {
        'status_code': 400,
        'json': {'error': 'slow_down', 'error_description': 'Too fast polling'}
    }


@pytest.fixture
def error_response_access_denied():
    """Mock access denied response."""
    return {
        'status_code': 400,
        'json': {'error': 'access_denied', 'error_description': 'User denied access'}
    }


@pytest.fixture
def error_response_expired_token():
    """Mock expired token response."""
    return {
        'status_code': 400,
        'json': {'error': 'expired_token', 'error_description': 'Device code has expired'}
    }
