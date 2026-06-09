# 02 — Getting Started na dev VM

Se você trabalha numa **VM de desenvolvimento** do projeto (criada pelo `reusable-terraform`),
a configuração é **mais simples** do que no PC: a service account da VM já tem acesso ao bucket e
já pode assinar o JWT do IAP. Não há `gcloud auth application-default login` — o ADC vem do
metadata server.

## Por que é mais simples

Na VM, o cliente roda como a **service account da VM**. A infra já concede a essa SA:

- `roles/storage.objectUser` no bucket → ela pode ler/gravar artefatos no GCS;
- `roles/iam.serviceAccountTokenCreator` na SA cliente `destaquesgovbr-mlflow-client` → ela pode
  chamar `signJwt` para assinar o JWT do IAP.

Além disso, a VM tem um **metadata server** do GCP, que entrega o ADC automaticamente (sem
`application-default login`). O `dgb-mlflow` usa esse ADC para chamar `signJwt` na SA cliente — o
**mesmo fluxo do PC**, só que sem o login interativo. O ambiente é detectado automaticamente.

```python
# Na VM, internamente, o JWT é auto-assinado via signJwt na SA cliente, usando o ADC do
# metadata server. A audience é a URL do serviço + "/*" (igual ao PC).
import dgb_mlflow
dgb_mlflow.configure()        # o ADC da VM chama signJwt na destaquesgovbr-mlflow-client
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
pip install "git+https://github.com/destaquesgovbr/ml-platform.git@main#subdirectory=client"
# para desenvolvimento, de dentro do repo: pip install -e /caminho/para/ml-platform/client
```

## Passo 3 — Variável de ambiente

Igual à do PC (veja [como obter](README.md#os-valores-que-você-vai-precisar)):

```bash
export DGB_MLFLOW_TRACKING_URI="https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"
```

> A antiga `DGB_MLFLOW_IAP_CLIENT_ID` não é mais necessária (descontinuada).
> Dica: coloque essa linha no `~/.bashrc` da VM para não repetir a cada sessão.

## Passo 4 — Configurar e logar o primeiro run

A API é **idêntica** à do PC — `configure()` cuida da diferença de ambiente por baixo dos panos:

```python
import dgb_mlflow
dgb_mlflow.configure()          # na VM, o ADC vem do metadata server e assina o JWT via signJwt

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
`https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app` no navegador você precisa estar em `mlflow_users` (mesma regra do PC). Tipicamente:

- da VM você **loga experimentos** (cliente Python, identidade = SA da VM);
- do seu PC/navegador você **abre a UI** para visualizar (identidade = sua conta Google).

Os dois enxergam os mesmos experimentos, pois compartilham o mesmo backend.

## Diferenças PC × VM (resumo)

| Aspecto | PC | Dev VM |
|---------|----|--------|
| Identidade do cliente | sua conta (usuário) | SA da VM |
| ADC | `gcloud auth application-default login` | metadata server (automático) |
| JWT do IAP | `signJwt` na `destaquesgovbr-mlflow-client` (aud = URL + `/*`) | `signJwt` na `destaquesgovbr-mlflow-client` (aud = URL + `/*`) |
| `roles/iam.serviceAccountTokenCreator` na client SA | **na sua conta** | **na SA da VM** |
| Acesso ao bucket | `storage.objectUser` na sua conta | `storage.objectUser` na SA da VM |
| Código (`configure()` + `mlflow.*`) | **igual** | **igual** |

Próximo: [03 — Como funciona o IAP](03-como-funciona-iap.md) ·
[04 — Model Registry](04-model-registry.md) ·
[06 — Troubleshooting](06-troubleshooting.md).
