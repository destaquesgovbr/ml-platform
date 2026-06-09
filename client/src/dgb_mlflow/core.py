"""``configure()`` — ponto de entrada de alto nível da biblioteca.

Resolve a tracking URI, ativa/desativa o provider de headers conforme o modo
(remoto-IAP ou local) e chama ``mlflow.set_tracking_uri``.
"""

from __future__ import annotations

import logging

import mlflow

from . import config, headers

logger = logging.getLogger(__name__)


def configure(tracking_uri: str | None = None) -> str:
    """Configura o MLflow para o ambiente DGB e retorna a tracking URI efetiva.

    Ordem da URI: ``tracking_uri`` explícito > env ``DGB_MLFLOW_TRACKING_URI`` >
    fallback local ``sqlite:///mlflow.db``. Se houver tracking remoto (http/https),
    ativa o provider de headers que injeta ``Authorization: Bearer <JWT>``, onde o
    JWT é auto-assinado pela SA cliente via signJwt com audience = URL + ``/*``.
    Caso contrário, opera em modo local (offline), com o provider desativado.
    """
    uri = config.resolve_tracking_uri(tracking_uri)

    if config.is_remote_uri(uri):
        audience = config.resolve_audience(uri)
        signer_sa = config.resolve_client_sa()
        headers.set_iap_state(True, audience, signer_sa)
        logger.info(
            "dgb-mlflow: modo remoto-IAP (uri=%s, aud=%s, sa=%s).",
            uri,
            audience,
            signer_sa,
        )
    else:
        headers.set_iap_state(False)
        logger.info("dgb-mlflow: modo local (uri=%s).", uri)

    mlflow.set_tracking_uri(uri)
    return uri
