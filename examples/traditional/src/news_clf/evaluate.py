"""Métricas de avaliação do classificador."""
from __future__ import annotations

from typing import Dict, Sequence

from sklearn.metrics import accuracy_score, f1_score


def compute_metrics(y_true: Sequence, y_pred: Sequence) -> Dict[str, float]:
    """Calcula métricas determinísticas para classificação multiclasse.

    Retorna um dicionário com ``accuracy`` e ``f1_macro``. O f1 macro dá
    peso igual a cada classe (bom para datasets balanceados).
    """
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
    }
