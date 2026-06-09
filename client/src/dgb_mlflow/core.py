"""``configure()`` — ponto de entrada de alto nível da biblioteca.

Resolve a tracking URI e o client id do IAP, ativa/desativa o provider de headers
conforme o modo, e chama ``mlflow.set_tracking_uri``.
"""

from __future__ import annotations

import logging

import mlflow

from . import config, headers

logger = logging.getLogger(__name__)


def configure(tracking_uri: str | None = None) -> str:
    """Configura o MLflow para o ambiente DGB e retorna a tracking URI efetiva.

    Ordem da URI: ``tracking_uri`` explícito > env ``DGB_MLFLOW_TRACKING_URI`` >
    fallback local ``sqlite:///mlflow.db``. Se houver tracking remoto (https) e um
    IAP client id (env ``DGB_MLFLOW_IAP_CLIENT_ID``), ativa o provider de headers
    que injeta ``Authorization: Bearer <ID token>``. Caso contrário, opera em modo
    local (offline), com o provider desativado.
    """
    uri = config.resolve_tracking_uri(tracking_uri)
    client_id = config.resolve_iap_client_id()

    if config.is_iap_mode(uri, client_id):
        headers.set_iap_state(True, client_id)
        logger.info("dgb-mlflow: modo remoto-IAP (uri=%s).", uri)
    else:
        headers.set_iap_state(False)
        if config.is_remote_uri(uri) and not client_id:
            logger.warning(
                "dgb-mlflow: tracking remoto (%s) sem DGB_MLFLOW_IAP_CLIENT_ID; "
                "as requisições NÃO serão autenticadas no IAP.",
                uri,
            )
        else:
            logger.info("dgb-mlflow: modo local (uri=%s).", uri)

    mlflow.set_tracking_uri(uri)
    return uri
