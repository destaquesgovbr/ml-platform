"""Testes de templates de prompt e (se disponível) do prompt registry do MLflow."""

import mlflow
import pytest

from news_genai import prompts


def test_render_summary_prompt_insere_texto():
    texto = "O Ministério da Saúde anunciou um novo programa de vacinação."
    rendered = prompts.render_summary_prompt(texto)
    assert texto in rendered
    # O template deve instruir a tarefa de sumarização em PT-BR.
    assert "resum" in rendered.lower()


def test_render_classification_prompt_lista_categorias():
    texto = "Nova linha de crédito do BNDES para pequenas empresas."
    rendered = prompts.render_classification_prompt(
        texto, categories=["economia", "saude", "educacao"]
    )
    assert texto in rendered
    for cat in ("economia", "saude", "educacao"):
        assert cat in rendered


def test_summary_template_constante_tem_placeholder():
    # O template exposto deve conter o placeholder {text} para o registry.
    assert "{text}" in prompts.SUMMARY_PROMPT_TEMPLATE


def _load_prompt_fn():
    """Resolve a função de load do prompt registry (genai ou legado)."""
    try:
        from mlflow.genai import load_prompt

        return load_prompt
    except Exception:
        return getattr(mlflow, "load_prompt", None)


def test_register_and_load_prompt(local_tracking):
    """Registra e recupera um prompt via prompt registry, se a feature existir.

    Pula se a versão instalada do MLflow não expõe register_prompt/load_prompt.
    """
    pytest.importorskip("mlflow")
    load_prompt = _load_prompt_fn()
    if prompts._register_prompt_fn() is None or load_prompt is None:
        pytest.skip("prompt registry não disponível nesta versão do MLflow")

    name = "dgb-news-summary"
    pv = prompts.register_summary_prompt(name=name)
    assert pv is not None

    loaded = load_prompt(f"prompts:/{name}/{pv.version}")
    # O template carregado deve conter o placeholder.
    assert "{{text}}" in loaded.template or "{text}" in loaded.template
