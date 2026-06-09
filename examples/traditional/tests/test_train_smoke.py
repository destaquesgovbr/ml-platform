"""Smoke test: treina o sklearn em dados toy e confere o run no tracking LOCAL.

Tudo offline: tracking em sqlite dentro de tmp_path, artefatos em ./mlruns local.
Nenhum acesso ao GCP/IAP.
"""
import mlflow
from mlflow.tracking import MlflowClient

from news_clf.train import train


def test_train_logs_run_with_params_metrics_and_model(tmp_path):
    tracking_uri = f"sqlite:///{tmp_path}/m.db"
    artifact_root = (tmp_path / "mlruns").as_uri()

    result = train(
        tracking_uri=tracking_uri,
        experiment_name="test-news-clf",
        artifact_location=artifact_root,
        random_state=42,
        register=False,
    )

    # O treino devolve identificadores e métricas
    assert "run_id" in result
    assert result["accuracy"] >= 0.0
    assert result["f1_macro"] >= 0.0

    # Consulta o tracking local para validar o que foi logado
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)
    run = client.get_run(result["run_id"])

    # Params esperados
    params = run.data.params
    assert "model_type" in params
    assert params["model_type"] == "tfidf+logreg"
    assert "random_state" in params

    # Metrics esperadas
    metrics = run.data.metrics
    assert "accuracy" in metrics
    assert "f1_macro" in metrics
    assert 0.0 <= metrics["accuracy"] <= 1.0

    # Artefato do modelo foi logado em "model/"
    artifacts = [a.path for a in client.list_artifacts(run.info.run_id)]
    assert "model" in artifacts

    # O modelo é recarregável e prediz
    model_uri = f"runs:/{result['run_id']}/model"
    loaded = mlflow.sklearn.load_model(model_uri)
    preds = loaded.predict(["o ministério anunciou novas medidas econômicas"])
    assert len(preds) == 1


def test_train_smoke_accuracy_reasonable_on_toy(tmp_path):
    """Em dados toy separáveis, o modelo deve acertar bem acima do acaso."""
    tracking_uri = f"sqlite:///{tmp_path}/m.db"
    result = train(
        tracking_uri=tracking_uri,
        experiment_name="test-acc",
        artifact_location=(tmp_path / "mlruns").as_uri(),
        random_state=0,
        register=False,
    )
    # 4 classes -> acaso ~0.25; dados toy são separáveis
    assert result["accuracy"] >= 0.5
