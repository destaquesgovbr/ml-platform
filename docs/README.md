# Documentação — MLflow DGB para Data Scientists

Estes tutoriais explicam como usar o servidor **MLflow compartilhado** do Destaques Gov.BR
(`destaquesgovbr-mlflow`), que roda em **Cloud Run protegido por IAP**, com backend de metadados
em **Cloud SQL Postgres** e artefatos em **GCS** (acesso direto pelos clientes).

> Os tutoriais assumem que o servidor **já está implantado**. Você só precisa configurar o seu
> cliente (PC ou VM) e começar a logar experimentos.

## Índice

| # | Tutorial | Quando usar |
|---|----------|-------------|
| — | [Visão geral da arquitetura](#visão-geral-da-arquitetura) | Entender o desenho antes de começar |
| 01 | [Getting Started no computador pessoal](01-getting-started-pc.md) | Você trabalha no seu laptop/PC (fora do GCP) |
| 02 | [Getting Started na dev VM](02-getting-started-vm.md) | Você trabalha numa VM de desenvolvimento do projeto |
| 03 | [Como funciona o IAP](03-como-funciona-iap.md) | Entender o token/IAP, gerar token manual, debugar acesso |
| 04 | [Model Registry](04-model-registry.md) | Registrar, versionar, promover e carregar modelos |
| 05 | [GenAI (tracing, evaluate, prompts)](05-genai.md) | Tracing de LLM, avaliação, prompt registry |
| 06 | [Troubleshooting](06-troubleshooting.md) | Resolver erros comuns (403 IAP, GCS, token, sqlite) |

Exemplos executáveis acompanham os tutoriais:
- [`../examples/traditional/`](../examples/traditional/) — ML tradicional (sklearn/BERT) com autolog + Model Registry.
- [`../examples/genai/`](../examples/genai/) — GenAI (tracing, `mlflow.evaluate`, prompt registry).

A biblioteca cliente que esconde a complexidade do IAP vive em [`../client/`](../client/) (`dgb-mlflow`).

## Placeholders que você vai precisar

Dois valores aparecem em todos os tutoriais. Pegue-os uma vez e guarde no seu shell.

| Placeholder | O que é | Como obter |
|-------------|---------|------------|
| `<MLFLOW_URL>` | URL `*.run.app` do serviço Cloud Run `destaquesgovbr-mlflow` | `gcloud run services describe destaquesgovbr-mlflow --project=inspire-7-finep --region=southamerica-east1 --format='value(status.url)'` |
| `<IAP_CLIENT_ID>` | OAuth client ID do IAP (a *audience* do ID token) | Veja abaixo |

### Obter o `<IAP_CLIENT_ID>`

O IAP client ID é exposto como output do Terraform (no repo `infra/`):

```bash
# No repo infra/, na pasta terraform/
terraform output -raw mlflow_iap_client_id
```

Se você não tem acesso ao state do Terraform, peça o valor para quem administra a infra
(ele também aparece no Console: **Security → Identity-Aware Proxy → seu serviço → OAuth client**).
É uma string no formato `NNNNNNNNNNNN-xxxxxxxx.apps.googleusercontent.com`.

> O `<IAP_CLIENT_ID>` **não é segredo** — é apenas o identificador do app OAuth (a *audience*).
> O que protege o acesso é a sua identidade Google + a lista `mlflow_users` no IAP.

## Visão geral da arquitetura

O servidor MLflow **não tem autenticação nativa**. Quem protege a porta é o **IAP**, direto no
Cloud Run (recurso GA, sem load balancer). Há **dois caminhos de acesso independentes**:

1. **Metadados** (experimentos, params, métricas, registry) → vão para o servidor MLflow,
   protegido pelo IAP. O cliente precisa mandar um **ID token OIDC** no header
   `Authorization: Bearer <token>`, com `aud = <IAP_CLIENT_ID>`.
2. **Artefatos** (modelos, arquivos, imagens) → o cliente **lê e grava direto no GCS**
   (`gs://inspire-7-finep-mlflow-artifacts`) usando ADC (Application Default Credentials).
   O servidor **não** faz proxy de artefatos (sem `--serve-artifacts`).

```
                          VOCÊ
        ┌───────────────────┴───────────────────────┐
        │                                            │
  (1) METADADOS                                (2) ARTEFATOS
  Authorization: Bearer <ID token>             ADC (google-cloud-storage)
  aud = <IAP_CLIENT_ID>                        leitura/escrita DIRETA
        │                                            │
        ▼                                            │
  ┌───────────┐  valida ID token / login Google      │
  │    IAP    │  (membros em mlflow_users)            │
  └─────┬─────┘                                       │
        │ run.invoker                                 │
        ▼                                             │
  ┌──────────────────────────────────┐               │
  │ Cloud Run: destaquesgovbr-mlflow  │               │
  │   mlflow server (gunicorn :8080)  │               │
  │   SEM auth nativa, SEM            │               │
  │   --serve-artifacts               │               │
  └───────┬──────────────────────────┘               │
          │ metadados                                 │
          ▼                                           ▼
  ┌────────────────────────┐          ┌──────────────────────────────────┐
  │ Cloud SQL Postgres     │          │ GCS                               │
  │ DB: mlflow             │          │ gs://inspire-7-finep-             │
  │ IP público <IP da instância Cloud SQL>│          │      mlflow-artifacts             │
  │ (experimentos, runs,   │          │ (modelos e arquivos;             │
  │  registry, métricas)   │          │  versionado + lifecycle)          │
  └────────────────────────┘          └──────────────────────────────────┘
```

Consequências práticas (importantes para entender os erros):

- Para a **UI no browser** você precisa estar na lista `mlflow_users` (role `iap.httpsResourceAccessor`).
  É um login Google normal.
- Para o **cliente Python** você precisa de **duas coisas ao mesmo tempo**:
  - acesso ao IAP (token válido) → senão dá **403 do IAP** nas chamadas de metadados;
  - ADC com permissão no bucket → senão dá **erro do GCS** ao subir/baixar artefatos.
- Um pode funcionar sem o outro: você pode logar params/métricas (metadados OK) mas falhar ao
  subir o artefato (GCS faltando), e vice-versa. Veja [Troubleshooting](06-troubleshooting.md).

## Desenvolvimento local (offline)

Você não precisa do servidor remoto para desenvolver e rodar testes. Dá para subir um MLflow
local com SQLite:

```bash
mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns
# ou, direto no código/teste:
#   import mlflow; mlflow.set_tracking_uri("sqlite:///mlflow.db")
```

O `dgb_mlflow.configure()` detecta a ausência do `<IAP_CLIENT_ID>` e cai para tracking local,
facilitando o ciclo de desenvolvimento. Detalhes em [Troubleshooting](06-troubleshooting.md#dev-local-com-sqlite).
