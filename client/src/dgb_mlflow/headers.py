"""Provider de headers que injeta o ``Authorization: Bearer <JWT>`` do IAP.

O MLflow descobre esta classe via entry point ``mlflow.request_header_provider``
(ver ``pyproject.toml``) e a consulta em toda requisição ao tracking server. O
provider só age (``in_context()`` -> True) quando :func:`dgb_mlflow.configure`
ativou o modo IAP — caso contrário fica inerte, sem afetar dev local nem outros
servidores.
"""

from __future__ import annotations

from mlflow.tracking.request_header.abstract_request_header_provider import (
    RequestHeaderProvider,
)

from .auth import get_iap_jwt

# Estado de módulo controlado por configure(). Mantido fora da instância porque o
# MLflow instancia o provider por conta própria (via entry point), então não temos
# como passar parâmetros pelo construtor.
_iap_active: bool = False
_audience: str | None = None
_signer_sa: str | None = None


def set_iap_state(
    active: bool,
    audience: str | None = None,
    signer_sa: str | None = None,
) -> None:
    """Ativa/desativa o modo IAP e guarda a audience + SA assinadora do JWT."""
    global _iap_active, _audience, _signer_sa
    _iap_active = bool(active)
    if active:
        _audience = audience
        _signer_sa = signer_sa
    else:
        _audience = None
        _signer_sa = None


def get_iap_state() -> tuple[bool, str | None, str | None]:
    """Retorna ``(ativo, audience, signer_sa)`` — útil p/ testes e introspecção."""
    return _iap_active, _audience, _signer_sa


class IAPRequestHeaderProvider(RequestHeaderProvider):
    """Injeta o cabeçalho de autenticação do IAP quando o modo IAP está ativo."""

    def in_context(self) -> bool:
        """True somente quando há modo IAP ativo com audience configurada."""
        return _iap_active and _audience is not None

    def request_headers(self) -> dict:
        """Monta ``{'Authorization': 'Bearer <JWT>'}`` para o IAP."""
        if not self.in_context():
            return {}
        return {"Authorization": f"Bearer {get_iap_jwt(_audience, _signer_sa)}"}
