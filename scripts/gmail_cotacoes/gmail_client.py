"""Cliente Gmail — Fase 2: integração real, SOMENTE LEITURA.

Escopo OAuth único e obrigatório: https://www.googleapis.com/auth/gmail.readonly
(ver config.GMAIL_READONLY_SCOPE). Este cliente NUNCA:
- envia e-mail, cria rascunho ou responde;
- altera labels/marcadores;
- arquiva, apaga ou marca mensagens como lidas/não lidas;
- usa qualquer escopo além de gmail.readonly (a credencial é validada em
  tempo de execução — ver _validar_escopo).

Credenciais:
- `credentials.json` (OAuth client "Desktop app" do Google Cloud Console) —
  nunca commitado, protegido pelo .gitignore da raiz do projeto.
- `token_gmail.json` (gerado automaticamente após o primeiro login OAuth,
  via `flow.run_local_server` — abre o navegador uma vez) — também nunca
  commitado.

Cuidado deliberado com corpo de e-mail: para conseguir os NOMES dos
anexos é preciso pedir `format="full"` à API (o Gmail não expõe a lista
de anexos em `format="metadata"`). Mesmo assim, este cliente nunca lê o
campo `body.data` de nenhuma parte do e-mail (é aí que ficaria o texto do
corpo) — só os cabeçalhos (Subject/From/Date), o snippet curto que a
própria API já devolve, e os metadados de anexo (nome, mimeType,
attachmentId, tamanho). O conteúdo binário de um anexo só é buscado
quando o chamador pede explicitamente para baixar aquele anexo.
"""

from __future__ import annotations

import base64
import email.utils
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import config
from perfil_tecnico import normalizar_texto


@dataclass
class EmailGmail:
    """Formato mínimo que qualquer fonte de e-mails (local ou Gmail real) deve produzir."""
    id_email: str
    marcador: str  # JESSICA | STHEFANY | PAMELA | LAYANE | PEDIDO
    assunto: str
    remetente: str
    data: str  # ISO 8601 quando possível, ou o cabeçalho Date cru
    anexos: list[str] = field(default_factory=list)
    link: str = ""
    corpo_texto: str = ""  # deliberadamente nunca preenchido nesta fase
    thread_id: str = ""
    labels: list[str] = field(default_factory=list)  # nomes resolvidos (não IDs) — ver correlacionador.extrair_marcadores_presentes
    snippet: str = ""


class GmailClientError(RuntimeError):
    """Base de erros do cliente Gmail real."""


class GmailApiNaoInstaladaError(GmailClientError):
    pass


class CredenciaisNaoEncontradasError(GmailClientError):
    pass


class EscopoGmailInvalidoError(GmailClientError):
    pass


