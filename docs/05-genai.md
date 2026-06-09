# 05 — GenAI (tracing, evaluate, prompt registry)

O MLflow tem um conjunto de recursos para **GenAI**: rastreamento (tracing) de chamadas a LLMs,
avaliação automatizada (`mlflow.evaluate`, inclusive LLM-as-judge) e um **prompt registry** para
versionar prompts. Tudo isso usa o mesmo servidor DGB (metadados via IAP, artefatos no GCS).

Pré-requisito: já ter configurado o cliente — veja [Getting Started no PC](01-getting-started-pc.md)
ou [na VM](02-getting-started-vm.md). Exemplo completo e executável em
[`../examples/genai/`](../examples/genai/).

> Instale os extras de GenAI conforme o provedor que for usar:
> `pip install mlflow anthropic` (Anthropic) ou `pip install mlflow openai` (OpenAI).

## 1. Tracing — rastrear chamadas ao LLM

O tracing captura cada chamada ao modelo (prompt, resposta, latência, tokens) e a anexa ao run no
MLflow, onde você visualiza na aba **Traces** da UI.

### Autolog por provedor (mais simples)

Ative o autolog do provedor antes de chamar o modelo — o MLflow instrumenta as chamadas
automaticamente.

```python
import dgb_mlflow
dgb_mlflow.configure()

import mlflow

# --- Anthropic ---
import anthropic
mlflow.anthropic.autolog()            # instrumenta o SDK da Anthropic

client = anthropic.Anthropic()        # usa ANTHROPIC_API_KEY do ambiente
mlflow.set_experiment("genai-noticias")

with mlflow.start_run(run_name="resumo-anthropic"):
    resp = client.messages.create(
        model="claude-opus-4-8",        # modelo atual da Anthropic
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": "Resuma em uma frase: a Receita anunciou novo prazo para a malha fina.",
        }],
    )
    print(resp.content[0].text)
# o trace (prompt, resposta, tokens, latência) aparece na aba Traces da UI
```

Para **OpenAI**, troque por:

```python
import openai
mlflow.openai.autolog()
client = openai.OpenAI()              # usa OPENAI_API_KEY do ambiente
# ... client.chat.completions.create(...)
```

### Tracing manual (qualquer código, sem provedor específico)

Se você usa um pipeline próprio (ex.: HuggingFace local, função de pós-processamento), instrumente
com o decorator `@mlflow.trace`:

```python
import mlflow

@mlflow.trace
def classificar_noticia(texto: str) -> str:
    # sua lógica (pode ser um pipeline HF local, regras, etc.)
    return "economia"

with mlflow.start_run(run_name="classificador-local"):
    classificar_noticia("Banco Central mantém a taxa Selic em 10,5%.")
```

> O tracing **não exige** chave de API: o caminho manual (`@mlflow.trace`) funciona com qualquer
> código. Use-o quando não quiser que todos da equipe precisem de uma chave Anthropic/OpenAI.

## 2. `mlflow.evaluate` — avaliação automatizada

`mlflow.evaluate` roda métricas sobre um conjunto de avaliação e registra os resultados no run.
Funciona desde métricas determinísticas até **LLM-as-judge** (um modelo avalia as respostas).

```python
import dgb_mlflow
dgb_mlflow.configure()

import mlflow
import pandas as pd

# Conjunto de avaliação: entradas + saídas esperadas (ground truth)
dados = pd.DataFrame({
    "inputs": [
        "A inflação subiu 0,5% em maio.",
        "O ministro inaugurou a nova ponte no Pará.",
    ],
    "ground_truth": ["economia", "infraestrutura"],
})

def minha_funcao(df: pd.DataFrame) -> list[str]:
    # sua função de inferência (modelo/pipeline) -> uma predição por linha
    return [classificar_noticia(t) for t in df["inputs"]]

with mlflow.start_run(run_name="eval-classificacao"):
    resultado = mlflow.evaluate(
        model=minha_funcao,
        data=dados,
        targets="ground_truth",
        extra_metrics=[mlflow.metrics.exact_match()],   # métrica determinística
    )
    print(resultado.metrics)
# as métricas e a tabela de avaliação ficam visíveis na UI, no run
```

Para **LLM-as-judge** (avaliar qualidade de respostas abertas, ex.: resumos), use métricas como
`mlflow.metrics.genai.answer_similarity()` ou defina um juiz customizado — veja o exemplo em
[`../examples/genai/`](../examples/genai/), que define o provedor concreto e a função de scoring.

## 3. Prompt Registry — versionar prompts

O prompt registry guarda prompts como artefatos versionados (como o Model Registry, mas para
prompts). Útil para evoluir um prompt sem perder o histórico e para reusar entre experimentos.

```python
import dgb_mlflow
dgb_mlflow.configure()

import mlflow

# Registra (ou cria nova versão de) um prompt nomeado
prompt = mlflow.register_prompt(
    name="resumo-noticia",
    template="Resuma a seguinte notícia do gov.br em uma frase objetiva:\n\n{{noticia}}",
    commit_message="versão inicial do prompt de resumo",
)
print(f"{prompt.name} v{prompt.version}")

# Carregar e usar
p = mlflow.load_prompt("prompts:/resumo-noticia/1")
texto = p.format(noticia="A Receita prorrogou o prazo de entrega da declaração.")
```

Cada `register_prompt` com o mesmo `name` cria uma nova versão. Combine com o tracing para
correlacionar uma versão de prompt com a qualidade medida no `evaluate`.

## Escolha do provedor

A documentação acima mostra Anthropic e OpenAI. Para Anthropic, o modelo padrão sugerido é
`claude-opus-4-8` (use adaptive thinking para tarefas complexas). O exemplo em
[`../examples/genai/`](../examples/genai/) fixa um provedor concreto e traz testes de parsing de
prompt e de scoring determinístico — comece por ele como walkthrough executável.

Próximo: [06 — Troubleshooting](06-troubleshooting.md).
