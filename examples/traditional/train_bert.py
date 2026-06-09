"""Caminho PESADO (opcional): fine-tune de BERT para a mesma tarefa.

Este script faz fine-tune de um modelo BERT (HuggingFace Transformers) para
classificar notícias gov.br nos mesmos temas do exemplo sklearn, usando o
``mlflow.transformers.autolog()`` para registrar params/métricas no MLflow.

⚠️ É o caminho "pesado": baixa pesos pré-treinados (centenas de MB) e exige
``torch``/``transformers``. Por isso:
  - NÃO é exercitado pelos testes (``tests/`` cobre apenas o sklearn).
  - As dependências ficam em ``requirements-bert.txt`` (separadas) e NÃO são
    instaladas no CI.
  - O script "pula" graciosamente (exit 0) se ``transformers``/``torch`` não
    estiverem disponíveis, ou se a env ``SKIP`` estiver setada.

Para rodar:
    pip install -r requirements.txt -r requirements-bert.txt
    # local (sqlite):
    python train_bert.py
    # contra o servidor DGB (atrás do IAP):
    python -c "import dgb_mlflow; dgb_mlflow.configure()" && python train_bert.py

Modelo padrão: ``neuralmind/bert-base-portuguese-cased`` (BERTimbau), adequado
ao português das notícias gov.br. Troque por ``--model`` se quiser algo menor.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys

# Reaproveita os dados toy do pacote sklearn (mesma tarefa/labels).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def _deps_available() -> bool:
    """True se transformers + torch + datasets estiverem instalados."""
    for mod in ("transformers", "torch", "datasets"):
        if importlib.util.find_spec(mod) is None:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune BERT (opcional/pesado).")
    parser.add_argument(
        "--model",
        default="neuralmind/bert-base-portuguese-cased",
        help="checkpoint HuggingFace base.",
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--experiment", default="news-clf-bert")
    args = parser.parse_args()

    # Guardas: pula sem falhar se não der para rodar o caminho pesado.
    if os.environ.get("SKIP"):
        print("SKIP setado — pulando fine-tune de BERT.")
        return 0
    if not _deps_available():
        print(
            "transformers/torch/datasets ausentes — pulando fine-tune de BERT.\n"
            "Instale com: pip install -r requirements.txt -r requirements-bert.txt"
        )
        return 0

    # Imports pesados só aqui dentro (depois das guardas).
    import mlflow
    import numpy as np
    from datasets import Dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    from news_clf.data import LABELS, load_toy_dataset, train_test_split_xy
    from news_clf.evaluate import compute_metrics

    label2id = {label: i for i, label in enumerate(LABELS)}
    id2label = {i: label for label, i in label2id.items()}

    df = load_toy_dataset()
    X_train, X_test, y_train, y_test = train_test_split_xy(
        df["text"].tolist(), df["label"].tolist(), test_size=0.25, random_state=42
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model)

    def to_dataset(texts, labels):
        enc = tokenizer(texts, truncation=True, padding=True, max_length=128)
        enc["labels"] = [label2id[l] for l in labels]
        return Dataset.from_dict(enc)

    train_ds = to_dataset(X_train, y_train)
    eval_ds = to_dataset(X_test, y_test)

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model, num_labels=len(LABELS), id2label=id2label, label2id=label2id
    )

    def hf_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        y_true = [id2label[int(i)] for i in labels]
        y_pred = [id2label[int(i)] for i in preds]
        return compute_metrics(y_true, y_pred)

    training_args = TrainingArguments(
        output_dir="./bert-out",
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        eval_strategy="epoch",
        logging_steps=5,
        report_to=["mlflow"],
    )

    # Autolog do MLflow para transformers (params, métricas, modelo).
    mlflow.transformers.autolog()
    mlflow.set_tracking_uri(
        os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    )
    mlflow.set_experiment(args.experiment)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        compute_metrics=hf_metrics,
    )
    with mlflow.start_run():
        trainer.train()
        eval_result = trainer.evaluate()
        print("Avaliação final:", eval_result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
