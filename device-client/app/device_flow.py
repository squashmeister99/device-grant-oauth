"""
Device Authorization Grant flow implementation.
Handles device code requests and polling with proper state machine.
"""

import logging
import time
import requests
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class DeviceCodeResponse:
    """Response from the device authorization endpoint."""
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int
    created_at: float = field(default_factory=time.time)
    
    def is_expired(self) -> bool:
        """Check if the device code has expired."""
        return time.time() > (self.created_at + self.expires_in)


@dataclass
class TokenResponse:
    """Response from the token endpoint."""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    
    @property
    def expiry_timestamp(self) -> float:
        """Calculate when this token expires (Unix timestamp)."""
        return time.time() + self.expires_in


class DeviceAuthorizationError(Exception):
    """Base exception for device authorization errors."""
    pass


class AccessDeniedException(DeviceAuthorizationError):
    """User denied access on the authorization device."""
    pass


class TokenExpiredException(DeviceAuthorizationError):
    """Device code has expired."""
    pass


class PollingTimeoutException(DeviceAuthorizationError):
    """Polling timed out waiting for authorization."""
    pass


class DeviceFlowClient:
    """Handles the OAuth 2.0 Device Authorization Grant flow."""
    
    def __init__(self, config):
        """Initialize the device flow client."""
        self.config = config
        self.device_code_response: Optional[DeviceCodeResponse] = None
        self.created_timestamp: Optional[float] = None
    
    def request_device_code(self) -> DeviceCodeResponse:
        """
        Request a device code from the authorization server.
        
        Returns:
            DeviceCodeResponse with device_code, user_code, verification_uri, etc.
            
        Raises:
            DeviceAuthorizationError: If the request fails.
        """
        logger.info(f"Requesting device code from {self.config.device_auth_endpoint}")
        
        try:
            response = requests.post(
                self.config.device_auth_endpoint,
                data={
                    'client_id': self.config.keycloak_client_id,
                    'scope': self.config.keycloak_scopes
                },
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"Device code response: user_code={data['user_code']}, "
                        f"expires_in={data['expires_in']}, interval={data['interval']}")
            
            self.device_code_response = DeviceCodeResponse(
                device_code=data['device_code'],
                user_code=data['user_code'],
                verification_uri=data['verification_uri'],
                verification_uri_complete=data['verification_uri_complete'],
                expires_in=data['expires_in'],
                interval=data['interval']
            )
            self.created_timestamp = time.time()
            
            return self.device_code_response
            
        except requests.RequestException as e:
            logger.error(f"Failed to request device code: {e}")
            raise DeviceAuthorizationError(f"Failed to request device code: {e}")
    
    def poll_token(self, max_retries: int = 60) -> TokenResponse:
        """
        Poll the token endpoint until authorization is granted or an error occurs.
        
        Implements proper handling of:
        - authorization_pending: retry at the given interval
        - slow_down: increase polling interval
        - access_denied: user denied access
        - expired_token: device code expired
        - success: return token response
        
        Args:
            max_retries: Maximum number of polling attempts.
            
        Returns:
            TokenResponse with access_token, refresh_token, etc.
            
        Raises:
            AccessDeniedException: If user denies access.
            TokenExpiredException: If device code expires.
            PollingTimeoutException: If max retries exceeded.
            DeviceAuthorizationError: For other errors.
        """
        if not self.device_code_response:
            raise DeviceAuthorizationError("Device code not requested yet")
        
        logger.info(f"Starting token polling with max {max_retries} retries")
        
        current_interval = self.device_code_response.interval
        retry_count = 0
        start_time = time.time()
        timeout = self.config.poll_timeout
        
        while retry_count < max_retries:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.error(f"Polling timeout after {elapsed:.1f}s")
                raise PollingTimeoutException(f"Polling timed out after {elapsed:.1f}s")
            
            # Check if device code has expired
            if self.device_code_response.is_expired():
                logger.error("Device code has expired")
                raise TokenExpiredException("Device code has expired")
            
            try:
                logger.debug(f"Polling attempt {retry_count + 1}/{max_retries} "
                           f"(elapsed: {elapsed:.1f}s, interval: {current_interval}s)")
                
                response = requests.post(
                    self.config.token_endpoint,
                    data={
                        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                        'device_code': self.device_code_response.device_code,
                        'client_id': self.config.keycloak_client_id
                    },
                    timeout=10
                )
                
                # Successful token response
                if response.status_code == 200:
                    data = response.json()
                    logger.info("Authorization successful! Token acquired.")
                    logger.debug(f"Token response: token_type={data['token_type']}, "
                               f"expires_in={data['expires_in']}, "
                               f"scope={data.get('scope', 'N/A')}")
                    logger.info(
                        "Token metadata: access_token=%s refresh_token=%s",
                        self._mask_token(data.get('access_token')),
                        self._mask_token(data.get('refresh_token'))
                    )
                    
                    return TokenResponse(
                        access_token=data['access_token'],
                        token_type=data['token_type'],
                        expires_in=data['expires_in'],
                        refresh_token=data.get('refresh_token'),
                        scope=data.get('scope')
                    )
                
                # Error responses
                elif response.status_code == 400:
                    error_data = response.json()
                    error = error_data.get('error', 'unknown')
                    
                    if error == 'authorization_pending':
                        logger.debug("Authorization pending, will retry...")
                        time.sleep(current_interval)
                        retry_count += 1
                        continue
                    
                    elif error == 'slow_down':
                        # Increase interval by 5 seconds (per RFC 8628)
                        current_interval = min(
                            current_interval + 5,
                            self.config.polling_interval_max
                        )
                        logger.info(f"Slow down requested, new interval: {current_interval}s")
                        time.sleep(current_interval)
                        retry_count += 1
                        continue
                    
                    elif error == 'access_denied':
                        logger.error("User denied access")
                        raise AccessDeniedException("User denied access")
                    
                    elif error == 'expired_token':
                        logger.error("Device code has expired")
                        raise TokenExpiredException("Device code has expired")
                    
                    else:
                        logger.error(f"Token endpoint error: {error}")
                        raise DeviceAuthorizationError(f"Token error: {error}")
                
                else:
                    logger.error(f"Unexpected response status {response.status_code}: {response.text}")
                    raise DeviceAuthorizationError(f"Unexpected response: {response.status_code}")
            
            except requests.RequestException as e:
                logger.warning(f"Network error during polling: {e}")
                time.sleep(current_interval)
                retry_count += 1
                continue
        
        logger.error(f"Max retries ({max_retries}) exceeded")
        raise PollingTimeoutException(f"Max retries ({max_retries}) exceeded")

    @staticmethod
    def _mask_token(token: Optional[str]) -> str:
        """Return a masked token string safe for logs."""
        if not token:
            return "<none>"
        if len(token) <= 12:
            return f"{token[0:2]}...{token[-2:]}"
        return f"{token[0:6]}...{token[-6:]}"
