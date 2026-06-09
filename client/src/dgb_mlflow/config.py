"""Resolução de configuração a partir de variáveis de ambiente.

Funções puras (sem efeitos colaterais) para facilitar os testes. Toda a leitura
de ``os.environ`` é feita aqui, isolando o resto do pacote de detalhes de ambiente.
"""

from __future__ import annotations

import os

# Variáveis de ambiente reconhecidas pelo pacote.
ENV_TRACKING_URI = "DGB_MLFLOW_TRACKING_URI"
ENV_CLIENT_SA = "DGB_MLFLOW_CLIENT_SA"
ENV_TRACKING_TOKEN = "MLFLOW_TRACKING_TOKEN"

# DEPRECADA: o IAP do Cloud Run usa o OAuth client GERENCIADO PELO GOOGLE, então
# acesso programático por ID token OIDC (aud = client_id) é bloqueado (401
# "Invalid JWT audience"). O fluxo atual usa um JWT auto-assinado pela SA via a
# API IAM Credentials signJwt, cuja audience é a URL do recurso + "/*". Esta
# constante é mantida apenas por compatibilidade e NÃO é mais usada.
ENV_IAP_CLIENT_ID = "DGB_MLFLOW_IAP_CLIENT_ID"

# Fallbacks para desenvolvimento local (offline, sem GCP).
LOCAL_TRACKING_URI = "sqlite:///mlflow.db"
LOCAL_ARTIFACT_ROOT = "./mlruns"

# SA cliente padrão que assina o JWT do IAP (signJwt). Já tem
# iap.httpsResourceAccessor; no desktop o usuário tem
# roles/iam.serviceAccountTokenCreator nela.
DEFAULT_CLIENT_SA = "destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com"


def resolve_tracking_uri(tracking_uri: str | None = None) -> str:
    """Resolve a tracking URI na ordem: arg explícito > env > fallback local.

    Strings vazias (ou só espaços) são tratadas como ausentes.
    """
    if tracking_uri and tracking_uri.strip():
        return tracking_uri.strip()

    env_uri = os.environ.get(ENV_TRACKING_URI)
    if env_uri and env_uri.strip():
        return env_uri.strip()

    return LOCAL_TRACKING_URI


def resolve_client_sa() -> str:
    """Retorna a SA cliente (env ``DGB_MLFLOW_CLIENT_SA`` ou o default do projeto)."""
    sa = os.environ.get(ENV_CLIENT_SA)
    if sa and sa.strip():
        return sa.strip()
    return DEFAULT_CLIENT_SA


def resolve_audience(uri: str) -> str:
    """Audience do JWT do IAP: a URL do recurso normalizada com sufixo ``/*``.

    O IAP do Cloud Run exige a URL do serviço com ``/*`` (a URL pura dá 401).
    """
    return uri.rstrip("/") + "/*"


def is_remote_uri(uri: str) -> bool:
    """True se a URI aponta para um servidor remoto HTTP(S) (não local)."""
    return uri.startswith("http://") or uri.startswith("https://")


def is_iap_mode(tracking_uri: str) -> bool:
    """O modo IAP vale para qualquer tracking remoto (http/https)."""
    return is_remote_uri(tracking_uri)
