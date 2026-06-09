# Exemplo tradicional — classificação de notícias gov.br

Classificador de texto de notícias do gov.br por tema
(`saude`, `educacao`, `economia`, `seguranca`), com tracking no **MLflow**.

Há dois caminhos:

| Caminho | Arquivo | Status |
|---------|---------|--------|
| **sklearn** (TF-IDF + LogisticRegression) | `src/news_clf/` | runnable + testado (rápido, offline) |
| **BERT** (HuggingFace Transformers) | `train_bert.py` | opcional, **pesado** — documentado, não testado |

Os dados usados são *toy*/sintéticos (gerados em `data.py`) — nada é baixado.

## Estrutura

```
examples/traditional/
├── src/news_clf/
│   ├── data.py       # dataset toy + split estratificado/determinístico
│   ├── train.py      # treina sklearn, loga no MLflow, registra no Model Registry
│   └── evaluate.py   # accuracy / f1_macro
├── train_bert.py     # fine-tune BERT (opcional, pesado)
├── tests/            # TDD: data / evaluate / smoke de treino (tracking local)
├── requirements.txt          # mlflow, scikit-learn, pandas, numpy (pinned)
├── requirements-dev.txt      # -r requirements.txt + pytest
└── requirements-bert.txt     # transformers, torch (NÃO instalado nos testes)
```

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Rodar os testes

Rápidos e **offline** — usam tracking local em `sqlite` num diretório temporário
(`tmp_path`), sem tocar no GCP/IAP.

```bash
pytest -q
```

## Treinar (sklearn)

### Local, contra MLflow em sqlite

```bash
# Tracking local: cria mlflow.db e artefatos em ./mlruns
export MLFLOW_TRACKING_URI=sqlite:///mlflow.db
python -m news_clf.train

# Opcional: registrar no Model Registry
MLFLOW_REGISTER=1 python -m news_clf.train

# UI local para inspecionar runs:
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

### Contra o servidor DGB (atrás do IAP)

A lib `dgb_mlflow` configura o cliente (JWT do IAP via `signJwt` + ADC para o GCS).
**Instale-a** — ela traz o `google-cloud-storage`, necessário para o MLflow gravar os
artefatos (modelo) direto no GCS (sem ele, `log_model` falha com `No module named 'google.cloud'`):

```bash
# git-install (traz google-cloud-storage + google-auth)
pip install "git+https://github.com/destaquesgovbr/ml-platform.git@main#subdirectory=client"
# de dentro do repo, `pip install -e ../../client` também funciona para dev
gcloud auth application-default login            # credencial p/ artefatos no GCS (desktop)
export DGB_MLFLOW_TRACKING_URI="https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"

python - <<'PY'
import dgb_mlflow
dgb_mlflow.configure()          # aponta para o servidor + auth do IAP
from news_clf.train import train
print(train(register=True))     # registra a versão no Model Registry
PY
```

Em VM de desenvolvimento, o `dgb_mlflow.configure()` usa a SA da VM
(metadata server) — sem `gcloud auth application-default login`.

## Treinar (BERT — caminho pesado, opcional)

Baixa pesos pré-treinados (centenas de MB) e exige `torch`/`transformers`.
**Não** é exercitado pelos testes.

```bash
pip install -r requirements.txt -r requirements-bert.txt
export MLFLOW_TRACKING_URI=sqlite:///mlflow.db   # ou use dgb_mlflow.configure()
python train_bert.py --epochs 3
```

O script **pula graciosamente** (sai com código 0) se `transformers`/`torch`
não estiverem instalados, ou se a env `SKIP` estiver setada — útil em CI.

Modelo padrão: `neuralmind/bert-base-portuguese-cased` (BERTimbau).
