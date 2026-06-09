# Handoff — Slides "MLflow para a equipe" (para o Claude Design)

> **Propósito deste documento:** subsidiar o Claude Design com TODO o contexto factual para
> desenhar uma apresentação. Eu (Claude Code) defino **o conteúdo, os fatos e os objetivos**.
> **Você (Claude Design) é dono da narrativa, da estrutura dos slides, da contagem de slides e
> de todo o design visual.** Onde este doc disser "fato rígido", reproduza exatamente (URLs,
> comandos, nomes) — não invente. Onde disser "à sua escolha", decida livremente.

---

## 1. Objetivo da apresentação

Apresentar à equipe de **desenvolvedores / data scientists do DGB** a **plataforma de MLflow** que
acabamos de construir: o que é, por que existe, e **como começar a usar hoje**. É uma *tech talk*
interna (PT-BR), curta e prática. Não é marketing — é "olha o que temos, e é assim que você usa".

**Resultado esperado:** ao fim, cada dev/DS sabe (a) o que a plataforma oferece, (b) consegue
instalar o cliente e logar o primeiro experimento sozinho, e (c) sabe onde achar docs/exemplos.

**Público:** técnico (Python, gcloud, GCP básico). Pode-se assumir familiaridade com o projeto DGB.
Mix de pessoas na org (cpqd.com.br) e externas (@gmail) — isso importa para o slide de acesso à UI.

---

## 2. O que construímos (a substância — adapte/condense à vontade)

Uma **plataforma MLflow compartilhada**, self-service, rodando na infra GCP do DGB:

- **Servidor MLflow** (v3.13.0) em **Cloud Run**, protegido por **IAP** (sem auth nativa do MLflow;
  o IAP é a porta). Backend de metadados em **Cloud SQL Postgres** (IP privado, via VPC). Artefatos
  em **GCS** com acesso **direto** pelos clientes (o servidor não faz proxy de artefatos).
- **`dgb-mlflow`** — biblioteca cliente (pacote Python, instalável via git) que **esconde toda a
  complexidade do IAP**. O dev faz `import dgb_mlflow; dgb_mlflow.configure()` e usa o `mlflow`
  normal. Por baixo: assina um JWT do IAP (signJwt da service account) e injeta no header a cada
  request; artefatos vão direto ao GCS via ADC. **TDD, 32 testes.**
- **Projetos de exemplo** (rodam de verdade, testados E2E contra o servidor):
  - *tradicional*: classificação de notícias (sklearn) com tracking + **Model Registry** (registra,
    versiona, carrega de volta, prediz). Há também um caminho BERT opcional.
  - *GenAI*: **tracing** (`@mlflow.trace`), **avaliação** (`mlflow.models.evaluate`) e **prompt
    registry**; provider plugável (Anthropic/OpenAI).
- **Documentação** (7 tutoriais PT-BR) + um tutorial no site de docs do DGB.
- **CI/CD**: testes automatizados como gate, build/deploy da imagem, e build do pacote com release
  versionada (v0.1.0) — tudo verde.
- **Infra como código** (Terraform/GitOps), tudo revisado e aplicado via PR.

### Por que isso importa (o "so what" — use para o fechamento/abertura)
- Antes: cada um rodava experimentos local, sem rastro compartilhado, sem registro de modelos.
- Agora: **um lugar comum** para experimentos, métricas, artefatos e modelos versionados — com
  governança (IAP/IAM) e custo controlado (scale-to-zero). Começar custa **uma linha de install**.

### Decisões/gotchas que viraram features (bom material para "bastidores", opcional)
- IAP-on-Cloud-Run só aceita *service accounts* no acesso programático → resolvemos com **JWT
  auto-assinado** (a lib faz isso sozinha; o dev não vê).
- Conta **@gmail** (externa à org) é barrada no **login de browser** do IAP → criamos um **proxy
  local** (`scripts/iap_ui_proxy.py`) que dá a UI em `localhost`.
- Postgres começou público → migramos o MLflow para **IP privado** (piloto), e abrimos issue para o
  resto.
- MLflow 3.x bloqueia o header Host (`*.run.app`) → ajustado (`MLFLOW_SERVER_ALLOWED_HOSTS`).

---

## 3. Como se usa (o essencial — provavelmente vira 2-3 slides "mãos à obra")

**Instalar o cliente:**
```bash
pip install "git+https://github.com/destaquesgovbr/ml-platform.git@v0.1.0#subdirectory=client"
```

**Configurar (uma vez no shell):**
```bash
export DGB_MLFLOW_TRACKING_URI="https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"
gcloud auth application-default login     # só no PC; na dev VM não precisa
```

**Primeiro experimento:**
```python
import dgb_mlflow, mlflow
dgb_mlflow.configure()                    # resolve URL + auth do IAP; nada mais
mlflow.set_experiment("meu-experimento")
with mlflow.start_run():
    mlflow.log_param("lr", 0.01)
    mlflow.log_metric("acc", 0.97)
    mlflow.log_artifact("modelo.pkl")     # vai direto ao GCS
```

**Ver a UI no browser:** conta da org → abre a URL e loga. Conta **@gmail** → rodar
`python3 scripts/iap_ui_proxy.py` e abrir `http://localhost:5000`.

**PC vs Dev VM:** o código é idêntico; muda só a credencial (PC = `gcloud auth application-default
login`; VM = automático pela service account da VM).

---

