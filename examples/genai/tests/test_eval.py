"""Testes das métricas custom determinísticas e do mlflow.evaluate (offline)."""

import mlflow
import pandas as pd

from news_genai import eval as ev


def test_metrica_compression_ratio_caso_conhecido():
    # resumo com metade do tamanho do original -> ratio 0.5
    ratio = ev.compression_ratio("a" * 100, "a" * 50)
    assert abs(ratio - 0.5) < 1e-9


def test_metrica_compression_ratio_original_vazio():
    # original vazio: razão definida como 0.0 (evita divisão por zero)
    assert ev.compression_ratio("", "qualquer") == 0.0


def test_metrica_keyword_coverage_caso_conhecido():
    summary = "vacinação contra a gripe começa amanhã"
    keywords = ["vacinação", "gripe", "dengue"]
    # 2 de 3 keywords presentes -> 0.6666...
    cov = ev.keyword_coverage(summary, keywords)
    assert abs(cov - 2 / 3) < 1e-9


def test_metrica_keyword_coverage_sem_keywords():
    # sem keywords: cobertura definida como 1.0 (nada a cobrir)
    assert ev.keyword_coverage("texto", []) == 1.0


def test_build_eval_dataset_formato():
    df = ev.build_eval_dataset()
    assert isinstance(df, pd.DataFrame)
    # Colunas mínimas esperadas pelo avaliador.
    for col in ("inputs", "keywords"):
        assert col in df.columns
    assert len(df) >= 2


def test_run_evaluation_offline(local_tracking):
    """mlflow.evaluate roda sobre um dataframe pequeno com o stub determinístico."""
    result = ev.run_evaluation()
    assert result is not None
    # As métricas custom determinísticas devem aparecer no resultado agregado.
    metrics = result.metrics
    assert isinstance(metrics, dict)
    # Procura pelas métricas custom (o nome agregado costuma ter sufixo /mean).
    joined = " ".join(metrics.keys())
    assert "compression_ratio" in joined
    assert "keyword_coverage" in joined
