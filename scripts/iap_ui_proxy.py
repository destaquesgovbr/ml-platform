#!/usr/bin/env python3
"""Proxy local para acessar a UI do MLflow (atrás do IAP) no browser.

Por que existe: o IAP-on-Cloud-Run aceita **service accounts** (via JWT assinado),
mas barra usuários externos (@gmail) no login de browser. Este proxy roda na sua
máquina, assina o JWT do IAP impersonando a client SA (a mesma identidade que o
`dgb-mlflow` usa e que o IAP aceita) e encaminha tudo para o MLflow. Você abre
http://localhost:5000 e usa a UI normalmente.

Pré-requisitos (uma vez):
  gcloud auth login            # sua conta com tokenCreator na client SA
  # (a client SA destaquesgovbr-mlflow-client já tem iap.httpsResourceAccessor)

Uso:
  python scripts/iap_ui_proxy.py
  # abre http://localhost:5000 no browser

Variáveis (opcionais):
  DGB_MLFLOW_TRACKING_URI  (default: a URL de produção abaixo)
  DGB_MLFLOW_CLIENT_SA     (default: destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com)
  IAP_PROXY_PORT           (default: 5000)
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TRACKING_URI = os.environ.get(
    "DGB_MLFLOW_TRACKING_URI",
    "https://destaquesgovbr-mlflow-klvx64dufq-rj.a.run.app",
).rstrip("/")
CLIENT_SA = os.environ.get(
    "DGB_MLFLOW_CLIENT_SA",
    "destaquesgovbr-mlflow-client@inspire-7-finep.iam.gserviceaccount.com",
)
AUDIENCE = f"{TRACKING_URI}/*"
PORT = int(os.environ.get("IAP_PROXY_PORT", "5000"))

# Cabeçalhos hop-by-hop que não devem ser repassados.
_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}

_token: dict = {"jwt": None, "exp": 0.0}


def _mint_jwt() -> str:
    """Assina um JWT do IAP (aud = URL/*) impersonando a client SA via signJwt."""
    now = int(time.time())
    claims = {
        "iss": CLIENT_SA, "sub": CLIENT_SA, "email": CLIENT_SA,
        "aud": AUDIENCE, "iat": now, "exp": now + 3600,
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(claims, f)
        claims_path = f.name
    try:
        out = subprocess.run(
            ["gcloud", "iam", "service-accounts", "sign-jwt",
             claims_path, "/dev/stdout", f"--iam-account={CLIENT_SA}"],
            capture_output=True, text=True, check=True,
        )
    finally:
        os.unlink(claims_path)
    return out.stdout.strip()


def _get_token() -> str:
    """Retorna um JWT válido, renovando ~10 min antes de expirar."""
    if not _token["jwt"] or time.time() > _token["exp"] - 600:
        _token["jwt"] = _mint_jwt()
        _token["exp"] = time.time() + 3600
    return _token["jwt"]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self) -> None:
        body = None
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            body = self.rfile.read(length)

        headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP}
        headers["Authorization"] = f"Bearer {_get_token()}"

        req = urllib.request.Request(
            url=f"{TRACKING_URI}{self.path}", data=body,
            method=self.command, headers=headers,
        )
        try:
            resp = urllib.request.urlopen(req)
            status, resp_headers, payload = resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            status, resp_headers, payload = e.code, e.headers, e.read()
        except Exception as e:  # noqa: BLE001
            self.send_error(502, f"proxy error: {e}")
            return

        self.send_response(status)
        for k, v in resp_headers.items():
            if k.lower() not in _HOP:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _proxy
    do_POST = _proxy
    do_PUT = _proxy
    do_DELETE = _proxy
    do_PATCH = _proxy
    do_HEAD = _proxy

    def log_message(self, fmt, *args):  # menos verboso
        pass


def main() -> None:
    _get_token()  # falha cedo se a auth/impersonation não funcionar
    print(f"MLflow via IAP proxy: http://localhost:{PORT}  ->  {TRACKING_URI}")
    print("Abra a URL acima no browser. Ctrl+C para parar.")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
