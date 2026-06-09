"""Testes de configure(): seta a tracking uri e ativa/desativa o provider."""

from __future__ import annotations

import mlflow
import pytest

from dgb_mlflow import config, core, headers


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in (
        config.ENV_TRACKING_URI,
        config.ENV_IAP_CLIENT_ID,
        config.ENV_CLIENT_SA,
        config.ENV_TRACKING_TOKEN,
    ):
        monkeypatch.delenv(var, raising=False)
    headers.set_iap_state(False)
    yield
    headers.set_iap_state(False)


def test_configure_local_por_padrao():
    uri = core.configure()
    assert uri == config.LOCAL_TRACKING_URI
    assert mlflow.get_tracking_uri() == config.LOCAL_TRACKING_URI
    ativo, _ = headers.get_iap_state()
    assert ativo is False


def test_configure_arg_explicito_local(tmp_path):
    db = f"sqlite:///{tmp_path / 'local.db'}"
    uri = core.configure(db)
    assert uri == db
    assert mlflow.get_tracking_uri() == db
    assert headers.get_iap_state()[0] is False


def test_configure_remoto_com_iap_ativa_provider(monkeypatch):
    monkeypatch.setenv(config.ENV_IAP_CLIENT_ID, "cid.apps.googleusercontent.com")
    uri = core.configure("https://mlflow.dgb.gov.br")

    assert uri == "https://mlflow.dgb.gov.br"
    assert mlflow.get_tracking_uri() == "https://mlflow.dgb.gov.br"
    ativo, cid = headers.get_iap_state()
    assert ativo is True
    assert cid == "cid.apps.googleusercontent.com"


def test_configure_remoto_sem_client_id_nao_ativa(monkeypatch):
    # Remoto mas sem DGB_MLFLOW_IAP_CLIENT_ID -> provider desativado (warning).
    uri = core.configure("https://mlflow.dgb.gov.br")
    assert uri == "https://mlflow.dgb.gov.br"
    assert headers.get_iap_state()[0] is False


def test_configure_usa_env_tracking_uri(monkeypatch):
    monkeypatch.setenv(config.ENV_TRACKING_URI, "https://mlflow.dgb.gov.br")
    monkeypatch.setenv(config.ENV_IAP_CLIENT_ID, "cid")
    uri = core.configure()
    assert uri == "https://mlflow.dgb.gov.br"
    assert headers.get_iap_state() == (True, "cid")


def test_configure_desativa_provider_ao_voltar_para_local(monkeypatch):
    # Primeiro ativa o IAP...
    monkeypatch.setenv(config.ENV_IAP_CLIENT_ID, "cid")
    core.configure("https://mlflow.dgb.gov.br")
    assert headers.get_iap_state()[0] is True

    # ...depois reconfigura local: o provider deve ser desativado.
    monkeypatch.delenv(config.ENV_IAP_CLIENT_ID, raising=False)
    core.configure("sqlite:///mlflow.db")
    assert headers.get_iap_state()[0] is False


def test_provider_descoberto_via_entry_point():
    """O MLflow deve enxergar nosso provider pelo entry point registrado."""
    from mlflow.tracking.request_header.registry import _request_header_provider_registry

    classes = {type(p).__name__ for p in _request_header_provider_registry._registry}
    assert "IAPRequestHeaderProvider" in classes
