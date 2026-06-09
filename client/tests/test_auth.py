"""Testes da obtenção do JWT do IAP (chamada signJwt mockada, sem rede)."""

from __future__ import annotations

import json

import pytest

from dgb_mlflow import auth, config

AUDIENCE = "https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app/*"
SIGNER_SA = config.DEFAULT_CLIENT_SA


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(config.ENV_TRACKING_TOKEN, raising=False)
    monkeypatch.delenv(config.ENV_CLIENT_SA, raising=False)


# --- (1) override por env -------------------------------------------------

def test_override_via_mlflow_tracking_token(monkeypatch):
    monkeypatch.setenv(config.ENV_TRACKING_TOKEN, "token-manual")

    # Se o override funcionar, signJwt não deve ser chamado.
    def _boom(*a, **k):  # pragma: no cover - não deve ser chamado
        raise AssertionError("não deveria assinar JWT quando há override")

    monkeypatch.setattr(auth, "_sign_jwt", _boom)

    assert auth.get_iap_jwt(AUDIENCE, SIGNER_SA) == "token-manual"


def test_override_vazio_e_ignorado(monkeypatch):
    monkeypatch.setenv(config.ENV_TRACKING_TOKEN, "   ")
    monkeypatch.setattr(auth, "_sign_jwt", lambda sa, payload: "jwt-assinado")
    assert auth.get_iap_jwt(AUDIENCE, SIGNER_SA) == "jwt-assinado"


# --- (2) JWT auto-assinado via signJwt ------------------------------------

def test_get_iap_jwt_assina_com_payload_correto(monkeypatch):
    capturado = {}

    def _sign(sa, payload_json):
        capturado["sa"] = sa
        capturado["payload"] = json.loads(payload_json)
        return "jwt-assinado"

    monkeypatch.setattr(auth, "_sign_jwt", _sign)

    assert auth.get_iap_jwt(AUDIENCE, SIGNER_SA) == "jwt-assinado"

    assert capturado["sa"] == SIGNER_SA
    payload = capturado["payload"]
    assert payload["iss"] == SIGNER_SA
    assert payload["sub"] == SIGNER_SA
    assert payload["email"] == SIGNER_SA
    assert payload["aud"] == AUDIENCE
    assert payload["exp"] - payload["iat"] == 3600


def test_get_iap_jwt_usa_sa_customizada(monkeypatch):
    custom_sa = "custom@projeto.iam.gserviceaccount.com"
    capturado = {}

    def _sign(sa, payload_json):
        capturado["sa"] = sa
        capturado["payload"] = json.loads(payload_json)
        return "jwt"

    monkeypatch.setattr(auth, "_sign_jwt", _sign)

    auth.get_iap_jwt(AUDIENCE, custom_sa)
    assert capturado["sa"] == custom_sa
    assert capturado["payload"]["iss"] == custom_sa


# --- erro quando a assinatura falha ---------------------------------------

def test_erro_claro_quando_sign_jwt_falha(monkeypatch):
    def _falha(sa, payload_json):
        raise RuntimeError("sem permissão signJwt")

    monkeypatch.setattr(auth, "_sign_jwt", _falha)

    with pytest.raises(RuntimeError) as exc:
        auth.get_iap_jwt(AUDIENCE, SIGNER_SA)

    msg = str(exc.value)
    assert "IAP" in msg
    assert SIGNER_SA in msg
    assert "serviceAccountTokenCreator" in msg
