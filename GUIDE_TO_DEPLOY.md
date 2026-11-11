# MAS-RA Deployment Guide

Complete step-by-step guide to deploying the **Autonomous AI Research & Literature Review Assistant (MAS-RA)** across Docker Compose, Cloud PaaS, a Linux VPS, or static hosting (for the classroom demo).

---

## 1. Deployable Components Overview

| Component | Purpose | Entrypoint / Source | Default Port | Persistence |
| :--- | :--- | :--- | :--- | :--- |
| **FastAPI REST Backend** | Project CRUD, background research runs, HITL resume, JSON/MD/PDF export | `app/api/app.py` (`uvicorn app.api.app:app`) | `8000` | PostgreSQL or SQLite (`research.db` + `research_checkpoints.db`) |
| **Streamlit Dashboard** | Interactive UI for project creation, run monitoring, review checkpoints, exports | `streamlit_app.py` / `streamlit_app/app.py` | `8501` | Runs LangGraph in-process via `@st.cache_resource`; uses same DB config |
| **PostgreSQL + pgvector** | Production relational tables (`projects`, `research_runs`, `reports`) and LangGraph checkpoints | `pgvector/pgvector:pg16` (in `docker-compose.yml`) | `5432` | Persistent Docker volume (`postgres_data`) or managed Postgres |
| **Classroom Interactive Demo** | Zero-backend, single-page educational walkthrough | `interactive demo/` (`index.html`, `styles.css`, `app.js`) | Static HTTPS (`80`/`443`) | Client-side only (no DB or API keys required) |

---

## 2. Pre-Deployment Checklist & Known Codebase Caveats

Check these 5 items before building or publishing to any production environment:

1. **Populate `.dockerignore` (currently empty):**
   - `.dockerignore` in the repo root is empty, while `Dockerfile` executes `COPY . .`.
   - Before running `docker build` or `docker compose up --build`, add the exclusions below to `.dockerignore` so local secrets, virtual environments, and test databases are not baked into image layers:
     ```gitignore
     .venv/
     venv/
     __pycache__/
     *.py[cod]
     .pytest_cache/
     .git/
     .github/
     .vscode/
     .env
     .env.*
     !.env.example
     *.db
     *.sqlite
     *.sqlite3
     backups/
     reports/
     *.pptx
     ```

2. **Avoid Stale `.env` Overrides on Cloud/Container Hosts:**
   - `app/config.py` calls `load_dotenv(dotenv_path=_ENV_PATH, override=True)`.
   - Because `override=True` replaces process environment variables if `.env` exists at the repository root, never deploy or commit a `.env` file when you intend to inject configuration through Docker Compose, PaaS secrets, or `systemd` `EnvironmentFile`.

3. **Account for the `localhost:5432` PostgreSQL Connectivity Check:**
   - `app/database/checkpointer.py` (`_is_postgres_available`) and `app/database/service.py` (`_is_postgres_available`) currently probe `host="localhost", port=5432` by default instead of parsing the hostname and port out of `DATABASE_URL`.
   - **What this means in practice:**
     - **Same-VM / Localhost Postgres (`localhost:5432`)**: Connects cleanly to PostgreSQL and `PostgresSaver`.
     - **Docker Compose (`@postgres:5432`) or Cloud Postgres (`@your-db-host:5432`)**: Without updating `_is_postgres_available` to extract the hostname/port from `DATABASE_URL`, the app detects port `5432` as closed on `localhost` inside the app container and falls back to container-local SQLite (`research.db` and `research_checkpoints.db`).
   - Update `_is_postgres_available` to parse `urllib.parse.urlparse(db_url)` host/port before relying on Docker networking (`@postgres:5432`) or managed cloud Postgres in production.

4. **Restrict CORS & Protect `/api/*` Endpoints Before Public Exposure:**
   - `app/api/app.py` currently configures `CORSMiddleware` with `allow_origins=["*"]`.
   - `app/api/auth.py` implements `verify_api_key` (`X-API-Key` header checked against `API_AUTH_KEY`), but `app/api/routes.py` does not currently wire `Depends(verify_api_key)` onto its `APIRouter(prefix="/api")` routes.
   - Before exposing port `8000` publicly: either attach `dependencies=[Depends(verify_api_key)]` to `router` (with `API_AUTH_KEY` set) and narrow `allow_origins`, or keep port `8000` internal behind Nginx/Caddy or private networking.

