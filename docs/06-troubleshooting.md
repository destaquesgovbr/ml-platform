# 06 — Troubleshooting

Erros comuns ao usar o MLflow DGB e como resolvê-los. Lembre o princípio central: há **dois
caminhos independentes** — **metadados** (servidor MLflow atrás do IAP) e **artefatos** (GCS
direto). Identificar qual falhou resolve a maioria dos casos. Veja
[Como funciona o IAP](03-como-funciona-iap.md#403-do-iap--401403-do-gcs--como-distinguir).

## Índice rápido

- [403 do IAP](#403-do-iap)
- [Credenciais do GCS ausentes ou insuficientes](#credenciais-do-gcs-ausentes-ou-insuficientes)
- [Token expirado](#token-expirado)
- [Impersonation falha (serviceAccountTokenCreator)](#impersonation-falha-serviceaccounttokencreator)
- [O artefato não sobe](#o-artefato-não-sobe)
- [UI dá 403 no browser](#ui-dá-403-no-browser)
- [`configure()` cai para local sem querer](#configure-cai-para-local-sem-querer)
- [Dev local com sqlite](#dev-local-com-sqlite)

---

## 403 do IAP

**Sintoma:** chamadas de **metadados** (criar experimento, `log_param`, `log_metric`, registry)
falham com HTTP 403 (às vezes uma página HTML do Google "You don't have access").

**Causas e correções:**

1. **Sua conta não está em `mlflow_users`.** Peça ao administrador da infra para incluir seu email.
2. **Token com a audience errada.** O ID token precisa ter `aud = <IAP_CLIENT_ID>`. Confira se o
   `DGB_MLFLOW_IAP_CLIENT_ID` está correto. Decodifique o token para conferir:
   ```bash
   echo "$MLFLOW_TRACKING_TOKEN" | cut -d. -f2 | tr '_-' '/+' | base64 -d 2>/dev/null | python -m json.tool
   # confira "aud" e "email"
   ```
3. **No PC: sem permissão de impersonation** — veja
   [impersonation falha](#impersonation-falha-serviceaccounttokencreator).
4. **Token expirado** se você fixou `MLFLOW_TRACKING_TOKEN` manualmente — veja
   [token expirado](#token-expirado).

**Teste isolado** (confirma se o IAP deixa passar, sem o resto do MLflow):

```bash
# PC:
TOKEN="$(gcloud auth print-identity-token \
  --impersonate-service-account=destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com \
  --audiences=<IAP_CLIENT_ID>)"
# VM:  TOKEN="$(gcloud auth print-identity-token --audiences=<IAP_CLIENT_ID>)"

curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer ${TOKEN}" "<MLFLOW_URL>/health"
# 200 = IAP OK;  403 = problema de acesso/audience
```

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

**Sintoma:** funciona por ~1 hora e depois começa a dar 403 nos metadados.

**Causa:** você fixou um token estático via `MLFLOW_TRACKING_TOKEN`. ID tokens expiram em ~1h.

**Correção:** **não** fixe o token manualmente. Use `dgb_mlflow.configure()`, que registra um
provider que **regenera** o token a cada request. Se precisar do override só para debug pontual,
relembre que ele expira:

```bash
unset MLFLOW_TRACKING_TOKEN     # deixa o dgb-mlflow gerenciar o token (recomendado)
```

## Impersonation falha (serviceAccountTokenCreator)

**Sintoma (PC):** ao chamar `configure()` ou gerar token manual, erro do IAM como
`Permission 'iam.serviceAccounts.getOpenIdToken' denied on resource ...destaquesgovbr-mlflow-client...`
ou `PermissionDenied: 403`.

**Causa:** sua conta de usuário não tem `roles/iam.serviceAccountTokenCreator` na service account
de cliente `destaquesgovbr-mlflow-client`, então não pode impersoná-la para gerar o ID token.

**Correção:** peça ao administrador da infra para conceder
`roles/iam.serviceAccountTokenCreator` à sua conta na SA `destaquesgovbr-mlflow-client` (isso
normalmente vem junto com a inclusão em `mlflow_users`). Confirme:

```bash
gcloud auth print-identity-token \
  --impersonate-service-account=destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com \
  --audiences=<IAP_CLIENT_ID> >/dev/null && echo "impersonation OK"
```

> Na **VM** isso não se aplica — a VM usa o metadata server e não impersona ninguém.

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

## UI dá 403 no browser

**Sintoma:** ao abrir `<MLFLOW_URL>` no navegador, aparece a tela do Google negando acesso.

**Correção:** faça login com a conta que está em `mlflow_users` (papel
`roles/iap.httpsResourceAccessor` no recurso do IAP). Se você tem várias contas Google logadas,
o navegador pode estar usando a errada — abra numa janela anônima e logue com a conta certa.

## `configure()` cai para local sem querer

**Sintoma:** você esperava falar com o servidor remoto, mas `mlflow.get_tracking_uri()` mostra um
`sqlite:///...` ou `file:./mlruns` local.

**Causa:** o `dgb_mlflow.configure()` detecta a **ausência** de `DGB_MLFLOW_IAP_CLIENT_ID` (ou de
`DGB_MLFLOW_TRACKING_URI`) e cai para tracking local, para facilitar dev offline.

**Correção:** exporte as duas variáveis antes de configurar:

```bash
export DGB_MLFLOW_TRACKING_URI="<MLFLOW_URL>"
export DGB_MLFLOW_IAP_CLIENT_ID="<IAP_CLIENT_ID>"
python -c "import dgb_mlflow, mlflow; dgb_mlflow.configure(); print(mlflow.get_tracking_uri())"
# deve imprimir o <MLFLOW_URL>
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
