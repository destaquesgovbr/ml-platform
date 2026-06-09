#!/usr/bin/env bash
# Smoke test do servidor MLflow.
#
# Builda a imagem, sobe o container com backend SQLite + artefatos locais
# (sem tocar GCP) e verifica o endpoint de health (/health).
#
# Uso:
#   ./tests/test_smoke.sh
#
# Requer Docker. Se Docker não estiver disponível, o script falha cedo com
# uma mensagem clara (não há fallback).
set -euo pipefail

IMAGE_TAG="dgb-mlflow-server:smoke"
CONTAINER_NAME="dgb-mlflow-smoke"
PORT="8080"

# Diretório do server/ (pai de tests/).
SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: docker não encontrado no PATH. Smoke test requer Docker." >&2
  exit 1
fi

cleanup() {
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo ">> Buildando imagem ($IMAGE_TAG)..."
docker build -t "$IMAGE_TAG" "$SERVER_DIR"

echo ">> Subindo container (SQLite + artefatos locais em /tmp)..."
docker run -d --name "$CONTAINER_NAME" \
  -p "${PORT}:8080" \
  -e MLFLOW_BACKEND_STORE_URI="sqlite:////tmp/mlflow.db" \
  -e MLFLOW_DEFAULT_ARTIFACT_ROOT="/tmp/mlruns" \
  "$IMAGE_TAG"

echo ">> Aguardando o servidor responder em /health..."
ATTEMPTS=30
for i in $(seq 1 "$ATTEMPTS"); do
  if curl -fsS "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    echo ">> OK: /health respondeu (tentativa $i)."
    echo ">> Smoke test PASSOU."
    exit 0
  fi
  sleep 2
done

echo "ERRO: /health não respondeu após $((ATTEMPTS * 2))s." >&2
echo "----- logs do container -----" >&2
docker logs "$CONTAINER_NAME" >&2 || true
exit 1
