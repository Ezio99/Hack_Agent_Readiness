# Hosted Agent Readiness (Ironbark): API + worker + jailed Chromium + Replay Studio build.
# Build from the repository root:  docker compose -f deploy/compose.yaml build
FROM node:22-bookworm-slim AS studio
WORKDIR /dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY dashboard/ ./
COPY collaboration/reports/007-pilot-data /collaboration/reports/007-pilot-data
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright BROWSER_USE_CONFIG_DIR=/tmp/browser-use
WORKDIR /app
COPY requirements.lock ./
RUN pip install -r requirements.lock && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-deps . && python -c "import agent_readiness.hosted.serve"
# Sanitized, versioned lifecycle datasets (M8): the preloaded M7 evaluation; validated at startup (a dataset that fails is not served).
COPY datasets ./datasets
COPY --from=studio /dashboard/dist /srv/studio
COPY deploy/jail-policy.json /etc/agent-readiness/jail.json
# Defence in depth only (the network namespace is the boundary): no local-file pages in Chromium.
COPY deploy/chromium-policy.json /etc/chromium/policies/managed/agent-readiness.json
RUN useradd --uid 10001 --create-home --home-dir /home/agent agent \
    && mkdir -p /data /app/scanner-data/live && chown -R agent:agent /data /app
USER agent
# Lifecycle (M8): the owner-approved frozen suites (store) and the Stage B root (owner armings, launch claims, per-launch authorisations and
# ledgers) live on the data volume; the serve process AND the owner's `docker compose exec app python -m agent_readiness.lifecycle.arming` use them.
ENV AR_HOSTED_DATA=/data/hosted AR_STATIC_DIR=/srv/studio AR_HOST=0.0.0.0 AR_PORT=8080 AR_LIFECYCLE_DATASETS=/app/datasets/lifecycle \
    AR_LIFECYCLE_STORE=/data/hosted/lifecycle/store AR_STAGE_B_ROOT=/data/hosted/lifecycle/stage-b \
    AGENT_READINESS_BROWSER_JAIL=/etc/agent-readiness/jail.json
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=5)"]
CMD ["python", "-m", "agent_readiness.hosted.serve"]
