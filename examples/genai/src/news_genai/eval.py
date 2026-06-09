"""Avaliação determinística com ``mlflow.models.evaluate`` e métricas custom.

Monta um pequeno dataset de avaliação e roda ``mlflow.models.evaluate`` sobre o stub
determinístico de sumarização, usando duas métricas custom OFFLINE:

- ``compression_ratio``: tamanho do resumo / tamanho do original (menor = mais
  comprimido);
- ``keyword_coverage``: fração das palavras-chave esperadas presentes no resumo.

Nenhuma métrica depende de LLM-as-judge nem de rede — são puramente determinísticas,
o que torna os testes reprodutíveis. (O README mostra como adicionar um juiz real.)

Nota: usamos ``mlflow.models.evaluate`` (com ``make_metric``), a API recomendada no
MLflow 3.x para métricas custom *determinísticas* sobre um dataframe — mantém total
compatibilidade com a antiga ``mlflow.evaluate`` (que foi descontinuada na 3.0). Para
LLM-as-judge existe ``mlflow.genai.evaluate`` (baseada em *scorers*); o README mostra
como migrar para ela quando quiser um juiz real.
"""

from __future__ import annotations

from typing import Sequence

import mlflow
import pandas as pd
from mlflow.metrics import MetricValue, make_metric

from . import pipeline


# ---------------------------------------------------------------------------
# Funções de métrica determinísticas (puras, testáveis isoladamente)
# ---------------------------------------------------------------------------


def compression_ratio(original: str, summary: str) -> float:
    """Razão de compressão = len(resumo) / len(original).

    Retorna 0.0 quando o original é vazio (evita divisão por zero).
    """
    if not original:
        return 0.0
    return len(summary) / len(original)


def keyword_coverage(summary: str, keywords: Sequence[str]) -> float:
    """Fração das ``keywords`` presentes (case-insensitive) no ``summary``.

    Retorna 1.0 quando não há keywords (nada a cobrir).
    """
    if not keywords:
        return 1.0
    s = summary.lower()
    hits = sum(1 for k in keywords if k.lower() in s)
    return hits / len(keywords)


# ---------------------------------------------------------------------------
# Métricas no formato do mlflow.evaluate (make_metric)
# ---------------------------------------------------------------------------


def _compression_ratio_eval_fn(predictions, metrics, inputs):
    """eval_fn do mlflow.evaluate para compression_ratio.

    O ``DefaultEvaluator`` injeta ``predictions`` (saída do modelo) e cada coluna
    do dataset como um parâmetro nomeado igual ao nome da coluna (``inputs``).
    """
    preds = list(predictions)
    origs = list(inputs)
    scores = [compression_ratio(o, p) for o, p in zip(origs, preds)]
    return MetricValue(scores=scores)


def _keyword_coverage_eval_fn(predictions, metrics, keywords):
    """eval_fn do mlflow.evaluate para keyword_coverage.

    As keywords esperadas vêm da coluna ``keywords`` do dataset, injetada como
    parâmetro nomeado pelo ``DefaultEvaluator``.
    """
    preds = list(predictions)
    kw_lists = list(keywords)
    scores = [keyword_coverage(p, kw) for p, kw in zip(preds, kw_lists)]
    return MetricValue(scores=scores)


def compression_ratio_metric():
    """Métrica MLflow custom de compression_ratio (menor é melhor)."""
    return make_metric(
        eval_fn=_compression_ratio_eval_fn,
        greater_is_better=False,
        name="compression_ratio",
    )


def keyword_coverage_metric():
    """Métrica MLflow custom de keyword_coverage (maior é melhor)."""
    return make_metric(
        eval_fn=_keyword_coverage_eval_fn,
        greater_is_better=True,
        name="keyword_coverage",
    )


# ---------------------------------------------------------------------------
# Dataset de avaliação + execução
# ---------------------------------------------------------------------------


def build_eval_dataset() -> pd.DataFrame:
    """Monta um pequeno dataset de notícias gov.br para avaliação.

    Colunas:
        - ``inputs``: texto da notícia (entrada do modelo);
        - ``keywords``: palavras-chave esperadas no resumo.
    """
    rows = [
        {
            "inputs": (
                "O Ministério da Saúde anunciou a ampliação da campanha de "
                "vacinação contra a gripe. A medida vale para todos os estados."
            ),
            "keywords": ["vacinação", "gripe"],
        },
        {
            "inputs": (
                "O BNDES lançou uma nova linha de crédito para pequenas empresas. "
                "O objetivo é estimular a economia e gerar empregos."
            ),
            "keywords": ["crédito", "empresas"],
        },
        {
            "inputs": (
                "O Ministério da Educação ampliou o programa de bolsas. "
                "Estudantes de baixa renda serão priorizados."
            ),
            "keywords": ["bolsas", "educação"],
        },
    ]
    return pd.DataFrame(rows)


def run_evaluation(model_fn=None):
    """Roda ``mlflow.models.evaluate`` sobre o dataset com as métricas custom.

    As predições são calculadas previamente (com ``model_fn`` ou o stub
    determinístico) e gravadas numa coluna ``prediction`` do dataset. Isso mantém
    ``inputs`` e ``keywords`` disponíveis como colunas para as métricas custom.

    Args:
        model_fn: callable opcional (prompt) -> str para gerar os resumos. Default
            = stub determinístico offline (via ``pipeline.summarize``).

    Returns:
        O objeto ``EvaluationResult`` do MLflow (com ``.metrics``). Tudo offline.
    """
    df = build_eval_dataset()
    df = df.copy()
    df["prediction"] = [
        pipeline.summarize(text, model_fn=model_fn) for text in df["inputs"]
    ]
    with mlflow.start_run(run_name="genai-eval"):
        result = mlflow.models.evaluate(
            data=df,
            predictions="prediction",
            extra_metrics=[compression_ratio_metric(), keyword_coverage_metric()],
            evaluators="default",
        )
    return result