5. **Run FastAPI with 1 Worker Process:**
   - `app/api/routes.py` stores active graph instances in an in-memory dictionary (`_ACTIVE_GRAPHS`) inside the worker process.
   - Keep Uvicorn at 1 worker (matching `CMD ["uvicorn", "app.api.app:app", "--host", "0.0.0.0", "--port", "8000"]` in `Dockerfile` and `docker-compose.yml`).

---

## 3. Environment Variables Reference

Values are loaded in `app/config.py` (with defaults shown from `.env.example` and `Settings`):

| Variable | Required? | Default / Example | Notes |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | Recommended | `production` (`development` in `.env.example`) | Controls `/health` `env` output; avoid `testing` in prod (`testing` uses RAM-only `MemorySaver`) |
| `LOG_LEVEL` | Optional | `INFO` | Logging verbosity |
| `OPENAI_API_KEY` | Recommended | `sk-...` | Required for live LLM agent calls; omitted/mock falls back offline where supported |
| `OPENAI_MODEL_NAME` | Optional | `gpt-4o-mini` | Primary LLM model |
| `OPENAI_EMBEDDING_MODEL` | Optional | `text-embedding-3-small` | Embedding model setting |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional | `""` | Strongly recommended in prod to reduce Semantic Scholar HTTP 429 rate limiting |
| `ARXIV_REQUEST_DELAY_SECONDS` | Optional | `3.0` | Delay between arXiv API requests (keep `>= 3.0`) |
| `POSTGRES_USER` | Docker Compose | `postgres` | Passed to `pgvector/pgvector:pg16` container |
| `POSTGRES_PASSWORD` | Docker Compose | `postgres` | **Change to a strong secret in production** |
| `POSTGRES_DB` | Docker Compose | `research_db` | PostgreSQL database name |
| `POSTGRES_PORT` | Docker Compose | `5432` | Host port mapped to Postgres container |
| `DATABASE_URL` | Production DB | `postgresql+psycopg://postgres:postgres@localhost:5432/research_db` | Override for Compose (`@postgres:5432`) or managed cloud Postgres |
| `API_AUTH_KEY` | Optional | `None` | Key expected by `verify_api_key` in `app/api/auth.py` |
| `MAX_PAPERS_PER_TASK` | Optional | `10` | Per-task search paper cap |
| `SEARCH_TIMEOUT_SECONDS` | Optional | `15` | External search timeout |
| `MAX_REVISION_CYCLES` | Optional | `2` | Critic revision loop limit |
| `MAX_PDF_SIZE_MB` | Optional | `15` | Per-PDF download size ceiling |
| `PDF_DOWNLOAD_TIMEOUT_SECONDS` | Optional | `15` | Timeout for PDF retrieval |
| `LANGSMITH_TRACING` | Optional | `false` | Set `true` to enable LangSmith traces |
| `LANGSMITH_API_KEY` | Optional | `""` | Required if `LANGSMITH_TRACING=true` |
| `LANGSMITH_PROJECT` | Optional | `mas-research-assistant` | LangSmith project name |

---

## 4. Option 1: Docker Compose Deployment (Recommended Full Stack)

`docker-compose.yml` defines three services: `postgres` (`pgvector/pgvector:pg16`), `api` (`8000`), and `streamlit` (`8501`).

### Step 1: Prepare `.env` and `.dockerignore`
1. Populate `.dockerignore` using the block in Section 2.
2. Create `.env` on the Docker host (not baked into the image):
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` with real values for `OPENAI_API_KEY`, a strong `POSTGRES_PASSWORD`, `APP_ENV=production`, and optional `SEMANTIC_SCHOLAR_API_KEY`.
   - Note: `docker-compose.yml` automatically passes `DATABASE_URL: postgresql+psycopg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-research_db}` to both `api` and `streamlit`. Ensure `_is_postgres_available` parses non-localhost hosts (Section 2.3) so containers connect to `postgres:5432` rather than falling back to ephemeral SQLite.

### Step 2: Build and Start Services
```bash
docker compose up -d --build
```

### Step 3: Run Alembic Schema Migrations
Once `mas_ra_postgres` passes its `pg_isready` healthcheck and `mas_ra_api` starts, apply migrations (matching `.github/workflows/ci.yml`):
```bash
docker compose exec api alembic upgrade head
```

### Step 4: Verify Containers & Endpoints
```bash
docker compose ps
curl http://localhost:8000/health
```
- Expected `/health` response: `{"status":"healthy","env":"production"}`
- FastAPI Swagger UI: `http://<host-ip>:8000/docs`
- Streamlit Dashboard: `http://<host-ip>:8501`

