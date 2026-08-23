"""
Thread-safe orchestrator that drives the device authorization flow for the
web UI: tracks in-progress login polling, and handles refresh/logout, so
HTTP request handlers never block on the OAuth polling loop.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

import jwt

from .device_flow import (
    DeviceFlowClient,
    AccessDeniedException,
    TokenExpiredException,
    PollingTimeoutException,
    DeviceAuthorizationError,
)
from .token_store import TokenStore, TokenStoreError, NoTokenError
from .display import Display

logger = logging.getLogger(__name__)


class AuthController:
    """Coordinates login/refresh/logout actions triggered from the web UI."""

    def __init__(self, config):
        self.config = config
        self.device_flow = DeviceFlowClient(config)
        self.token_store = TokenStore(config)
        self._lock = threading.Lock()
        # phase: idle | starting | pending | success | error | denied | expired
        self._state: Dict[str, Any] = {
            'phase': 'idle',
            'message': '',
            'user_code': None,
            'verification_uri': None,
            'expires_in': None,
            'time_remaining': None,
            'created_at': None,
            'session': None,
        }
        self._load_existing_session()

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of current flow/session state for polling."""
        with self._lock:
            state = dict(self._state)
        if state['phase'] == 'pending' and state['created_at'] and state['expires_in']:
            elapsed = time.time() - state['created_at']
            state['time_remaining'] = max(0, int(state['expires_in'] - elapsed))
        return state

    def start_login(self) -> Dict[str, Any]:
        """Kick off the device flow in a background thread and return immediately."""
        with self._lock:
            if self._state['phase'] in ('starting', 'pending'):
                return dict(self._state)
            self._state.update({
                'phase': 'starting',
                'message': 'Requesting device code...',
                'user_code': None,
                'verification_uri': None,
                'expires_in': None,
                'time_remaining': None,
                'created_at': None,
            })
        threading.Thread(target=self._run_login_flow, daemon=True).start()
        return self.get_status()

    def refresh(self) -> Dict[str, Any]:
        """Refresh the access token using the stored refresh token."""
        try:
            new_tokens = self.token_store.refresh_tokens()
            self._set_success_from_tokens(
                access_token=new_tokens['access_token'],
                refresh_token=new_tokens.get('refresh_token'),
                expires_in=new_tokens['expires_in']
            )
            logger.info("Access token refreshed successfully")
        except NoTokenError:
            self._set_error("No token found. Please log in first.")
        except TokenStoreError as e:
            self._set_error(f"Refresh failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected refresh error: {e}", exc_info=True)
            self._set_error(f"Unexpected error: {e}")
        return self.get_status()

    def logout(self) -> Dict[str, Any]:
        """Revoke tokens with the server and clear local session state."""
        try:
            self.token_store.revoke_tokens()
            self.token_store.delete_local_state()
            with self._lock:
                self._state.update({
                    'phase': 'idle',
                    'message': 'Logged out successfully.',
                    'user_code': None,
                    'verification_uri': None,
                    'session': None
                })
            logger.info("Logged out successfully")
        except NoTokenError:
            with self._lock:
                self._state.update({
                    'phase': 'idle',
                    'message': 'No active session to log out.',
                    'session': None
                })
        except Exception as e:
            logger.error(f"Logout failed: {e}", exc_info=True)
            self._set_error(f"Logout failed: {e}")
        return self.get_status()

    def qr_source_uri(self) -> Optional[str]:
        """Return the verification URI currently encoded in the QR image, if any."""
        if self.device_flow.device_code_response:
            return self.device_flow.device_code_response.verification_uri_complete
        return None

    def _run_login_flow(self) -> None:
        try:
            device_code_response = self.device_flow.request_device_code()
            with self._lock:
                self._state.update({
                    'phase': 'pending',
                    'message': 'Waiting for authorization...',
                    'user_code': device_code_response.user_code,
                    'verification_uri': device_code_response.verification_uri,
                    'expires_in': device_code_response.expires_in,
                    'time_remaining': device_code_response.expires_in,
                    'created_at': time.time()
                })

            token_response = self.device_flow.poll_token()

            self.token_store.save_tokens(
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                expires_in=token_response.expires_in
            )
            self._set_success_from_tokens(
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                expires_in=token_response.expires_in
            )
            logger.info("Login flow completed successfully")

        except AccessDeniedException:
            self._set_error("Access denied. You declined the authorization request.", phase='denied')
        except TokenExpiredException:
            self._set_error("Device code expired. Click Login to try again.", phase='expired')
        except PollingTimeoutException:
            self._set_error("Timed out waiting for authorization.")
        except DeviceAuthorizationError as e:
            self._set_error(str(e))
        except Exception as e:
            logger.error(f"Unexpected error during login: {e}", exc_info=True)
            self._set_error(f"Unexpected error: {e}")

    def _set_success_from_tokens(
        self,
        access_token: str,
        refresh_token: Optional[str],
        expires_in: int
    ) -> None:
        try:
            decoded = jwt.decode(access_token, options={"verify_signature": False})
        except Exception:
            decoded = {}

        session = {
            'username': decoded.get('preferred_username', 'unknown'),
            'scopes': decoded.get('scope', 'unknown'),
            'expires_in': expires_in,
            'access_token_masked': Display._mask_token(access_token),
            'refresh_token_masked': Display._mask_token(refresh_token) if refresh_token else None
        }
        with self._lock:
            self._state.update({
                'phase': 'success',
                'message': 'Authentication successful.',
                'user_code': None,
                'verification_uri': None,
                'session': session
            })

    def _set_error(self, message: str, phase: str = 'error') -> None:
        with self._lock:
            self._state.update({
                'phase': phase,
                'message': message,
                'user_code': None,
                'verification_uri': None
            })

    def _load_existing_session(self) -> None:
        """Populate session info from any tokens already saved on disk."""
        try:
            info = self.token_store.get_token_info()
            if not info.get('valid'):
                return
            token_data = self.token_store.load_tokens()
            decoded = jwt.decode(token_data['access_token'], options={"verify_signature": False})
            with self._lock:
                self._state['session'] = {
                    'username': decoded.get('preferred_username', 'unknown'),
                    'scopes': decoded.get('scope', 'unknown'),
                    'expires_in': info.get('time_remaining'),
                    'access_token_masked': Display._mask_token(token_data['access_token']),
                    'refresh_token_masked': (
                        Display._mask_token(token_data['refresh_token'])
                        if token_data.get('refresh_token') else None
                    )
                }
                self._state['phase'] = 'success'
                self._state['message'] = 'Existing session found.'
        except Exception:
            pass
