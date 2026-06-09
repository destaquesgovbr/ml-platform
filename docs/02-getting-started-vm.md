# 02 — Getting Started na dev VM

Se você trabalha numa **VM de desenvolvimento** do projeto (criada pelo `reusable-terraform`),
a configuração é **mais simples** do que no PC: a service account da VM já é principal do IAP e
já tem acesso ao bucket. Não há impersonation, não há `gcloud auth application-default login`.

## Por que é mais simples

Na VM, o cliente roda como a **service account da VM**. A infra já concede a essa SA:

- `roles/iap.httpsResourceAccessor` no recurso do IAP → ela pode chamar o servidor MLflow;
- `roles/storage.objectUser` no bucket → ela pode ler/gravar artefatos no GCS.

Além disso, a VM tem um **metadata server** do GCP, que entrega tanto o ADC (para o GCS) quanto
o **ID token OIDC** com a audience certa — **sem impersonation**. O `dgb-mlflow` detecta esse
ambiente automaticamente.

```python
# Na VM, internamente, o token vem direto do metadata server:
import google.oauth2.id_token
from google.auth.transport.requests import Request

token = google.oauth2.id_token.fetch_id_token(Request(), "<IAP_CLIENT_ID>")
# vai no header Authorization: Bearer <token>
```

## Passo 1 — Conferir as credenciais da VM

As credenciais já estão presentes via metadata server. Confirme rapidamente:

```bash
gcloud auth list                 # deve mostrar a SA da VM como ativa
gcloud config set project inspire-7-finep
```

Você **não** precisa rodar `gcloud auth application-default login` na VM — o ADC já vem do
metadata server. Confirme que o ADC resolve:

```bash
gcloud auth application-default print-access-token >/dev/null && echo "ADC OK"
```

## Passo 2 — Instalar a `dgb-mlflow`

```bash
python -m venv .venv && source .venv/bin/activate     # sempre use venv
pip install -e /caminho/para/ml-platform/client       # path local do repo
# (no futuro): pip install dgb-mlflow
```

## Passo 3 — Variáveis de ambiente

Iguais às do PC (veja [como obter](README.md#placeholders-que-você-vai-precisar)):

```bash
export DGB_MLFLOW_TRACKING_URI="<MLFLOW_URL>"
export DGB_MLFLOW_IAP_CLIENT_ID="<IAP_CLIENT_ID>"
```

> Dica: coloque essas linhas no `~/.bashrc` da VM para não repetir a cada sessão.

## Passo 4 — Configurar e logar o primeiro run

A API é **idêntica** à do PC — `configure()` cuida da diferença de ambiente por baixo dos panos:

```python
import dgb_mlflow
dgb_mlflow.configure()          # detecta a VM e usa o metadata server (sem impersonation)

import mlflow

mlflow.set_experiment("teste-na-vm")

with mlflow.start_run(run_name="hello-vm"):
    mlflow.log_param("alpha", 0.5)        # metadado → Postgres (via IAP)
    mlflow.log_metric("acuracia", 0.93)

    with open("notas-vm.txt", "w") as f:
        f.write("artefato gerado na dev VM\n")
    mlflow.log_artifact("notas-vm.txt")   # artefato → GCS direto (ADC da VM)

print("Run logado da VM!")
```

## E a UI?

A UI roda no **browser**, com sua identidade **de usuário** (não a da VM). Então, para abrir a
`<MLFLOW_URL>` no navegador você precisa estar em `mlflow_users` (mesma regra do PC). Tipicamente:

- da VM você **loga experimentos** (cliente Python, identidade = SA da VM);
- do seu PC/navegador você **abre a UI** para visualizar (identidade = sua conta Google).

Os dois enxergam os mesmos experimentos, pois compartilham o mesmo backend.

## Diferenças PC × VM (resumo)

| Aspecto | PC | Dev VM |
|---------|----|--------|
| Identidade do cliente | sua conta (usuário) | SA da VM |
| ADC | `gcloud auth application-default login` | metadata server (automático) |
| ID token do IAP | impersonando `destaquesgovbr-mlflow-client` | metadata server direto |
| `roles/iam.serviceAccountTokenCreator` | **necessário** | não necessário |
| Acesso ao bucket | `storage.objectUser` na sua conta | `storage.objectUser` na SA da VM |
| Código (`configure()` + `mlflow.*`) | **igual** | **igual** |

Próximo: [03 — Como funciona o IAP](03-como-funciona-iap.md) ·
[04 — Model Registry](04-model-registry.md) ·
[06 — Troubleshooting](06-troubleshooting.md).