### Step 5: Operations & Backups
- View logs:
  ```bash
  docker compose logs -f api streamlit postgres
  ```
- Backup PostgreSQL volume data:
  ```bash
  docker compose exec postgres pg_dump -U postgres research_db > backup.sql
  ```

---

## 5. Option 2: Cloud PaaS Deployment (Streamlit Cloud / Render / Railway)

Because `streamlit_app/app.py` compiles and invokes the LangGraph pipeline directly inside the Streamlit process (`get_shared_compiled_graph()`), you can deploy Streamlit standalone without running a separate FastAPI worker, OR deploy FastAPI and Streamlit as two services sharing one PostgreSQL database.

### A. Deploying Standalone Streamlit UI (Streamlit Community Cloud)
1. **Push clean source to GitHub/GitLab** (`.gitignore` already excludes `.venv/`, `.env`, `*.db`, and `reports/*.pdf`).
2. **Provision a Managed PostgreSQL Database** (e.g., Neon, Supabase, or Railway Postgres with `pgvector`) if persistence across app restarts/sleep is required.
   - Without remote Postgres (remember Section 2.3), Streamlit Community Cloud containers reset local files (`research.db`) on sleep or redeploy.
3. **Create the App in Streamlit Cloud:**
   - **Repository / Branch:** your repo and target branch
   - **Main file path:** `streamlit_app.py` (root wrapper that configures `sys.path` and imports `streamlit_app.app`)
   - **Python version:** `3.12`
   - **Dependencies:** automatically read from `requirements.txt`
4. **Configure App Secrets (TOML format in Streamlit Cloud UI):**
   ```toml
   APP_ENV = "production"
   OPENAI_API_KEY = "sk-your-key"
   OPENAI_MODEL_NAME = "gpt-4o-mini"
   SEMANTIC_SCHOLAR_API_KEY = ""
   ARXIV_REQUEST_DELAY_SECONDS = "3.0"
   DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"
   ```
5. **Run migrations once from your terminal against the managed database:**
   ```bash
   DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require" alembic upgrade head
   ```

### B. Deploying FastAPI + Streamlit on Render / Railway / Fly.io
Deploy from the existing `Dockerfile` or buildpacks with two services pointing at one managed Postgres instance:
- **API Service:**
  - Start command: `uvicorn app.api.app:app --host 0.0.0.0 --port $PORT`
  - Pre-deploy / Release command: `alembic upgrade head`
  - Health Check Path: `/health`
- **Streamlit Service:**
  - Start command: `streamlit run streamlit_app/app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true`
- **Shared Env Vars:** `APP_ENV=production`, `OPENAI_API_KEY`, `DATABASE_URL`, and optional `SEMANTIC_SCHOLAR_API_KEY`.

---

## 6. Option 3: Linux VPS Production Deployment (`systemd` + Nginx / Caddy)

Running natively on Ubuntu/Debian Linux avoids container-layer database quirks (`localhost:5432` works out of the box) and avoids Windows App Control restrictions on compiled Python wheels.

### Step 1: Install System Packages
```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv build-essential postgresql postgresql-16-pgvector nginx
```

### Step 2: Create PostgreSQL User and Database
```bash
sudo -u postgres psql -c "CREATE USER masra WITH PASSWORD 'CHANGE_THIS_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE research_db OWNER masra;"
sudo -u postgres psql -d research_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Step 3: Clone Code, Install Dependencies, and Run Migrations
```bash
sudo mkdir -p /opt/mas-ra && sudo chown $USER:$USER /opt/mas-ra
git clone <your-repo-url> /opt/mas-ra
cd /opt/mas-ra

