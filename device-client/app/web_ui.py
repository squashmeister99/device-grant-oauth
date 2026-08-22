"""
FastAPI web server for displaying QR code and polling status.
Provides a TV-like interface for device authentication.
"""

import logging
import time
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)


class StatusResponse(BaseModel):
    """Status response model."""
    status: str
    user_code: Optional[str] = None
    verification_uri: Optional[str] = None
    expires_in: Optional[int] = None
    time_remaining: Optional[int] = None
    message: str = ""


class WebUI:
    """Web UI server for device authorization display."""
    
    def __init__(self, config, device_flow_client, display):
        """
        Initialize the web UI server.
        
        Args:
            config: Application configuration.
            device_flow_client: Device flow client instance.
            display: Display module for QR generation.
        """
        self.config = config
        self.device_flow_client = device_flow_client
        self.display = display
        self.app = FastAPI(title="Device Authorization Grant Demo")
        self.setup_routes()
    
    def setup_routes(self) -> None:
        """Set up FastAPI routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            """Serve the main HTML page."""
            return self.get_html_page()
        
        @self.app.get("/api/status", response_model=StatusResponse)
        async def get_status():
            """Get current polling status."""
            if not self.device_flow_client.device_code_response:
                return StatusResponse(
                    status="idle",
                    message="No authorization in progress"
                )
            
            device_code_resp = self.device_flow_client.device_code_response
            elapsed = time.time() - (self.device_flow_client.created_timestamp or time.time())
            time_remaining = max(0, device_code_resp.expires_in - int(elapsed))
            
            return StatusResponse(
                status="pending",
                user_code=device_code_resp.user_code,
                verification_uri=device_code_resp.verification_uri,
                expires_in=device_code_resp.expires_in,
                time_remaining=time_remaining,
                message="Waiting for authorization"
            )
        
        @self.app.get("/api/qr")
        async def get_qr():
            """Get QR code as PNG image."""
            if not self.device_flow_client.device_code_response:
                return Response(
                    content=b"",
                    media_type="image/png",
                    status_code=204
                )
            
            verification_uri_complete = (
                self.device_flow_client.device_code_response.verification_uri_complete
            )
            
            qr_image = self.display.generate_qr_image(verification_uri_complete)
            if qr_image:
                return Response(content=qr_image, media_type="image/png")
            else:
                return Response(content=b"", media_type="image/png", status_code=500)
    
    def get_html_page(self) -> str:
        """Generate the HTML page."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Device Authorization Grant Demo</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 600px;
            padding: 40px;
            text-align: center;
        }
        
        .header {
            margin-bottom: 40px;
        }
        
        .header h1 {
            font-size: 32px;
            color: #1e3c72;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 16px;
            color: #666;
        }
        
        .qr-section {
            margin: 30px 0;
        }
        
        .qr-code {
            background: white;
            padding: 20px;
            border-radius: 10px;
            display: inline-block;
            border: 2px solid #e0e0e0;
        }
        
        .qr-code img {
            width: 300px;
            height: 300px;
            display: block;
        }
        
        .code-section {
            background: #f5f5f5;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        
        .code-section p {
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }
        
        .user-code {
            font-size: 36px;
            font-weight: bold;
            color: #1e3c72;
            letter-spacing: 5px;
            font-family: 'Courier New', monospace;
            margin: 15px 0;
        }
        
        .status {
            margin-top: 30px;
            padding: 15px;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 500;
        }
        
        .status.pending {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeeba;
        }
        
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .countdown {
            font-size: 18px;
            margin-top: 15px;
            color: #666;
        }
        
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #1e3c72;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            vertical-align: middle;
            margin-right: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .idle {
            color: #999;
            font-size: 18px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Device Authorization</h1>
            <p>Authenticate using your phone or computer</p>
        </div>
        
        <div id="idle-state" class="idle" style="display: none;">
            <p>Waiting for authorization to start...</p>
        </div>
        
        <div id="auth-state" style="display: none;">
            <div class="qr-section">
                <div class="qr-code">
                    <img id="qr-image" src="/api/qr" alt="QR Code">
                </div>
            </div>
            
            <div class="code-section">
                <p>Or enter this code:</p>
                <div class="user-code" id="user-code">-</div>
                <p style="font-size: 12px; color: #999;">
                    Visit: <code id="verification-uri">-</code>
                </p>
            </div>
            
            <div class="status pending">
                <div>
                    <span class="spinner"></span>
                    <span id="status-message">Waiting for authorization...</span>
                </div>
                <div class="countdown">
                    Expires in <span id="countdown">-</span>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const statusUrl = '/api/status';
        const qrImageUrl = '/api/qr';
        let countdownInterval = null;
        
        async function updateStatus() {
            try {
                const response = await fetch(statusUrl);
                const data = await response.json();
                
                const idleState = document.getElementById('idle-state');
                const authState = document.getElementById('auth-state');
                
                if (data.status === 'idle') {
                    idleState.style.display = 'block';
                    authState.style.display = 'none';
                    clearInterval(countdownInterval);
                } else {
                    idleState.style.display = 'none';
                    authState.style.display = 'block';
                    
                    // Update user code
                    if (data.user_code) {
                        const formatted = data.user_code.match(/.{1,2}/g).join(' - ');
                        document.getElementById('user-code').textContent = formatted;
                    }
                    
                    // Update verification URI
                    if (data.verification_uri) {
                        document.getElementById('verification-uri').textContent = data.verification_uri;
                    }
                    
                    // Update countdown
                    if (data.time_remaining !== undefined) {
                        const minutes = Math.floor(data.time_remaining / 60);
                        const seconds = data.time_remaining % 60;
                        document.getElementById('countdown').textContent = 
                            `${minutes}m ${seconds}s`;
                    }
                    
                    // Refresh QR image
                    const img = document.getElementById('qr-image');
                    img.src = qrImageUrl + '?t=' + Date.now();
                }
            } catch (error) {
                console.error('Error updating status:', error);
            }
        }
        
        // Initial update
        updateStatus();
        
        // Poll for status every 500ms
        setInterval(updateStatus, 500);
    </script>
</body>
</html>
        """


def create_web_ui(config, device_flow_client, display):
    """Factory function to create web UI instance."""
    return WebUI(config, device_flow_client, display)
