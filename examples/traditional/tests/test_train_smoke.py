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
    # MLflow 3.x: o modelo logado é de primeira classe (tem model_id/model_uri).
    assert "model_id" in result
    assert "model_uri" in result
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

    # MLflow 3.x: o modelo é um "logged model" de primeira classe (não mais um
    # artefato em runs:/<run>/model). Deve aparecer com nome lógico "model".
    logged_models = mlflow.search_logged_models(
        experiment_ids=[run.info.experiment_id], output_format="list"
    )
    names = {lm.name for lm in logged_models}
    assert "model" in names

    # O modelo é recarregável (pelo model_uri devolvido) e prediz
    loaded = mlflow.sklearn.load_model(result["model_uri"])
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
