"""Testes determinísticos das métricas de avaliação."""
import math

from news_clf.evaluate import compute_metrics


def test_perfect_predictions():
    y_true = ["saude", "economia", "saude", "educacao"]
    y_pred = ["saude", "economia", "saude", "educacao"]
    m = compute_metrics(y_true, y_pred)
    assert m["accuracy"] == 1.0
    assert m["f1_macro"] == 1.0


def test_all_wrong_predictions():
    y_true = ["saude", "economia", "saude", "economia"]
    y_pred = ["economia", "saude", "economia", "saude"]
    m = compute_metrics(y_true, y_pred)
    assert m["accuracy"] == 0.0


def test_half_correct_accuracy():
    y_true = ["a", "a", "b", "b"]
    y_pred = ["a", "b", "b", "a"]
    m = compute_metrics(y_true, y_pred)
    assert math.isclose(m["accuracy"], 0.5, rel_tol=1e-9)


def test_metrics_keys_and_ranges():
    y_true = ["a", "b", "a", "b", "a"]
    y_pred = ["a", "b", "b", "b", "a"]
    m = compute_metrics(y_true, y_pred)
    assert set(m.keys()) >= {"accuracy", "f1_macro"}
    for v in m.values():
        assert 0.0 <= v <= 1.0


def test_f1_macro_known_value():
    # 2 classes, matriz de confusão conhecida.
    # Classe "a": tp=2, fp=0, fn=1 -> precision=1, recall=2/3 -> f1=0.8
    # Classe "b": tp=2, fp=1, fn=0 -> precision=2/3, recall=1 -> f1=0.8
    # macro = 0.8
    y_true = ["a", "a", "a", "b", "b"]
    y_pred = ["a", "a", "b", "b", "b"]
    m = compute_metrics(y_true, y_pred)
    assert math.isclose(m["f1_macro"], 0.8, rel_tol=1e-9)
