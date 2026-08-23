# Native Python Client (Host-Run)

Runs the same OAuth 2.0 Device Authorization Grant client as `../device-client`, but
directly on your machine with a local Python virtual environment instead of inside
Docker. Keycloak and Postgres still run in Docker; this client connects to Keycloak
over `localhost:8080` (already published by the root `docker-compose.yml`).

Unlike the containerized client, this version can open your default browser
automatically, since it runs on the host desktop.

## Prerequisites

- Python 3.11+ installed on your host machine (no virtual environment required)
- Keycloak + Postgres running via Docker Compose from the repo root

## Setup

```powershell
# From the repo root, start only Keycloak + Postgres (skip the containerized client)
docker-compose up -d postgres keycloak

# In this folder: install dependencies directly with your installed Python
cd native-client
python -m pip install -r requirements.txt

# Optional: copy and edit environment overrides
copy .env.example .env
```

## Usage

```powershell
python main.py login      # Start device authorization flow (opens browser automatically)
python main.py status     # Check current token status
python main.py refresh    # Refresh access token
python main.py logout     # Revoke tokens and clean up local state
```

Tokens are saved to `native-client/data/tokens.json` (not shared with the
containerized `device-client`, which stores its own tokens inside its container).

## Configuration

All settings are environment variables (see `.env.example`). Key difference from the
containerized client: `KEYCLOAK_URL` defaults to `http://localhost:8080` instead of
`http://keycloak:8080`, since there's no Docker network to resolve the `keycloak`
hostname from the host.

To disable the automatic browser launch, set `OPEN_BROWSER=false`.
