# Plano — MLflow para a equipe de Data Science (DGB)

## Context

A equipe de DS precisa de um servidor MLflow compartilhado para tracking de experimentos,
model registry e features de GenAI (tracing/avaliação). Os data scientists trabalham tanto
nas **VMs de desenvolvimento** (uma por pessoa, criadas pelo `reusable-terraform`) quanto nos
**computadores pessoais (internet)**. Para simplificar, o MLflow roda **sem autenticação nativa**,
protegido por **IAP**.

Descoberta-chave da pesquisa: **IAP direto no Cloud Run é GA** (sem load balancer, sem custo extra,
a URL `*.run.app` já fica protegida). Isso encaixa no padrão do projeto (tudo em Cloud Run, sem LB)
e elimina toda a stack de ALB + NEG + cert gerenciado que seria necessária antes.

Decisões confirmadas com o usuário:
- **Acesso**: lista de emails individuais numa variável `mlflow_users` no Terraform (não Google Group).
- **Código**: novo repo dedicado **`ml-platform`** (segue o padrão multi-repo: portal/, graphql-api/, …).
- **Identidades**: há membros externos (gov/parceiros/gmail) → tela de consentimento OAuth do tipo **External**.
- **Artefatos** (decidido antes): **acesso direto ao GCS** pelos clientes (modelos grandes), não proxied.
- **TDD** onde fizer sentido (helper lib + projetos de exemplo; infra validada por smoke test E2E).

## Arquitetura

```
  Browser (UI)        ─┐
  Cliente MLflow (VM)  ├─►  IAP (consent External, run.invoker p/ IAP SA)
  Cliente MLflow (PC)  ─┘     │  valida ID token (aud = IAP client ID) / login Google
                             ▼
              ┌─────────────────────────────────────┐
              │ Cloud Run: destaquesgovbr-mlflow      │
              │  mlflow server (gunicorn, :8080)      │
              │  iap_enabled = true                   │
              │  ingress = INGRESS_TRAFFIC_ALL        │
              │  min_instances = 1                    │
              └──────┬──────────────────────┬─────────┘
       metadados     │                      │  (registry/preview lê artefato)
       (backend)     ▼                      ▼
        ┌────────────────────────┐   ┌──────────────────────────────┐
        │ Cloud SQL Postgres     │   │ GCS: inspire-7-finep-         │
        │ DB: mlflow / mlflow_app│   │      mlflow-artifacts         │
        │ via IP público          │   │ (versionado + lifecycle)      │
        │ <IP da instância Cloud SQL> (DATABASE_ │   └──────────────────────────────┘
        │ URL secret) — sem VPC    │            ▲
        └────────────────────────┘            │ upload/download DIRETO
                                              │ (google-cloud-storage + ADC)
                          Clientes (VM SA + usuários) ──┘
```

**Fluxo de auth do cliente** (o ponto sensível):
- **Metadados** → o cliente manda `Authorization: Bearer <ID token>` (aud = **IAP OAuth client ID**).
  MLflow injeta esse header via `MLFLOW_TRACKING_TOKEN` **ou** via plugin `request_header_provider`
  (preferido — regenera o token a cada request, contornando a expiração de ~1h).
- **Artefatos** → o cliente lê/grava `gs://…-mlflow-artifacts` direto, usando ADC
  (`gcloud auth application-default login` no PC; SA da VM na VM). Servidor **não** usa `--serve-artifacts`.

## Workstreams e arquivos

### WS1 — Infra (repo `infra/`, GitOps via PR)

Novo arquivo **`infra/terraform/mlflow.tf`** espelhando os padrões de `graphql-api.tf` + `cloud_sql.tf`:

- `google_artifact_registry_repository.mlflow` → `destaquesgovbr-mlflow` (DOCKER, cleanup keep 30).
- `google_service_account.mlflow` → `destaquesgovbr-mlflow`.
- `google_sql_database.mlflow` + `google_sql_user.mlflow_app` (+ `random_password`) na instância
  `destaquesgovbr-postgres` existente.
