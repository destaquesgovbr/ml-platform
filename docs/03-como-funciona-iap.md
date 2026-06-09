# 03 — Como funciona o IAP

Este documento explica o mecanismo de autenticação por trás do MLflow DGB. Ler isto ajuda muito
a **debugar** erros de acesso (a maioria cai em "token errado" ou "credencial do GCS faltando").

## O desenho: IAP direto no Cloud Run

O servidor MLflow **não tem login próprio**. Quem fica na frente é o **IAP**
(Identity-Aware Proxy), habilitado **direto no serviço do Cloud Run** (recurso GA — sem load
balancer, sem custo extra). Toda requisição para a `<MLFLOW_URL>` passa antes pelo IAP, que:

1. exige uma **identidade Google** válida (login no browser **ou** ID token OIDC em chamadas programáticas);
2. confere se essa identidade tem `roles/iap.httpsResourceAccessor` no recurso (i.e., está em `mlflow_users`);
3. só então encaminha a request para o container (com `roles/run.invoker` concedido ao service agent do IAP).

```
  Cliente / Browser
        │  Authorization: Bearer <ID token>   (ou cookie de sessão, no browser)
        ▼
   ┌─────────┐   aud == <IAP_CLIENT_ID>?   identidade ∈ mlflow_users?
   │   IAP   │ ─── não ──►  403
   └────┬────┘
        │ sim (run.invoker)
        ▼
   Cloud Run: mlflow server (sem auth nativa)
```

## O ID token (a parte que confunde)

Para chamadas **programáticas** (cliente Python, `curl`), o IAP espera um **ID token OIDC** no
header HTTP:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

O detalhe crítico: o token precisa ter `aud` (audience) **igual ao `<IAP_CLIENT_ID>`**. Um token
com a audience errada é rejeitado com **403**, mesmo que a identidade tenha acesso.

- **Na VM**: o token vem do **metadata server**:
  `google.oauth2.id_token.fetch_id_token(Request(), "<IAP_CLIENT_ID>")`.
- **No PC**: credenciais de usuário não emitem ID token com audience customizada → o `dgb-mlflow`
  **impersona** a SA `destaquesgovbr-mlflow-client` e pede a ela um ID token com
  `target_audience=<IAP_CLIENT_ID>` (`include_email=True`). Requer
  `roles/iam.serviceAccountTokenCreator` na client SA.

### Token sempre fresco (não use só `MLFLOW_TRACKING_TOKEN`)

ID tokens expiram em ~1h. Se você fixar um token via `MLFLOW_TRACKING_TOKEN`, depois de uma hora
as chamadas começam a dar 403. Por isso o `dgb-mlflow` registra um **request header provider**
que **regenera o token a cada request**. Você não precisa pensar nisso — `configure()` já cuida.

O `MLFLOW_TRACKING_TOKEN` existe como **override manual** para debug ou casos especiais:

```bash
export MLFLOW_TRACKING_TOKEN="$(gcloud auth print-identity-token \
  --impersonate-service-account=destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com \
  --audiences=<IAP_CLIENT_ID>)"
```

Se setado, ele tem precedência; lembre que **vai expirar** em ~1h.

## Gerar um token manualmente (para debug)

Útil para testar o `/health` com `curl` e isolar "o IAP está deixando passar?" do resto.

**No PC (impersonando a client SA):**

```bash
TOKEN="$(gcloud auth print-identity-token \
  --impersonate-service-account=destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com \
  --audiences=<IAP_CLIENT_ID>)"
```

**Na VM (identidade da SA da VM):**

```bash
TOKEN="$(gcloud auth print-identity-token --audiences=<IAP_CLIENT_ID>)"
```

**Testar o endpoint de saúde:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer ${TOKEN}" \
  "<MLFLOW_URL>/health"
# espere: 200
```

E confirme que **sem token** o IAP bloqueia:

```bash
curl -s -o /dev/null -w "%{http_code}\n" "<MLFLOW_URL>/health"
# espere: 302 (redireciona p/ login) ou 403 — ou seja, o IAP está protegendo
```

> O `curl` serve para validar o **caminho do IAP/metadados**. Ele **não** exercita o caminho de
> **artefatos no GCS** — esse é puramente client-side (google-cloud-storage + ADC). Para validar
> artefatos, faça um `mlflow.log_artifact(...)` real (veja o [tutorial 01](01-getting-started-pc.md#passo-5--primeiro-run-param-métrica-artefato)).

## Decodificar o token (conferir a audience)

Se desconfiar da audience, decodifique o payload do JWT (apenas debug — não valida assinatura):

```bash
echo "$TOKEN" | cut -d. -f2 | tr '_-' '/+' | base64 -d 2>/dev/null | python -m json.tool
# confira:  "aud": "<IAP_CLIENT_ID>"   e   "email": "<sua conta ou a client SA>"
```

## 403 do IAP × 401/403 do GCS — como distinguir

São **duas portas diferentes**. Saber qual falhou economiza muito tempo.

| Sintoma | Origem | Causa provável | Onde olhar |
|---------|--------|----------------|------------|
| 403 em chamadas de **metadados** (criar experimento, log_param, registry) | **IAP** | token ausente/expirado, `aud` errada, identidade fora de `mlflow_users`, sem `serviceAccountTokenCreator` (PC) | [Troubleshooting → 403 do IAP](06-troubleshooting.md#403-do-iap) |
| Erro ao **subir/baixar artefato** (`403`, `Forbidden`, `Anonymous caller`, `DefaultCredentialsError`) | **GCS** | ADC ausente, sem `storage.objectUser` no bucket | [Troubleshooting → erros do GCS](06-troubleshooting.md#credenciais-do-gcs-ausentes-ou-insuficientes) |
| **302/login no browser** | IAP | sessão não autenticada | faça login com a conta em `mlflow_users` |

Regra mental: **se o erro fala em GCS/bucket/storage/credentials → é o caminho de artefatos**;
**se fala em 403 numa rota HTTP do MLflow → é o IAP**.

Próximo: [04 — Model Registry](04-model-registry.md) ·
[06 — Troubleshooting](06-troubleshooting.md).
