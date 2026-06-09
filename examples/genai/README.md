# Exemplo GenAI — sumarização/classificação de notícias gov.br

Demonstra três features de **GenAI do MLflow** sobre um caso de uso de notícias do
governo federal (gov.br):

- **Tracing** — `@mlflow.trace` captura as chamadas do pipeline como *traces*.
- **Avaliação** — `mlflow.evaluate` com métricas custom **determinísticas**
  (comprimento/keywords), além de um caminho documentado para *LLM-as-judge*.
- **Prompt registry** — registra/recupera templates de prompt versionados.

O "modelo" é um **callable plugável**. O default é um **stub determinístico**,
totalmente *offline* (sem chave de API, sem rede) — perfeito para TDD e CI. Para
usar um provider real (Anthropic ou OpenAI), basta passar `model_fn=`.

## Estrutura

```
examples/genai/
├── src/news_genai/
│   ├── __init__.py
│   ├── pipeline.py     # summarize()/classify() com @mlflow.trace; stub default
│   ├── prompts.py      # templates de prompt + prompt registry
│   └── eval.py         # dataset de avaliação + mlflow.evaluate + métricas custom
├── providers.py        # providers reais (Anthropic/OpenAI) — documentado
├── tests/              # testes OFFLINE e DETERMINÍSTICOS (tracking local em tmp_path)
├── requirements.txt            # mlflow, pandas (pinned)
├── requirements-dev.txt        # -r requirements.txt + pytest
└── requirements-providers.txt  # anthropic, openai (NÃO instalados nos testes)
```

## Setup local

```bash
cd examples/genai
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

Os testes não exigem chaves de API nem rede: cada teste aponta o tracking do MLflow
para um SQLite temporário em `tmp_path`.

## Tracing

O pipeline expõe `summarize(text, model_fn=None)` e `classify(text, categories, model_fn=None)`,
ambos decorados com `@mlflow.trace`. Cada chamada gera um *trace* visível no tracking
(local ou no servidor).

```python
import mlflow
from news_genai import pipeline

mlflow.set_tracking_uri("sqlite:///mlflow.db")
mlflow.set_experiment("genai-news")

resumo = pipeline.summarize(
    "O Ministério da Saúde anunciou a ampliação da campanha de vacinação."
)
print(resumo)

# Inspeciona os traces gerados
traces = mlflow.search_traces()
print(traces[["trace_id", "request", "response"]])
```

## Avaliação (`mlflow.evaluate`)

`eval.run_evaluation()` monta um pequeno dataset de notícias e roda `mlflow.evaluate`
com duas métricas custom **determinísticas**:

- `compression_ratio` — `len(resumo) / len(original)` (menor = mais comprimido);
- `keyword_coverage` — fração das palavras-chave esperadas presentes no resumo.

```python
from news_genai import eval as ev

result = ev.run_evaluation()       # usa o stub determinístico
print(result.metrics)              # compression_ratio/mean, keyword_coverage/mean, ...

# Com um provider real:
# import providers
# result = ev.run_evaluation(model_fn=providers.make_anthropic_model())
```

### LLM-as-judge (juiz real)

As métricas acima são determinísticas de propósito (CI reprodutível). Para um juiz
baseado em LLM, use a API moderna **`mlflow.genai.evaluate`** com *scorers* (ex.:
`Correctness`, `RelevanceToQuery`) — ela exige um provider configurado e, portanto,
não roda nos testes offline. Esboço:

```python
import mlflow.genai
from mlflow.genai.scorers import Correctness, RelevanceToQuery

mlflow.genai.evaluate(
    data=[{"inputs": {"text": noticia}, "outputs": resumo}],
    scorers=[Correctness(), RelevanceToQuery()],
)
```

## Prompt registry

Os templates ficam em `prompts.py` (sintaxe `str.format` com `{text}`). Para versioná-los
no registry do MLflow:

```python
from news_genai import prompts
import mlflow.genai

pv = prompts.register_summary_prompt(name="dgb-news-summary")
loaded = mlflow.genai.load_prompt(f"prompts:/dgb-news-summary/{pv.version}")
print(loaded.template)   # usa a sintaxe {{text}} do registry
```

`register_summary_prompt` prefere `mlflow.genai.register_prompt` (MLflow 3.x) e cai
para o legado `mlflow.register_prompt` em versões mais antigas.

## Plugando um provider real (Anthropic / OpenAI)

Veja `providers.py` (totalmente documentado). Resumo:

```bash
pip install -r requirements-providers.txt
export ANTHROPIC_API_KEY=...        # ou OPENAI_API_KEY=...
```

```python
import mlflow
import providers
from news_genai import pipeline

mlflow.anthropic.autolog()                       # captura as chamadas Anthropic
model = providers.make_anthropic_model()         # callable (prompt) -> str
resumo = pipeline.summarize(noticia, model_fn=model)
```

- **Anthropic**: modelo default `claude-opus-4-8` (mais capaz) / `claude-sonnet-4-6`
  (custo/latência). Opus 4.x usa *adaptive thinking*; `temperature`/`top_p`/
  `budget_tokens` não são aceitos. Ative `mlflow.anthropic.autolog()`.
- **OpenAI**: `providers.make_openai_model()` + `mlflow.openai.autolog()`.

Os *autologs* dos providers complementam o tracing manual (`@mlflow.trace`) do pipeline,
capturando automaticamente as requisições ao LLM.

## Apontando para o servidor compartilhado (atrás do IAP)

Em produção, em vez do SQLite local, use o helper `dgb_mlflow.configure()` (pacote
`client/`), que resolve a tracking URI e o token do IAP:

```python
import dgb_mlflow
dgb_mlflow.configure()               # detecta VM vs PC; configura tracking + IAP

from news_genai import pipeline
pipeline.summarize("...")            # traces/experimentos vão para o servidor Cloud Run
```

Sem `configure()`, defina manualmente:

```python
import mlflow
mlflow.set_tracking_uri("sqlite:///mlflow.db")   # dev local
```
