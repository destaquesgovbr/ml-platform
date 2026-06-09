"""Geração e preparo de dados *toy* para classificação de notícias gov.br.

Os textos são sintéticos e curtos, montados a partir de gabaritos por tema,
o suficiente para um pipeline TF-IDF + LogisticRegression aprender padrões
óbvios. Nada é baixado da internet — ideal para testes rápidos e offline.
"""
from __future__ import annotations

import itertools
from typing import List, Tuple

import pandas as pd
from sklearn.model_selection import train_test_split

# Vocabulário de classes (temas de notícias do gov.br)
LABELS: List[str] = ["saude", "educacao", "economia", "seguranca"]

# Quantos exemplos gerar por classe (mantém o dataset balanceado).
_PER_CLASS = 30

# Para o pipeline TF-IDF aprender padrões generalizáveis, os exemplos são
# gerados combinatoriamente a partir de fragmentos com FORTE sobreposição
# lexical dentro de cada classe (verbos + assunto + complemento por tema).
# Assim treino e teste compartilham vocabulário discriminativo por classe.
_SUBJECTS = [
    "Ministério",
    "Governo federal",
    "Programa nacional",
    "Secretaria",
    "Órgão público",
]

_VERBS = ["anuncia", "amplia", "reforça", "investe em", "lança"]

# Complementos carregados de termos típicos de cada tema (sinal forte).
_TOPICS = {
    "saude": [
        "vacinação e atendimento no SUS",
        "hospitais e leitos de UTI",
        "campanha de saúde contra a dengue",
        "medicamentos e exames médicos",
        "vacinas e prevenção de doenças",
        "atendimento clínico e enfermagem",
    ],
    "educacao": [
        "vagas em universidades e escolas",
        "bolsas para estudantes do ensino superior",
        "professores e formação pedagógica",
        "merenda escolar e creches",
        "matrículas no ensino técnico",
        "pesquisa científica e pós-graduação",
    ],
    "economia": [
        "crescimento do PIB e da economia",
        "taxa de juros e controle da inflação",
        "crédito para empresas e indústria",
        "exportações e balança comercial",
        "imposto de renda e reforma tributária",
        "empregos e investimento financeiro",
    ],
    "seguranca": [
        "operação policial contra o crime",
        "policiamento e segurança pública",
        "apreensão de armas e drogas",
        "combate ao tráfico nas fronteiras",
        "fiscalização nas estradas federais",
        "investigação de fraude e prisões",
    ],
}


def load_toy_dataset() -> pd.DataFrame:
    """Devolve um DataFrame *toy* balanceado com colunas ``text`` e ``label``.

    As frases são geradas combinando ``sujeito + verbo + tópico`` por tema, de
    forma determinística. Cada classe contribui com o mesmo número de exemplos
    (``_PER_CLASS``), garantindo balanceamento e sinal lexical separável.
    """
    rows = []
    for label, topics in _TOPICS.items():
        combos = itertools.product(_SUBJECTS, _VERBS, topics)
        gerados = 0
        for subject, verb, topic in combos:
            if gerados >= _PER_CLASS:
                break
            rows.append(
                {"text": f"{subject} {verb} {topic}", "label": label}
            )
            gerados += 1
    df = pd.DataFrame(rows, columns=["text", "label"])
    # Ordem estável e reprodutível
    return df.reset_index(drop=True)


def train_test_split_xy(
    X: List[str],
    y: List[str],
    test_size: float = 0.25,
    random_state: int = 42,
) -> Tuple[List[str], List[str], List[str], List[str]]:
    """Split estratificado e determinístico (wrapper fino do scikit-learn).

    Retorna ``(X_train, X_test, y_train, y_test)`` como listas.
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=y,
        shuffle=True,
    )
    return list(X_train), list(X_test), list(y_train), list(y_test)
