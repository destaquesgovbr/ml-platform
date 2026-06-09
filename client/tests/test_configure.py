"""Testes de configure(): seta a tracking uri e ativa/desativa o provider."""

from __future__ import annotations

import mlflow
import pytest

from dgb_mlflow import config, core, headers

REMOTE_URI = "https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"
REMOTE_AUDIENCE = REMOTE_URI + "/*"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in (
        config.ENV_TRACKING_URI,
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
    ativo, _, _ = headers.get_iap_state()
    assert ativo is False


def test_configure_arg_explicito_local(tmp_path):
    db = f"sqlite:///{tmp_path / 'local.db'}"
    uri = core.configure(db)
    assert uri == db
    assert mlflow.get_tracking_uri() == db
    assert headers.get_iap_state()[0] is False


def test_configure_remoto_ativa_provider_com_audience_e_sa():
    uri = core.configure(REMOTE_URI)

    assert uri == REMOTE_URI
    assert mlflow.get_tracking_uri() == REMOTE_URI
    ativo, audience, signer_sa = headers.get_iap_state()
    assert ativo is True
    assert audience == REMOTE_AUDIENCE
    assert signer_sa == config.DEFAULT_CLIENT_SA


def test_configure_remoto_usa_sa_customizada(monkeypatch):
    monkeypatch.setenv(config.ENV_CLIENT_SA, "custom@projeto.iam.gserviceaccount.com")
    core.configure(REMOTE_URI)
    ativo, audience, signer_sa = headers.get_iap_state()
    assert ativo is True
    assert audience == REMOTE_AUDIENCE
    assert signer_sa == "custom@projeto.iam.gserviceaccount.com"


def test_configure_usa_env_tracking_uri(monkeypatch):
    monkeypatch.setenv(config.ENV_TRACKING_URI, REMOTE_URI)
    uri = core.configure()
    assert uri == REMOTE_URI
    assert headers.get_iap_state() == (True, REMOTE_AUDIENCE, config.DEFAULT_CLIENT_SA)


def test_configure_desativa_provider_ao_voltar_para_local():
    # Primeiro ativa o IAP...
    core.configure(REMOTE_URI)
    assert headers.get_iap_state()[0] is True

    # ...depois reconfigura local: o provider deve ser desativado.
    core.configure("sqlite:///mlflow.db")
    assert headers.get_iap_state() == (False, None, None)


def test_provider_descoberto_via_entry_point():
    """O MLflow deve enxergar nosso provider pelo entry point registrado."""
    from mlflow.tracking.request_header.registry import _request_header_provider_registry

    classes = {type(p).__name__ for p in _request_header_provider_registry._registry}
    assert "IAPRequestHeaderProvider" in classes
