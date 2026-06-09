"""Testes do provider de headers do IAP."""

from __future__ import annotations

import pytest

from dgb_mlflow import headers


@pytest.fixture(autouse=True)
def _reset_state():
    """Reseta o estado de módulo do provider antes e depois de cada teste."""
    headers.set_iap_state(False)
    yield
    headers.set_iap_state(False)


def test_in_context_false_quando_iap_inativo():
    provider = headers.IAPRequestHeaderProvider()
    assert provider.in_context() is False


def test_in_context_true_no_modo_iap():
    headers.set_iap_state(True, "client-id")
    provider = headers.IAPRequestHeaderProvider()
    assert provider.in_context() is True


def test_in_context_false_se_ativo_mas_sem_client_id():
    # set_iap_state(True, None) é estado degenerado; deve continuar inerte.
    headers.set_iap_state(True, None)
    provider = headers.IAPRequestHeaderProvider()
    assert provider.in_context() is False


def test_request_headers_monta_bearer(monkeypatch):
    headers.set_iap_state(True, "client-id")
    monkeypatch.setattr(headers, "get_iap_token", lambda cid: f"TOKEN[{cid}]")

    provider = headers.IAPRequestHeaderProvider()
    result = provider.request_headers()

    assert result == {"Authorization": "Bearer TOKEN[client-id]"}


def test_request_headers_vazio_fora_do_contexto(monkeypatch):
    headers.set_iap_state(False)

    def _boom(cid):  # pragma: no cover - não deve ser chamado
        raise AssertionError("não deveria gerar token fora do contexto IAP")

    monkeypatch.setattr(headers, "get_iap_token", _boom)

    provider = headers.IAPRequestHeaderProvider()
    assert provider.request_headers() == {}


def test_set_iap_state_limpa_client_id_ao_desativar():
    headers.set_iap_state(True, "client-id")
    headers.set_iap_state(False)
    ativo, cid = headers.get_iap_state()
    assert ativo is False
    assert cid is None
