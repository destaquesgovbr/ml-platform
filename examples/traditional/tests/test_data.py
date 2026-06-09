"""Testes do preparo de dados toy (offline, rápidos)."""
import numpy as np

from news_clf.data import LABELS, load_toy_dataset, train_test_split_xy


def test_load_toy_dataset_shape_and_columns():
    df = load_toy_dataset()
    # Colunas esperadas
    assert set(df.columns) == {"text", "label"}
    # Há linhas suficientes para um split estratificado
    assert len(df) >= 40
    # Sem textos vazios
    assert (df["text"].str.len() > 0).all()


def test_labels_are_known_and_balanced():
    df = load_toy_dataset()
    rotulos = set(df["label"].unique())
    # Todos os rótulos pertencem ao vocabulário de classes definido
    assert rotulos <= set(LABELS)
    # Toy dataset usa todas as classes
    assert rotulos == set(LABELS)
    # Classes balanceadas (mesmo número de exemplos por classe)
    contagens = df["label"].value_counts().to_dict()
    assert len(set(contagens.values())) == 1, contagens


def test_train_test_split_is_deterministic_and_stratified():
    df = load_toy_dataset()
    X = df["text"].tolist()
    y = df["label"].tolist()

    X_train, X_test, y_train, y_test = train_test_split_xy(
        X, y, test_size=0.25, random_state=42
    )

    # Tamanhos coerentes e sem perda de exemplos
    assert len(X_train) + len(X_test) == len(df)
    assert len(X_train) == len(y_train)
    assert len(X_test) == len(y_test)
    # ~25% no teste
    assert abs(len(X_test) / len(df) - 0.25) < 0.05

    # Estratificado: todas as classes aparecem no treino e no teste
    assert set(y_train) == set(LABELS)
    assert set(y_test) == set(LABELS)

    # Determinístico: mesma seed -> mesmo split
    X_train2, X_test2, y_train2, y_test2 = train_test_split_xy(
        X, y, test_size=0.25, random_state=42
    )
    assert X_train == X_train2
    assert X_test == X_test2
    assert y_train == y_train2
    assert y_test == y_test2


def test_split_respects_random_state_difference():
    df = load_toy_dataset()
    X = df["text"].tolist()
    y = df["label"].tolist()
    _, X_test_a, _, _ = train_test_split_xy(X, y, test_size=0.25, random_state=1)
    _, X_test_b, _, _ = train_test_split_xy(X, y, test_size=0.25, random_state=2)
    # Seeds diferentes geram (com alta probabilidade) partições diferentes
    assert X_test_a != X_test_b
    # Mas o conjunto total continua íntegro
    assert len(X_test_a) == len(X_test_b)
    assert set(np.unique(y)) == set(LABELS)
