# 04 — Model Registry

O **Model Registry** do MLflow é o catálogo versionado de modelos do time. Aqui você aprende a
**registrar**, **versionar**, **promover** e **carregar** modelos no MLflow DGB.

> Lembre: os **binários** dos modelos ficam no **GCS** (`gs://inspire-7-finep-mlflow-artifacts`),
> acessados direto pelo seu cliente via ADC. Os **metadados** do registry (nomes, versões,
> aliases/stages) ficam no Postgres, via servidor IAP. Você precisa dos dois caminhos OK.

Pré-requisito: já ter feito o [Getting Started](01-getting-started-pc.md) (PC) ou
[na VM](02-getting-started-vm.md). Exemplo completo e executável em
[`../examples/traditional/`](../examples/traditional/).

## Registrar um modelo

A forma mais direta é logar o modelo **e** registrá-lo no mesmo passo, com `registered_model_name`:

```python
import dgb_mlflow
dgb_mlflow.configure()

import mlflow
import mlflow.sklearn
from sklearn.linear_model import LogisticRegression

mlflow.set_experiment("classificador-noticias")

with mlflow.start_run(run_name="logreg-v1"):
    model = LogisticRegression(max_iter=1000).fit(X_train, y_train)
    mlflow.log_metric("f1", 0.88)

    # loga o artefato no GCS E cria/atualiza a entrada no registry (Postgres)
    mlflow.sklearn.log_model(
        sk_model=model,
        name="modelo",
        registered_model_name="classificador-noticias-govbr",
    )
```

Cada `log_model` com o mesmo `registered_model_name` cria uma **nova versão** (v1, v2, ...).

### Registrar um modelo já logado

Se o modelo já foi logado num run, registre depois pela URI do artefato:

```python
result = mlflow.register_model(
    model_uri="runs:/<RUN_ID>/modelo",
    name="classificador-noticias-govbr",
)
print(result.name, result.version)   # ex.: classificador-noticias-govbr 3
```

## Versionar e organizar

Toda vez que você registra com o mesmo nome, ganha uma versão incremental. Liste e inspecione:

```python
from mlflow import MlflowClient
client = MlflowClient()

for mv in client.search_model_versions("name='classificador-noticias-govbr'"):
    print(f"v{mv.version}  run={mv.run_id}  aliases={mv.aliases}  tags={mv.tags}")
```

Use **tags** e **descrições** para dar contexto:

```python
client.set_model_version_tag(
    name="classificador-noticias-govbr", version="3",
    key="dataset", value="2026-05-snapshot",
)
client.update_model_version(
    name="classificador-noticias-govbr", version="3",
    description="LogReg treinado no snapshot de maio/2026; f1=0.88.",
)
```

## Promover modelos (aliases — recomendado)

O padrão moderno do MLflow usa **aliases** (ponteiros nomeados para uma versão), em vez dos antigos
*stages* (`Staging`/`Production`, hoje *deprecated*). Convenção sugerida para o time: `staging` e
`producao`.

```python
from mlflow import MlflowClient
client = MlflowClient()

# aponta o alias "producao" para a versão 3
client.set_registered_model_alias(
    name="classificador-noticias-govbr", alias="producao", version="3",
)

# promover uma nova versão = re-apontar o alias
client.set_registered_model_alias(
    name="classificador-noticias-govbr", alias="producao", version="5",
)

# remover um alias
client.delete_registered_model_alias(
    name="classificador-noticias-govbr", alias="staging",
)
```

> **Aliases vs Stages**: prefira aliases. Stages (`transition_model_version_stage`) ainda funcionam,
> mas estão *deprecated* no MLflow recente. Padronizar em aliases evita retrabalho.

## Carregar um modelo do registry

Você carrega **por alias** (recomendado) ou **por versão**. O download do binário vem do GCS
automaticamente (precisa do ADC + acesso ao bucket).

```python
import mlflow.pyfunc

# por alias (segue sempre o que estiver promovido):
modelo = mlflow.pyfunc.load_model("models:/classificador-noticias-govbr@producao")

# por versão fixa (reprodutibilidade):
modelo_v3 = mlflow.pyfunc.load_model("models:/classificador-noticias-govbr/3")

predicoes = modelo.predict(X_novo)
```

Use o *flavor* específico se precisar do objeto nativo (ex.: `mlflow.sklearn.load_model(...)`
devolve o estimador sklearn em vez do wrapper `pyfunc`).

## Fluxo típico do time (resumo)

1. Treinar e logar com `registered_model_name` → cria a versão N.
2. Avaliar; se boa, `set_registered_model_alias("staging", N)`.
3. Validar em staging; aprovado, `set_registered_model_alias("producao", N)`.
4. Em produção/serving, carregar sempre por `models:/<nome>@producao`.

Walkthrough executável de ponta a ponta: [`../examples/traditional/`](../examples/traditional/).

Próximo: [05 — GenAI](05-genai.md) · [06 — Troubleshooting](06-troubleshooting.md).
