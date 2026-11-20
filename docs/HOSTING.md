# Hosting

Everything runs from one Python process with no third-party packages. That process serves both the four apps and the API. There are three ways to host it, from quickest to production.

## Option A: a laptop (demos, today)

```bash
./run.sh
```

On Windows, double-click `run.bat`. Then open http://localhost:8000/. To let others on the same network see it, give them `http://<your-ip>:8000/`. Stop with Ctrl+C. The database is `server/data/ccl.db`; delete it to start fresh.

## Option B: a container (pilot)

The delivery folder includes a `Dockerfile`:

```bash
docker build -t chronic-care-loop .
docker run -p 8000:8000 -v ccl-data:/data chronic-care-loop
```

The database lives on the `ccl-data` volume, so it survives restarts. The same image runs on any container host. Pick one in an approved UAE region for health data:

| Platform | How |
|----------|-----|
| **Azure Container Apps / App Service (UAE North)** | Push the image to Azure Container Registry, create the app with target port 8000, and mount Azure Files at `/data`. Turn on Microsoft Entra ID sign-in ("Easy Auth") so only staff can reach it. |
| **Kubernetes (on-premises or a cloud cluster)** | A Deployment with 1 replica (SQLite is single-writer), a PersistentVolumeClaim at `/data`, and an Ingress behind your SSO proxy. |
| **A Linux VM** | Install Python 3.10+ and run `run.sh` under systemd. Put nginx in front with TLS and SSO. |

Run the nightly from the host's scheduler:

```bash
docker exec <container> python3 -m backend.engine
```

Or call `POST /api/runs/nightly` with any HTTP client.

## Option C: production

- Use PostgreSQL. Load `4-data-model/schema.postgres.sql` and `4-data-model/rules/rules.sql`.
- Port the engine to your scheduled-job platform and the API to your API stack (see `HANDOFF.md`).
- Rebuild the UIs, or keep them as static files on a web server.

## Static only (no backend)

The four HTML files work on any static host, such as SharePoint, an internal web server or Azure Static Web Apps. They then use built-in demo data, not the rules. This is useful for showing the screens to people who don't need live data.

## Security notes

- The demo server has **no login**. Never expose it to the internet. Put it behind SSO (Entra ID, an SSO proxy, or VPN-only access).
- The server refuses to serve its own code, databases and the raw extract as files. Keep `server/data/` out of any public share anyway.
- `event_log` records every API read and write. Keep it for audit.