def _parse_data_iso(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError as exc:
        raise ValueError(f"Data invalida '{valor}'. Use o formato YYYY-MM-DD.") from exc


def montar_query_gmail_periodo(marcador_nome: str, data_inicio: str | None = None, data_fim: str | None = None) -> str:
    """Monta a query Gmail por marcador e data do e-mail.

    `before:` e exclusivo no Gmail; data_fim e somada em 1 dia para incluir
    todo o ultimo dia informado. Este filtro nao altera DATA_VENDA, que
    continua vindo da Ordem de Compra.
    """
    inicio = _parse_data_iso(data_inicio)
    fim = _parse_data_iso(data_fim)
    if inicio and fim and inicio > fim:
        raise ValueError("--data-inicio nao pode ser maior que --data-fim.")

    partes = [f"label:{marcador_nome}"]
    if inicio:
        partes.append(f"after:{inicio.strftime('%Y/%m/%d')}")
    if fim:
        fim_exclusivo = fim + timedelta(days=1)
        partes.append(f"before:{fim_exclusivo.strftime('%Y/%m/%d')}")
    return " ".join(partes)


def montar_query_gmail_oc_texto(data_inicio: str | None = None, data_fim: str | None = None, marcador_nome: str | None = None) -> str:
    """Query ampla para apurar vendas por Ordem de Compra, sem depender de PEDIDO."""
    inicio = _parse_data_iso(data_inicio)
    fim = _parse_data_iso(data_fim)
    if inicio and fim and inicio > fim:
        raise ValueError("--data-inicio nao pode ser maior que --data-fim.")

    partes = ['"ordem de compra"']
    if marcador_nome:
        partes.append(f"label:{marcador_nome}")
    if inicio:
        partes.append(f"after:{inicio.strftime('%Y/%m/%d')}")
    if fim:
        fim_exclusivo = fim + timedelta(days=1)
        partes.append(f"before:{fim_exclusivo.strftime('%Y/%m/%d')}")
    partes.append("has:attachment")
    return " ".join(partes)


def _extrair_cabecalhos(payload: dict) -> dict:
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
    data_bruta = headers.get("Date", "")
    data_iso = data_bruta
    try:
        dt = email.utils.parsedate_to_datetime(data_bruta)
        if dt is not None:
            data_iso = dt.isoformat()
    except (TypeError, ValueError):
        pass
    return {
        "assunto": headers.get("Subject", ""),
        "remetente": headers.get("From", ""),
        "data": data_iso,
    }


def _extrair_metadados_anexos(payload: dict) -> list[dict]:
    """Só nome/mimeType/attachmentId/tamanho — NUNCA lê part['body']['data']."""
    resultado: list[dict] = []

    def _percorrer(parte: dict) -> None:
        filename = parte.get("filename") or ""
        if filename:
            body = parte.get("body", {}) or {}
            resultado.append({
                "filename": filename,
                "attachment_id": body.get("attachmentId"),
                "mime_type": parte.get("mimeType", ""),
                "size": body.get("size", 0),
            })
        for sub in parte.get("parts", []) or []:
            _percorrer(sub)

    _percorrer(payload)
    return resultado


def _validar_escopo(creds) -> None:
    escopos = set(getattr(creds, "scopes", None) or [])
    if not escopos:
        return  # alguns fluxos não expõem escopos no objeto Credentials; nada a validar
    permitidos = {config.GMAIL_READONLY_SCOPE}
    extras = escopos - permitidos
    if extras:
        raise EscopoGmailInvalidoError(
            f"O token Gmail contém escopo(s) além de {config.GMAIL_READONLY_SCOPE}: {sorted(extras)}. "
            "Apague token_gmail.json e gere um novo token só com o escopo readonly."
        )


def _obter_credenciais(credentials_path: Path, token_path: Path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise GmailApiNaoInstaladaError(
            "Bibliotecas OAuth do Google não instaladas. "
            "pip install google-auth google-auth-oauthlib google-api-python-client"
        ) from exc

    escopos = [config.GMAIL_READONLY_SCOPE]
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), escopos)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise CredenciaisNaoEncontradasError(
                    f"{credentials_path} não encontrado. Gere um OAuth client (tipo Desktop app) "
                    "no Google Cloud Console, com o escopo gmail.readonly, e salve o JSON nesse caminho."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), escopos)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    _validar_escopo(creds)
    return creds


