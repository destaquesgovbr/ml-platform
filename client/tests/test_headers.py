"""Testes do provider de headers do IAP."""

from __future__ import annotations

import pytest

from dgb_mlflow import headers

AUDIENCE = "https://mlflow.dgb.gov.br/*"
SIGNER_SA = "sa@projeto.iam.gserviceaccount.com"


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
    headers.set_iap_state(True, AUDIENCE, SIGNER_SA)
    provider = headers.IAPRequestHeaderProvider()
    assert provider.in_context() is True


def test_in_context_false_se_ativo_mas_sem_audience():
    # set_iap_state(True, None) é estado degenerado; deve continuar inerte.
    headers.set_iap_state(True, None, SIGNER_SA)
    provider = headers.IAPRequestHeaderProvider()
    assert provider.in_context() is False


def test_request_headers_monta_bearer(monkeypatch):
    headers.set_iap_state(True, AUDIENCE, SIGNER_SA)

    capturado = {}

    def _fake_jwt(audience, signer_sa):
        capturado["audience"] = audience
        capturado["signer_sa"] = signer_sa
        return "JWT"

    monkeypatch.setattr(headers, "get_iap_jwt", _fake_jwt)

    provider = headers.IAPRequestHeaderProvider()
    result = provider.request_headers()

    assert result == {"Authorization": "Bearer JWT"}
    assert capturado["audience"] == AUDIENCE
    assert capturado["signer_sa"] == SIGNER_SA


def test_request_headers_vazio_fora_do_contexto(monkeypatch):
    headers.set_iap_state(False)

    def _boom(audience, signer_sa):  # pragma: no cover - não deve ser chamado
        raise AssertionError("não deveria gerar JWT fora do contexto IAP")

    monkeypatch.setattr(headers, "get_iap_jwt", _boom)

    provider = headers.IAPRequestHeaderProvider()
    assert provider.request_headers() == {}


def test_set_iap_state_limpa_estado_ao_desativar():
    headers.set_iap_state(True, AUDIENCE, SIGNER_SA)
    headers.set_iap_state(False)
    ativo, audience, signer_sa = headers.get_iap_state()
    assert ativo is False
    assert audience is None
    assert signer_sa is None
