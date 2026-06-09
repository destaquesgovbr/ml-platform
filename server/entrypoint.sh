#!/bin/sh
# Entrypoint do servidor MLflow.
#
# Precisa de um shell para expandir as env vars de configuração injetadas
# pelo Cloud Run (geridas pelo Terraform):
#   - MLFLOW_BACKEND_STORE_URI     -> Cloud SQL Postgres (backend store)
#   - MLFLOW_DEFAULT_ARTIFACT_ROOT -> gs://... (artefatos lidos/escritos
#                                     DIRETO pelos clientes; servidor SEM
#                                     --serve-artifacts)
#
# Não passamos --serve-artifacts de propósito: os clientes acessam o GCS
# diretamente via ADC. O servidor só guarda os metadados/URIs.
set -e

exec mlflow server \
  --host 0.0.0.0 \
  --port 8080 \
  --backend-store-uri "$MLFLOW_BACKEND_STORE_URI" \
  --default-artifact-root "$MLFLOW_DEFAULT_ARTIFACT_ROOT" \
  --gunicorn-opts "--timeout 120 --workers 2"
