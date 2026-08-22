# OAuth 2.0 Device Authorization Grant - Prototype Demo

A complete, production-ready prototype demonstrating the OAuth 2.0 Device Authorization Grant flow using Keycloak as the identity provider and Python as the device client. Everything runs via Docker Compose in a single command.

## 📋 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Available Commands](#available-commands)
- [Step-by-Step Walkthrough](#step-by-step-walkthrough)
- [Keycloak Admin Console](#keycloak-admin-console)
- [Web UI Display](#web-ui-display)
- [Configuration](#configuration)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Production Deployment Notes](#production-deployment-notes)
- [Technical Decisions](#technical-decisions)

## 🎯 Overview

### The Problem

Smart appliances like TV-based conference room systems have no keyboard or mouse. They need to authenticate users securely without exposing credentials on the device itself.

### The Solution

The **OAuth 2.0 Device Authorization Grant** (RFC 8628) is designed exactly for this scenario:

1. **Device** requests a device code and user code from the authorization server
2. **Device** displays a QR code (encoding the verification URL) and a short user code
3. **User** scans the QR or manually enters the code on their phone/browser
4. **User** authenticates on a separate browser/device
5. **Device** polls the authorization server until the user approves
6. **Device** receives tokens and can now make API calls on behalf of the user

### Key Features

✅ **No password on device** — User authenticates on their own device  
✅ **QR code display** — Two formats: ASCII terminal + web UI  
✅ **Automatic realm setup** — Keycloak pre-configured via JSON import  
✅ **Token lifecycle** — Save, refresh, revoke with automatic rotation  
✅ **Full test coverage** — Unit tests for device flow and token management  
✅ **Structured logging** — Token values redacted, protocol steps logged  
✅ **Single-command startup** — `docker-compose up` and you're ready  

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Port 8080 available (Keycloak)
- Port 8000 available (Web UI)

### Launch

```bash
# Clone the repository
git clone <repo-url>
cd device-grant-oauth

# Start all services (Keycloak + Python client)
make start

# In another terminal, run the device authorization flow
make login
```

**That's it!** You'll see a QR code in the console and a web UI at `http://localhost:8000`.

### 🪟 Windows Users (No `make` Command)

Run these PowerShell commands directly instead:

```powershell
# Start all services
docker-compose up -d

# Run device authorization flow
docker-compose exec device-client python main.py login

# Refresh token
docker-compose exec device-client python main.py refresh

# Logout
docker-compose exec device-client python main.py logout

# Run tests
docker-compose exec device-client pytest -v

# View logs
docker-compose logs -f

# Stop services
docker-compose stop

# Reset everything
docker-compose down -v

# Rebuild images
docker-compose build --no-cache
```

See [Available Commands](#-available-commands) section below for all options.

## 🔄 How It Works

### Architecture

```
┌─────────────────────────────────────────┐
│         Device Client                   │
│  ┌───────────────────────────────────┐  │
│  │ Device Flow (OAuth 2.0 RFC 8628) │  │
│  │ - request_device_code()           │  │
│  │ - poll_token() with state machine │  │
│  │ - refresh & revoke support        │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ Display Layer                     │  │
│  │ - ASCII QR code (terminal)        │  │
│  │ - FastAPI web UI (TV-like screen) │  │
│  │ - Token claims decoder            │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ Token Store                       │  │
│  │ - Persist tokens locally          │  │
│  │ - Handle refresh token rotation   │  │
│  │ - Revoke via Keycloak API         │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
                   ↕ HTTP
┌─────────────────────────────────────────┐
│       Keycloak (OIDC Provider)          │
│  ┌───────────────────────────────────┐  │
│  │ Device Authorization Grant        │  │
│  │ - /auth/device endpoint           │  │
│  │ - /token endpoint                 │  │
│  │ - /revoke endpoint                │  │
│  │ - /userinfo endpoint              │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ Pre-configured Realm              │  │
│  │ - device-grant-demo               │  │
│  │ - Public client (no secret)       │  │
│  │ - Offline access scope            │  │
│  │ - Test user: testuser/testpass123 │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │ PostgreSQL Database               │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### Device Flow Sequence

```
1. Device requests device code
   POST /auth/device
   ← device_code, user_code, verification_uri_complete, expires_in=600, interval=2

2. Device displays QR code (verification_uri_complete) + user_code

3. User scans QR code or visits verification_uri in browser

4. User logs in with credentials (testuser/testpass123)

5. User approves device access

6. Device polls token endpoint (at 2s intervals, adjusting on "slow_down")
   POST /token with grant_type=urn:ietf:params:oauth:grant-type:device_code
   ← authorization_pending (retry)
   ← authorization_pending (retry)
   ← 200 OK: access_token, refresh_token, expires_in=3600

7. Device stores tokens and displays claims

8. User can later use `make refresh` to get new tokens

9. User can use `make logout` to revoke all tokens
```

## 📁 Project Structure

```
device-grant-oauth/
├── docker-compose.yml           # Orchestration: Keycloak + Python client
├── Makefile                     # Quick commands: make start, login, refresh, logout, reset
├── README.md                    # This file
├── .env.example                 # Configuration template
├── .gitignore                   # Git ignore rules
│
├── keycloak/
│   ├── Dockerfile               # Keycloak 23.x base image
│   └── realm-export.json        # Pre-configured realm (client, scopes, user)
│
└── device-client/
    ├── Dockerfile               # Python 3.12 slim image + venv
    ├── requirements.txt         # Pinned dependencies (requests, fastapi, qrcode, etc.)
    ├── main.py                  # CLI entry point (login, refresh, logout, status)
    ├── .env.example             # Per-service config example
    │
    ├── app/
    │   ├── __init__.py
    │   ├── config.py            # Pydantic config loader (env vars)
    │   ├── device_flow.py       # Device auth request + polling state machine
    │   ├── token_store.py       # Token persistence, refresh, revoke
    │   ├── display.py           # ASCII QR + status printing
    │   └── web_ui.py            # FastAPI web server for QR display
    │
    └── tests/
        ├── conftest.py          # pytest fixtures and mocks
        ├── test_device_flow.py  # State machine, polling, error handling
        ├── test_token_store.py  # Persistence, refresh, revocation
        └── test_config.py       # Config loading and validation
```

## 📦 Available Commands

### Option A: Using Make (Linux/macOS)

```bash
make start      # Start all services
make stop       # Stop services (keep volumes)
make login      # Run device authorization flow
make refresh    # Refresh access token
make logout     # Revoke tokens and clean up
make reset      # Stop and remove all containers and volumes
make test       # Run pytest suite
make logs       # Tail docker-compose logs
make rebuild    # Rebuild Docker images (no cache)
make help       # Show all available commands
```

### Option B: Direct Docker Commands (Windows/No Make)

```powershell
docker-compose up -d                              # Start all services
docker-compose stop                               # Stop services
docker-compose exec device-client python main.py login      # Login
docker-compose exec device-client python main.py refresh    # Refresh
docker-compose exec device-client python main.py logout     # Logout
docker-compose exec device-client python main.py status     # Check status
docker-compose exec device-client pytest -v      # Run tests
docker-compose logs -f                            # View logs
docker-compose down -v                            # Reset everything
docker-compose build --no-cache                   # Rebuild images
```

### Example Workflow

**Using Make:**
```bash
# Terminal 1: Start services
make start
# ... wait ~30s for Keycloak to be ready ...

# Terminal 2: Run device flow
make login
# Scan QR code or open http://localhost:8000 to see status

# Later: Refresh token
make refresh

# Later: Logout
make logout

# Cleanup everything
make reset
```

**Using PowerShell (Windows):**
```powershell
# Terminal 1: Start services
docker-compose up -d

# Terminal 2: Run device flow
docker-compose exec device-client python main.py login
# Scan QR code or open http://localhost:8000 to see status

# Later: Refresh token
docker-compose exec device-client python main.py refresh

# Later: Logout
docker-compose exec device-client python main.py logout

# Cleanup everything
docker-compose down -v
```

## 🔐 Step-by-Step Walkthrough

### 1. Starting the Services

```bash
make start
```

**What happens:**
- `docker-compose up -d` launches three containers:
  - **postgres**: Database for Keycloak
  - **keycloak**: Keycloak 23.x with auto-import of `realm-export.json`
  - **device-client**: Python 3.12 environment
- Keycloak imports the pre-configured realm and waits for health check
- Device client container is ready (waits for manual `make login`)

**Expected logs:**
```
postgres_1  | ready to accept connections
keycloak_1  | KC-SERVICES0090000: Importing realm: device-grant-demo
keycloak_1  | KC-SERVICES0050000: Realm 'device-grant-demo' imported
device_1    | (waiting for command)
```

### 2. Running Device Authorization Flow

```bash
make login
```

**Console output:**
```
============================================================
DEVICE AUTHORIZATION GRANT - LOGIN
============================================================

[10:15:30] Requesting device code from authorization server

============================================================
SCAN THIS QR CODE TO AUTHENTICATE
============================================================

  ▄▄▄▄▄▄▄ ▀██▀██ ▄▄▄▄▄▄▄
  █ ▀▀▀ █ ▀ ▀ ██ █ ▀▀▀ █
  █ ███ █ ▄█  ▀▀ █ ███ █
  █▄▄▄▄▄█ ▄ ▄ ▄ ▄ █▄▄▄▄▄█
  ▄▄▄▄▄▄▄ ▀▀▀▀▀▀ ▄▄▄▄▄▄▄
  (actual QR code rendered here)
  ▀▀▀▀▀▀▀ ▀█ ▀▄ ▀▀▀▀▀▀▀

============================================================

============================================================
ENTER THIS CODE ON YOUR DEVICE
============================================================

  >>> AB - CD - 12 - 34 <<<

============================================================

Verification URL: http://localhost:8080/auth/device

Device code expires in 600 seconds
Polling interval: 2 seconds

Waiting for authorization (press Ctrl+C to cancel)...

[10:15:32] [INFO] [device_flow] Polling device code: (redacted)...
[10:15:34] [INFO] [device_flow] Polling device code: (redacted)...
```

### 3. User Authenticates in Browser

The user has **two options:**

#### Option A: Scan QR Code
- Use phone/laptop camera to scan the QR code
- Automatically opens verification URL

#### Option B: Manual Entry
- Open browser: `http://localhost:8080/auth/device`
- Enter code: `ABCD1234`
- Click "Submit"

**Keycloak login page appears:**
```
═════════════════════════════════════════════════════════════
               Keycloak Login - device-grant-demo
═════════════════════════════════════════════════════════════

Username:  testuser
Password:  testpass123  [enter testuser/testpass123]

[Sign In]
═════════════════════════════════════════════════════════════
```

**After login:**
```
═════════════════════════════════════════════════════════════
               Grant Access
═════════════════════════════════════════════════════════════

The device is requesting access to:
  - openid
  - profile
  - email
  - offline_access

[Cancel]  [Yes, Grant Access]
═════════════════════════════════════════════════════════════
```

Click **"Yes, Grant Access"** to approve.

### 4. Device Receives Tokens

Back in the device console:

```
[10:15:45] [INFO] [device_flow] Authorization successful! Token acquired.
[10:15:45] [INFO] [token_store] Tokens saved to /data/tokens.json

============================================================
TOKEN CLAIMS
============================================================
  sub: user-uuid-12345
  preferred_username: testuser
  email: testuser@example.com
  exp: 1724164545 (2026-08-22T10:15:45+00:00)
  iat: 1724160945
  scope: openid profile email offline_access
  given_name: Test
  family_name: User
============================================================

============================================================
✅ AUTHENTICATION SUCCESSFUL
============================================================
  User: testuser
  Scopes: openid profile email offline_access
  Token expires: 2026-08-22T11:15:45+00:00
  (~3600 seconds)
============================================================
```

**What was saved locally:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJAR1dRViJ9.eyJqdGkiOiI0ZDQ...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_at": 1724164545.0,
  "expires_in": 3600,
  "saved_at": "2026-08-22T10:15:45.123456",
  "token_type": "Bearer"
}
```

(Stored at `/data/tokens.json` inside the container)

### 5. Web UI Status

Open `http://localhost:8000` to see the live web interface:

```
═══════════════════════════════════════════════════════════
                  🔐 Device Authorization
            Authenticate using your phone or computer
═══════════════════════════════════════════════════════════

                    ┌──────────────────┐
                    │ (QR Code Image)  │
                    │  150x150 pixels  │
                    └──────────────────┘

                Or enter this code:
                   AB - CD - 12 - 34
              Visit: http://localhost:8080/auth/device

                 ⏳ Waiting for authorization...
                    Expires in 9m 45s

═══════════════════════════════════════════════════════════
```

After user approves (refresh the page or auto-refresh):

```
                      ✅ Approved!
                   User authorized at 10:15:45
═══════════════════════════════════════════════════════════
```

### 6. Refresh Token

```bash
make refresh
```

**Output:**
```
============================================================
REFRESH ACCESS TOKEN
============================================================

[10:20:00] [INFO] [token_store] Attempting to refresh access token
[10:20:01] [INFO] [token_store] Access token refreshed successfully

============================================================
✅ AUTHENTICATION SUCCESSFUL
============================================================
  User: (refreshed)
  Scopes: openid profile email offline_access
  Token expires: 2026-08-22T11:20:01+00:00
  (~3600 seconds)
============================================================

============================================================
TOKEN CLAIMS
============================================================
  sub: user-uuid-12345
  preferred_username: testuser
  email: testuser@example.com
  exp: 1724165201
  ...
============================================================
```

### 7. Logout / Revoke

```bash
make logout
```

**Output:**
```
============================================================
LOGOUT
============================================================

[10:25:00] [INFO] [token_store] Revoking tokens
[10:25:00] [DEBUG] [token_store] Access token revoked
[10:25:00] [DEBUG] [token_store] Refresh token revoked
[10:25:00] [INFO] [token_store] Local token state deleted

✅ Logged out successfully
All tokens have been revoked and local state deleted.
```

**What happened:**
- Access token revoked on Keycloak server
- Refresh token revoked on Keycloak server
- Local token file deleted

---

## 🖥️ Keycloak Admin Console

### Access

```
URL: http://localhost:8080/admin
Username: admin
Password: change-me
```

### Inspect the Configuration

1. **Log in** with `admin` / `change-me`
2. **Select realm**: `device-grant-demo` (dropdown top-left)
3. **Navigate to:**
   - **Clients** → `device-client`:
     - ✅ Public client (no secret)
     - ✅ Device Authorization Grant enabled
     - ✅ Scopes: openid, profile, email, offline_access
     - ✅ Redirect URIs: http://localhost:8000/*, http://localhost:3000/*
   
   - **Users** → `testuser`:
     - Username: testuser
     - Email: testuser@example.com
     - Credentials tab → Password: testpass123 (temporary=false)
   
   - **Sessions**:
     - View active device authorization sessions
   
   - **Events**:
     - Audit log of all login attempts, approvals, token issues

### Testing Device Flow Authorization

1. Clear all tokens: `make reset`
2. Start fresh: `make start`
3. Open admin console: http://localhost:8080/admin
4. In another terminal: `make login` to trigger device flow
5. Watch **Events** tab update in real-time with:
   - DEVICE_AUTH_CODE_ISSUED
   - LOGIN
   - AUTHZ_CONSENT (if first time)
   - TOKEN_ISSUED
   - REFRESH_TOKEN_ISSUED

---

## 🌐 Web UI Display

The web UI (`http://localhost:8000`) simulates a TV screen display with:

### Features

- **Large QR code** — 300×300px, high error correction
- **User code display** — Big font, easy to read/remember
- **Countdown timer** — Shows time remaining before code expires
- **Live status updates** — Frontend polls backend every 500ms
- **Responsive design** — Works on TV screens (1920×1080) and desktops
- **TV-friendly colors** — Dark background, high contrast

### Technical Details

- **Backend**: FastAPI server on port 8000
- **Frontend**: Single-page HTML + vanilla JavaScript
- **API endpoints**:
  - `GET /` — HTML page
  - `GET /api/status` — JSON status (pending/approved/denied/expired + countdown)
  - `GET /api/qr` — QR code as PNG image

### CSS Styling

The UI includes:
- Dark blue gradient background
- Large typography (32px headers, 18px status)
- Rounded corners and shadows for depth
- Green/red/yellow status indicators
- Centered layout with max-width for readability

---

## ⚙️ Configuration

### Environment Variables

All configuration is via environment variables. Create `.env` file or pass to `docker-compose`:

```bash
# Keycloak
KEYCLOAK_REALM=device-grant-demo
KEYCLOAK_CLIENT_ID=device-client
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_SCOPES=openid profile email      # Add offline_access only if your realm/client allows it
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=change-me

# Device flow
DEVICE_CODE_LIFETIME=600               # Device code valid for 10 minutes
POLL_TIMEOUT=30                        # Stop polling after 30 seconds (fail)
POLLING_INTERVAL_MIN=2                 # Minimum poll interval
POLLING_INTERVAL_MAX=120               # Maximum poll interval (slow_down cap)

# Storage
TOKEN_STORAGE_PATH=/data/tokens.json   # Where to save tokens

# Web UI
WEB_UI_PORT=8000
WEB_UI_HOST=0.0.0.0

# Logging
LOG_LEVEL=INFO                         # DEBUG, INFO, WARNING, ERROR
```

### Keycloak 23.x Specific Settings

- **Device Authorization Grant endpoint**: `/protocol/openid-connect/auth/device`
- **Token endpoint**: `/protocol/openid-connect/token`
- **Device code lifetime**: Configured in `realm-export.json` (600s default)
- **Minimum polling interval**: 2s (RFC 8628 minimum)

**If upgrading to Keycloak 24+:**
- Verify endpoints haven't changed (unlikely, they're standardized)
- Check realm export JSON format compatibility
- Test device flow thoroughly

---

## 🧪 Testing

### Run Tests

```bash
make test
```

**Output:**
```
device_1  | ============================= test session starts ==============================
device_1  | collected 42 items
device_1  |
device_1  | tests/test_device_flow.py::TestDeviceCodeRequest::test_request_device_code_success PASSED
device_1  | tests/test_device_flow.py::TestPollingStateMachine::test_poll_success_immediate PASSED
device_1  | tests/test_device_flow.py::TestPollingStateMachine::test_poll_authorization_pending PASSED
device_1  | tests/test_device_flow.py::TestPollingStateMachine::test_poll_slow_down PASSED
device_1  | tests/test_device_flow.py::TestPollingStateMachine::test_poll_access_denied PASSED
device_1  | tests/test_device_flow.py::TestPollingStateMachine::test_poll_expired_token PASSED
device_1  | ...
device_1  | tests/test_token_store.py::TestTokenStoreSave::test_save_tokens PASSED
device_1  | tests/test_token_store.py::TestTokenStoreLoad::test_load_valid_tokens PASSED
device_1  | tests/test_token_store.py::TestTokenRefresh::test_refresh_tokens_success PASSED
device_1  | ...
device_1  | ============================== 42 passed in 3.45s ==============================
```

### Test Coverage

**Device Flow (test_device_flow.py):**
- ✅ Device code request success and errors
- ✅ Polling state machine: authorization_pending, slow_down, access_denied, expired_token
- ✅ Successful token acquisition
- ✅ Polling timeout
- ✅ Network error handling

**Token Store (test_token_store.py):**
- ✅ Save tokens (creates file, sets expiry)
- ✅ Load tokens (valid, expired, missing)
- ✅ Expiry checking with buffer
- ✅ Token refresh with rotation
- ✅ Token revocation
- ✅ Local state deletion
- ✅ Token info retrieval

**Config (test_config.py):**
- ✅ Default values
- ✅ Environment variable loading
- ✅ Endpoint URL construction
- ✅ Validation (invalid types)
- ✅ Logging setup

### Manual Testing Checklist

- [ ] `make start` completes without errors
- [ ] Keycloak health check passes (http://localhost:8080/admin/realms works)
- [ ] `make login` displays QR code + user code
- [ ] Web UI accessible at http://localhost:8000
- [ ] Scan QR or visit verification URL → Keycloak login
- [ ] Login with testuser/testpass123 → Approval screen
- [ ] Click approve → Device receives tokens
- [ ] Token claims displayed correctly
- [ ] `make refresh` works with existing token
- [ ] `make logout` revokes tokens
- [ ] `make status` shows token validity
- [ ] `make reset` cleans up everything
- [ ] `make test` passes all 42 tests

---

## 🔧 Troubleshooting

### "Connection refused to Keycloak" / "HTTP error 502"

**Symptom:**
```
[ERROR] Failed to request device code: Connection refused
```

**Cause:** Keycloak is still starting up (takes ~30-60 seconds first time)

**Solution:**
```bash
# Check Keycloak logs
make logs | grep keycloak

# Wait for health check
docker-compose ps | grep keycloak
# Should show "healthy" status

# Keycloak ready when you see:
# KC-SERVICES0050000: Realm 'device-grant-demo' imported
```

### "Device flow not enabled on client"

**Symptom:**
```
[ERROR] Token error: unsupported_grant_type
```

**Cause:** Keycloak didn't import realm or client not configured

**Solution:**
```bash
# Check Keycloak logs for import errors
make logs | grep IMPORT

# Verify realm was created
curl http://localhost:8080/realms/device-grant-demo

# If missing, manually re-import:
make reset
make start
# Wait for full startup
make login
```

### "Invalid device code" / "Expired token"

**Symptom:**
```
[ERROR] Token error: expired_token
```

**Cause:** Device code expires after 10 minutes (by default)

**Solution:**
```bash
# Run login command again to get fresh device code
make login
```

### "Token error: not_allowed"

**Symptom:**
```
[ERROR] Token error: not_allowed
```

**Cause:** Requested scopes are not permitted for the current user/client (commonly `offline_access`).

**Solution:**
```bash
# In .env, request base scopes first
KEYCLOAK_SCOPES=openid profile email

# Restart and run a fresh flow
docker-compose up -d --build
docker-compose exec device-client python main.py login
```

If you need offline tokens, re-enable `offline_access` only after confirming the realm/client user permissions allow it.

**Or increase device code lifetime:**
```bash
# Edit .env
DEVICE_CODE_LIFETIME=1800  # 30 minutes

make reset
make start
make login
```

### "Token has expired" when running `make refresh`

**Symptom:**
```
[ERROR] Token has expired
```

**Cause:** Access token expired (default 1 hour) or refresh token revoked

**Solution:**
```bash
# Run login again
make login

# Or increase token lifetime in Keycloak:
# (Edit realm-export.json, change "accessTokenLifespan": 3600 to 7200)
```

### "Clock skew" / "Token validation failed"

**Symptom:**
```
[ERROR] Token exp time in future / exp time in past
```

**Cause:** Container clocks out of sync

**Solution:**
```bash
# Check container time
docker-compose exec keycloak date
docker-compose exec device-client date

# Sync host clock and restart
timedatectl set-ntp true  # Linux
# or System Preferences → Date & Time → Update Now  # macOS
# or Settings → Time & Language → Date & time  # Windows

make reset
make start
```

### "Port 8080 already in use"

**Symptom:**
```
ERROR: for keycloak  Cannot start service keycloak: Bind for 0.0.0.0:8080 failed
```

**Solution:**
```bash
# Find process using port 8080
lsof -i :8080  # macOS/Linux
netstat -ano | findstr :8080  # Windows

# Kill process or change port in docker-compose.yml
# Change: ports: - "8080:8080"  →  ports: - "9090:8080"
# Then: KEYCLOAK_URL=http://localhost:9090
```

### "QR code not displaying"

**Symptom:**
```
QR Code generation failed: ...
```

**Cause:** qrcode library issue

**Solution:**
```bash
# Rebuild container (installs deps from scratch)
make rebuild
make start

# Or manually install dependencies
docker-compose exec device-client pip install --no-cache-dir -r requirements.txt
```

### "No token found" after logout

**Expected behavior:**
```
⚠️  No tokens found to revoke.
Local state was already clean.
```

This is correct. Token file was deleted by logout.

### Keycloak admin console unreachable

**Symptom:**
```
http://localhost:8080/admin → Refused to connect
```

**Cause:** Keycloak not ready

**Solution:**
```bash
# Wait for health check
docker-compose logs keycloak | tail -20
# Look for: KC-SERVICES0050000

# If crashed, check error:
docker-compose logs keycloak
```

---

## 🏭 Production Deployment Notes

This prototype is fully functional but designed for demo/testing. Here are key differences in production:

### 1. **Token Storage**

**Prototype:**
```python
# Plaintext JSON file
tokens.json = {
  "access_token": "eyJ...",
  "refresh_token": "eyJ..."
}
```

**Production:**
```python
# Hardware security module (TPM) or secure enclave
# - On Raspberry Pi: Use GPIO + secure storage
# - On x86: Use TPM 2.0 module
# - On AWS: Use AWS Secrets Manager / KMS
# - On Azure: Use Key Vault
# - Token never written to disk unencrypted
```

### 2. **TLS Certificate Validation**

**Prototype:**
```python
# HTTP (insecure)
response = requests.post(url, ...)  # No cert validation
```

**Production:**
```python
# HTTPS with certificate pinning
requests.post(
    url,
    verify='/path/to/ca-bundle.pem',  # Validate Keycloak certificate
    # Or use certificate pinning:
    # verify=('/path/to/keycloak-cert.pem', '/path/to/device-key.pem')
)
```

### 3. **Service Identity**

**Prototype:**
```python
# Public client (no authentication)
data = {
    'client_id': 'device-client',  # No secret
    'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'
}
```

**Production:**
```python
# Confidential client with mutual TLS (mTLS)
# Device authenticates itself to Keycloak using client certificate
# Step 1: Bootstrap device with client cert (manual provisioning or PKI)
# Step 2: Use mTLS for all API calls
data = {
    'client_id': 'device-client-12345',
    'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
    'client_assertion': jwt.encode(...)  # Self-signed JWT with device cert
}
```

### 4. **Key Rotation**

**Prototype:**
```python
# Static Keycloak certificate (not rotated)
# Device doesn't validate signature
```

**Production:**
```python
# Monitor Keycloak JWKS endpoint for key changes
# Implement key rotation:
GET https://keycloak.example.com/realms/device-grant-demo/.well-known/openid-configuration
GET https://keycloak.example.com/realms/device-grant-demo/protocol/openid-connect/certs

# Periodically refresh cached JWKS
# Update local trust store automatically
# Alert on unexpected key changes
```

### 5. **Audit Logging**

**Prototype:**
```python
logger.info(f"[{timestamp}] [device-flow] Polling device code...")
# Logs stay in container, lost on restart
```

**Production:**
```python
# Send to centralized audit service
# Include: timestamp, user_id, action, outcome, IP, device_id
# Encrypt in transit and at rest
# Retain for 7+ years per compliance
# Example: Syslog, CloudWatch, Splunk, ELK stack

audit_log({
    'event': 'DEVICE_AUTH_CODE_ISSUED',
    'device_id': 'device-12345',
    'keycloak_url': 'https://auth.example.com',
    'timestamp': datetime.now().isoformat(),
    'status': 'success'
})
```

### 6. **Network Security**

**Prototype:**
- HTTP (unencrypted)
- Docker internal network
- No firewall rules

**Production:**
- HTTPS / TLS 1.3+ only
- Private VPN / zero-trust network
- Firewall rules:
  - Device → Keycloak only on 443/TCP
  - Keycloak → Database only on 5432/TCP
  - Keycloak admin console → Only from bastion
- Rate limiting on device code endpoint

### 7. **Monitoring & Alerting**

**Prototype:**
- No monitoring

**Production:**
```python
# Metrics to track:
- Device code issuance rate (anomaly detection)
- Polling success rate (track user approval)
- Token refresh rate
- Authorization failures by error type
- Keycloak response times
- Database connection pool

# Alerts:
- "More than 100 device codes issued in 1 minute" (possible attack)
- "Token refresh success < 80%" (service degradation)
- "Keycloak response time > 1s" (performance issue)
- "Database disconnections" (critical)
```

### 8. **Database**

**Prototype:**
- PostgreSQL in container
- Single replica (no redundancy)
- No backups

**Production:**
- PostgreSQL with read replicas
- Daily encrypted backups (test restores weekly)
- High availability (multi-AZ, auto-failover)
- Point-in-time recovery enabled
- Connection pooling (pgBouncer)

### 9. **Versioning & Compatibility**

**Prototype:**
- Keycloak 23.x

**Production:**
- Keycloak 23.x LTS (or latest stable)
- Regular security update cadence (monthly)
- Test all updates in staging first
- Upgrade path for minor/major versions planned

### 10. **Scaling**

**Prototype:**
- Single instance

**Production:**
```yaml
# Horizontal scaling
Keycloak:
  - 3+ instances behind load balancer
  - Sticky sessions or distributed session store
  - Redis / external cache for sessions
  
Python Device Clients:
  - Each device is independent
  - Stateless (tokens stored locally)
  - No server-side affinity needed
  - Can scale to thousands of devices
```

---

## 📚 Technical Decisions

### Why Keycloak 23.x?

- ✅ Latest stable release (LTS)
- ✅ Full RFC 8628 Device Authorization Grant support
- ✅ No external extensions needed
- ✅ Realm import via JSON (no manual setup)
- ✅ Well-documented

### Why Python 3.12?

- ✅ Latest stable release
- ✅ Best performance (3.11+ C API improvements)
- ✅ Good library ecosystem (requests, fastapi, pydantic)
- ✅ Easy to read/debug for demo purposes

### Why FastAPI for Web UI?

- ✅ Modern async framework
- ✅ Auto-generated OpenAPI docs (`/docs`)
- ✅ Pydantic validation
- ✅ Minimal dependencies
- ✅ Fast enough for this use case

### Why file-based token storage?

- ✅ Simple for prototype
- ✅ No external services
- ✅ Good for demo in containers
- ❌ **NOT** secure for production (see notes above)

### Why requests library (sync)?

- ✅ Simpler for demonstration
- ✅ Polling loop is simple to understand
- ✅ No async/await complexity
- ⚠️ Could be upgraded to `httpx` async for production

### Why qrcode library?

- ✅ Minimal dependencies
- ✅ Supports ASCII and PNG output
- ✅ Standard Python package

---

## 📝 License

This prototype is provided as-is for educational and demonstration purposes.

---

## 🤝 Contributing

This is a reference implementation. Feel free to fork and adapt for your use case.

### Common Modifications

- **Change device code lifetime**: Edit `keycloak/realm-export.json` → `devices` section
- **Add more test users**: Edit `realm-export.json` → `users` array
- **Customize web UI**: Edit `device-client/app/web_ui.py` → HTML template
- **Change polling behavior**: Edit `device-client/app/device_flow.py` → `poll_token()` method
- **Add device ID**: Modify config to include device-specific identifier, send in device code request

---

## 📞 Support

For Keycloak documentation: https://www.keycloak.org/documentation  
For OAuth 2.0 Device Authorization Grant (RFC 8628): https://tools.ietf.org/html/rfc8628

---

**Happy authenticating! 🔐**
