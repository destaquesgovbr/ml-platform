"""Testes da resolução de configuração (funções puras de env)."""

from __future__ import annotations

import pytest

from dgb_mlflow import config


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Garante ambiente limpo das vars do pacote em cada teste."""
    for var in (
        config.ENV_TRACKING_URI,
        config.ENV_CLIENT_SA,
        config.ENV_TRACKING_TOKEN,
    ):
        monkeypatch.delenv(var, raising=False)


# --- tracking URI: arg > env > local --------------------------------------

def test_tracking_uri_arg_tem_prioridade(monkeypatch):
    monkeypatch.setenv(config.ENV_TRACKING_URI, "https://env.example")
    assert config.resolve_tracking_uri("https://arg.example") == "https://arg.example"


def test_tracking_uri_usa_env_quando_sem_arg(monkeypatch):
    monkeypatch.setenv(config.ENV_TRACKING_URI, "https://mlflow.dgb.gov.br")
    assert config.resolve_tracking_uri() == "https://mlflow.dgb.gov.br"


def test_tracking_uri_fallback_local_quando_nada():
    assert config.resolve_tracking_uri() == config.LOCAL_TRACKING_URI
    assert config.resolve_tracking_uri() == "sqlite:///mlflow.db"


def test_tracking_uri_string_vazia_e_tratada_como_ausente(monkeypatch):
    monkeypatch.setenv(config.ENV_TRACKING_URI, "  ")
    assert config.resolve_tracking_uri("") == config.LOCAL_TRACKING_URI


# --- client SA: env > default ---------------------------------------------

def test_client_sa_default_quando_sem_env():
    assert config.resolve_client_sa() == config.DEFAULT_CLIENT_SA
    assert "destaquesgovbr-mlflow-client@" in config.resolve_client_sa()


def test_client_sa_lido_do_env(monkeypatch):
    monkeypatch.setenv(config.ENV_CLIENT_SA, "outra-sa@projeto.iam.gserviceaccount.com")
    assert config.resolve_client_sa() == "outra-sa@projeto.iam.gserviceaccount.com"


# --- audience: URL + "/*" -------------------------------------------------

def test_audience_adiciona_estrela():
    uri = "https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"
    assert config.resolve_audience(uri) == uri + "/*"


def test_audience_normaliza_barra_final():
    uri = "https://mlflow.dgb.gov.br/"
    assert config.resolve_audience(uri) == "https://mlflow.dgb.gov.br/*"


def test_audience_normaliza_multiplas_barras_finais():
    assert config.resolve_audience("https://x.run.app///") == "https://x.run.app/*"


# --- detecção de modo -----------------------------------------------------

@pytest.mark.parametrize(
    "uri,esperado",
    [
        ("https://mlflow.dgb.gov.br", True),
        ("http://localhost:5000", True),
        ("sqlite:///mlflow.db", False),
        ("./mlruns", False),
    ],
)
def test_is_remote_uri(uri, esperado):
    assert config.is_remote_uri(uri) is esperado


def test_is_iap_mode_so_depende_de_remoto():
    assert config.is_iap_mode("https://mlflow.dgb.gov.br") is True
    assert config.is_iap_mode("http://localhost:5000") is True
    assert config.is_iap_mode("sqlite:///mlflow.db") is False
    assert config.is_iap_mode("./mlruns") is False
