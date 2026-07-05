"""Cliente Gmail — INTERFACE AINDA NÃO IMPLEMENTADA.

Por instrução explícita, a integração real com a Gmail API não foi
configurada nesta etapa: nenhuma credencial, OAuth flow, token ou envio
de e-mail acontece aqui. Este módulo só define o formato (schema) que o
restante do pipeline espera, para que a troca do modo local pelo modo
Gmail real, no futuro, não exija mudar main.py/correlacionador.py.

Quando a integração real for autorizada, este arquivo passará a:
- autenticar via OAuth2 (google-auth, google-auth-oauthlib, google-api-python-client)
- usar um token salvo em token_gmail.json (git-ignorado)
- ler e-mails dos marcadores JESSICA/STHEFANY/PAMELA/LAYANE e PEDIDO
- baixar anexos para data/gmail_cotacoes/anexos/

Nada disso está implementado ainda.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmailGmail:
    """Formato mínimo que qualquer fonte de e-mails (local ou Gmail real) deve produzir."""
    id_email: str
    marcador: str  # JESSICA | STHEFANY | PAMELA | LAYANE | PEDIDO
    assunto: str
    remetente: str
    data: str  # ISO 8601
    anexos: list[str] = field(default_factory=list)
    link: str = ""
    corpo_texto: str = ""


class GmailClientNaoConfigurado(RuntimeError):
    """Levantada sempre que algo tentar usar a Gmail API real neste estágio do projeto."""


class GmailClient:
    """Placeholder. Não autentica, não lista, não baixa e não envia nada."""

    def __init__(self, *_args, **_kwargs):
        raise GmailClientNaoConfigurado(
            "Integração real com Gmail API ainda não foi configurada neste projeto. "
            "Rode o robô em --somente-local com um manifesto local "
            "(ver manifesto_local.py) enquanto credentials.json/token_gmail.json "
            "não forem provisionados e autorizados explicitamente."
        )

    def listar_emails_por_marcador(self, marcador: str, limite: int | None = None) -> list[EmailGmail]:
        raise GmailClientNaoConfigurado("listar_emails_por_marcador ainda não implementado.")

    def baixar_anexo(self, id_email: str, nome_anexo: str, destino_dir) -> str:
        raise GmailClientNaoConfigurado("baixar_anexo ainda não implementado.")
