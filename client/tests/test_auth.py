"""Testes da obtenção do ID token do IAP (todas as chamadas google mockadas)."""

from __future__ import annotations

import pytest

from dgb_mlflow import auth, config

CLIENT_ID = "client-id.apps.googleusercontent.com"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(config.ENV_TRACKING_TOKEN, raising=False)
    monkeypatch.delenv(config.ENV_CLIENT_SA, raising=False)


# --- (1) override por env -------------------------------------------------

def test_override_via_mlflow_tracking_token(monkeypatch):
    monkeypatch.setenv(config.ENV_TRACKING_TOKEN, "token-manual")

    # Se o override funcionar, nenhuma chamada google deve ocorrer.
    def _boom(*a, **k):  # pragma: no cover - não deve ser chamado
        raise AssertionError("não deveria tocar o google quando há override")

    monkeypatch.setattr(auth, "_fetch_id_token_via_metadata", _boom)
    monkeypatch.setattr(auth, "_fetch_id_token_via_impersonation", _boom)

    assert auth.get_iap_token(CLIENT_ID) == "token-manual"


def test_override_vazio_e_ignorado(monkeypatch):
    monkeypatch.setenv(config.ENV_TRACKING_TOKEN, "   ")
    monkeypatch.setattr(
        auth, "_fetch_id_token_via_metadata", lambda cid: "token-metadata"
    )
    assert auth.get_iap_token(CLIENT_ID) == "token-metadata"


# --- (2) metadata server (VM/SA) ------------------------------------------

def test_token_via_metadata(monkeypatch):
    chamado = {}

    def _meta(cid):
        chamado["cid"] = cid
        return "token-metadata"

    monkeypatch.setattr(auth, "_fetch_id_token_via_metadata", _meta)
    monkeypatch.setattr(
        auth,
        "_fetch_id_token_via_impersonation",
        lambda cid, sa: (_ for _ in ()).throw(AssertionError("não deveria impersonar")),
    )

    assert auth.get_iap_token(CLIENT_ID) == "token-metadata"
    assert chamado["cid"] == CLIENT_ID


# --- (3) fallback para impersonação ---------------------------------------

def test_fallback_impersonacao_quando_metadata_falha(monkeypatch):
    def _meta_falha(cid):
        raise RuntimeError("sem metadata server (desktop)")

    capturado = {}

    def _imp(cid, sa):
        capturado["cid"] = cid
        capturado["sa"] = sa
        return "token-impersonado"

    monkeypatch.setattr(auth, "_fetch_id_token_via_metadata", _meta_falha)
    monkeypatch.setattr(auth, "_fetch_id_token_via_impersonation", _imp)

    assert auth.get_iap_token(CLIENT_ID) == "token-impersonado"
    assert capturado["cid"] == CLIENT_ID
    assert capturado["sa"] == config.DEFAULT_CLIENT_SA


def test_impersonacao_usa_sa_customizada(monkeypatch):
    monkeypatch.setenv(config.ENV_CLIENT_SA, "custom@projeto.iam.gserviceaccount.com")
    monkeypatch.setattr(
        auth,
        "_fetch_id_token_via_metadata",
        lambda cid: (_ for _ in ()).throw(RuntimeError("falhou")),
    )

    capturado = {}

    def _imp(cid, sa):
        capturado["sa"] = sa
        return "token"

    monkeypatch.setattr(auth, "_fetch_id_token_via_impersonation", _imp)

    auth.get_iap_token(CLIENT_ID)
    assert capturado["sa"] == "custom@projeto.iam.gserviceaccount.com"


# --- erro quando tudo falha -----------------------------------------------

def test_erro_claro_quando_tudo_falha(monkeypatch):
    monkeypatch.setattr(
        auth,
        "_fetch_id_token_via_metadata",
        lambda cid: (_ for _ in ()).throw(RuntimeError("sem metadata")),
    )
    monkeypatch.setattr(
        auth,
        "_fetch_id_token_via_impersonation",
        lambda cid, sa: (_ for _ in ()).throw(RuntimeError("sem permissão")),
    )

    with pytest.raises(RuntimeError) as exc:
        auth.get_iap_token(CLIENT_ID)

    msg = str(exc.value)
    assert "IAP" in msg
    assert config.DEFAULT_CLIENT_SA in msg
