# 01 — Getting Started no computador pessoal

Este guia leva você do zero ao **primeiro run** no MLflow DGB, trabalhando do seu
**computador pessoal** (laptop, fora do GCP). Tempo estimado: ~10 minutos.

No PC você usa as **suas credenciais** do Google (ADC) tanto para o GCS quanto, via
**impersonation** de uma service account de cliente, para gerar o token do IAP.

## Pré-requisitos

- Python 3.11.
- [`gcloud` CLI](https://cloud.google.com/sdk/docs/install) instalado.
- Sua conta Google deve estar na lista `mlflow_users` (peça ao administrador da infra).
- Os valores `<MLFLOW_URL>` e `<IAP_CLIENT_ID>` — veja [como obter](README.md#placeholders-que-você-vai-precisar).

## Passo 1 — Autenticar (ADC)

O **ADC** (Application Default Credentials) é a credencial que o `google-cloud-storage` usa para
ler/gravar artefatos no GCS, e que o `dgb-mlflow` usa para impersonar a SA de cliente do IAP.

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

A lib cliente está em [`../client/`](../client/). Instale a partir do path local:

```bash
python -m venv .venv && source .venv/bin/activate    # sempre use um venv
pip install -e ../client            # a partir de ml-platform/docs; ajuste o path conforme seu cwd
# (no futuro, quando publicada): pip install dgb-mlflow
```

A `dgb-mlflow` já traz o `mlflow` e o `google-cloud-storage` como dependências.

## Passo 3 — Configurar as variáveis de ambiente

O `dgb-mlflow` lê dois envs. Exporte-os no seu shell (ou coloque num `.env`):

```bash
export DGB_MLFLOW_TRACKING_URI="<MLFLOW_URL>"
export DGB_MLFLOW_IAP_CLIENT_ID="<IAP_CLIENT_ID>"
```

Substitua pelos valores reais (veja o [README](README.md#placeholders-que-você-vai-precisar)). Exemplo:

```bash
export DGB_MLFLOW_TRACKING_URI="https://destaquesgovbr-mlflow-abcdef-rj.a.run.app"
export DGB_MLFLOW_IAP_CLIENT_ID="990583792367-xxxxxxxx.apps.googleusercontent.com"
```

## Passo 4 — Configurar o cliente no código

Chame `dgb_mlflow.configure()` **uma vez**, no início do seu script/notebook. Ele:

1. Lê `DGB_MLFLOW_TRACKING_URI` e `DGB_MLFLOW_IAP_CLIENT_ID`.
2. Detecta que você está num PC (sem metadata server do GCP) e gera o ID token do IAP via
   **impersonation** da SA de cliente (veja a seção [Impersonation](#sobre-a-impersonation-da-client-sa)).
3. Registra o provider que injeta `Authorization: Bearer <ID token>` em cada request (token sempre fresco).
4. Chama `mlflow.set_tracking_uri(...)` apontando para o `<MLFLOW_URL>`.

```python
import dgb_mlflow
dgb_mlflow.configure()      # lê os envs; nada mais é necessário

import mlflow
print(mlflow.get_tracking_uri())   # deve imprimir o <MLFLOW_URL>
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

Abra o `<MLFLOW_URL>` no navegador:

```bash
open "$DGB_MLFLOW_TRACKING_URI"      # macOS; no Linux use xdg-open
```

O IAP vai pedir um **login Google**. Use a mesma conta que está em `mlflow_users`. Depois você
verá o experimento `meu-primeiro-experimento` e o run `hello-dgb`, com o param, a métrica e o
artefato `notas.txt`.

> Para a **UI** funcionar, sua conta precisa do papel `roles/iap.httpsResourceAccessor` no recurso
> do IAP (é o que a inclusão em `mlflow_users` concede). Se a UI der 403, veja
> [Troubleshooting](06-troubleshooting.md#403-do-iap).

## Sobre a impersonation da client SA

No PC você se autentica como **usuário** (ADC de usuário). Mas o IAP, para clientes
programáticos, espera um **ID token OIDC** cuja `aud` seja o `<IAP_CLIENT_ID>` — e credenciais de
usuário não geram esse token diretamente. A solução padrão do `dgb-mlflow` é **impersonar uma
service account de cliente** (`destaquesgovbr-mlflow-client`) e pedir a ela um ID token com a
audience certa:

```python
# É o que o dgb_mlflow.configure() faz internamente, de forma simplificada:
from google.auth import default, impersonated_credentials
from google.auth.transport.requests import Request

source_credentials, _ = default()                      # seu ADC de usuário
target = impersonated_credentials.Credentials(
    source_credentials=source_credentials,
    target_principal="destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com",
    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
)
id_creds = impersonated_credentials.IDTokenCredentials(
    target, target_audience="<IAP_CLIENT_ID>", include_email=True,
)
id_creds.refresh(Request())
token = id_creds.token        # vai no header Authorization: Bearer <token>
```

Para isso funcionar, **a sua conta precisa do papel `roles/iam.serviceAccountTokenCreator`** na
service account `destaquesgovbr-mlflow-client` (a infra concede isso aos membros de `mlflow_users`).
Sem ele, a impersonation falha com um 403 do IAM (veja [Troubleshooting](06-troubleshooting.md)).

## Resumo dos dois papéis que você precisa (no PC)

| Para... | Papel necessário | Concedido por |
|---------|------------------|---------------|
| Abrir a UI / chamar o servidor (metadados) | `roles/iap.httpsResourceAccessor` no recurso IAP | inclusão em `mlflow_users` |
| Gerar o ID token impersonando a client SA | `roles/iam.serviceAccountTokenCreator` na `destaquesgovbr-mlflow-client` | inclusão em `mlflow_users` |
| Ler/gravar artefatos no bucket | `roles/storage.objectUser` no bucket | inclusão em `mlflow_users` |

Próximo: [02 — Getting Started na dev VM](02-getting-started-vm.md) ·
[03 — Como funciona o IAP](03-como-funciona-iap.md) ·
[04 — Model Registry](04-model-registry.md).
