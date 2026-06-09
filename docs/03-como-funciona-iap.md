# 03 — Como funciona o IAP

Este documento explica o mecanismo de autenticação por trás do MLflow DGB. Ler isto ajuda muito
a **debugar** erros de acesso (a maioria cai em "token errado" ou "credencial do GCS faltando").

## O desenho: IAP direto no Cloud Run

O servidor MLflow **não tem login próprio**. Quem fica na frente é o **IAP**
(Identity-Aware Proxy), habilitado **direto no serviço do Cloud Run** (recurso GA — sem load
balancer, sem custo extra). Toda requisição para a `https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app` passa antes pelo IAP, que:

1. exige uma **identidade Google** válida (login no browser **ou** JWT assinado em chamadas programáticas);
2. confere se essa identidade tem `roles/iap.httpsResourceAccessor` no recurso (i.e., está em `mlflow_users`);
3. só então encaminha a request para o container (com `roles/run.invoker` concedido ao service agent do IAP).

```
  Cliente / Browser
        │  Authorization: Bearer <JWT da SA>   (ou cookie de sessão, no browser)
        ▼
   ┌─────────┐   aud == <URL do serviço>/* ?    identidade ∈ mlflow_users?
   │   IAP   │ ─── não ──►  401 (aud errada) / 403 (sem acesso)
   └────┬────┘
        │ sim (run.invoker)
        ▼
   Cloud Run: mlflow server (sem auth nativa)
```

## O JWT auto-assinado (a parte que confunde)

Para chamadas **programáticas** (cliente Python, `curl`), o IAP espera um **JWT** assinado por
uma service account, no header HTTP:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

Por que **não** um ID token OIDC com `aud = <IAP client id>`? Porque o IAP do Cloud Run (GA)
usa o **OAuth client gerenciado pelo Google** — não existe um OAuth client id próprio para você
mintar um ID token. Tentar esse caminho (`fetch_id_token`, `IDTokenCredentials` com
`target_audience = client_id`) é **bloqueado**, com **401 `Invalid JWT audience`**.

O fluxo correto, validado em produção, é um **JWT auto-assinado** pela service account cliente
(`destaquesgovbr-mlflow-client`) via a API **IAM Credentials `signJwt`**. O detalhe crítico é a
**audience**: ela precisa ser **a URL do serviço com o sufixo `/*`**, por exemplo
`https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app/*`. A URL **pura** (sem `/*`) é rejeitada.
Os claims do JWT são:

```json
{
  "iss":   "destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com",
  "sub":   "destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com",
  "email": "destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com",
  "aud":   "https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app/*",
  "iat":   <agora>,
  "exp":   <agora + 3600>
}
```

- **No PC**: o `dgb-mlflow` usa o **seu ADC de usuário** para chamar `signJwt` na SA cliente.
  Requer `roles/iam.serviceAccountTokenCreator` na `destaquesgovbr-mlflow-client`.
- **Na VM**: o `dgb-mlflow` usa o **ADC do metadata server** (a SA da VM) para chamar `signJwt`
  na **mesma** SA cliente. A SA da VM também tem `tokenCreator` nela — mesmo fluxo, sem login.

### Como a `dgb-mlflow` injeta o header

A lib registra um `RequestHeaderProvider` via entry point `mlflow.request_header_provider`. O
MLflow consulta esse provider em **toda** requisição ao tracking server; quando `configure()`
ativou o modo IAP, ele monta `{"Authorization": "Bearer <JWT>"}` chamando
`get_iap_jwt(audience, signer_sa)` — que assina um JWT **fresco** a cada request. Você não fixa
nem renova nada manualmente.

### `MLFLOW_TRACKING_TOKEN` (override manual)

JWTs expiram em ~1h. Por isso o provider regenera o token a cada request. O `MLFLOW_TRACKING_TOKEN`
existe só como **override manual** (debug/CI): se setado, tem precedência sobre o `signJwt`, e
**vai expirar** em ~1h.

## Gerar um token manualmente (para debug)

Útil para testar o `/health` com `curl` e isolar "o IAP está deixando passar?" do resto. Use o
`gcloud iam service-accounts sign-jwt`, montando os claims com a audience `<URL>/*`:

```bash
SA=destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com
U=https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app
NOW=$(date +%s)
printf '{"iss":"%s","sub":"%s","email":"%s","aud":"%s/*","iat":%s,"exp":%s}' \
  "$SA" "$SA" "$SA" "$U" "$NOW" $((NOW+3600)) > /tmp/c.json

JWT=$(gcloud iam service-accounts sign-jwt /tmp/c.json /dev/stdout --iam-account="$SA")
```

Funciona tanto no PC (seu usuário com `tokenCreator` na SA) quanto na VM (a SA da VM com
`tokenCreator` na SA cliente).

**Testar o endpoint de saúde:**

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer ${JWT}" \
  "$U/health"
# espere: 200
```

E confirme que **sem token** o IAP bloqueia:

```bash
curl -s -o /dev/null -w "%{http_code}\n" "$U/health"
# espere: 302 (redireciona p/ login) ou 401/403 — ou seja, o IAP está protegendo
```

> O `curl` serve para validar o **caminho do IAP/metadados**. Ele **não** exercita o caminho de
> **artefatos no GCS** — esse é puramente client-side (google-cloud-storage + ADC). Para validar
> artefatos, faça um `mlflow.log_artifact(...)` real (veja o [tutorial 01](01-getting-started-pc.md#passo-5--primeiro-run-param-métrica-artefato)).

## Decodificar o token (conferir a audience)

Se desconfiar da audience, decodifique o payload do JWT (apenas debug — não valida assinatura):

```bash
echo "$JWT" | cut -d. -f2 | tr '_-' '/+' | base64 -d 2>/dev/null | python -m json.tool
# confira:  "aud": "https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app/*"
#           "email": "destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com"
```

## 403 do IAP × 401/403 do GCS — como distinguir

São **duas portas diferentes**. Saber qual falhou economiza muito tempo.

| Sintoma | Origem | Causa provável | Onde olhar |
|---------|--------|----------------|------------|
| 401/403 em chamadas de **metadados** (criar experimento, log_param, registry) | **IAP** | `aud` errada (deve ser `<URL>/*`) → **401**; identidade fora de `mlflow_users` ou sem `tokenCreator` na client SA → **403** | [Troubleshooting → 401/403 do IAP](06-troubleshooting.md#401403-do-iap) |
| Erro ao **subir/baixar artefato** (`403`, `Forbidden`, `Anonymous caller`, `DefaultCredentialsError`) | **GCS** | ADC ausente, sem `storage.objectUser` no bucket | [Troubleshooting → erros do GCS](06-troubleshooting.md#credenciais-do-gcs-ausentes-ou-insuficientes) |
| **302/login no browser** | IAP | sessão não autenticada | faça login com a conta em `mlflow_users` |

Regra mental: **se o erro fala em GCS/bucket/storage/credentials → é o caminho de artefatos**;
**se fala em 403 numa rota HTTP do MLflow → é o IAP**.

Próximo: [04 — Model Registry](04-model-registry.md) ·
[06 — Troubleshooting](06-troubleshooting.md).
