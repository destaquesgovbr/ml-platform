"""Testes do pipeline de sumarização com tracing do MLflow (offline)."""

import mlflow

from news_genai import pipeline


def test_summarize_stub_deterministico():
    """O stub determinístico produz a mesma saída para a mesma entrada."""
    texto = (
        "O Ministério da Educação anunciou hoje a ampliação do programa de "
        "bolsas. A medida deve beneficiar milhares de estudantes em todo o país."
    )
    out1 = pipeline.summarize(texto)
    out2 = pipeline.summarize(texto)
    assert out1 == out2
    assert isinstance(out1, str)
    assert len(out1) > 0
    # O stub resume pegando a primeira frase — deve ser mais curto que o original.
    assert len(out1) <= len(texto)


def test_summarize_usa_model_fn_plugavel():
    """summarize() aceita um callable 'modelo' que substitui o stub."""

    def fake_model(prompt: str) -> str:
        # Modelo plugado: retorna algo determinístico e identificável.
        assert "resum" in prompt.lower()  # recebeu o prompt renderizado
        return "RESUMO-PLUGADO"

    out = pipeline.summarize("Texto qualquer de notícia.", model_fn=fake_model)
    assert out == "RESUMO-PLUGADO"


def test_summarize_gera_trace(local_tracking):
    """A chamada de summarize() (decorada com @mlflow.trace) gera um trace."""
    texto = "Governo federal lança plano nacional de infraestrutura digital."
    resultado = pipeline.summarize(texto)
    assert resultado

    # Recupera os traces do experimento ativo. A API de tracing deve ter
    # registrado pelo menos um trace para a função decorada.
    traces = mlflow.search_traces(max_results=10)
    assert len(traces) >= 1


def test_classify_stub_deterministico():
    """O stub de classificação é determinístico e retorna uma das categorias."""
    cats = ["economia", "saude", "educacao"]
    texto = "Novo hospital universitário será inaugurado pelo SUS."
    out1 = pipeline.classify(texto, categories=cats)
    out2 = pipeline.classify(texto, categories=cats)
    assert out1 == out2
    assert out1 in cats
