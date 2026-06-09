"""news_genai — exemplo de GenAI do MLflow sobre notícias gov.br.

Demonstra três features de GenAI do MLflow de forma OFFLINE e plugável:

- **tracing** (``pipeline.summarize`` decorado com ``@mlflow.trace``);
- **avaliação** (``eval.run_evaluation`` com ``mlflow.models.evaluate`` + métricas custom
  determinísticas);
- **prompt registry** (``prompts.register_summary_prompt``).

O "modelo" é um *callable* plugável. O default é um stub determinístico (sem rede,
sem chave de API), ideal para testes/TDD. Para usar um provider real (Anthropic ou
OpenAI), veja ``providers.py`` e passe o callable via ``model_fn=``.
"""

from . import eval, pipeline, prompts  # noqa: F401

__all__ = ["pipeline", "prompts", "eval"]
