"""Templates de prompt e integração com o prompt registry do MLflow.

Os templates usam ``str.format`` com o placeholder ``{text}`` (e ``{categories}``
para classificação). Para o *prompt registry* do MLflow, o template é convertido
para a sintaxe de chaves duplas (``{{text}}``) esperada pela API.
"""

from __future__ import annotations

from typing import Optional, Sequence

import mlflow

# ---------------------------------------------------------------------------
# Templates (sintaxe str.format, com placeholder {text})
# ---------------------------------------------------------------------------

SUMMARY_PROMPT_TEMPLATE = (
    "Você é um assistente que resume notícias do governo federal brasileiro "
    "(gov.br) de forma objetiva, em português do Brasil.\n\n"
    "Resuma a notícia a seguir em uma única frase curta, mantendo os fatos "
    "principais e sem opinião:\n\n"
    "Notícia:\n{text}\n\n"
    "Resumo:"
)

CLASSIFICATION_PROMPT_TEMPLATE = (
    "Você classifica notícias do governo federal brasileiro (gov.br) em uma das "
    "categorias fornecidas. Responda apenas com o nome exato da categoria.\n\n"
    "Categorias possíveis: {categories}\n\n"
    "Notícia:\n{text}\n\n"
    "Categoria:"
)


def render_summary_prompt(text: str) -> str:
    """Renderiza o prompt de sumarização para o texto dado."""
    return SUMMARY_PROMPT_TEMPLATE.format(text=text)


def render_classification_prompt(text: str, categories: Sequence[str]) -> str:
    """Renderiza o prompt de classificação para o texto e categorias dados."""
    return CLASSIFICATION_PROMPT_TEMPLATE.format(
        text=text, categories=", ".join(categories)
    )


# ---------------------------------------------------------------------------
# Prompt registry do MLflow
# ---------------------------------------------------------------------------


def _to_registry_template(template: str) -> str:
    """Converte placeholders ``{text}`` -> ``{{text}}`` para o registry do MLflow.

    O prompt registry do MLflow usa a sintaxe de chaves duplas para variáveis.
    """
    # Converte {text} em {{text}} sem afetar chaves já duplas.
    return template.replace("{text}", "{{text}}").replace(
        "{categories}", "{{categories}}"
    )


def _register_prompt_fn():
    """Resolve a função de registro de prompt na API disponível do MLflow.

    Prefere o namespace moderno ``mlflow.genai.register_prompt`` (MLflow 3.x) e cai
    para ``mlflow.register_prompt`` em versões mais antigas. Retorna ``None`` se
    nenhuma estiver disponível.
    """
    try:
        from mlflow.genai import register_prompt  # MLflow 3.x

        return register_prompt
    except Exception:
        return getattr(mlflow, "register_prompt", None)


def register_summary_prompt(
    name: str = "dgb-news-summary",
    commit_message: Optional[str] = None,
):
    """Registra o template de sumarização no prompt registry do MLflow.

    Usa ``mlflow.genai.register_prompt`` (ou o legado ``mlflow.register_prompt``).
    Retorna o objeto ``PromptVersion`` (com ``.version``). Levanta ``RuntimeError``
    se o registry não estiver disponível.
    """
    register_prompt = _register_prompt_fn()
    if register_prompt is None:
        raise RuntimeError(
            "Esta versão do MLflow não expõe register_prompt; "
            "atualize o MLflow para usar o prompt registry."
        )
    return register_prompt(
        name=name,
        template=_to_registry_template(SUMMARY_PROMPT_TEMPLATE),
        commit_message=commit_message or "Template de sumarização de notícias gov.br",
    )
