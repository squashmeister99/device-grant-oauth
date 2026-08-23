"""
FastAPI web server providing a button-driven UI (login/refresh/logout) with
a modal <dialog> for QR display and flow status, instead of a terminal.
"""

import logging
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)


class WebUI:
    """Web UI server for device authorization display and control."""

    def __init__(self, config, controller, display):
        """
        Initialize the web UI server.

        Args:
            config: Application configuration.
            controller: AuthController instance driving login/refresh/logout.
            display: Display module for QR generation.
        """
        self.config = config
        self.controller = controller
        self.display = display
        self.app = FastAPI(title="Device Authorization Grant Demo")
        self.setup_routes()

    def setup_routes(self) -> None:
        """Set up FastAPI routes."""

        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            """Serve the main HTML page."""
            return self.get_html_page()

        @self.app.get("/api/status")
        async def get_status():
            """Get current flow/session status for the UI to poll."""
            return JSONResponse(self.controller.get_status())

        @self.app.post("/api/login")
        async def start_login():
            """Start the device authorization flow in the background."""
            return JSONResponse(self.controller.start_login())

        @self.app.post("/api/refresh")
        async def refresh_token():
            """Refresh the access token using the stored refresh token."""
            return JSONResponse(self.controller.refresh())

        @self.app.post("/api/logout")
        async def logout():
            """Revoke tokens and clear local session state."""
            return JSONResponse(self.controller.logout())

        @self.app.get("/api/qr")
        async def get_qr():
            """Get QR code as PNG image for the in-progress login flow."""
            verification_uri_complete = self.controller.qr_source_uri()
            if not verification_uri_complete:
                return Response(content=b"", media_type="image/png", status_code=204)

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
            max-width: 520px;
            width: 100%;
            padding: 40px;
            text-align: center;
        }

        .header {
            margin-bottom: 30px;
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

        #session-panel {
            margin: 20px 0 30px;
        }

        .button-row {
            display: flex;
            gap: 12px;
            justify-content: center;
            margin-bottom: 10px;
        }

        button {
            font-size: 15px;
            font-weight: 600;
            padding: 12px 22px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            color: white;
            transition: opacity 0.15s ease;
        }

        button:disabled {
            opacity: 0.45;
            cursor: not-allowed;
        }

        #btn-login { background: #1e3c72; }
        #btn-refresh { background: #2a5298; }
        #btn-logout { background: #a33; }

        .qr-code {
            background: white;
            padding: 20px;
            border-radius: 10px;
            display: inline-block;
            border: 2px solid #e0e0e0;
            margin: 10px 0;
        }

        .qr-code img {
            width: 260px;
            height: 260px;
            display: block;
        }

        .code-section {
            background: #f5f5f5;
            padding: 16px;
            border-radius: 10px;
            margin: 16px 0;
        }

        .code-section p {
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        }

        .user-code {
            font-size: 32px;
            font-weight: bold;
            color: #1e3c72;
            letter-spacing: 5px;
            font-family: 'Courier New', monospace;
            margin: 10px 0;
        }

        .status {
            padding: 14px;
            border-radius: 10px;
            font-size: 15px;
            font-weight: 500;
            text-align: left;
        }

        .status.pending {
            background: #fff3cd;
            color: #856404;
            border: 1px solid #ffeeba;
            text-align: center;
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

        .idle {
            color: #999;
            font-size: 15px;
        }

        .countdown {
            font-size: 16px;
            margin-top: 12px;
            color: #666;
            text-align: center;
        }

        .spinner {
            display: inline-block;
            width: 18px;
            height: 18px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #1e3c72;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            vertical-align: middle;
            margin-right: 8px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        dialog#flow-dialog {
            border: none;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
            padding: 30px;
            max-width: 420px;
            width: 90%;
        }

        dialog#flow-dialog::backdrop {
            background: rgba(0, 0, 0, 0.5);
        }

        #dialog-title {
            font-size: 20px;
            color: #1e3c72;
            margin-bottom: 16px;
            text-align: center;
        }

        #dialog-close {
            margin-top: 18px;
            width: 100%;
            background: #1e3c72;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔐 Device Authorization</h1>
            <p>Login, refresh, or logout &mdash; all from this page</p>
        </div>

        <div id="session-panel"></div>

        <div class="button-row">
            <button id="btn-login">Login</button>
            <button id="btn-refresh">Refresh</button>
            <button id="btn-logout">Logout</button>
        </div>
    </div>

    <dialog id="flow-dialog">
        <div id="dialog-title">Status</div>
        <div id="dialog-body"></div>
        <button id="dialog-close" style="display: none;">Close</button>
    </dialog>

    <script>
        const dialog = document.getElementById('flow-dialog');
        const dialogTitle = document.getElementById('dialog-title');
        const dialogBody = document.getElementById('dialog-body');
        const closeBtn = document.getElementById('dialog-close');
        const loginBtn = document.getElementById('btn-login');
        const refreshBtn = document.getElementById('btn-refresh');
        const logoutBtn = document.getElementById('btn-logout');
        let pollHandle = null;

        function setButtonsEnabled(hasSession, inFlight) {
            loginBtn.disabled = inFlight;
            refreshBtn.disabled = inFlight || !hasSession;
            logoutBtn.disabled = inFlight || !hasSession;
        }

        function sessionHtml(session) {
            return `
                <div class="status success">
                    <strong>User:</strong> ${session.username}<br>
                    <strong>Scopes:</strong> ${session.scopes}<br>
                    <strong>Access token:</strong> ${session.access_token_masked}<br>
                    ${session.refresh_token_masked ? `<strong>Refresh token:</strong> ${session.refresh_token_masked}<br>` : ''}
                </div>`;
        }

        function renderSessionPanel(status) {
            const panel = document.getElementById('session-panel');
            panel.innerHTML = status.session
                ? sessionHtml(status.session)
                : `<div class="idle">No active session. Click Login to authenticate.</div>`;
            setButtonsEnabled(!!status.session, false);
        }

        function renderDialog(status) {
            if (status.phase === 'starting' || status.phase === 'pending') {
                dialogTitle.textContent = 'Device Authorization';
                let codeHtml = '';
                if (status.user_code) {
                    const formatted = status.user_code.match(/.{1,2}/g).join(' - ');
                    const minutes = Math.floor((status.time_remaining || 0) / 60);
                    const seconds = (status.time_remaining || 0) % 60;
                    codeHtml = `
                        <div style="text-align:center;">
                            <div class="qr-code"><img src="/api/qr?t=${Date.now()}" alt="QR Code"></div>
                        </div>
                        <div class="code-section">
                            <p>Or enter this code:</p>
                            <div class="user-code">${formatted}</div>
                            <p style="font-size: 12px; color: #999;">Visit: <a href="${status.verification_uri}" target="_blank" rel="noopener noreferrer">${status.verification_uri}</a></p>
                        </div>
                        <div class="countdown">Expires in ${minutes}m ${seconds}s</div>`;
                }
                dialogBody.innerHTML = `
                    <div class="status pending"><span class="spinner"></span>${status.message}</div>
                    ${codeHtml}`;
                closeBtn.style.display = 'none';
            } else if (status.phase === 'success') {
                dialogTitle.textContent = '✅ Authentication Successful';
                dialogBody.innerHTML = sessionHtml(status.session);
                closeBtn.style.display = 'block';
            } else if (['error', 'denied', 'expired'].includes(status.phase)) {
                dialogTitle.textContent = '❌ ' + status.phase.charAt(0).toUpperCase() + status.phase.slice(1);
                dialogBody.innerHTML = `<div class="status error">${status.message}</div>`;
                closeBtn.style.display = 'block';
            } else {
                dialogTitle.textContent = 'Status';
                dialogBody.innerHTML = `<div class="status">${status.message || ''}</div>`;
                closeBtn.style.display = 'block';
            }
            if (!dialog.open) dialog.showModal();
        }

        async function pollLoginStatus() {
            const res = await fetch('/api/status');
            const status = await res.json();
            renderDialog(status);
            if (status.phase === 'starting' || status.phase === 'pending') {
                pollHandle = setTimeout(pollLoginStatus, 1000);
            } else {
                clearTimeout(pollHandle);
                renderSessionPanel(status);
            }
        }

        loginBtn.addEventListener('click', async () => {
            setButtonsEnabled(false, true);
            await fetch('/api/login', { method: 'POST' });
            pollLoginStatus();
        });

        refreshBtn.addEventListener('click', async () => {
            setButtonsEnabled(true, true);
            const res = await fetch('/api/refresh', { method: 'POST' });
            const status = await res.json();
            renderDialog(status);
            renderSessionPanel(status);
        });

        logoutBtn.addEventListener('click', async () => {
            setButtonsEnabled(true, true);
            const res = await fetch('/api/logout', { method: 'POST' });
            const status = await res.json();
            renderDialog(status);
            renderSessionPanel(status);
        });

        closeBtn.addEventListener('click', () => dialog.close());

        // Initial load: show existing session state, if any.
        fetch('/api/status').then(r => r.json()).then(renderSessionPanel);
    </script>
</body>
</html>
        """


def create_web_ui(config, controller, display):
    """Factory function to create web UI instance."""
    return WebUI(config, controller, display)
