"""dgb-mlflow — cliente helper do MLflow para o Destaques Gov.BR.

Esconde a complexidade do IAP (autenticação por JWT auto-assinado via signJwt) e
do tracking remoto. Uso típico::

    import dgb_mlflow
    dgb_mlflow.configure()   # remoto-IAP ou local, conforme o ambiente

Veja o README para variáveis de ambiente e exemplos (PC e VM).
"""

from __future__ import annotations

from .auth import get_iap_jwt
from .core import configure

__version__ = "0.1.0"

__all__ = ["__version__", "configure", "get_iap_jwt"]
