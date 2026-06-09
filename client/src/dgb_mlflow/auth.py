"""Obtenção do ID token OIDC usado para autenticar no IAP.

Ordem de resolução do token (ver :func:`get_iap_token`):

1. ``MLFLOW_TRACKING_TOKEN`` (override manual) — útil em CI ou debugging;
2. ``google.oauth2.id_token.fetch_id_token`` — funciona em VM/Cloud Run/SA via
   metadata server, retornando um ID token com a audiência = IAP client id;
3. impersonação da SA cliente (``DGB_MLFLOW_CLIENT_SA``) via
   ``impersonated_credentials.IDTokenCredentials`` — caminho do desktop, onde a
   ADC é uma credencial de usuário e não consegue cunhar ID tokens diretamente.

As chamadas às libs do google ficam isoladas em funções pequenas para mockar nos
testes (offline, sem rede).
"""

from __future__ import annotations

import logging
import os

from . import config

logger = logging.getLogger(__name__)


def _token_from_env() -> str | None:
    """Retorna ``MLFLOW_TRACKING_TOKEN`` se setado (override manual)."""
    token = os.environ.get(config.ENV_TRACKING_TOKEN)
    if token and token.strip():
        return token.strip()
    return None


def _fetch_id_token_via_metadata(client_id: str) -> str:
    """ID token via metadata server (VM/Cloud Run/SA).

    Wrapper fino sobre ``google.oauth2.id_token.fetch_id_token`` para mockar.
    """
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    return id_token.fetch_id_token(Request(), client_id)


def _fetch_id_token_via_impersonation(client_id: str, client_sa: str) -> str:
    """ID token impersonando a SA cliente (caminho desktop com ADC de usuário)."""
    import google.auth
    from google.auth import impersonated_credentials
    from google.auth.transport.requests import Request

    source_credentials, _ = google.auth.default()
    id_creds = impersonated_credentials.IDTokenCredentials(
        target_credentials=impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=client_sa,
            target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        ),
        target_audience=client_id,
        include_email=True,
    )
    id_creds.refresh(Request())
    return id_creds.token


def get_iap_token(client_id: str) -> str:
    """Retorna um ID token OIDC com audiência = ``client_id`` (IAP OAuth client).

    Tenta, em ordem: override de ambiente, metadata server e impersonação.
    Levanta ``RuntimeError`` com mensagem clara se nenhum caminho funcionar.
    """
    override = _token_from_env()
    if override:
        logger.debug("Token do IAP via MLFLOW_TRACKING_TOKEN (override).")
        return override

    try:
        token = _fetch_id_token_via_metadata(client_id)
        if token:
            logger.debug("Token do IAP via metadata server (VM/SA).")
            return token
    except Exception as exc:  # noqa: BLE001 - fallback intencional p/ impersonação
        logger.debug("fetch_id_token (metadata) falhou: %s. Tentando impersonação.", exc)

    client_sa = config.resolve_client_sa()
    try:
        token = _fetch_id_token_via_impersonation(client_id, client_sa)
        if token:
            logger.debug("Token do IAP via impersonação de %s.", client_sa)
            return token
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Falha ao obter ID token do IAP. Tentativas: "
            "(1) MLFLOW_TRACKING_TOKEN não setado; "
            "(2) metadata server indisponível; "
            f"(3) impersonação de '{client_sa}' falhou: {exc}. "
            "No desktop, rode 'gcloud auth application-default login' e garanta a "
            "permissão roles/iam.serviceAccountTokenCreator na SA cliente."
        ) from exc

    raise RuntimeError(
        "Não foi possível obter um ID token do IAP (todas as estratégias "
        "retornaram vazio)."
    )
