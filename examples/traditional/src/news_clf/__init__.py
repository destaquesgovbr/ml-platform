"""news_clf — classificador de texto de notícias gov.br (exemplo tradicional).

Pipeline TF-IDF + LogisticRegression com tracking no MLflow. Os dados usados
nos testes são *toy*/sintéticos (sem download pesado). O caminho "pesado"
(fine-tune de BERT) vive em `train_bert.py`, fora deste pacote.
"""

from .data import LABELS, load_toy_dataset, train_test_split_xy
from .evaluate import compute_metrics
from .train import train

__all__ = [
    "LABELS",
    "load_toy_dataset",
    "train_test_split_xy",
    "compute_metrics",
    "train",
]
