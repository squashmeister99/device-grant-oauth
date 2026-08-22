"""
Token persistence and lifecycle management.
Handles saving, loading, refreshing, and revoking tokens.
"""

import logging
import json
import os
import time
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class TokenStoreError(Exception):
    """Base exception for token store errors."""
    pass


class TokenExpiredError(TokenStoreError):
    """Token has expired."""
    pass


class NoTokenError(TokenStoreError):
    """No token found in storage."""
    pass


class TokenStore:
    """Manages OAuth 2.0 token storage, refresh, and revocation."""
    
    def __init__(self, config):
        """Initialize the token store."""
        self.config = config
        self.storage_path = Path(config.token_storage_path)
        # Ensure parent directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def save_tokens(self, access_token: str, refresh_token: Optional[str], 
                   expires_in: int) -> None:
        """
        Save tokens to local storage.
        
        Args:
            access_token: The access token.
            refresh_token: The refresh token (optional).
            expires_in: Token lifetime in seconds.
        """
        try:
            expires_at = time.time() + expires_in
            token_data = {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_at': expires_at,
                'expires_in': expires_in,
                'saved_at': datetime.now().isoformat(),
                'token_type': 'Bearer'
            }
            
            with open(self.storage_path, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            logger.info(f"Tokens saved to {self.storage_path}")
            logger.info(
                "Saved token metadata: access_token=%s refresh_token=%s",
                self._mask_token(access_token),
                self._mask_token(refresh_token)
            )
            logger.debug(f"Token expiry: {datetime.fromtimestamp(expires_at).isoformat()}")
            
        except IOError as e:
            logger.error(f"Failed to save tokens: {e}")
            raise TokenStoreError(f"Failed to save tokens: {e}")
    
    def load_tokens(self) -> Dict[str, Any]:
        """
        Load tokens from storage.
        
        Returns:
            Dictionary containing access_token, refresh_token, expires_at, etc.
            
        Raises:
            NoTokenError: If no token file exists.
            TokenExpiredError: If token has expired.
        """
        if not self.storage_path.exists():
            logger.warning("No token file found")
            raise NoTokenError("No token file found")
        
        try:
            with open(self.storage_path, 'r') as f:
                token_data = json.load(f)
            
            # Check if token has expired (with 30s buffer)
            expires_at = token_data.get('expires_at', 0)
            expiry_buffer = 30  # seconds
            
            if time.time() > (expires_at - expiry_buffer):
                logger.warning("Token has expired")
                raise TokenExpiredError("Token has expired")
            
            logger.debug(f"Tokens loaded from {self.storage_path}")
            return token_data
            
        except IOError as e:
            logger.error(f"Failed to load tokens: {e}")
            raise TokenStoreError(f"Failed to load tokens: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid token file format: {e}")
            raise TokenStoreError(f"Invalid token file format: {e}")
    
    def is_token_expired(self, expiry_buffer: int = 30) -> bool:
        """
        Check if the token has expired.
        
        Args:
            expiry_buffer: Seconds before actual expiry to consider token expired.
            
        Returns:
            True if token is expired or doesn't exist, False otherwise.
        """
        try:
            if not self.storage_path.exists():
                return True

            with open(self.storage_path, 'r') as f:
                token_data = json.load(f)

            expires_at = token_data.get('expires_at', 0)
            return time.time() > (expires_at - expiry_buffer)
        except (IOError, json.JSONDecodeError, TypeError, ValueError):
            return True
    
    def get_token_info(self) -> Dict[str, Any]:
        """
        Get human-readable token information.
        
        Returns:
            Dictionary with token metadata (expiry time, time remaining, etc.)
        """
        try:
            token_data = self.load_tokens()
            expires_at = token_data.get('expires_at', 0)
            now = time.time()
            time_remaining = expires_at - now
            
            return {
                'valid': True,
                'expires_at': datetime.fromtimestamp(expires_at).isoformat(),
                'time_remaining': int(time_remaining),
                'time_remaining_readable': self._format_duration(int(time_remaining))
            }
        except TokenExpiredError:
            return {'valid': False, 'reason': 'Token expired'}
        except NoTokenError:
            return {'valid': False, 'reason': 'No token found'}
    
    def refresh_tokens(self) -> Dict[str, Any]:
        """
        Refresh the access token using the refresh token.
        
        Returns:
            New token response with access_token, refresh_token, expires_in.
            
        Raises:
            NoTokenError: If no refresh token available.
            TokenStoreError: If refresh fails.
        """
        try:
            token_data = self.load_tokens()
        except TokenExpiredError:
            # Try to use expired token's refresh token
            if not self.storage_path.exists():
                raise NoTokenError("No token found")
            try:
                with open(self.storage_path, 'r') as f:
                    token_data = json.load(f)
            except Exception as e:
                raise TokenStoreError(f"Failed to load token data: {e}")
        except NoTokenError as e:
            raise NoTokenError("No token found to refresh") from e
        
        refresh_token = token_data.get('refresh_token')
        if not refresh_token:
            raise NoTokenError("No refresh token available")
        
        logger.info("Attempting to refresh access token")
        logger.debug("Using refresh token: %s", self._mask_token(refresh_token))
        
        try:
            response = requests.post(
                self.config.token_endpoint,
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': self.config.keycloak_client_id
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info("Access token refreshed successfully")
            logger.info(
                "Refreshed token metadata: access_token=%s refresh_token=%s",
                self._mask_token(data.get('access_token')),
                self._mask_token(data.get('refresh_token', refresh_token))
            )
            logger.debug(f"New token expires in {data['expires_in']}s")
            
            # Handle refresh token rotation
            new_refresh_token = data.get('refresh_token', refresh_token)
            
            # Save new tokens
            self.save_tokens(
                access_token=data['access_token'],
                refresh_token=new_refresh_token,
                expires_in=data['expires_in']
            )
            
            return {
                'access_token': data['access_token'],
                'refresh_token': new_refresh_token,
                'expires_in': data['expires_in'],
                'token_type': data.get('token_type', 'Bearer')
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to refresh token: {e}")
            raise TokenStoreError(f"Failed to refresh token: {e}")
    
    def revoke_tokens(self) -> None:
        """
        Revoke all tokens with the server.
        
        Raises:
            NoTokenError: If no tokens available to revoke.
            TokenStoreError: If revocation fails.
        """
        try:
            token_data = self.load_tokens()
        except TokenStoreError:
            # Still try to read from file even if expired
            if not self.storage_path.exists():
                raise NoTokenError("No token found to revoke")
            try:
                with open(self.storage_path, 'r') as f:
                    token_data = json.load(f)
            except Exception as e:
                raise TokenStoreError(f"Failed to load token data: {e}")
        
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        
        logger.info("Revoking tokens")
        logger.info(
            "Revocation targets: access_token=%s refresh_token=%s",
            self._mask_token(access_token),
            self._mask_token(refresh_token)
        )
        
        revocation_failures = []
        
        # Revoke access token
        if access_token:
            try:
                response = requests.post(
                    self.config.revoke_endpoint,
                    data={
                        'token': access_token,
                        'client_id': self.config.keycloak_client_id
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    logger.debug("Access token revoked")
                else:
                    logger.warning(f"Access token revocation returned {response.status_code}")
            except requests.RequestException as e:
                logger.warning(f"Failed to revoke access token: {e}")
                revocation_failures.append(f"access_token: {e}")
        
        # Revoke refresh token
        if refresh_token:
            try:
                response = requests.post(
                    self.config.revoke_endpoint,
                    data={
                        'token': refresh_token,
                        'token_type_hint': 'refresh_token',
                        'client_id': self.config.keycloak_client_id
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    logger.debug("Refresh token revoked")
                else:
                    logger.warning(f"Refresh token revocation returned {response.status_code}")
            except requests.RequestException as e:
                logger.warning(f"Failed to revoke refresh token: {e}")
                revocation_failures.append(f"refresh_token: {e}")
        
        if revocation_failures:
            logger.warning(f"Some tokens failed to revoke: {', '.join(revocation_failures)}")
    
    def delete_local_state(self) -> None:
        """
        Delete local token storage.
        
        Raises:
            TokenStoreError: If deletion fails.
        """
        try:
            if self.storage_path.exists():
                self.storage_path.unlink()
                logger.info(f"Local token state deleted: {self.storage_path}")
            else:
                logger.debug("No token file to delete")
        except OSError as e:
            logger.error(f"Failed to delete token file: {e}")
            raise TokenStoreError(f"Failed to delete token file: {e}")
    
    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Format a duration in seconds to a human-readable string."""
        if seconds < 0:
            return "expired"
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")
        return " ".join(parts)

    @staticmethod
    def _mask_token(token: Optional[str]) -> str:
        """Return a masked token string safe for logs."""
        if not token:
            return "<none>"
        if len(token) <= 12:
            return f"{token[0:2]}...{token[-2:]}"
        return f"{token[0:6]}...{token[-6:]}"
