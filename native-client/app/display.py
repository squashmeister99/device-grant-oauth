"""
Display module for showing QR codes and status information.
Supports both ASCII terminal output and web UI integration.
"""

import logging
import base64
from io import BytesIO
from typing import Optional
import qrcode
import json
import jwt
from datetime import datetime

logger = logging.getLogger(__name__)


class Display:
    """Handles display of QR codes, user codes, and status information."""

    @staticmethod
    def print_qr_ascii(verification_uri_complete: str) -> None:
        """
        Print QR code in ASCII format to console.

        Args:
            verification_uri_complete: The complete verification URI to encode.
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=1,
                border=1,
            )
            qr.add_data(verification_uri_complete)
            qr.make(fit=True)

            print("\n" + "="*60)
            print("SCAN THIS QR CODE TO AUTHENTICATE")
            print("="*60)
            qr.print_ascii(invert=True)
            print("="*60 + "\n")

        except Exception as e:
            logger.error(f"Failed to generate QR code: {e}")
            print(f"QR Code generation failed: {e}")

    @staticmethod
    def generate_qr_image(verification_uri_complete: str) -> Optional[bytes]:
        """
        Generate QR code as PNG image bytes.

        Args:
            verification_uri_complete: The complete verification URI to encode.

        Returns:
            PNG image bytes, or None if generation fails.
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(verification_uri_complete)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to PNG bytes
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            return img_bytes.getvalue()

        except Exception as e:
            logger.error(f"Failed to generate QR image: {e}")
            return None

    @staticmethod
    def print_user_code(user_code: str) -> None:
        """
        Print the user code in large, clear format.

        Args:
            user_code: The short user code to display.
        """
        print("\n" + "="*60)
        print("ENTER THIS CODE ON YOUR DEVICE")
        print("="*60)
        print("")
        # Print with extra spacing for visibility
        formatted_code = " - ".join(user_code[i:i+2] for i in range(0, len(user_code), 2))
        print(f"  >>> {formatted_code} <<<")
        print("")
        print("="*60 + "\n")

    @staticmethod
    def print_verification_url(verification_uri: str) -> None:
        """
        Print the verification URL for manual entry.

        Args:
            verification_uri: The verification URL.
        """
        print(f"Verification URL: {verification_uri}")
        print("Open this URL in a browser and enter the code above.\n")

    @staticmethod
    def print_status(status: str, message: str = "", details: dict = None) -> None:
        """
        Print status message with optional details.

        Args:
            status: Status type (pending, approved, denied, expired, success).
            message: Optional message to display.
            details: Optional dict of additional details to display.
        """
        status_symbols = {
            'pending': '⏳',
            'approved': '✅',
            'denied': '❌',
            'expired': '⏰',
            'success': '✅',
            'error': '❌',
            'info': 'ℹ️'
        }

        symbol = status_symbols.get(status, 'ℹ️')
        timestamp = datetime.now().strftime('%H:%M:%S')

        print(f"[{timestamp}] {symbol} {status.upper()}")
        if message:
            print(f"  {message}")

        if details:
            for key, value in details.items():
                print(f"  {key}: {value}")
        print()

    @staticmethod
    def print_token_claims(access_token: str, hide_raw: bool = True) -> None:
        """
        Print decoded token claims (without printing raw token).

        Args:
            access_token: The JWT access token.
            hide_raw: If True, never print the raw token.
        """
        try:
            # Decode without verification (for display purposes only)
            decoded = jwt.decode(access_token, options={"verify_signature": False})

            print("\n" + "="*60)
            print("TOKEN CLAIMS")
            print("="*60)

            # Print key claims
            important_claims = [
                'sub', 'preferred_username', 'email', 'exp', 'iat', 'scope',
                'given_name', 'family_name'
            ]

            for claim in important_claims:
                if claim in decoded:
                    value = decoded[claim]
                    if claim == 'exp' or claim == 'iat':
                        # Convert Unix timestamp to readable format
                        dt = datetime.fromtimestamp(value)
                        value = f"{value} ({dt.isoformat()})"
                    print(f"  {claim}: {value}")

            # Print remaining claims
            printed_claims = set(important_claims)
            remaining = {k: v for k, v in decoded.items() if k not in printed_claims}
            if remaining:
                print("\n  Additional claims:")
                for key, value in remaining.items():
                    print(f"    {key}: {value}")

            print("="*60 + "\n")

        except Exception as e:
            logger.error(f"Failed to decode token claims: {e}")
            print(f"Failed to decode token: {e}")

    @staticmethod
    def print_polling_status(elapsed: float, retry_count: int, status: str = "pending") -> None:
        """
        Print polling status with elapsed time and retry count.

        Args:
            elapsed: Seconds elapsed since polling started.
            retry_count: Number of polling attempts made.
            status: Current status message.
        """
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        print(f"\r⏳ Polling... ({minutes}m {seconds}s elapsed, attempt {retry_count}) - {status}", end='', flush=True)

    @staticmethod
    def print_error(error_title: str, error_details: str = "") -> None:
        """
        Print an error message.

        Args:
            error_title: The error title/type.
            error_details: Additional error details.
        """
        print("\n" + "!"*60)
        print(f"ERROR: {error_title}")
        if error_details:
            print(f"{error_details}")
        print("!"*60 + "\n")

    @staticmethod
    def print_success_summary(
        username: str,
        scopes: str,
        expires_in: int,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None
    ) -> None:
        """
        Print a success summary with key information.

        Args:
            username: The authenticated username.
            scopes: Authorized scopes.
            expires_in: Token lifetime in seconds.
            access_token: Access token value (masked when displayed).
            refresh_token: Refresh token value (masked when displayed).
        """
        expires_dt = datetime.fromtimestamp(datetime.now().timestamp() + expires_in)
        print("\n" + "="*60)
        print("✅ AUTHENTICATION SUCCESSFUL")
        print("="*60)
        print(f"  User: {username}")
        print(f"  Scopes: {scopes}")
        print(f"  Token expires: {expires_dt.isoformat()}")
        print(f"  (~{expires_in} seconds)")
        if access_token:
            print(f"  Access token (masked): {Display._mask_token(access_token)}")
        if refresh_token:
            print(f"  Refresh token (masked): {Display._mask_token(refresh_token)}")
        print("="*60 + "\n")

    @staticmethod
    def _mask_token(token: str) -> str:
        """Mask token value for safe terminal display."""
        if len(token) <= 12:
            return f"{token[0:2]}...{token[-2:]}"
        return f"{token[0:6]}...{token[-6:]}"
