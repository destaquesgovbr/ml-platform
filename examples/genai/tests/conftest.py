"""Fixtures compartilhadas dos testes de GenAI.

Princípio: tudo OFFLINE e DETERMINÍSTICO. Cada teste aponta o tracking do MLflow
para um SQLite temporário dentro do ``tmp_path``, sem tocar em GCP/rede nem exigir
chaves de API.
"""

import sys
from pathlib import Path

import mlflow
import pytest

# Garante que ``src/`` esteja no path (o exemplo não é instalado como pacote).
SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def local_tracking(tmp_path, monkeypatch):
    """Configura o MLflow para tracking local (SQLite) isolado por teste.

    Retorna o ``tracking_uri`` usado, caso o teste precise inspecioná-lo.
    """
    db = tmp_path / "mlflow.db"
    artifacts = tmp_path / "mlruns"
    artifacts.mkdir()
    tracking_uri = f"sqlite:///{db}"

    # Limpa qualquer chave de API que por acaso esteja no ambiente: os testes
    # NÃO podem chamar providers reais.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Tracing síncrono nos testes: garante que os traces sejam gravados antes de
    # ``mlflow.search_traces`` ser chamado (sem corrida com a fila assíncrona).
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("genai-tests")
    return tracking_uri
