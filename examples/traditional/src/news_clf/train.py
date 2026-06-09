"""Treino do classificador tradicional (TF-IDF + LogisticRegression) com MLflow.

Loga params, métricas e o modelo serializado. Quando ``register=True`` (ou
``MLFLOW_REGISTER=1``), também registra a versão no Model Registry.

Uso típico:

    # Local, contra sqlite:
    python -m news_clf.train

    # Contra o servidor DGB (atrás do IAP):
    import dgb_mlflow; dgb_mlflow.configure()
    python -m news_clf.train

O ``tracking_uri`` pode vir por argumento, pela env ``MLFLOW_TRACKING_URI`` ou,
em último caso, cai para ``sqlite:///mlflow.db`` (desenvolvimento local).
"""
from __future__ import annotations

import os
from typing import Dict, Optional

import mlflow
import mlflow.sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from .data import LABELS, load_toy_dataset, train_test_split_xy
from .evaluate import compute_metrics

# Nome do modelo no Model Registry
REGISTERED_MODEL_NAME = "dgb-news-clf"


def build_pipeline(random_state: int = 42) -> Pipeline:
    """Monta o pipeline TF-IDF + LogisticRegression."""
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    C=4.0,
                    random_state=random_state,
                ),
            ),
        ]
    )


def _resolve_tracking_uri(tracking_uri: Optional[str]) -> str:
    if tracking_uri:
        return tracking_uri
    return os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")


def train(
    tracking_uri: Optional[str] = None,
    experiment_name: str = "news-clf-traditional",
    artifact_location: Optional[str] = None,
    test_size: float = 0.25,
    random_state: int = 42,
    register: Optional[bool] = None,
) -> Dict[str, object]:
    """Treina o classificador e loga um run no MLflow.

    Args:
        tracking_uri: URI de tracking. Se ``None``, usa ``MLFLOW_TRACKING_URI``
            ou ``sqlite:///mlflow.db``.
        experiment_name: experimento alvo (criado se não existir).
        artifact_location: raiz de artefatos para o experimento (apenas na
            criação). Útil nos testes para apontar a um diretório temporário.
        test_size: fração do conjunto de teste.
        random_state: semente para reprodutibilidade.
        register: se ``True``, registra no Model Registry. Quando ``None``,
            usa a env ``MLFLOW_REGISTER`` (``1`` ativa).

    Returns:
        dict com ``run_id``, ``accuracy``, ``f1_macro`` e, se registrado,
        ``model_version``.
    """
    uri = _resolve_tracking_uri(tracking_uri)
    mlflow.set_tracking_uri(uri)

    if register is None:
        register = os.environ.get("MLFLOW_REGISTER", "0") == "1"

    # Garante o experimento (com artifact_location na criação, se fornecido)
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(
            experiment_name, artifact_location=artifact_location
        )
    else:
        experiment_id = experiment.experiment_id
    mlflow.set_experiment(experiment_id=experiment_id)

    # Dados
    df = load_toy_dataset()
    X_train, X_test, y_train, y_test = train_test_split_xy(
        df["text"].tolist(), df["label"].tolist(),
        test_size=test_size, random_state=random_state,
    )

    pipeline = build_pipeline(random_state=random_state)

    with mlflow.start_run() as run:
        # Params (logging manual — explícito e independente de autolog)
        mlflow.log_params(
            {
                "model_type": "tfidf+logreg",
                "ngram_range": "(1, 2)",
                "C": 4.0,
                "max_iter": 1000,
                "test_size": test_size,
                "random_state": random_state,
                "n_train": len(X_train),
                "n_test": len(X_test),
                "labels": ",".join(LABELS),
            }
        )

        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)
        metrics = compute_metrics(y_test, y_pred)
        mlflow.log_metrics(metrics)

        # Loga o modelo com nome lógico "model".
        #
        # MLflow 3.x: o modelo é um *logged model* de primeira classe (com
        # ``model_id`` próprio), não mais um artefato em ``runs:/<run>/model``.
        # O parâmetro ``artifact_path`` foi descontinuado em favor de ``name``.
        # O ``ModelInfo`` retornado traz ``model_id`` e ``model_uri``
        # (``models:/<model_id>``), que é a forma recomendada de referenciar o
        # modelo daqui em diante.
        registered_name = REGISTERED_MODEL_NAME if register else None
        model_info = mlflow.sklearn.log_model(
            sk_model=pipeline,
            name="model",
            registered_model_name=registered_name,
        )

        result: Dict[str, object] = {
            "run_id": run.info.run_id,
            "experiment_id": experiment_id,
            "model_id": model_info.model_id,
            "model_uri": model_info.model_uri,
            **metrics,
        }

    if register:
        # Descobre a última versão registrada deste run
        from mlflow.tracking import MlflowClient

        client = MlflowClient(tracking_uri=uri)
        versions = client.search_model_versions(
            f"name='{REGISTERED_MODEL_NAME}'"
        )
        if versions:
            latest = max(versions, key=lambda v: int(v.version))
            result["model_version"] = latest.version

    return result


def main() -> None:  # pragma: no cover - conveniência de CLI
    result = train()
    print("Run logado:")
    for k, v in result.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":  # pragma: no cover
    main()
