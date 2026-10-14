FROM node:22-bookworm-slim AS node-runtime
FROM python:3.12-slim-bookworm
WORKDIR /opt/risk-agent
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
COPY requirements.txt package.json ./
RUN pip install --no-cache-dir -r requirements.txt && npm install --omit=dev && npx playwright install --with-deps chromium
COPY app ./app
COPY config ./config
COPY frontend ./frontend
COPY scripts ./scripts
COPY models ./models
COPY reference/report-template.html ./reference/report-template.html
RUN useradd --uid 10001 --create-home risk && mkdir -p runtime && chown -R risk:risk /opt/risk-agent /opt/ms-playwright
USER risk
ENV PYTHONUNBUFFERED=1 AUTH_MODE=token
EXPOSE 8000
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1"]
