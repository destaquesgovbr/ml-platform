"""Provider de headers que injeta o ``Authorization: Bearer <ID token>`` do IAP.

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

from .auth import get_iap_token

# Estado de módulo controlado por configure(). Mantido fora da instância porque o
# MLflow instancia o provider por conta própria (via entry point), então não temos
# como passar parâmetros pelo construtor.
_iap_active: bool = False
_iap_client_id: str | None = None


def set_iap_state(active: bool, client_id: str | None = None) -> None:
    """Ativa/desativa o modo IAP e guarda o client id usado para cunhar o token."""
    global _iap_active, _iap_client_id
    _iap_active = bool(active)
    _iap_client_id = client_id if active else None


def get_iap_state() -> tuple[bool, str | None]:
    """Retorna ``(ativo, client_id)`` — útil para testes e introspecção."""
    return _iap_active, _iap_client_id


class IAPRequestHeaderProvider(RequestHeaderProvider):
    """Injeta o cabeçalho de autenticação do IAP quando o modo IAP está ativo."""

    def in_context(self) -> bool:
        """True somente quando há modo IAP ativo com client id configurado."""
        return _iap_active and _iap_client_id is not None

    def request_headers(self) -> dict:
        """Monta ``{'Authorization': 'Bearer <ID token>'}`` para o IAP."""
        if not self.in_context():
            return {}
        return {"Authorization": f"Bearer {get_iap_token(_iap_client_id)}"}
