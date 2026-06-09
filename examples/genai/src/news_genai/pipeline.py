"""Pipeline de sumarização/classificação de notícias com tracing do MLflow.

A função ``summarize`` recebe um *callable* ``model_fn`` que age como "modelo":
recebe o prompt renderizado (str) e devolve a resposta (str). O default é um stub
determinístico, offline, ideal para testes/TDD. Troque por um provider real
passando ``model_fn=`` (veja ``providers.py``).

As funções públicas são decoradas com ``@mlflow.trace`` para gerar *traces* do
MLflow (visíveis no servidor ou no tracking local).
"""

from __future__ import annotations

import re
from typing import Callable, Optional, Sequence

import mlflow

from . import prompts

# Tipo do "modelo": recebe um prompt e devolve texto.
ModelFn = Callable[[str], str]


# ---------------------------------------------------------------------------
# Stub determinístico (default) — sem rede, sem chave de API
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _stub_summary_model(prompt: str) -> str:
    """Stub determinístico de sumarização.

    Estratégia simples e previsível: extrai a notícia do prompt e devolve a
    primeira frase como "resumo". Totalmente offline e determinístico.
    """
    # O prompt termina com "Notícia:\n{text}\n\nResumo:"; extrai o {text}.
    text = _extract_section(prompt, start="Notícia:", end="Resumo:")
    first = _SENTENCE_SPLIT.split(text.strip(), maxsplit=1)[0]
    return first.strip()


def _stub_classification_model(prompt: str) -> str:
    """Stub determinístico de classificação.

    Conta ocorrências de cada categoria (e de algumas palavras-âncora) no texto
    e devolve a categoria de maior contagem; em empate, a primeira listada.
    """
    categories = _extract_categories(prompt)
    text = _extract_section(prompt, start="Notícia:", end="Categoria:").lower()
    # Pontua cada categoria pela frequência do seu nome no texto.
    best = categories[0]
    best_score = -1
    for cat in categories:
        score = text.count(cat.lower())
        if score > best_score:
            best_score = score
            best = cat
    return best


def _extract_section(prompt: str, start: str, end: str) -> str:
    """Extrai o trecho entre ``start`` e ``end`` no prompt (ou tudo após start)."""
    after = prompt.split(start, 1)[-1]
    return after.split(end, 1)[0]


def _extract_categories(prompt: str) -> list[str]:
    """Extrai a lista de categorias da linha 'Categorias possíveis: a, b, c'."""
    marker = "Categorias possíveis:"
    if marker in prompt:
        line = prompt.split(marker, 1)[-1].splitlines()[0]
        return [c.strip() for c in line.split(",") if c.strip()]
    return []


# ---------------------------------------------------------------------------
# API pública (com tracing)
# ---------------------------------------------------------------------------


@mlflow.trace(name="summarize_news")
def summarize(text: str, model_fn: Optional[ModelFn] = None) -> str:
    """Resume uma notícia gov.br.

    Args:
        text: texto da notícia.
        model_fn: callable que recebe o prompt renderizado e devolve o resumo.
            Default = stub determinístico offline. Para um provider real, passe
            ``model_fn=providers.make_anthropic_model()`` (ou OpenAI).

    Returns:
        O resumo (str).
    """
    fn = model_fn or _stub_summary_model
    prompt = prompts.render_summary_prompt(text)
    return fn(prompt)


@mlflow.trace(name="classify_news")
def classify(
    text: str,
    categories: Sequence[str],
    model_fn: Optional[ModelFn] = None,
) -> str:
    """Classifica uma notícia gov.br em uma das ``categories``.

    Args:
        text: texto da notícia.
        categories: categorias possíveis.
        model_fn: callable que recebe o prompt e devolve a categoria. Default =
            stub determinístico offline.

    Returns:
        A categoria escolhida (str), garantida dentro de ``categories`` para o stub.
    """
    fn = model_fn or _stub_classification_model
    prompt = prompts.render_classification_prompt(text, categories)
    return fn(prompt)
