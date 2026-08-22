"""
Unit tests for device flow implementation.
Tests the polling state machine and device code request.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
import requests
from app.device_flow import (
    DeviceFlowClient, DeviceCodeResponse, TokenResponse,
    AccessDeniedException, TokenExpiredException, PollingTimeoutException,
    DeviceAuthorizationError
)


class TestDeviceCodeRequest:
    """Test device code request functionality."""
    
    @patch('app.device_flow.requests.post')
    def test_request_device_code_success(self, mock_post, mock_config, device_code_response):
        """Test successful device code request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = device_code_response
        mock_post.return_value = mock_response
        
        client = DeviceFlowClient(mock_config)
        response = client.request_device_code()
        
        assert response.device_code == 'test-device-code-abc123'
        assert response.user_code == 'ABCD1234'
        assert response.verification_uri == 'http://localhost:8080/auth/device'
        assert response.expires_in == 600
        assert response.interval == 2
    
    @patch('app.device_flow.requests.post')
    def test_request_device_code_network_error(self, mock_post, mock_config):
        """Test device code request with network error."""
        mock_post.side_effect = requests.RequestException("Network error")
        
        client = DeviceFlowClient(mock_config)
        with pytest.raises(DeviceAuthorizationError):
            client.request_device_code()


class TestPollingStateMachine:
    """Test the token polling state machine."""
    
    @patch('app.device_flow.requests.post')
    @patch('app.device_flow.time.sleep')
    def test_poll_success_immediate(self, mock_sleep, mock_post, mock_config, 
                                    device_code_response, token_response):
        """Test immediate success on first poll."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = token_response
        
        client = DeviceFlowClient(mock_config)
        client.device_code_response = DeviceCodeResponse(**device_code_response)
        client.created_timestamp = time.time()
        
        token = client.poll_token()
        
        assert token.access_token == token_response['access_token']
        assert token.token_type == 'Bearer'
        assert token.expires_in == 3600
    
    @patch('app.device_flow.requests.post')
    @patch('app.device_flow.time.sleep')
    def test_poll_authorization_pending(self, mock_sleep, mock_post, mock_config,
                                       device_code_response, token_response, 
                                       error_response_pending):
        """Test polling with authorization_pending response."""
        # First two calls return pending, third returns success
        pending_response = Mock()
        pending_response.status_code = 400
        pending_response.json.return_value = error_response_pending['json']
        
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = token_response
        
        mock_post.side_effect = [pending_response, pending_response, success_response]
        
        client = DeviceFlowClient(mock_config)
        client.device_code_response = DeviceCodeResponse(**device_code_response)
        client.created_timestamp = time.time()
        
        token = client.poll_token()
        
        assert token.access_token == token_response['access_token']
        assert mock_sleep.call_count == 2  # Sleep called twice for pending responses
    
    @patch('app.device_flow.requests.post')
    @patch('app.device_flow.time.sleep')
    def test_poll_slow_down(self, mock_sleep, mock_post, mock_config,
                           device_code_response, token_response,
                           error_response_slow_down):
        """Test polling with slow_down response increases interval."""
        slow_down_response = Mock()
        slow_down_response.status_code = 400
        slow_down_response.json.return_value = error_response_slow_down['json']
        
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = token_response
        
        mock_post.side_effect = [slow_down_response, success_response]
        
        client = DeviceFlowClient(mock_config)
        client.device_code_response = DeviceCodeResponse(**device_code_response)
        client.created_timestamp = time.time()
        
        token = client.poll_token()
        
        # Verify interval increased (should sleep with increased interval)
        calls = mock_sleep.call_args_list
        assert len(calls) == 1
        assert calls[0][0][0] == 7  # Initial 2 + 5 from slow_down
    
    @patch('app.device_flow.requests.post')
    def test_poll_access_denied(self, mock_post, mock_config, device_code_response,
                               error_response_access_denied):
        """Test polling when user denies access."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = error_response_access_denied['json']
        mock_post.return_value = mock_response
        
        client = DeviceFlowClient(mock_config)
        client.device_code_response = DeviceCodeResponse(**device_code_response)
        client.created_timestamp = time.time()
        
        with pytest.raises(AccessDeniedException):
            client.poll_token()
    
    @patch('app.device_flow.requests.post')
    def test_poll_expired_token(self, mock_post, mock_config, device_code_response,
                               error_response_expired_token):
        """Test polling when device code has expired."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = error_response_expired_token['json']
        mock_post.return_value = mock_response
        
        client = DeviceFlowClient(mock_config)
        client.device_code_response = DeviceCodeResponse(**device_code_response)
        client.created_timestamp = time.time()
        
        with pytest.raises(TokenExpiredException):
            client.poll_token()
    
    @patch('app.device_flow.requests.post')
    @patch('app.device_flow.time.sleep')
    @patch('app.device_flow.time.time')
    def test_poll_timeout(self, mock_time, mock_sleep, mock_post, mock_config,
                         device_code_response, error_response_pending):
        """Test polling timeout after exceeding max time."""
        # Mock time to simulate timeout
        mock_time.side_effect = [0, 1, 2, 31, 31, 31]  # Extra values cover logging's internal time.time() calls
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = error_response_pending['json']
        mock_post.return_value = mock_response
        
        client = DeviceFlowClient(mock_config)
        client.device_code_response = DeviceCodeResponse(**device_code_response, created_at=0)
        client.created_timestamp = 0
        
        with pytest.raises(PollingTimeoutException):
            client.poll_token()
    
    @patch('app.device_flow.requests.post')
    @patch('app.device_flow.time.sleep')
    def test_poll_without_device_code(self, mock_sleep, mock_post, mock_config):
        """Test polling without requesting device code first."""
        client = DeviceFlowClient(mock_config)
        
        with pytest.raises(DeviceAuthorizationError):
            client.poll_token()


class TestTokenResponse:
    """Test TokenResponse dataclass."""
    
    def test_token_response_creation(self, token_response):
        """Test creating a token response object."""
        token = TokenResponse(
            access_token=token_response['access_token'],
            token_type=token_response['token_type'],
            expires_in=token_response['expires_in'],
            refresh_token=token_response['refresh_token'],
            scope=token_response['scope']
        )
        
        assert token.access_token == token_response['access_token']
        assert token.expires_in == 3600
        assert token.refresh_token is not None
