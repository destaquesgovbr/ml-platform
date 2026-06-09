# 06 — Troubleshooting

Erros comuns ao usar o MLflow DGB e como resolvê-los. Lembre o princípio central: há **dois
caminhos independentes** — **metadados** (servidor MLflow atrás do IAP) e **artefatos** (GCS
direto). Identificar qual falhou resolve a maioria dos casos. Veja
[Como funciona o IAP](03-como-funciona-iap.md#403-do-iap--401403-do-gcs--como-distinguir).

## Índice rápido

- [401/403 do IAP](#401403-do-iap)
- [Credenciais do GCS ausentes ou insuficientes](#credenciais-do-gcs-ausentes-ou-insuficientes)
- [Token expirado](#token-expirado)
- [`signJwt` falha (serviceAccountTokenCreator)](#signjwt-falha-serviceaccounttokencreator)
- [O artefato não sobe](#o-artefato-não-sobe)
- [UI dá "You don't have access" no browser (conta externa @gmail → proxy)](#ui-dá-you-dont-have-access-no-browser)
- [`configure()` cai para local sem querer](#configure-cai-para-local-sem-querer)
- [Dev local com sqlite](#dev-local-com-sqlite)

---

## 401/403 do IAP

**Sintoma:** chamadas de **metadados** (criar experimento, `log_param`, `log_metric`, registry)
falham com HTTP **401** (`Invalid JWT audience`) ou **403** (às vezes uma página HTML do Google
"You don't have access").

Lembre o fluxo correto (validado em produção): o acesso programático usa um **JWT auto-assinado**
pela SA cliente `destaquesgovbr-mlflow-client` via `signJwt`, com **`aud = <URL do serviço>/*`**.
**Não** existe ID token OIDC com `aud = <IAP client id>` — esse caminho é bloqueado (era o que a
descontinuada `DGB_MLFLOW_IAP_CLIENT_ID` tentava fazer). Diagnostique pelo código HTTP:

**401 `Invalid JWT audience` → audience errada.** A `aud` do JWT **tem que ser** a URL do serviço
com o sufixo `/*` (ex.: `https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app/*`). A URL pura
(sem `/*`) ou um `aud = client id` dão 401. Decodifique o token para conferir:
```bash
echo "$JWT" | cut -d. -f2 | tr '_-' '/+' | base64 -d 2>/dev/null | python -m json.tool
# "aud" deve ser "<URL do serviço>/*"
```
O `dgb_mlflow.configure()` já calcula a audience certa — se você está vendo 401, provavelmente
fixou um `MLFLOW_TRACKING_TOKEN` manual com a audience errada (`unset` e deixe a lib gerenciar).

**403 → falta de acesso.** Duas causas:
1. **Sua conta (ou a SA da VM) não tem `roles/iap.httpsResourceAccessor`** no recurso IAP, i.e.,
   não está em `mlflow_users`. Peça ao administrador da infra para incluir seu email.
2. **Falta `roles/iam.serviceAccountTokenCreator` na client SA** → o `signJwt` falha antes mesmo
   de chamar o IAP. Veja [`signJwt` falha](#signjwt-falha-serviceaccounttokencreator).

**Teste isolado** (confirma se o IAP deixa passar, sem o resto do MLflow) — assina um JWT com a
audience `<URL>/*` e bate no `/health`:

```bash
SA=destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com
U=https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app
NOW=$(date +%s)
printf '{"iss":"%s","sub":"%s","email":"%s","aud":"%s/*","iat":%s,"exp":%s}' \
  "$SA" "$SA" "$SA" "$U" "$NOW" $((NOW+3600)) > /tmp/c.json
JWT=$(gcloud iam service-accounts sign-jwt /tmp/c.json /dev/stdout --iam-account="$SA")

curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer ${JWT}" "$U/health"
# 200 = IAP OK;  401 = audience errada;  403 = sem acesso (mlflow_users / tokenCreator)
```

Funciona tanto no PC (seu usuário com `tokenCreator` na SA) quanto na VM (a SA da VM com
`tokenCreator` na SA cliente).

## Credenciais do GCS ausentes ou insuficientes

**Sintoma:** os metadados gravam normalmente, mas ao **subir/baixar artefato** aparece um erro do
GCS: `google.auth.exceptions.DefaultCredentialsError`, `403 Forbidden`, `Anonymous caller`, ou
`does not have storage.objects.create access`.

**Causas e correções:**

1. **ADC ausente (PC).** Você esqueceu o login do Application Default Credentials:
   ```bash
   gcloud auth application-default login
   gcloud auth application-default set-quota-project inspire-7-finep
   ```
2. **Sem acesso ao bucket.** Sua conta (PC) ou a SA da VM precisa de `roles/storage.objectUser` no
   bucket `gs://inspire-7-finep-mlflow-artifacts`. Confirme com:
   ```bash
   gcloud storage ls gs://inspire-7-finep-mlflow-artifacts/ --project=inspire-7-finep
   # se der AccessDenied, peça o papel storage.objectUser ao administrador
   ```
3. **Projeto de quota errado.** Em alguns ambientes o ADC reclama de billing/quota — rode o
   `set-quota-project` acima.

> Esse caminho é **client-side**: o servidor MLflow não está envolvido. Por isso um `curl` ao
> `/health` passar (200) **não** garante que os artefatos vão subir — são portas diferentes.

## Token expirado

**Sintoma:** funciona por ~1 hora e depois começa a dar 401/403 nos metadados.

**Causa:** você fixou um token estático via `MLFLOW_TRACKING_TOKEN`. O JWT expira em ~1h.

**Correção:** **não** fixe o token manualmente. Use `dgb_mlflow.configure()`, que registra um
provider que **regenera** o token (assina um JWT fresco) a cada request. Se precisar do override
só para debug pontual, relembre que ele expira:

```bash
unset MLFLOW_TRACKING_TOKEN     # deixa o dgb-mlflow gerenciar o token (recomendado)
```

## `signJwt` falha (serviceAccountTokenCreator)

**Sintoma:** ao chamar `configure()` ou gerar o token manual, erro do IAM como
`Permission 'iam.serviceAccounts.signJwt' denied on resource ...destaquesgovbr-mlflow-client...`
ou `PermissionDenied: 403`. A própria `dgb-mlflow` reembrulha isso num `RuntimeError` pedindo
`roles/iam.serviceAccountTokenCreator` + ADC.

**Causa:** a identidade que chama `signJwt` (sua conta de usuário no PC, ou a SA da VM) não tem
`roles/iam.serviceAccountTokenCreator` na service account cliente `destaquesgovbr-mlflow-client`,
então não pode assinar o JWT em nome dela.

**Correção:** peça ao administrador da infra para conceder
`roles/iam.serviceAccountTokenCreator` à sua conta (PC) ou à SA da VM, na SA
`destaquesgovbr-mlflow-client` (isso normalmente vem junto com a inclusão em `mlflow_users`).
No PC, confirme também que o ADC está autenticado (`gcloud auth application-default login`).
Confirme assinando um JWT de teste:

```bash
SA=destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com
U=https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app
NOW=$(date +%s)
printf '{"iss":"%s","sub":"%s","email":"%s","aud":"%s/*","iat":%s,"exp":%s}' \
  "$SA" "$SA" "$SA" "$U" "$NOW" $((NOW+3600)) > /tmp/c.json
gcloud iam service-accounts sign-jwt /tmp/c.json /dev/stdout --iam-account="$SA" >/dev/null \
  && echo "signJwt OK"
```

> O mesmo fluxo vale para o PC e a VM. A diferença é só quem é a identidade chamadora (seu usuário
> vs a SA da VM); ambos precisam de `tokenCreator` na SA cliente.

## O artefato não sobe

**Sintoma:** o run aparece na UI, params e métricas estão lá, mas o **artefato não**.

**Diagnóstico em ordem:**

1. Confirme que é erro de **GCS** (e não de IAP) — veja
   [credenciais do GCS](#credenciais-do-gcs-ausentes-ou-insuficientes).
2. Confirme que o ADC resolve e tem acesso ao bucket:
   ```bash
   gcloud auth application-default print-access-token >/dev/null && echo "ADC OK"
   gcloud storage ls gs://inspire-7-finep-mlflow-artifacts/ --project=inspire-7-finep
   ```
3. Lembre que o servidor roda **sem `--serve-artifacts`**: o upload é **direto** do seu cliente
   para o GCS. Se a sua rede bloqueia `storage.googleapis.com`, o upload falha mesmo com IAP OK.

## UI dá "You don't have access" no browser

**Sintoma:** ao abrir `https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app` no navegador, o IAP
mostra **"You don't have access"** com o seu email.

**Caso 1 — múltiplas contas Google:** se você tem várias contas logadas, o navegador pode estar
usando a errada. Abra numa **janela anônima** e logue com a conta que está em `mlflow_users`.

**Caso 2 — conta externa à organização (ex.: `@gmail`):** o IAP-on-Cloud-Run (OAuth client
gerenciado pelo Google, projeto na org cpqd.com.br) **aceita service accounts mas barra
identidades externas no login de browser** — mesmo com o binding IAM correto e mesmo em janela
anônima. Não é falta de permissão (o acesso *programático* pelo `dgb-mlflow` funciona, pois usa a SA).

Solução: **proxy local que injeta o token da SA** (a SA é aceita pelo IAP). Você abre a UI em
`localhost`:

```bash
cd ml-platform
gcloud auth login            # sua conta (precisa de tokenCreator na client SA — já provisionado)
python3 scripts/iap_ui_proxy.py
# abre http://localhost:5000 no browser → UI do MLflow completa
```

O proxy ([`scripts/iap_ui_proxy.py`](../scripts/iap_ui_proxy.py)) é local e por-usuário; escuta só
em `127.0.0.1` (não expõe nada). Variáveis opcionais: `DGB_MLFLOW_TRACKING_URI`, `IAP_PROXY_PORT`.

> Alternativa definitiva (precisa de Console): em **APIs & Services → OAuth consent screen**,
> publicar o app (*In Production*) ou adicionar os emails externos como *test users* — se resolver,
> o login de browser passa a funcionar direto, sem proxy.

## `configure()` cai para local sem querer

**Sintoma:** você esperava falar com o servidor remoto, mas `mlflow.get_tracking_uri()` mostra um
`sqlite:///...` ou `file:./mlruns` local.

**Causa:** o `dgb_mlflow.configure()` ativa o modo remoto-IAP só quando `DGB_MLFLOW_TRACKING_URI`
aponta para `http(s)://`. Sem essa variável, ele cai para tracking local (`sqlite:///mlflow.db`),
para facilitar dev offline.

**Correção:** exporte a variável antes de configurar:

```bash
export DGB_MLFLOW_TRACKING_URI="https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app"
python -c "import dgb_mlflow, mlflow; dgb_mlflow.configure(); print(mlflow.get_tracking_uri())"
# deve imprimir o https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app
```

## Dev local com sqlite

Para desenvolver/rodar testes **offline**, sem tocar no GCP, suba um MLflow local:

```bash
# opção A: servidor local com UI
mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns
# UI em http://127.0.0.1:5000

# opção B: direto no código/teste, sem servidor
python - <<'PY'
import mlflow
mlflow.set_tracking_uri("sqlite:///mlflow.db")
mlflow.set_experiment("dev-local")
with mlflow.start_run():
    mlflow.log_param("x", 1)
    mlflow.log_metric("y", 2.0)
print("ok — tudo local, sem IAP nem GCS")
PY
```

Nesse modo **não há IAP nem GCS**: os artefatos vão para `./mlruns` no disco. Os testes de TDD da
`dgb-mlflow` e dos exemplos usam exatamente isso (tracking local em `tmp_path`), então rodam sem
credenciais. Veja [`../client/`](../client/) e [`../examples/`](../examples/).

---

Se nada acima resolver, colete: (1) a saída de `mlflow.get_tracking_uri()`, (2) o `%{http_code}` do
teste de `/health` com token, (3) a mensagem exata do erro (IAP vs GCS), e leve ao canal da equipe
de Data Science.