class GmailClient:
    """Cliente Gmail real, somente leitura. Nunca envia, altera ou apaga nada."""

    def __init__(self, credentials_path: Path | str | None = None, token_path: Path | str | None = None):
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GmailApiNaoInstaladaError(
                "google-api-python-client não está instalado. pip install google-api-python-client"
            ) from exc

        self._credentials_path = Path(credentials_path) if credentials_path else config.CREDENTIALS_PATH
        self._token_path = Path(token_path) if token_path else config.TOKEN_GMAIL_PATH
        creds = _obter_credenciais(self._credentials_path, self._token_path)
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        self._mapa_labels_cache: dict[str, str] | None = None

    def listar_labels(self) -> list[dict]:
        resposta = self._service.users().labels().list(userId="me").execute()
        return [{"id": l["id"], "name": l["name"]} for l in resposta.get("labels", [])]

    def _mapa_labels(self) -> dict[str, str]:
        """id -> nome do label, cacheado (uma única chamada labels.list por cliente)."""
        if self._mapa_labels_cache is None:
            self._mapa_labels_cache = {l["id"]: l["name"] for l in self.listar_labels()}
        return self._mapa_labels_cache

    def resolver_labels(self, nomes_desejados: list[str]) -> dict[str, str | None]:
        """Tolerante a acento/caixa/hierarquia (ex.: "Vendedoras/STHEFANY" casa com "STHEFANY")."""
        labels = self.listar_labels()
        resultado: dict[str, str | None] = {}
        for nome in nomes_desejados:
            alvo = normalizar_texto(nome)
            encontrado = None
            for label in labels:
                candidatos = [label["name"]] + label["name"].split("/")
                if any(normalizar_texto(c) == alvo for c in candidatos):
                    encontrado = label["id"]
                    break
            resultado[nome] = encontrado
        return resultado

    def _obter_mensagem(self, message_id: str) -> dict:
        return self._service.users().messages().get(userId="me", id=message_id, format="full").execute()

    def listar_labels_thread(self, thread_id: str) -> list[str]:
        """Lista nomes de labels presentes em qualquer mensagem do thread."""
        if not thread_id:
            return []
        thread = self._service.users().threads().get(
            userId="me", id=thread_id, format="minimal",
        ).execute()
        mapa_labels = self._mapa_labels()
        labels_ids: set[str] = set()
        for msg in thread.get("messages", []):
            labels_ids.update(msg.get("labelIds", []))
        return sorted(mapa_labels.get(label_id, label_id) for label_id in labels_ids)

    def listar_emails_por_marcador(
        self,
        label_id: str,
        marcador_nome: str,
        limite: int,
        data_inicio: str | None = None,
        data_fim: str | None = None,
    ) -> list[EmailGmail]:
        if not limite or limite <= 0:
            raise ValueError("listar_emails_por_marcador exige um limite positivo explícito.")

        query = montar_query_gmail_periodo(marcador_nome, data_inicio, data_fim)
        resposta = self._service.users().messages().list(
            userId="me", labelIds=[label_id], q=query, maxResults=limite,
        ).execute()

        mapa_labels = self._mapa_labels()
        resultado: list[EmailGmail] = []
        for ref in resposta.get("messages", []):
            msg = self._obter_mensagem(ref["id"])
            payload = msg.get("payload", {}) or {}
            cabecalhos = _extrair_cabecalhos(payload)
            anexos_meta = _extrair_metadados_anexos(payload)
            nomes_labels = [mapa_labels.get(lid, lid) for lid in msg.get("labelIds", [])]

            resultado.append(EmailGmail(
                id_email=msg["id"],
                marcador=marcador_nome,
                assunto=cabecalhos["assunto"],
                remetente=cabecalhos["remetente"],
                data=cabecalhos["data"],
                anexos=[a["filename"] for a in anexos_meta],
                link=f"https://mail.google.com/mail/u/0/#all/{msg['id']}",
                corpo_texto="",
                thread_id=msg.get("threadId", ""),
                labels=nomes_labels,
                snippet=(msg.get("snippet") or "")[:140],
            ))
        return resultado

    def listar_emails_por_query(self, query: str, marcador_nome: str, limite: int) -> list[EmailGmail]:
        """Lista mensagens por query Gmail livre, somente metadados/anexos."""
        if not limite or limite <= 0:
            raise ValueError("listar_emails_por_query exige um limite positivo explicito.")

        resposta = self._service.users().messages().list(
            userId="me", q=query, maxResults=limite,
        ).execute()

        mapa_labels = self._mapa_labels()
        resultado: list[EmailGmail] = []
        for ref in resposta.get("messages", []):
            msg = self._obter_mensagem(ref["id"])
            payload = msg.get("payload", {}) or {}
            cabecalhos = _extrair_cabecalhos(payload)
            anexos_meta = _extrair_metadados_anexos(payload)
            nomes_labels = [mapa_labels.get(lid, lid) for lid in msg.get("labelIds", [])]

            resultado.append(EmailGmail(
                id_email=msg["id"],
                marcador=marcador_nome,
                assunto=cabecalhos["assunto"],
                remetente=cabecalhos["remetente"],
                data=cabecalhos["data"],
                anexos=[a["filename"] for a in anexos_meta],
                link=f"https://mail.google.com/mail/u/0/#all/{msg['id']}",
                corpo_texto="",
                thread_id=msg.get("threadId", ""),
                labels=nomes_labels,
                snippet=(msg.get("snippet") or "")[:140],
            ))
        return resultado

    def baixar_anexos_amostra(
        self, label_id: str, label_nome: str, pasta_anexos: Path,
        limite_mensagens: int, limite_anexos_por_mensagem: int | None = None,
    ) -> list[Path]:
        """Baixa só uma amostra: `limite_mensagens` e-mails, no máximo
        `limite_anexos_por_mensagem` anexos por e-mail (None = todos os
        anexos daquele e-mail, ainda limitado pelo limite de mensagens)."""
        if not limite_mensagens or limite_mensagens <= 0:
            raise ValueError("baixar_anexos_amostra exige limite_mensagens positivo explícito.")

        from extrator_anexos import salvar_anexo_gmail

        resposta = self._service.users().messages().list(
            userId="me", labelIds=[label_id], maxResults=limite_mensagens,
        ).execute()

        caminhos_salvos: list[Path] = []
        for ref in resposta.get("messages", []):
            msg = self._obter_mensagem(ref["id"])
            payload = msg.get("payload", {}) or {}
            anexos_meta = _extrair_metadados_anexos(payload)
            if limite_anexos_por_mensagem is not None:
                anexos_meta = anexos_meta[:limite_anexos_por_mensagem]

            for anexo in anexos_meta:
                if not anexo["attachment_id"]:
                    continue
                dados = self._service.users().messages().attachments().get(
                    userId="me", messageId=msg["id"], id=anexo["attachment_id"],
                ).execute()
                conteudo = base64.urlsafe_b64decode(dados["data"])
                caminho = salvar_anexo_gmail(
                    pasta_anexos=pasta_anexos, label=label_nome, message_id=msg["id"],
                    nome_arquivo=anexo["filename"], conteudo=conteudo,
                )
                caminhos_salvos.append(caminho)
        return caminhos_salvos

    def baixar_anexos_mensagem(
        self,
        message_id: str,
        label_nome: str,
        pasta_anexos: Path,
        somente_ordem_compra: bool = False,
        limite_anexos: int | None = None,
    ) -> list[dict]:
        """Baixa anexos de uma mensagem especifica. Somente leitura no Gmail.

        Retorna metadados locais suficientes para persistencia idempotente:
        caminho, filename, attachment_id, mime_type e tamanho.
        """
        from extrator_anexos import parece_ordem_compra, salvar_anexo_gmail

        msg = self._obter_mensagem(message_id)
        payload = msg.get("payload", {}) or {}
        anexos_meta = _extrair_metadados_anexos(payload)
        if somente_ordem_compra:
            anexos_meta = [a for a in anexos_meta if parece_ordem_compra(a["filename"])]
        if limite_anexos is not None:
            anexos_meta = anexos_meta[:limite_anexos]

        baixados: list[dict] = []
        for anexo in anexos_meta:
            if not anexo["attachment_id"]:
                continue
            dados = self._service.users().messages().attachments().get(
                userId="me", messageId=message_id, id=anexo["attachment_id"],
            ).execute()
            conteudo = base64.urlsafe_b64decode(dados["data"])
            caminho = salvar_anexo_gmail(
                pasta_anexos=pasta_anexos,
                label=label_nome,
                message_id=message_id,
                nome_arquivo=anexo["filename"],
                conteudo=conteudo,
            )
            baixados.append({
                "caminho": caminho,
                "filename": anexo["filename"],
                "attachment_id": anexo["attachment_id"],
                "mime_type": anexo["mime_type"],
                "size": anexo["size"],
            })
        return baixados
