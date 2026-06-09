"""Obtenção do JWT usado para autenticar no IAP do Cloud Run.

O IAP do servidor MLflow usa o OAuth client **gerenciado pelo Google**, então
acesso programático por ID token OIDC (``aud = client_id``) é bloqueado pelo IAP
(401 "Invalid JWT audience"). O fluxo que funciona é um **JWT auto-assinado** pela
service account via a API IAM Credentials ``signJwt``, cuja audience é a URL do
recurso + ``/*``.

Ordem de resolução (ver :func:`get_iap_jwt`):

1. ``MLFLOW_TRACKING_TOKEN`` (override manual) — útil em CI ou debugging;
2. JWT assinado pela SA cliente (``DGB_MLFLOW_CLIENT_SA``) via ``signJwt``.

A chamada às libs do google fica isolada em :func:`_sign_jwt` para mockar nos
testes (offline, sem rede).
"""

from __future__ import annotations

import json
import logging
import os
import time

from . import config

logger = logging.getLogger(__name__)

_IAM_CREDENTIALS_ENDPOINT = (
    "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{sa}:signJwt"
)


def _token_from_env() -> str | None:
    """Retorna ``MLFLOW_TRACKING_TOKEN`` se setado (override manual)."""
    token = os.environ.get(config.ENV_TRACKING_TOKEN)
    if token and token.strip():
        return token.strip()
    return None


def _sign_jwt(signer_sa: str, payload_json: str) -> str:
    """Assina ``payload_json`` com a SA ``signer_sa`` via IAM Credentials signJwt.

    Wrapper fino sobre a API do google (mockado nos testes). Usa a ADC corrente
    (``google.auth.default``) para autenticar a chamada ao endpoint signJwt e
    retorna o JWT assinado.
    """
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = AuthorizedSession(credentials)
    resp = session.post(
        _IAM_CREDENTIALS_ENDPOINT.format(sa=signer_sa),
        data=json.dumps({"payload": payload_json}),
    )
    resp.raise_for_status()
    return resp.json()["signedJwt"]


def get_iap_jwt(audience: str, signer_sa: str) -> str:
    """Retorna o JWT (Bearer) para autenticar no IAP do Cloud Run.

    Ordem: override de ambiente (``MLFLOW_TRACKING_TOKEN``) e, caso ausente, um
    JWT auto-assinado pela SA ``signer_sa`` via signJwt, com ``aud = audience``
    (a URL do recurso com sufixo ``/*``).

    Levanta ``RuntimeError`` com mensagem clara se a assinatura falhar.
    """
    override = _token_from_env()
    if override:
        logger.debug("JWT do IAP via MLFLOW_TRACKING_TOKEN (override).")
        return override

    now = int(time.time())
    payload = {
        "iss": signer_sa,
        "sub": signer_sa,
        "email": signer_sa,
        "aud": audience,
        "iat": now,
        "exp": now + 3600,
    }

    try:
        signed = _sign_jwt(signer_sa, json.dumps(payload))
    except Exception as exc:  # noqa: BLE001 - reembrulha com dica acionável
        raise RuntimeError(
            "Falha ao assinar o JWT do IAP via signJwt para a SA "
            f"'{signer_sa}' (audience='{audience}'): {exc}. "
            "Garanta a permissão roles/iam.serviceAccountTokenCreator nessa SA e, "
            "no desktop, rode 'gcloud auth application-default login'."
        ) from exc

    logger.debug("JWT do IAP assinado por %s (aud=%s).", signer_sa, audience)
    return signed