- `google_secret_manager_secret.mlflow_postgres_connection_string` (`mlflow-postgres-connection-string`)
  — versão construída com **IP público `<IP da instância Cloud SQL>`** (mesmo padrão real do govbrnews; ver Nota 1).
- `google_storage_bucket` `inspire-7-finep-mlflow-artifacts` — região SP, uniform access,
  versioning on, lifecycle (NEARLINE 90d / COLDLINE 365d), seguindo `gcs.tf`.
- `google_cloud_run_v2_service.mlflow`:
  - `ingress = INGRESS_TRAFFIC_ALL`, `iap_enabled = true`.
  - imagem placeholder + `lifecycle { ignore_changes = [template[0].containers[0].image] }`.
  - `scaling { min_instance_count = 1, max = 3 }`, `cpu_idle = true`, gen2, porta 8080.
  - env: `MLFLOW_BACKEND_STORE_URI` (secret), `MLFLOW_DEFAULT_ARTIFACT_ROOT=gs://…`, `GOOGLE_CLOUD_PROJECT`.
  - startup/liveness probe em `/health`.
  - SA: `roles/cloudsql.client` (projeto), `secretAccessor` no secret, `artifactregistry.reader`,
    `storage.objectViewer` no bucket (registry/preview).
- **IAP IAM**:
  - `roles/run.invoker` para o IAP service agent `service-<PROJECT_NUMBER>@gcp-sa-iap.iam.gserviceaccount.com`.
  - `google_iap_web_cloud_run_service_iam_member` com `roles/iap.httpsResourceAccessor` para cada email
    de `var.mlflow_users` **e** para a SA compartilhada das dev VMs (`module.dev_devvm…service_account`).
- **GCS IAM** (acesso direto): `roles/storage.objectUser` no bucket para cada `var.mlflow_users` e para a SA das dev VMs.
- Nova variável em **`variables.tf`**: `mlflow_users` (list(string)); valores em `terraform.tfvars`.
- Outputs: `mlflow_url`, `mlflow_iap_client_id`, `mlflow_artifacts_bucket`.

### WS2 — Servidor MLflow (novo repo `ml-platform/`, subpasta `server/`)

Padrão do streamlit-app: `Dockerfile` (python:3.11-slim, não-root, HEALTHCHECK em `/health`),
`requirements.txt` (`mlflow[extras]`, `psycopg2-binary`, `google-cloud-storage`, `gunicorn`),
entrypoint `mlflow server --host 0.0.0.0 --port 8080 --backend-store-uri $MLFLOW_BACKEND_STORE_URI
--default-artifact-root $MLFLOW_DEFAULT_ARTIFACT_ROOT --gunicorn-opts "--timeout 120 --workers 2"`.
CI **`.github/workflows/build-deploy.yml`** (Workload Identity Federation, push→Artifact Registry
`destaquesgovbr-mlflow`, `gcloud run services update destaquesgovbr-mlflow --image …`).
Smoke test do container: subir com `sqlite:///mlflow.db` + artefatos locais e `curl /health`.

### WS3 — Biblioteca helper de cliente `dgb-mlflow` (`ml-platform/client/`) — **TDD**

Pacote Python instalável (`pip install dgb-mlflow`) que esconde a complexidade do IAP:
- `configure(tracking_uri=None)` → resolve URI + IAP client ID, registra o `request_header_provider`
  que mina ID token fresco (`google.oauth2.id_token.fetch_id_token`), valida ADC do GCS, chama
  `mlflow.set_tracking_uri`. Detecta VM vs PC automaticamente (metadata server vs ADC).
- entrypoint do plugin: `mlflow.request_header_provider` (mecanismo oficial de injeção de header).
- **Testes primeiro** (pytest, mock de `google.auth`/`id_token`): construção da aud, header `Authorization`,
  fallback de credenciais, montagem da tracking URI, comportamento sem ADC. Sem rede real.

### WS4 — Projetos de exemplo (`ml-platform/examples/`) — **TDD**

- **`traditional/`** — fine-tune de um BERT (HF Transformers) ou baseline sklearn para classificação de
  notícias gov.br; usa `mlflow.autolog()`, registra métricas/artefatos e promove no Model Registry.
  Testes: funções de preparação de dados, split, métricas de avaliação; smoke test que loga um run num
  tracking sqlite temporário (`tmp_path`) e confere params/metrics/artefato.
