# dgb-mlflow

Biblioteca cliente que configura o MLflow do **Destaques Gov.BR** escondendo a
complexidade do **IAP** (Identity-Aware Proxy) e do tracking remoto.

O servidor de tracking roda em Cloud Run **sem auth nativa do MLflow**, protegido
por IAP. A autenticação do cliente tem duas partes independentes:

1. **Metadados** (experimentos, runs, métricas): header
   `Authorization: Bearer <ID token OIDC>`, com `aud` = IAP OAuth client id.
   Este pacote injeta esse header automaticamente.
2. **Artefatos** (modelos, plots, datasets): o cliente lê/grava **direto** no
   bucket GCS via `google-cloud-storage` + ADC. Não passa pelo servidor.

## Instalação

```bash
pip install dgb-mlflow          # ou: pip install ./client (deste repo)
```

## Uso

```python
import dgb_mlflow
import mlflow

dgb_mlflow.configure()          # resolve o ambiente (remoto-IAP ou local)

with mlflow.start_run():
    mlflow.log_metric("acc", 0.97)
    mlflow.log_artifact("modelo.pkl")   # vai direto pro GCS
```

`configure()` retorna a tracking URI efetiva e loga o modo escolhido
(`remoto-IAP` ou `local`).

### No PC (desktop)

```bash
gcloud auth application-default login            # ADC p/ artefatos + impersonação
export DGB_MLFLOW_TRACKING_URI="https://mlflow.dgb.gov.br"
export DGB_MLFLOW_IAP_CLIENT_ID="<IAP OAuth client id>"
```

Como a ADC do desktop é uma credencial de **usuário** (não cunha ID tokens
diretamente), o pacote **impersona** a SA cliente
`destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com` para gerar
o ID token. Você precisa de `roles/iam.serviceAccountTokenCreator` nessa SA.

### Na VM / Cloud Run (Service Account)

```bash
export DGB_MLFLOW_TRACKING_URI="https://mlflow.dgb.gov.br"
export DGB_MLFLOW_IAP_CLIENT_ID="<IAP OAuth client id>"
```

Na VM/SA o ID token vem direto do **metadata server**
(`fetch_id_token`) — sem impersonação. Os artefatos usam a SA da própria VM.

### Desenvolvimento local (offline, sem GCP)

Sem `DGB_MLFLOW_TRACKING_URI`, o pacote cai no fallback local:

```python
dgb_mlflow.configure()          # -> sqlite:///mlflow.db, artefatos em ./mlruns
```

Ou rode um servidor local:

```bash
mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns
```

## Variáveis de ambiente

| Variável | Descrição | Default |
|----------|-----------|---------|
| `DGB_MLFLOW_TRACKING_URI` | URI do tracking server | `sqlite:///mlflow.db` (local) |
| `DGB_MLFLOW_IAP_CLIENT_ID` | IAP OAuth client id (`aud` do ID token) | — (sem ele, sem auth IAP) |
| `DGB_MLFLOW_CLIENT_SA` | SA cliente p/ impersonação (desktop) | `destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com` |
| `MLFLOW_TRACKING_TOKEN` | Override manual do ID token (debug/CI) | — |

O modo **remoto-IAP** só é ativado quando a URI é `https://...` **e** há um
`DGB_MLFLOW_IAP_CLIENT_ID`. Caso contrário, opera em **modo local**.

## API

- `dgb_mlflow.configure(tracking_uri: str | None = None) -> str`
  Resolve a URI (`arg > env > local`), ativa/desativa o provider de headers do
  IAP e chama `mlflow.set_tracking_uri`. Retorna a URI efetiva.
- `dgb_mlflow.get_iap_token(client_id: str) -> str`
  Retorna um ID token OIDC (`aud = client_id`). Ordem:
  `MLFLOW_TRACKING_TOKEN` > metadata server (VM/SA) > impersonação (desktop).

## Como o header é injetado

O pacote registra um `RequestHeaderProvider` via entry point
`mlflow.request_header_provider`. O MLflow o consulta em **toda** requisição ao
tracking server; ele só age quando `configure()` ativou o modo IAP.

## Desenvolvimento

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
ruff check src tests
```

Os testes rodam **offline**: todas as chamadas ao Google
(`fetch_id_token` / impersonação) são mockadas e o tracking usa SQLite em
`tmp_path`.
