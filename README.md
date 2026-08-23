# OAuth 2.0 Device Authorization Grant - Prototype Demo

A prototype demonstrating the OAuth 2.0 Device Authorization Grant flow (RFC 8628)
using Keycloak as the identity provider and a native Python client with a
button-driven web UI.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Keycloak Admin Console](#keycloak-admin-console)
- [Troubleshooting](#troubleshooting)
- [Production Deployment Notes](#production-deployment-notes)

## 🎯 Overview

Smart appliances like TV-based conference room systems have no keyboard or mouse.
They need to authenticate users securely without exposing credentials on the
device itself. The **OAuth 2.0 Device Authorization Grant** is designed exactly
for this scenario:

1. **Device** requests a device code and user code from the authorization server
2. **Device** displays a QR code (encoding the verification URL) and a short user code
3. **User** scans the QR or manually enters the code on their phone/browser
4. **User** authenticates on a separate browser/device
5. **Device** polls the authorization server until the user approves
6. **Device** receives tokens and can now make API calls on behalf of the user

## 🏗️ Architecture

Only **Keycloak** and **Postgres** run in Docker (via `docker-compose.yml`).
The Python client runs directly on your host machine with your installed
Python — no container, no virtual environment required — and connects to
Keycloak over `localhost:8080`.

```
┌────────────────────────────┐        ┌──────────────────────────┐
│  Client (host)              │  HTTP  │  Keycloak (Docker)        │
│  - FastAPI web UI + buttons│◄──────►│  - Device Authorization    │
│  - Login/Refresh/Logout    │        │    Grant realm             │
│  - Token storage (local)   │        │  - Postgres backend        │
└────────────────────────────┘        └──────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ installed on your host machine
- Port 8080 available (Keycloak) and port 8000 available (web UI)

### 1. Start Keycloak + Postgres

```powershell
docker-compose up -d
```

### 2. Run the client

```powershell
python -m pip install -r requirements.txt
python main.py
```

This opens a browser window with **Login**, **Refresh**, and **Logout** buttons.
Click **Login** to see the QR code and user code in a dialog, approve on your
phone or another browser tab, and the dialog will show your session details
(username, scopes, masked tokens) once authorized.

Terminal-only fallback (no web UI):

```powershell
python main.py login      # Start device authorization flow (ASCII QR in terminal)
python main.py status     # Check current token status
python main.py refresh    # Refresh access token
python main.py logout     # Revoke tokens and clean up local state
```

All settings are environment variables (see `.env.example`). To disable the
automatic browser launch, set `OPEN_BROWSER=false`.

## 📁 Project Structure

```
device-grant-oauth/
├── docker-compose.yml           # Orchestration: Keycloak + Postgres only
├── Makefile                     # docker-compose helpers (start/stop/reset/logs)
├── README.md                    # This file
├── .env / .env.example          # Keycloak config + client app config (shared)
├── .gitignore
├── requirements.txt
├── main.py                      # Entry point: web UI by default, CLI subcommands as fallback
│
├── keycloak/
│   ├── Dockerfile               # Keycloak 23.x base image
│   └── realm-export.json        # Pre-configured realm (client, scopes, user)
│
├── app/
│   ├── config.py                # Pydantic config loader (env vars)
│   ├── controller.py            # Thread-safe login/refresh/logout orchestrator
│   ├── device_flow.py           # Device auth request + polling state machine
│   ├── token_store.py           # Token persistence, refresh, revoke
│   ├── display.py               # ASCII QR + terminal status printing (CLI fallback)
│   └── web_ui.py                # FastAPI web UI: buttons + QR/status dialog
│
└── data/                          # Local token storage (gitignored)
```

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
   - **Users** → `testuser`:
     - Username: testuser
     - Email: testuser@example.com
     - Credentials tab → Password: testpass123 (temporary=false)
   - **Sessions**: View active device authorization sessions
   - **Events**: Audit log of all login attempts, approvals, token issues

## 🔧 Troubleshooting

### "Connection refused to Keycloak"

Keycloak takes ~30-60 seconds to start the first time. Check readiness:

```powershell
docker-compose ps
docker-compose logs keycloak | Select-String "imported"
```

### "Token error: not_allowed"

Requested scopes aren't permitted for the client/user (commonly `offline_access`).
In `.env`, keep `KEYCLOAK_SCOPES=openid profile email` and restart
the flow.

### "Port 8080/8000 already in use"

```powershell
netstat -ano | findstr :8080
```

Kill the conflicting process, or change the published port in `docker-compose.yml`
(Keycloak) or `.env` (`WEB_UI_PORT`).

### "pip install fails with a build error"

Some pinned dependency versions may lack prebuilt wheels for very new Python
releases. `requirements.txt` uses `>=` minimums so pip resolves
compatible versions automatically — rerun `python -m pip install -r requirements.txt`.

## 🏭 Production Deployment Notes

This prototype is fully functional but designed for demo/testing:

- **Token storage**: plaintext JSON file on disk — production should use a
  hardware security module, OS keychain, or secrets manager.
- **TLS**: Keycloak runs over HTTP here — production requires HTTPS/TLS with
  certificate validation.
- **Client identity**: uses a public client with no secret — production
  device fleets typically use mTLS or per-device credentials.
- **Audit logging**: logs stay local — production should ship auth events to
  a centralized audit service.

---

**Happy authenticating! 🔐**