- **`genai/`** — MLflow GenAI: tracing + `mlflow.evaluate` (LLM-as-judge) + prompt registry sobre um caso
  de sumarização/classificação de notícias. Provider flexível (`mlflow.anthropic.autolog()` /
  `mlflow.openai.autolog()` ou pipeline HF local p/ não exigir API key de todos). **Definir provider na
  implementação** (carregar a skill `claude-api` se for Anthropic). Testes: parsing/format** de prompt,
  função de scoring determinística, smoke de tracing com cliente fake.

### WS5 — Documentação / tutoriais (`ml-platform/docs/`)

Para data scientists, em PT-BR: (1) Getting started no **PC** (`gcloud auth application-default login`,
`pip install dgb-mlflow`, `configure()`, primeiro run); (2) Getting started na **VM**; (3) como funciona
o IAP + token; (4) artefatos/Model Registry; (5) features GenAI; (6) troubleshooting (403 IAP, 401 GCS).
Linkar os exemplos de WS4 como walkthroughs executáveis.

## Valores resolvidos (da inspeção do infra/)

- **Project number**: `990583792367` → IAP service agent `service-990583792367@gcp-sa-iap.iam.gserviceaccount.com`.
- **`mlflow_users`** (default) = donos das dev VMs (= os data scientists), de `terraform.auto.tfvars`:
  `nitaibezerra@gmail.com`, `lmauricio@cpqd.com.br`, `mfilho@cpqd.com.br`, `mauriciom@cpqd.com.br`,
  `christianmoryah@gmail.com`, `augusto.herrmann@gmail.com`, `cesarv@cpqd.com.br`, `manoelad@cpqd.com.br`,
  `lpmoraes@cpqd.com.br`. Mix gmail/cpqd → **confirma consent External**.
- **SA das dev VMs**: referenciável por `module.dev_devvm.devvm_service_account_email` (output já exposto).
- **Cloud SQL**: `postgres_authorized_networks = [0.0.0.0/0]` já permite acesso público → Cloud Run alcança
  `<IP da instância Cloud SQL>` sem VPC (confirma a Nota 1). Reusar o mesmo caminho.
- **CI/WIF**: repo novo usa `vars.GCP_WORKLOAD_IDENTITY_PROVIDER` + `vars.GCP_SERVICE_ACCOUNT` (org vars),
  registry `destaquesgovbr-mlflow`. Garantir que o WIF provider aceita o repo `ml-platform`.

## Desenvolvimento local

O MLflow pode rodar **localmente** para desenvolver os projetos de exemplo (WS4) e a helper (WS3):
`mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns` (ou
`mlflow.set_tracking_uri("sqlite:///mlflow.db")` direto nos testes). Os smoke tests de TDD usam tracking
local em `tmp_path`, sem tocar no servidor Cloud Run nem no GCS. `dgb-mlflow.configure()` detecta ausência
de IAP client ID e cai para tracking local, facilitando o ciclo dev.

## Execução com Workflow + Subagentes

A implementação é orquestrada por um **Workflow** que faz fan-out de subagentes independentes, um por
workstream com diretório próprio (sem conflito de arquivos):

- **Fase Scaffold (main loop)**: cria o repo `ml-platform/` (git init), estrutura de pastas, arquivos base
  (`.gitignore`, `README.md`, `LICENSE`), `_plan/` com este plano, e o `mlflow.tf` base no `infra/`.
- **Fase Build (workflow, paralelo)** — subagentes:
  1. `server/` — Dockerfile + requirements + entrypoint + CI `build-deploy.yml` + smoke test.
  2. `client/` — pacote `dgb-mlflow` **com TDD** (testes primeiro, mocks de google.auth).
  3. `examples/traditional/` — BERT/sklearn + MLflow autolog/registry **com TDD** (tracking local).
  4. `examples/genai/` — tracing + evaluate + prompt registry **com TDD** (provider flexível; carregar
     skill `claude-api` se Anthropic).
  5. `docs/` — tutoriais PT-BR (PC + VM + IAP + registry + GenAI + troubleshooting).
  6. `infra/terraform/mlflow.tf` + `variables.tf` + `mlflow_users` no `auto.tfvars` (subagente dedicado,
     respeitando convenções de `graphql-api.tf`/`cloud_sql.tf`/`gcs.tf`).
