# 01 — Getting Started no computador pessoal

Este guia leva você do zero ao **primeiro run** no MLflow DGB, trabalhando do seu
**computador pessoal** (laptop, fora do GCP). Tempo estimado: ~10 minutos.

No PC você usa as **suas credenciais** do Google (ADC) tanto para o GCS quanto para chamar a
API IAM Credentials `signJwt` na service account cliente, que **auto-assina** o JWT do IAP.

## Pré-requisitos

- Python 3.11.
- [`gcloud` CLI](https://cloud.google.com/sdk/docs/install) instalado.
- Sua conta Google deve estar na lista `mlflow_users` (peça ao administrador da infra).
- A URL do serviço `https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app` — veja [como obter](README.md#os-valores-que-você-vai-precisar).

## Passo 1 — Autenticar (ADC)

O **ADC** (Application Default Credentials) é a credencial que o `google-cloud-storage` usa para
ler/gravar artefatos no GCS, e que o `dgb-mlflow` usa para chamar `signJwt` na SA cliente do IAP.

```bash
# Login normal da CLI (interativo, abre o browser):
gcloud auth login

# Application Default Credentials — É ESTA que as libs Python usam:
gcloud auth application-default login
```

> São dois logins diferentes. O segundo (`application-default`) é o que importa para o Python.
> Sem ele você verá erros de credencial do GCS ao subir artefatos.

Defina o projeto de quota (evita avisos):

```bash
gcloud auth application-default set-quota-project inspire-7-finep
```

## Passo 2 — Instalar a biblioteca `dgb-mlflow`

A lib cliente está em [`../client/`](../client/) e instala-se direto do git:

```bash
python -m venv .venv && source .venv/bin/activate    # sempre use um venv
pip install "git+https://github.com/destaquesgovbr/ml-platform.git@main#subdirectory=client"
# para desenvolvimento, de dentro do repo: pip install -e ../client (a partir de ml-platform/docs)
```

A `dgb-mlflow` já traz o `mlflow` e o `google-cloud-storage` como dependências.

## Passo 3 — Configurar a variável de ambiente

O `dgb-mlflow` precisa de **um** env para o modo remoto. Exporte-o no seu shell (ou num `.env`):

```bash
export DGB_MLFLOW_TRACKING_URI="https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"
```

Substitua pela URL real (veja o [README](README.md#os-valores-que-você-vai-precisar)). Exemplo:

```bash
export DGB_MLFLOW_TRACKING_URI="https://destaquesgovbr-mlflow-abcdef-rj.a.run.app"
```

> A antiga `DGB_MLFLOW_IAP_CLIENT_ID` foi **descontinuada** e não é mais necessária — o IAP do
> Cloud Run usa o OAuth client gerenciado pelo Google, então não há client id para acesso
> programático. O JWT é auto-assinado pela SA cliente (veja [como funciona](03-como-funciona-iap.md)).

## Passo 4 — Configurar o cliente no código

Chame `dgb_mlflow.configure()` **uma vez**, no início do seu script/notebook. Ele:

1. Lê `DGB_MLFLOW_TRACKING_URI`.
2. Calcula a *audience* do JWT (a URL do serviço + `/*`) e gera, via **`signJwt`** na SA cliente
   `destaquesgovbr-mlflow-client`, um **JWT auto-assinado** com essa audience (veja a seção
   [JWT auto-assinado](#sobre-o-jwt-auto-assinado-da-client-sa)).
3. Registra o provider que injeta `Authorization: Bearer <JWT>` em cada request (token sempre fresco).
4. Chama `mlflow.set_tracking_uri(...)` apontando para o `https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app`.

```python
import dgb_mlflow
dgb_mlflow.configure()      # lê o env; nada mais é necessário

import mlflow
print(mlflow.get_tracking_uri())   # deve imprimir o https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app
```

## Passo 5 — Primeiro run (param, métrica, artefato)

```python
import dgb_mlflow
dgb_mlflow.configure()

import mlflow

mlflow.set_experiment("meu-primeiro-experimento")

with mlflow.start_run(run_name="hello-dgb"):
    # metadado → vai para o Postgres via servidor (IAP)
    mlflow.log_param("alpha", 0.5)
    mlflow.log_metric("acuracia", 0.91)

    # artefato → vai DIRETO para o GCS (ADC)
    with open("notas.txt", "w") as f:
        f.write("primeiro artefato no MLflow DGB\n")
    mlflow.log_artifact("notas.txt")

print("Run logado com sucesso!")
```

Se isso rodar sem erro, **os dois caminhos** (metadados via IAP + artefatos via GCS) estão OK.

## Passo 6 — Abrir a UI no browser

Abra o `https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app` no navegador:

```bash
open "$DGB_MLFLOW_TRACKING_URI"      # macOS; no Linux use xdg-open
```

O IAP vai pedir um **login Google**. Use a mesma conta que está em `mlflow_users`. Depois você
verá o experimento `meu-primeiro-experimento` e o run `hello-dgb`, com o param, a métrica e o
artefato `notas.txt`.

> Para a **UI** funcionar, sua conta precisa do papel `roles/iap.httpsResourceAccessor` no recurso
> do IAP (é o que a inclusão em `mlflow_users` concede). Se a UI der 403, veja
> [Troubleshooting](06-troubleshooting.md#ui-dá-403-no-browser).

## Sobre o JWT auto-assinado da client SA

No PC você se autentica como **usuário** (ADC de usuário). O IAP do Cloud Run usa o OAuth client
**gerenciado pelo Google**, então **não há** client id para gerar um ID token OIDC programático —
tentar isso dá 401 `Invalid JWT audience`. O fluxo que funciona (validado em produção) é um
**JWT auto-assinado** pela service account cliente (`destaquesgovbr-mlflow-client`) via a API IAM
Credentials `signJwt`, cuja `aud` é **a URL do serviço + `/*`**:

```python
# É o que o dgb_mlflow.configure() faz internamente, de forma simplificada:
import json, time
import google.auth
from google.auth.transport.requests import AuthorizedSession

SA = "destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com"
URI = "https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"

now = int(time.time())
payload = {
    "iss": SA, "sub": SA, "email": SA,
    "aud": URI.rstrip("/") + "/*",        # a URL pura, sem /*, dá 401
    "iat": now, "exp": now + 3600,
}

creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
session = AuthorizedSession(creds)        # usa o seu ADC de usuário
resp = session.post(
    f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{SA}:signJwt",
    data=json.dumps({"payload": json.dumps(payload)}),
)
token = resp.json()["signedJwt"]          # vai no header Authorization: Bearer <token>
```

Para isso funcionar, **a sua conta precisa do papel `roles/iam.serviceAccountTokenCreator`** na
service account `destaquesgovbr-mlflow-client` (a infra concede isso aos membros de `mlflow_users`).
Sem ele, o `signJwt` falha com um 403 do IAM (veja [Troubleshooting](06-troubleshooting.md)).

## Resumo dos papéis que você precisa (no PC)

| Para... | Papel necessário | Concedido por |
|---------|------------------|---------------|
| Abrir a UI / chamar o servidor (metadados) | `roles/iap.httpsResourceAccessor` no recurso IAP | inclusão em `mlflow_users` |
| Assinar o JWT do IAP via `signJwt` na client SA | `roles/iam.serviceAccountTokenCreator` na `destaquesgovbr-mlflow-client` | inclusão em `mlflow_users` |
| Ler/gravar artefatos no bucket | `roles/storage.objectUser` no bucket | inclusão em `mlflow_users` |

Próximo: [02 — Getting Started na dev VM](02-getting-started-vm.md) ·
[03 — Como funciona o IAP](03-como-funciona-iap.md) ·
[04 — Model Registry](04-model-registry.md).
