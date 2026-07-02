"""Envio de e-mail transacional via Resend (HTTP puro, sem dependência nova).

Ativado por RESEND_API_KEY no ambiente do engine (plist). Sem a key, roda em
modo dev: loga o conteúdo em vez de enviar — o fluxo de reset continua
testável localmente sem conta no Resend.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
FROM_ADDRESS = os.environ.get(
    "ESCORA_EMAIL_FROM", "estrutura.app <nao-responda@estrutura.app>"
)


def send_email(to: str, subject: str, html: str) -> bool:
    """Envia um e-mail. Retorna True se enviado (ou logado em modo dev)."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        logger.info(
            "RESEND_API_KEY ausente — e-mail NAO enviado (modo dev). "
            f"to={to} subject={subject!r} html={html!r}"
        )
        return True

    payload = json.dumps({
        "from": FROM_ADDRESS,
        "to": [to],
        "subject": subject,
        "html": html,
    }).encode()
    req = urllib.request.Request(
        RESEND_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            ok = 200 <= res.status < 300
            if not ok:
                logger.warning(f"Resend retornou status {res.status} para {to}")
            return ok
    except urllib.error.URLError as e:
        logger.error(f"Falha ao enviar e-mail para {to}: {e}")
        return False


def send_password_reset(to: str, reset_link: str) -> bool:
    return send_email(
        to,
        "estrutura.app — redefinição de senha",
        (
            "<p>Recebemos um pedido para redefinir a senha da sua conta no "
            "<b>estrutura.app</b>.</p>"
            f'<p><a href="{reset_link}">Clique aqui para escolher uma nova senha</a> '
            "(o link vale por 1 hora e só pode ser usado uma vez).</p>"
            "<p>Se você não pediu a redefinição, ignore este e-mail — sua senha "
            "continua a mesma.</p>"
        ),
    )
