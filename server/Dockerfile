FROM python:3.11-slim

WORKDIR /app

# Dependências de sistema:
#   - build-essential: compila wheels nativas (ex.: dependências do mlflow[extras])
#   - curl: usado pelo HEALTHCHECK
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências primeiro (camada cacheável).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Entrypoint que expande as env vars de configuração em runtime.
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Usuário não-root.
RUN useradd --create-home --uid 10001 mlflow \
    && chown -R mlflow:mlflow /app
USER mlflow

# Cloud Run injeta a porta via env, mas fixamos 8080 (alinhado ao entrypoint).
EXPOSE 8080

# Health check — endpoint nativo do MLflow é /health.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl --fail http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