## 4. Mensagens-chave / o que não pode faltar nos slides

(Ordem e formato à sua escolha; estes são os pontos que precisam aparecer.)

1. **O que é:** MLflow compartilhado do DGB (experimentos + modelos + GenAI), atrás de IAP.
2. **Diagrama de arquitetura:** os **dois caminhos** — (a) metadados: cliente → IAP → Cloud Run →
   Postgres; (b) artefatos: cliente → **direto** no GCS (ADC). Isto é o coração do desenho e merece
   um slide visual forte. (Há um mermaid pronto em `ml-platform/docs/README.md` e no tutorial do
   site — use como referência conceitual, redesenhe à vontade.)
3. **Começar é uma linha:** o install + `configure()`. Enfatizar que a auth do IAP é **transparente**.
4. **Recursos:** tracking, Model Registry, GenAI (tracing/evaluate/prompts).
5. **Acesso à UI + a pegadinha @gmail → proxy.** (Vários da equipe são @gmail; é prático mostrar.)
6. **Onde achar mais:** repo `ml-platform`, os exemplos, os docs, o tutorial no site.
7. **Call to action:** "instale, rode o exemplo, logue seu primeiro run hoje."

---

## 5. Fatos rígidos (reproduza exatamente — NÃO inventar)

| Item | Valor |
|------|-------|
| URL do servidor | `https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app` |
| Install do cliente | `pip install "git+https://github.com/destaquesgovbr/ml-platform.git@v0.1.0#subdirectory=client"` |
| Repo (público) | `github.com/destaquesgovbr/ml-platform` |
| Pacote / versão | `dgb-mlflow` v0.1.0 · MLflow **3.13.0** · Python 3.11+ |
| Env var | `DGB_MLFLOW_TRACKING_URI` |
| API da lib | `dgb_mlflow.configure()` (e `get_iap_jwt`) |
| Proxy de UI | `python3 scripts/iap_ui_proxy.py` → `http://localhost:5000` |
| Bucket de artefatos | `gs://inspire-7-finep-mlflow-artifacts` |
| Infra | Cloud Run + IAP · Cloud SQL Postgres (privado) · GCS · projeto `inspire-7-finep` · região `southamerica-east1` |
| Pré-requisito de acesso | estar na lista `mlflow_users` (acesso via IAP/IAM) |

**Não** mencione um "IAP client id" como necessário — não é (a antiga `DGB_MLFLOW_IAP_CLIENT_ID` foi
descontinuada; a lib usa JWT auto-assinado com a URL como audience).

---

## 6. O que está DEFINIDO vs o que VOCÊ decide

**Definido por mim (não precisa mudar):** objetivo, público, os fatos da seção 5, as mensagens-chave
da seção 4, o conteúdo técnico (seções 2-3), tom (técnico, prático, interno, PT-BR).

**Você decide (Claude Design):** narrativa e arco da apresentação; número e ordem dos slides;
quanto texto por slide vs notas do apresentador; estilo visual, paleta, tipografia, ícones; como
representar o diagrama de arquitetura; se inclui seção de "bastidores/decisões" (seção 2 final);
abertura e fechamento; eventuais analogias/ganchos. Sugira o que achar melhor — você é o designer.

---

## 7. Material-fonte no repo (o `ml-platform` será compartilhado com você)

Para cavar detalhes/exatidão, leia:
- `README.md` (raiz) — visão geral e estrutura.
- `docs/README.md` — **diagrama mermaid** da arquitetura + os 2 caminhos (boa base visual).
- `docs/01-getting-started-pc.md`, `02-getting-started-vm.md` — fluxo de uso PC/VM.
- `docs/03-como-funciona-iap.md` — auth (signed JWT) explicada.
- `docs/04-model-registry.md`, `docs/05-genai.md` — features.
- `docs/06-troubleshooting.md` — a pegadinha @gmail + proxy.
- `client/README.md` e `client/src/dgb_mlflow/` — a lib.
- `examples/traditional/` e `examples/genai/` — exemplos reais (bons para um slide "exemplos prontos").
- `scripts/iap_ui_proxy.py` — o proxy de UI.
- `_plan/mlflow-platform-plan.md` — o plano/arquitetura completo (contexto profundo).

---

## 8. Tom & identidade visual (sugestões, não regras)

- Projeto governamental brasileiro (gov.br / DGB). O site de docs usa **Material com accent verde** e
  o logo do DGB — pode servir de fio condutor de identidade, mas **a estética é sua**.
- Tom dos slides: direto, técnico, "feito pela equipe, para a equipe". Evite jargão de marketing.
- Idioma: **PT-BR**.

---

## 9. Sobre compartilhar o repo `docs` também (recomendação)

- **Essencial:** compartilhar o repo **`ml-platform`** — tem tudo (lib, docs, exemplos, proxy, plano).
  Só com ele você desenha a apresentação inteira.
- **Opcional e útil:** compartilhar o repo **`docs`** (site do DGB) **se** você quiser posicionar o
  MLflow dentro da **arquitetura maior do DGB** (onde ele se encaixa entre scraper, portal, GraphQL,
  etc.) — bom para um slide de contexto/abertura. O tutorial novo está em `docs/docs/modulos/mlflow.md`
  e a visão geral da plataforma em `docs/docs/arquitetura/visao-geral.md`. Se a apresentação for focada
  só no "como usar o MLflow", `ml-platform` basta.
