# dgb-mlflow

Biblioteca cliente que configura o MLflow do **Destaques Gov.BR** escondendo a
complexidade do **IAP** (Identity-Aware Proxy) e do tracking remoto.

O servidor de tracking roda em Cloud Run **sem auth nativa do MLflow**, protegido
por **IAP direto (GA)**. Como o IAP usa o OAuth client **gerenciado pelo Google**,
acesso programático por ID token OIDC (`aud` = client id) é **bloqueado** (401
"Invalid JWT audience"). O fluxo que funciona é um **JWT auto-assinado** pela
service account via a API IAM Credentials `signJwt`. A autenticação do cliente
tem duas partes independentes:

1. **Metadados** (experimentos, runs, métricas): header
   `Authorization: Bearer <JWT>`, onde o JWT é assinado pela SA cliente (signJwt)
   com `aud` = **URL do recurso + `/*`** (ex.: `https://...run.app/*`; a URL pura,
   sem `/*`, dá 401). Este pacote injeta esse header automaticamente.
2. **Artefatos** (modelos, plots, datasets): o cliente lê/grava **direto** no
   bucket GCS via `google-cloud-storage` + ADC. Não passa pelo servidor.

## Instalação

```bash
pip install "git+https://github.com/destaquesgovbr/ml-platform.git@main#subdirectory=client"
```

Isso traz `mlflow`, `google-auth` e `google-cloud-storage` (necessário para os
artefatos no GCS) como dependências. Para desenvolvimento, de dentro do repo,
`pip install -e ./client` também funciona.

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
gcloud auth application-default login            # ADC p/ artefatos + signJwt
export DGB_MLFLOW_TRACKING_URI="https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"
```

O pacote usa a ADC para chamar `signJwt` na SA cliente
`destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com`, que assina
o JWT do IAP (audience = `<TRACKING_URI>/*`). Você precisa de
`roles/iam.serviceAccountTokenCreator` nessa SA. **Não** é necessário nenhum IAP
client id.

### Na VM / Cloud Run (Service Account)

```bash
export DGB_MLFLOW_TRACKING_URI="https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"
```

Mesmo fluxo: a ADC da própria VM/SA chama `signJwt` (na SA cliente ou nela mesma,
se configurada) para assinar o JWT. Os artefatos usam a SA da própria VM.

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
| `DGB_MLFLOW_CLIENT_SA` | SA que assina o JWT do IAP (signJwt) | `destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com` |
| `MLFLOW_TRACKING_TOKEN` | Override manual do JWT (debug/CI) | — |

O modo **remoto-IAP** é ativado sempre que a URI for `http://`/`https://`. Caso
contrário, opera em **modo local**. (A antiga `DGB_MLFLOW_IAP_CLIENT_ID` foi
**descontinuada** e é ignorada: o IAP do Cloud Run usa o OAuth client gerenciado
pelo Google, então não há client id para acesso programático.)

## API

- `dgb_mlflow.configure(tracking_uri: str | None = None) -> str`
  Resolve a URI (`arg > env > local`), ativa/desativa o provider de headers do
  IAP e chama `mlflow.set_tracking_uri`. Retorna a URI efetiva.
- `dgb_mlflow.get_iap_jwt(audience: str, signer_sa: str) -> str`
  Retorna o JWT (Bearer) do IAP. Ordem: `MLFLOW_TRACKING_TOKEN` (override) > JWT
  auto-assinado pela `signer_sa` via `signJwt` (`aud = audience`, a URL + `/*`).

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

Os testes rodam **offline**: a chamada ao Google (`signJwt`, isolada em
`auth._sign_jwt`) é mockada e o tracking usa SQLite em `tmp_path`.
