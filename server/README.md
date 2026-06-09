# server/ — Servidor de tracking do MLflow (DGB)

Imagem Docker do **MLflow tracking server** que roda em **Cloud Run**, sem auth
nativa do MLflow, protegido por **IAP** (direto no Cloud Run, GA).

- **Backend store:** Cloud SQL Postgres (metadados, runs, Model Registry).
- **Artifact store:** GCS (`gs://inspire-7-finep-mlflow-artifacts`), com acesso
  **direto pelos clientes**. O servidor sobe **sem** `--serve-artifacts` — ele
  só guarda os URIs; o upload/download dos artefatos é feito pelo cliente via
  `google-cloud-storage` + ADC.

## Configuração (env vars)

O `entrypoint.sh` espera duas env vars (geridas pelo **Terraform** no Cloud Run,
não definidas na imagem):

| Env var | Exemplo | Descrição |
|---------|---------|-----------|
| `MLFLOW_BACKEND_STORE_URI` | `postgresql+psycopg2://USER:PASS@HOST:5432/mlflow` | Backend store (Cloud SQL Postgres) |
| `MLFLOW_DEFAULT_ARTIFACT_ROOT` | `gs://inspire-7-finep-mlflow-artifacts` | Raiz dos artefatos (GCS) |

O servidor escuta em `0.0.0.0:8080` e expõe o health em `/health`.

## Rodar localmente (SQLite + ./mlruns)

Sem Docker, direto com o MLflow instalado (use venv):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

mlflow server \
  --host 0.0.0.0 --port 8080 \
  --backend-store-uri sqlite:///mlflow.db \
  --default-artifact-root ./mlruns
# health: curl -f http://localhost:8080/health
```

Com Docker (mesma imagem do Cloud Run, backend SQLite p/ teste):

```bash
docker build -t dgb-mlflow-server .
docker run --rm -p 8080:8080 \
  -e MLFLOW_BACKEND_STORE_URI="sqlite:////tmp/mlflow.db" \
  -e MLFLOW_DEFAULT_ARTIFACT_ROOT="/tmp/mlruns" \
  dgb-mlflow-server
```

## Smoke test

```bash
./tests/test_smoke.sh
```

Builda a imagem, sobe o container com SQLite + artefatos locais e faz
`curl -f localhost:8080/health`. Requer Docker.

## Build & deploy (CI)

O deploy é automático via GitHub Actions (`.github/workflows/server-build-deploy.yml`),
em `push` na `main` que toque `server/**`:

1. Autentica no GCP via Workload Identity Federation.
2. Builda e dá push em
   `southamerica-east1-docker.pkg.dev/inspire-7-finep/destaquesgovbr-mlflow/mlflow:<sha>` (e `:latest`).
3. `gcloud run services update destaquesgovbr-mlflow --image ... --region southamerica-east1`.

> O deploy **só atualiza a imagem**. Env vars (`MLFLOW_BACKEND_STORE_URI`,
> `MLFLOW_DEFAULT_ARTIFACT_ROOT`), IAP, conexão Cloud SQL e service account
> são geridos pelo **Terraform** no repo `infra/`.