python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create `/opt/mas-ra/.env` (readable only by the service user: `chmod 600 /opt/mas-ra/.env`):
```ini
APP_ENV=production
LOG_LEVEL=INFO
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL_NAME=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
SEMANTIC_SCHOLAR_API_KEY=
ARXIV_REQUEST_DELAY_SECONDS=3.0
DATABASE_URL=postgresql+psycopg://masra:CHANGE_THIS_PASSWORD@localhost:5432/research_db
```

Run Alembic migrations:
```bash
alembic upgrade head
```

### Step 4: Create `systemd` Services

**API unit (`/etc/systemd/system/mas-ra-api.service`):**
```ini
[Unit]
Description=MAS-RA FastAPI Backend
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/mas-ra
EnvironmentFile=/opt/mas-ra/.env
ExecStart=/opt/mas-ra/.venv/bin/uvicorn app.api.app:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Streamlit unit (`/etc/systemd/system/mas-ra-ui.service`):**
```ini
[Unit]
Description=MAS-RA Streamlit Dashboard
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/mas-ra
EnvironmentFile=/opt/mas-ra/.env
ExecStart=/opt/mas-ra/.venv/bin/streamlit run streamlit_app/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start both services:
```bash
sudo chown -R www-data:www-data /opt/mas-ra
sudo systemctl daemon-reload
sudo systemctl enable --now mas-ra-api mas-ra-ui
sudo systemctl status mas-ra-api mas-ra-ui
```

### Step 5: Configure Nginx Reverse Proxy + HTTPS
Create `/etc/nginx/sites-available/mas-ra`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Streamlit Dashboard + WebSocket support
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # Optional: Expose FastAPI endpoints & healthcheck behind TLS
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location = /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}
```

Enable the site and issue a Let's Encrypt SSL certificate:
```bash
sudo ln -s /etc/nginx/sites-available/mas-ra /etc/nginx/sites-enabled/mas-ra
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 7. Option 4: Deploying the Static Classroom Demo (`interactive demo/`)

The `interactive demo/` folder contains only client-side assets (`index.html`, `styles.css`, `app.js`). It requires **no Python runtime, no database, and no API keys**.

### Deploy Steps (Any Static Host)
- **GitHub Pages:**
  1. Push the repository to GitHub (or copy `interactive demo/index.html`, `styles.css`, and `app.js` into a `docs/` folder or `gh-pages` branch).
  2. In GitHub repo **Settings -> Pages**, choose the branch/folder containing those 3 files and save.
- **Netlify / Cloudflare Pages / Vercel:**
  1. Connect the repository (or drag-and-drop the `interactive demo/` folder in Netlify Drop).
  2. Leave **Build command** empty.
  3. Set **Publish / Output directory** to `interactive demo`.

---

## 8. Post-Deployment Verification & Troubleshooting

### Smoke Test Checklist
1. **API Health:**
   ```bash
   curl -s https://your-domain.com/health
   # Expected: {"status":"healthy","env":"production"}
   ```
2. **Database Check:** Confirm projects created in Streamlit appear after restarting the service. If projects disappear on container restart, the app fell back to container-local SQLite (`research.db`) instead of PostgreSQL (see Section 2.3).
3. **Create & Run End-to-End Test:** Launch a small 2-paper project (`skip_human_review=False`) and confirm:
   - Papers and extracted evidence populate.
   - Execution pauses at **Human Review Checkpoint**.
   - Approving resumes synthesis and generates downloadable `.md` and `.pdf` reports.

### Common Deployment Issues
- **Previous Reports Missing After Restart:** Caused by ephemeral container storage when falling back to SQLite or missing persistent Docker volume mounts (`postgres_data`). Verify `DATABASE_URL` and Postgres connectivity.
- **Semantic Scholar HTTP 429 Rate Limits:** Set `SEMANTIC_SCHOLAR_API_KEY` in production environment variables.
- **arXiv Throttling:** Keep `ARXIV_REQUEST_DELAY_SECONDS>=3.0`.
- **Streamlit Stuck Connecting (`Please wait...`):** Missing Nginx WebSocket headers (`Upgrade` and `Connection "upgrade"`) or `proxy_read_timeout` too short.
- **Port `8000` or `8501` Permission / Firewall Blocked:** Ensure VPS firewall (`ufw allow 'Nginx Full'`) permits HTTPS (`443`) while keeping `5432` closed to public traffic.

