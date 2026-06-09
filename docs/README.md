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

## Os valores que você vai precisar

Toda a configuração se resume a **uma** variável de ambiente (mais o login do ADC). **Já está
preenchida nos tutoriais com a URL real do ambiente DGB** — basta exportá-la uma vez no seu shell:

```bash
export DGB_MLFLOW_TRACKING_URI="https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"
# no PC (desktop), autentique o ADC uma vez:
gcloud auth application-default login
```

| Variável | O que é | Como reconfirmar |
|----------|---------|------------------|
| `DGB_MLFLOW_TRACKING_URI` | URL `*.run.app` do serviço Cloud Run `destaquesgovbr-mlflow` | `gcloud run services describe destaquesgovbr-mlflow --project=inspire-7-finep --region=southamerica-east1 --format='value(status.url)'` |
| `DGB_MLFLOW_CLIENT_SA` (opcional) | SA que assina o JWT do IAP via `signJwt` | default: `destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com` |

> O acesso programático usa um **JWT auto-assinado** pela SA cliente (via `signJwt`), com audience
> = `<TRACKING_URI>/*`. Você **não** precisa de nenhum IAP client id — a antiga
> `DGB_MLFLOW_IAP_CLIENT_ID` foi **descontinuada**. O que protege o acesso é a sua identidade
> Google + a lista `mlflow_users` no IAP, e o papel `tokenCreator` na SA cliente.

## Visão geral da arquitetura

O servidor MLflow **não tem autenticação nativa**. Quem protege a porta é o **IAP**, direto no
Cloud Run (recurso GA, sem load balancer). Há **dois caminhos de acesso independentes**:

1. **Metadados** (experimentos, params, métricas, registry) → vão para o servidor MLflow,
   protegido pelo IAP. O cliente manda um **JWT auto-assinado** pela SA cliente (via `signJwt`) no
   header `Authorization: Bearer <JWT>`, com `aud = <TRACKING_URI>/*`.
2. **Artefatos** (modelos, arquivos, imagens) → o cliente **lê e grava direto no GCS**
   (`gs://inspire-7-finep-mlflow-artifacts`) usando ADC (Application Default Credentials).
   O servidor **não** faz proxy de artefatos (sem `--serve-artifacts`).

```
                          VOCÊ
        ┌───────────────────┴───────────────────────┐
        │                                            │
  (1) METADADOS                                (2) ARTEFATOS
  Authorization: Bearer <JWT da SA>            ADC (google-cloud-storage)
  aud = <TRACKING_URI>/*                       leitura/escrita DIRETA
        │  (assinado via signJwt)                    │
        ▼                                            │
  ┌───────────┐  valida JWT / login Google           │
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
  - ADC autenticado + `tokenCreator` na SA cliente (para assinar o JWT) + estar em `mlflow_users` →
    senão dá **401/403 do IAP** nas chamadas de metadados;
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

O `dgb_mlflow.configure()` ativa o modo remoto-IAP só quando `DGB_MLFLOW_TRACKING_URI` é
`http(s)://`; sem essa variável, ele cai para tracking local (`sqlite:///mlflow.db`), facilitando
o ciclo de desenvolvimento. Detalhes em [Troubleshooting](06-troubleshooting.md#dev-local-com-sqlite).
