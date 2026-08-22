"""
Unit tests for token store functionality.
Tests token persistence, refresh, and revocation.
"""

import pytest
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch
from app.token_store import (
    TokenStore, TokenStoreError, TokenExpiredError, NoTokenError
)


class TestTokenStoreSave:
    """Test token save functionality."""
    
    def test_save_tokens(self, mock_config):
        """Test saving tokens to file."""
        store = TokenStore(mock_config)
        
        store.save_tokens(
            access_token='test-access-token',
            refresh_token='test-refresh-token',
            expires_in=3600
        )
        
        # Verify file was created
        assert Path(mock_config.token_storage_path).exists()
        
        # Verify content
        with open(mock_config.token_storage_path, 'r') as f:
            data = json.load(f)
        
        assert data['access_token'] == 'test-access-token'
        assert data['refresh_token'] == 'test-refresh-token'
        assert data['token_type'] == 'Bearer'
        assert 'expires_at' in data
        assert 'saved_at' in data
    
    def test_save_tokens_creates_directory(self, mock_config):
        """Test that save_tokens creates parent directory if needed."""
        # Use a nested path
        mock_config.token_storage_path = '/tmp/deeply/nested/path/tokens.json'
        store = TokenStore(mock_config)
        
        store.save_tokens(
            access_token='test-token',
            refresh_token='test-refresh',
            expires_in=3600
        )
        
        assert Path(mock_config.token_storage_path).exists()
        Path(mock_config.token_storage_path).unlink()
        Path('/tmp/deeply/nested/path').rmdir()
        Path('/tmp/deeply/nested').rmdir()
        Path('/tmp/deeply').rmdir()


class TestTokenStoreLoad:
    """Test token load functionality."""
    
    def test_load_valid_tokens(self, mock_config):
        """Test loading valid tokens from file."""
        store = TokenStore(mock_config)
        
        # Save tokens first
        store.save_tokens(
            access_token='test-access-token',
            refresh_token='test-refresh-token',
            expires_in=3600
        )
        
        # Load tokens
        data = store.load_tokens()
        
        assert data['access_token'] == 'test-access-token'
        assert data['refresh_token'] == 'test-refresh-token'
    
    def test_load_nonexistent_tokens(self, mock_config):
        """Test loading tokens when file doesn't exist."""
        store = TokenStore(mock_config)
        
        with pytest.raises(NoTokenError):
            store.load_tokens()
    
    def test_load_expired_tokens(self, mock_config):
        """Test loading tokens that have expired."""
        store = TokenStore(mock_config)
        
        # Save tokens with very short expiry
        store.save_tokens(
            access_token='test-token',
            refresh_token='test-refresh',
            expires_in=0  # Expired immediately
        )
        
        with pytest.raises(TokenExpiredError):
            store.load_tokens()
    
    def test_load_invalid_json(self, mock_config):
        """Test loading invalid JSON file."""
        store = TokenStore(mock_config)
        
        # Write invalid JSON
        with open(mock_config.token_storage_path, 'w') as f:
            f.write('{ invalid json }')
        
        with pytest.raises(TokenStoreError):
            store.load_tokens()


class TestTokenExpiry:
    """Test token expiry checking."""
    
    def test_is_token_expired_valid(self, mock_config):
        """Test is_token_expired with valid token."""
        store = TokenStore(mock_config)
        
        store.save_tokens(
            access_token='test-token',
            refresh_token='test-refresh',
            expires_in=3600  # 1 hour
        )
        
        assert not store.is_token_expired()
    
    def test_is_token_expired_expired(self, mock_config):
        """Test is_token_expired with expired token."""
        store = TokenStore(mock_config)
        
        store.save_tokens(
            access_token='test-token',
            refresh_token='test-refresh',
            expires_in=0  # Already expired
        )
        
        assert store.is_token_expired()
    
    def test_is_token_expired_no_token(self, mock_config):
        """Test is_token_expired when no token exists."""
        store = TokenStore(mock_config)
        
        assert store.is_token_expired()
    
    def test_is_token_expired_with_buffer(self, mock_config):
        """Test is_token_expired with custom expiry buffer."""
        store = TokenStore(mock_config)
        
        # Token expires in 10 seconds
        store.save_tokens(
            access_token='test-token',
            refresh_token='test-refresh',
            expires_in=10
        )
        
        # With 30s buffer, should be expired
        assert store.is_token_expired(expiry_buffer=30)
        
        # With 5s buffer, should not be expired
        assert not store.is_token_expired(expiry_buffer=5)


