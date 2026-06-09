"""Providers reais de LLM (Anthropic e OpenAI) — documentado, NÃO usado nos testes.

O pipeline (``news_genai.pipeline.summarize``) recebe um *callable* ``model_fn`` que
recebe o prompt renderizado (str) e devolve a resposta (str). Por padrão usa um stub
determinístico offline. Este módulo mostra como construir ``model_fn`` a partir de um
provider real.

IMPORTANTE:
- As chaves de API vêm de variáveis de ambiente (``ANTHROPIC_API_KEY`` /
  ``OPENAI_API_KEY``). Nada é chamado no import — as funções só conectam quando
  invocadas.
- Os SDKs ``anthropic`` / ``openai`` estão em ``requirements-providers.txt`` e NÃO
  são instalados no ambiente de testes.
- O MLflow tem *autolog* nativo para esses providers, que captura automaticamente
  as chamadas como *traces* (junto com o tracing manual do ``@mlflow.trace`` do
  pipeline).

Uso típico:

    import mlflow
    from news_genai import pipeline
    import providers

    mlflow.anthropic.autolog()                  # captura as chamadas Anthropic
    model = providers.make_anthropic_model()    # callable (prompt) -> str
    resumo = pipeline.summarize(texto, model_fn=model)
"""

from __future__ import annotations

import os
from typing import Callable

ModelFn = Callable[[str], str]

# Modelo Anthropic mais recente e capaz (família Claude 4.x). Veja a skill
# `claude-api` para a lista completa de IDs.
ANTHROPIC_MODEL = "claude-opus-4-8"        # mais capaz
ANTHROPIC_MODEL_FAST = "claude-sonnet-4-6"  # melhor custo/latência

OPENAI_MODEL = "gpt-4o"


# ---------------------------------------------------------------------------
# Anthropic (Claude)
# ---------------------------------------------------------------------------


def make_anthropic_model(model: str = ANTHROPIC_MODEL, max_tokens: int = 256) -> ModelFn:
    """Cria um ``model_fn`` que usa a API da Anthropic (Claude).

    Pré-requisitos:
        pip install -r requirements-providers.txt
        export ANTHROPIC_API_KEY=...

    Recomendado ativar o autolog do MLflow antes de chamar o pipeline::

        import mlflow
        mlflow.anthropic.autolog()

    Notas (ver skill `claude-api`):
        - Opus 4.x usa *adaptive thinking* (``thinking={"type": "adaptive"}``);
          ``temperature``/``top_p``/``budget_tokens`` não são aceitos (400).
        - Para saídas longas, prefira streaming.
    """
    import anthropic  # import tardio: só quando o provider é usado de fato

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def _call(prompt: str) -> str:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # Concatena os blocos de texto da resposta.
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()

    return _call


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


def make_openai_model(model: str = OPENAI_MODEL, max_tokens: int = 256) -> ModelFn:
    """Cria um ``model_fn`` que usa a API da OpenAI.

    Pré-requisitos:
        pip install -r requirements-providers.txt
        export OPENAI_API_KEY=...

    Recomendado ativar o autolog do MLflow antes de chamar o pipeline::

        import mlflow
        mlflow.openai.autolog()
    """
    from openai import OpenAI  # import tardio

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def _call(prompt: str) -> str:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return (response.choices[0].message.content or "").strip()

    return _call
