"""
Main entry point for the native (host-run) device authorization grant client.
Provides CLI subcommands: login, refresh, logout, status.
Connects to Keycloak running in Docker (published on localhost:8080).
"""

import logging
import sys
import time
import json
import jwt
import threading
import webbrowser
from datetime import datetime
from typing import Optional
import uvicorn

from app.config import get_config, setup_logging
from app.device_flow import DeviceFlowClient, AccessDeniedException, TokenExpiredException, PollingTimeoutException
from app.token_store import TokenStore, TokenStoreError, NoTokenError
from app.display import Display
from app.controller import AuthController
from app.web_ui import create_web_ui

logger = logging.getLogger(__name__)


def run_web_ui() -> None:
    """Launch the button-driven web UI (login/refresh/logout) and open it in the browser."""
    config = get_config()
    setup_logging(config)

    controller = AuthController(config)
    display = Display()
    web_ui = create_web_ui(config, controller, display)

    url = f"http://{config.web_ui_host}:{config.web_ui_port}"
    print(f"Starting web UI at {url}")

    if config.open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(web_ui.app, host=config.web_ui_host, port=config.web_ui_port, log_level="warning")


class DeviceAuthClient:
    """Terminal-only CLI orchestrator (login/refresh/logout/status subcommands)."""

    def __init__(self):
        """Initialize the client."""
        self.config = get_config()
        setup_logging(self.config)

        self.device_flow = DeviceFlowClient(self.config)
        self.token_store = TokenStore(self.config)
        self.display = Display()

    def login(self) -> bool:
        """
        Execute the device authorization flow.

        Returns:
            True if authentication successful, False otherwise.
        """
        logger.info("Starting device authorization flow")
        print("\n" + "="*60)
        print("DEVICE AUTHORIZATION GRANT - LOGIN")
        print("="*60 + "\n")

        try:
            # Step 1: Request device code
            logger.info("Step 1: Requesting device code from authorization server")
            device_code_response = self.device_flow.request_device_code()

            # Display QR code and user code
            self.display.print_qr_ascii(device_code_response.verification_uri_complete)
            self.display.print_user_code(device_code_response.user_code)
            self.display.print_verification_url(device_code_response.verification_uri)

            print(f"Device code expires in {device_code_response.expires_in} seconds")
            print(f"Polling interval: {device_code_response.interval} seconds")
            print("\nWaiting for authorization (press Ctrl+C to cancel)...\n")

            # Step 2: Poll for token
            logger.info("Step 2: Polling token endpoint")
            start_time = time.time()

            try:
                token_response = self.device_flow.poll_token()
            except KeyboardInterrupt:
                logger.info("Device flow cancelled by user")
                print("\n\nDevice flow cancelled.")
                return False

            elapsed = time.time() - start_time
            logger.info(f"Authorization successful after {elapsed:.1f}s")

            # Step 3: Save tokens
            logger.info("Step 3: Saving tokens")
            self.token_store.save_tokens(
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                expires_in=token_response.expires_in
            )

            # Step 4: Display token claims
            self.display.print_token_claims(token_response.access_token)

            # Print success summary
            try:
                decoded = jwt.decode(
                    token_response.access_token,
                    options={"verify_signature": False}
                )
                username = decoded.get('preferred_username', 'unknown')
                scopes = decoded.get('scope', 'unknown')
                self.display.print_success_summary(
                    username,
                    scopes,
                    token_response.expires_in,
                    access_token=token_response.access_token,
                    refresh_token=token_response.refresh_token
                )
            except Exception as e:
                logger.warning(f"Failed to extract token info: {e}")

            return True

        except AccessDeniedException as e:
            self.display.print_error("Access Denied", str(e))
            logger.error(f"Access denied: {e}")
            return False

        except TokenExpiredException as e:
            self.display.print_error("Device Code Expired",
                                    "Please run 'python main.py login' again to get a new device code.")
            logger.error(f"Token expired: {e}")
            return False

        except PollingTimeoutException as e:
            self.display.print_error("Polling Timeout",
                                    "No response from server within timeout period.")
            logger.error(f"Polling timeout: {e}")
            return False

        except Exception as e:
            self.display.print_error("Authentication Failed", str(e))
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return False

    def refresh(self) -> bool:
        """
        Refresh the access token.

        Returns:
            True if refresh successful, False otherwise.
        """
        logger.info("Starting token refresh")
        print("\n" + "="*60)
        print("REFRESH ACCESS TOKEN")
        print("="*60 + "\n")

        try:
            logger.info("Attempting to refresh access token")
            new_tokens = self.token_store.refresh_tokens()

            logger.info("Token refreshed successfully")
            self.display.print_success_summary(
                username="(refreshed)",
                scopes="openid profile email offline_access",
                expires_in=new_tokens['expires_in'],
                access_token=new_tokens.get('access_token'),
                refresh_token=new_tokens.get('refresh_token')
            )

            # Display token claims
            self.display.print_token_claims(new_tokens['access_token'])

            return True

        except NoTokenError as e:
            self.display.print_error("No Token Found",
                                    "Please run 'python main.py login' first to authenticate.")
            logger.error(f"No token: {e}")
            return False

        except TokenStoreError as e:
            self.display.print_error("Token Refresh Failed", str(e))
            logger.error(f"Token refresh failed: {e}")
            return False

        except Exception as e:
            self.display.print_error("Unexpected Error", str(e))
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return False

    def logout(self) -> bool:
        """
        Revoke tokens and clean up local state.

        Returns:
            True if logout successful, False otherwise.
        """
        logger.info("Starting logout")
        print("\n" + "="*60)
        print("LOGOUT")
        print("="*60 + "\n")

        try:
            # Revoke tokens with the server
            logger.info("Revoking tokens with authorization server")
            self.token_store.revoke_tokens()

            # Delete local state
            logger.info("Deleting local token storage")
            self.token_store.delete_local_state()

            print("✅ Logged out successfully")
            print("All tokens have been revoked and local state deleted.\n")

            return True

        except NoTokenError:
            print("⚠️  No tokens found to revoke.")
            print("Local state was already clean.\n")
            return True

        except Exception as e:
            self.display.print_error("Logout Failed", str(e))
            logger.error(f"Logout failed: {e}", exc_info=True)
            return False

    def status(self) -> bool:
        """
        Print current token status.

        Returns:
            True if token is valid, False otherwise.
        """
        logger.info("Checking token status")
        print("\n" + "="*60)
        print("TOKEN STATUS")
        print("="*60 + "\n")

        try:
            token_info = self.token_store.get_token_info()

            if token_info['valid']:
                print(f"✅ Token is valid")
                print(f"   Expires at: {token_info['expires_at']}")
                print(f"   Time remaining: {token_info['time_remaining_readable']}\n")
                return True
            else:
                print(f"❌ Token is not valid")
                print(f"   Reason: {token_info['reason']}\n")
                return False

        except Exception as e:
            self.display.print_error("Status Check Failed", str(e))
            logger.error(f"Status check failed: {e}", exc_info=True)
            return False


def main():
    """Main entry point. No args launches the button-driven web UI."""
    if len(sys.argv) < 2:
        run_web_ui()
        return

    client = DeviceAuthClient()
    command = sys.argv[1].lower()

    try:
        if command == 'login':
            success = client.login()
            sys.exit(0 if success else 1)
        elif command == 'refresh':
            success = client.refresh()
            sys.exit(0 if success else 1)
        elif command == 'logout':
            success = client.logout()
            sys.exit(0 if success else 1)
        elif command == 'status':
            success = client.status()
            sys.exit(0 if success else 1)
        else:
            print(f"Unknown command: {command}")
            print("Commands: login, refresh, logout, status (or no args for the web UI)")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)


if __name__ == '__main__':
    main()