class TestTokenRefresh:
    """Test token refresh functionality."""
    
    @patch('app.token_store.requests.post')
    def test_refresh_tokens_success(self, mock_post, mock_config, token_response):
        """Test successful token refresh."""
        store = TokenStore(mock_config)
        
        # Save initial tokens
        store.save_tokens(
            access_token='old-access-token',
            refresh_token='old-refresh-token',
            expires_in=3600
        )
        
        # Mock the refresh response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response
        
        result = store.refresh_tokens()
        
        assert result['access_token'] == 'new-access-token'
        assert result['refresh_token'] == 'new-refresh-token'
        
        # Verify new tokens were saved
        data = store.load_tokens()
        assert data['access_token'] == 'new-access-token'
    
    @patch('app.token_store.requests.post')
    def test_refresh_with_token_rotation(self, mock_post, mock_config):
        """Test token refresh with refresh token rotation."""
        store = TokenStore(mock_config)
        
        # Save initial tokens
        store.save_tokens(
            access_token='old-access-token',
            refresh_token='old-refresh-token',
            expires_in=3600
        )
        
        # Mock response with new refresh token
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new-access-token',
            'refresh_token': 'new-refresh-token-rotated',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response
        
        result = store.refresh_tokens()
        
        # Verify new refresh token is returned
        assert result['refresh_token'] == 'new-refresh-token-rotated'
        
        # Verify new refresh token is saved
        data = store.load_tokens()
        assert data['refresh_token'] == 'new-refresh-token-rotated'
    
    def test_refresh_no_token(self, mock_config):
        """Test refresh when no token exists."""
        store = TokenStore(mock_config)
        
        with pytest.raises(NoTokenError):
            store.refresh_tokens()
    
    @patch('app.token_store.requests.post')
    def test_refresh_network_error(self, mock_post, mock_config):
        """Test refresh with network error."""
        store = TokenStore(mock_config)
        
        # Save initial tokens
        store.save_tokens(
            access_token='test-token',
            refresh_token='test-refresh',
            expires_in=3600
        )
        
        mock_post.side_effect = Exception("Network error")
        
        with pytest.raises(TokenStoreError):
            store.refresh_tokens()


class TestTokenRevocation:
    """Test token revocation functionality."""
    
    @patch('app.token_store.requests.post')
    def test_revoke_tokens(self, mock_post, mock_config):
        """Test token revocation."""
        store = TokenStore(mock_config)
        
        # Save tokens
        store.save_tokens(
            access_token='test-access-token',
            refresh_token='test-refresh-token',
            expires_in=3600
        )
        
        # Mock revocation responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        store.revoke_tokens()
        
        # Verify POST calls were made to revoke endpoint
        assert mock_post.call_count == 2  # One for access token, one for refresh
    
    def test_revoke_no_tokens(self, mock_config):
        """Test revocation when no tokens exist."""
        store = TokenStore(mock_config)
        
        with pytest.raises(NoTokenError):
            store.revoke_tokens()


class TestLocalStateDelete:
    """Test local state deletion."""
    
    def test_delete_local_state(self, mock_config):
        """Test deleting local token storage."""
        store = TokenStore(mock_config)
        
        # Save tokens first
        store.save_tokens(
            access_token='test-token',
            refresh_token='test-refresh',
            expires_in=3600
        )
        
        assert Path(mock_config.token_storage_path).exists()
        
        # Delete
        store.delete_local_state()
        
        assert not Path(mock_config.token_storage_path).exists()
    
    def test_delete_nonexistent_state(self, mock_config):
        """Test deleting when no token file exists."""
        store = TokenStore(mock_config)
        
        # Should not raise error
        store.delete_local_state()


class TestTokenInfo:
    """Test token info retrieval."""
    
    def test_get_token_info_valid(self, mock_config):
        """Test getting info for valid token."""
        store = TokenStore(mock_config)
        
        store.save_tokens(
            access_token='test-token',
            refresh_token='test-refresh',
            expires_in=3600
        )
        
        info = store.get_token_info()
        
        assert info['valid'] is True
        assert 'expires_at' in info
        assert 'time_remaining' in info
        assert 'time_remaining_readable' in info
    
    def test_get_token_info_expired(self, mock_config):
        """Test getting info for expired token."""
        store = TokenStore(mock_config)
        
        store.save_tokens(
            access_token='test-token',
            refresh_token='test-refresh',
            expires_in=0  # Already expired
        )
        
        info = store.get_token_info()
        
        assert info['valid'] is False
        assert 'reason' in info
    
    def test_get_token_info_none(self, mock_config):
        """Test getting info when no token exists."""
        store = TokenStore(mock_config)
        
        info = store.get_token_info()
        
        assert info['valid'] is False
        assert info['reason'] == 'No token found'