- **Fase Verify (main loop)**: rodar `pytest` (client + examples), `docker build` smoke do server,
  `terraform fmt -check`/`validate` no infra. Corrigir o que falhar.
- **Fase Infra deploy (main loop, fora do workflow)**: branch no `infra/`, commit, push, `gh pr create`,
  **verificar o terraform-plan comentado no PR**, e só então merge → `terraform-apply.yml` roda o apply.
  Pré-requisito manual: consent screen OAuth = External (sinalizar ao usuário).

## Estratégia de TDD

- **`dgb-mlflow` e exemplos**: ciclo red→green→refactor com pytest, mocks de GCP, sem rede. É onde o TDD rende.
- **Container do servidor**: smoke test (health + log local) — teste de fumaça, não unitário.
- **Infra (Terraform)**: validada por `terraform fmt -check` + `terraform validate` no CI de plan, e por um
  **script de smoke E2E pós-deploy** (ver Verificação). Terraform não é TDD-able de forma útil aqui.

## Passos manuais (fora do Terraform)

1. **Tela de consentimento OAuth = External** no projeto (uma vez), necessária para contas de outros domínios.
2. Setar a versão do secret `mlflow-postgres-connection-string` se optarmos por não commitar a senha no state
   (mesmo padrão do govbrnews, onde a "latest" foi setada via `gcloud`).
3. Primeiro build/push da imagem (o placeholder sobe primeiro; CI assume depois).
4. Recuperar o **IAP client ID** gerado e publicá-lo na doc + default do `dgb-mlflow`.

## Verificação (E2E)

Script `ml-platform/scripts/smoke.sh` rodando de um PC fora do GCP:
1. `gcloud auth application-default print-identity-token --audiences=<IAP_CLIENT_ID>` → 200 em `/health`
   (e 403 sem token, confirmando que o IAP protege).
2. `python -c "import dgb_mlflow; dgb_mlflow.configure(); import mlflow; mlflow.set_experiment('smoke'); …"`
   cria experimento, loga um run com param/metric, sobe um artefato → confirma escrita **direta no GCS**
   (`gsutil ls gs://…-mlflow-artifacts/…`) e leitura de volta.
3. Repetir o passo 2 **de dentro de uma dev VM** (auth pela SA da VM) — valida os dois caminhos de acesso.
4. UI: abrir a `run.app` no browser, passar pelo login Google, ver o experimento.

## Notas / riscos

- **Nota 1 (Cloud SQL)**: confirmado que o graphql-api fala com o Postgres pelo **IP público
  `<IP da instância Cloud SQL>`** (sem VPC connector, sem socket). MLflow segue igual. Conferir na implementação se o acesso
  depende de `postgres_authorized_networks` — pode ser preciso garantir que o egress do Cloud Run alcança o IP.
- **External consent**: contas fora do org precisam de grant explícito (já coberto por `mlflow_users` +
  `iap.httpsResourceAccessor`); a tela External evita o bloqueio de "app não verificado" para internos do fluxo.
- **Sem RBAC no MLflow**: todos os usuários veem/editam todos os experimentos. Aceitável no início.
- **Custo**: `min_instances=1` (Cloud Run sempre quente) + Cloud SQL/GCS marginais reusando o existente.
  IAP é grátis.

## Ordem de rollout

1. WS1 (infra) em PR no `infra/` → cria SA/bucket/DB/secret/Cloud Run placeholder + IAP/IAM. (consent External manual antes).
2. WS2 (servidor) repo `ml-platform` + primeiro build/push → CI atualiza a imagem.
3. Smoke E2E (Verificação) → confirma IAP + GCS direto nos dois caminhos.
4. WS3 (`dgb-mlflow`, TDD) → publica helper + IAP client ID.
5. WS4 (exemplos, TDD) + WS5 (docs).
```
