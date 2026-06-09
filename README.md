# ml-platform — MLflow para Data Science (DGB)

Plataforma de MLflow compartilhada da equipe de Data Science do Destaques Gov.BR.
Servidor de tracking em Cloud Run protegido por **IAP** (sem auth nativa do MLflow),
backend em Cloud SQL Postgres e artefatos em GCS (acesso direto).

## Estrutura

| Pasta | Conteúdo |
|-------|----------|
| `server/` | Imagem/Dockerfile do MLflow tracking server + CI de deploy (Cloud Run) |
| `client/` | `dgb-mlflow` — biblioteca helper que configura o cliente atrás do IAP |
| `examples/traditional/` | Exemplo ML tradicional (BERT/sklearn) com autolog + Model Registry |
| `examples/genai/` | Exemplo GenAI (tracing, evaluate, prompt registry) |
| `docs/` | Tutoriais para data scientists (PC + VM) |
| `scripts/` | Smoke test E2E e utilitários |
| `_plan/` | Plano de arquitetura e implementação |

## Acesso rápido

```bash
pip install ./client            # ou: pip install dgb-mlflow
gcloud auth application-default login   # credencial p/ artefatos no GCS
python -c "import dgb_mlflow; dgb_mlflow.configure()"
```

Veja [`docs/`](docs/) para os tutoriais completos. Infra (Terraform) vive no repo `infra/`.
