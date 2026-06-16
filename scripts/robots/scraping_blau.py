"""
scripts/robots/scraping_blau.py
Raspador do portfólio de produtos da Blau Farmacêutica.

Fluxo:
  1. Playwright headless Chromium
  2. Acessa a página índice de categorias (todos-os-produtos)
  3. Coleta as URLs de cada subcategoria (ex: /antibioticos/, /oncologicos/)
  4. Para cada subcategoria, extrai produtos com h4 (subgrupo) + li.list-unstyled
  5. Injeta fabricante fixo 'BLAU' e grupo_tag fixo
  6. Salva em lote na tabela importacao_raw — zero regras de negócio no loop

Uso:
  python scripts/robots/scraping_blau.py
  python scripts/robots/scraping_blau.py --dry-run   # imprime sem gravar
"""

import argparse
import logging
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH  = BASE_DIR / "banco" / "medbox_v3.db"

sys.path.insert(0, str(BASE_DIR))

URL_BASE      = "https://blau.com"
URL_INDICE    = f"{URL_BASE}/produtos/todos-os-produtos/"
FABRICANTE    = "BLAU"
GRUPO_TAG     = "Medicamentos / soluções / injetáveis"
FONTE         = "BLAU_SITE"
USER_AGENT    = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL da tabela de staging
# ---------------------------------------------------------------------------
DDL_STAGING = """
CREATE TABLE IF NOT EXISTS importacao_raw (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte             TEXT    NOT NULL,
    nome_produto      TEXT,
    principio_ativo   TEXT,
    apresentacao      TEXT,
    fabricante        TEXT,
    grupo_tag         TEXT,
    categoria_site    TEXT,
    sub_categoria_site TEXT,
    url_bula_paciente TEXT,
    url_bula_medico   TEXT,
    raw_text          TEXT,
    data_raspagem     TEXT    NOT NULL,
    processado        INTEGER NOT NULL DEFAULT 0
)
"""

# ---------------------------------------------------------------------------
# JavaScript executado dentro de cada página de categoria
#
# Coleta h4 (subgrupo, ex: "Cefalosporínicos") e li.list-unstyled (produto)
# em ordem de documento, associando cada produto ao h4 precedente.
# Usa querySelectorAll pois h4 e li são irmãos diretos no DOM da Blau —
# não há <ul> intermediário separando os subgrupos.
# ---------------------------------------------------------------------------
_JS_EXTRATOR_CATEGORIA = """
() => {
    const resultados = [];
    let subCategoria = "";

    document.querySelectorAll("h4, li.list-unstyled").forEach(el => {
        if (el.tagName === "H4") {
            subCategoria = el.innerText.trim();
            return;
        }

        const span = el.querySelector("span.mr-auto");
        if (!span) return;

        const rawText = span.innerText.trim();
        if (!rawText) return;

        const bulaP = el.querySelector("a.patient-leaflet");
        const bulaM = el.querySelector("a.medic-leaflet");

        resultados.push({
            raw_text:          rawText,
            sub_categoria:     subCategoria,
            url_bula_paciente: bulaP ? bulaP.href : null,
            url_bula_medico:   bulaM ? bulaM.href  : null,
        });
    });

    return resultados;
}
"""

# JavaScript que coleta os links de categoria da página índice
_JS_EXTRATOR_INDICE = """
() => {
    const links = [];
    const base = window.location.href;

    document.querySelectorAll("a[href*='/todos-os-produtos/']").forEach(a => {
        if (a.href !== base && a.href !== base.replace(/\\/$/, "")) {
            links.push({ url: a.href, nome: a.innerText.trim() });
        }
    });

    // Deduplica por URL
    const vistos = new Set();
    return links.filter(l => {
        if (vistos.has(l.url)) return false;
        vistos.add(l.url);
        return true;
    });
}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_nome_principio(raw: str) -> tuple[str, str]:
    """
    'Aricilina - Benzilpenicilina Potássica' → ('Aricilina', 'Benzilpenicilina Potássica')
    'Meropeném - genérico'                   → ('Meropeném', 'Meropeném')
    'Cefalotina Sódica'                       → ('Cefalotina Sódica', 'Cefalotina Sódica')

    Quando não há separador " - ", assume que o texto já é o DCI/genérico,
    então nome e princípio ativo são iguais.
    """
    partes = raw.split(" - ", maxsplit=1)
    if len(partes) == 2:
        nome      = partes[0].strip()
        principio = partes[1].strip()
        if principio.lower() in ("genérico", "generico", ""):
            principio = nome
        return nome, principio
    nome = raw.strip()
    return nome, nome


def _setup_staging(conn: sqlite3.Connection) -> None:
    conn.execute(DDL_STAGING)
    conn.commit()
    _log.info("Tabela importacao_raw verificada/criada.")


def _limpar_staging_anterior(conn: sqlite3.Connection) -> None:
    cur = conn.execute(
        "DELETE FROM importacao_raw WHERE fonte = ? AND processado = 0",
        (FONTE,),
    )
    conn.commit()
    if cur.rowcount:
        _log.info(f"  {cur.rowcount} registros anteriores não-processados removidos.")


def _salvar_em_lote(rows: list[dict], conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO importacao_raw
            (fonte, nome_produto, principio_ativo, apresentacao, fabricante,
             grupo_tag, categoria_site, sub_categoria_site,
             url_bula_paciente, url_bula_medico,
             raw_text, data_raspagem, processado)
        VALUES
            (:fonte, :nome_produto, :principio_ativo, :apresentacao, :fabricante,
             :grupo_tag, :categoria_site, :sub_categoria_site,
             :url_bula_paciente, :url_bula_medico,
             :raw_text, :data_raspagem, :processado)
        """,
        rows,
    )
    conn.commit()
    _log.info(f"  {len(rows)} registros gravados em importacao_raw.")


# ---------------------------------------------------------------------------
# Motor de raspagem
# ---------------------------------------------------------------------------

def scrape() -> list[dict]:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    _log.info("Iniciando Playwright (headless Chromium)...")
    todos_os_rows: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page    = browser.new_page(user_agent=USER_AGENT)

        # ------------------------------------------------------------------
        # Passo 1: coleta links de categoria na página índice
        # ------------------------------------------------------------------
        _log.info(f"Passo 1/3 — acessando índice: {URL_INDICE}")
        page.goto(URL_INDICE, wait_until="networkidle", timeout=30_000)

        categorias: list[dict] = page.evaluate(_JS_EXTRATOR_INDICE)
        _log.info(f"  {len(categorias)} categorias encontradas.")
        for c in categorias:
            _log.info(f"    → {c['nome']} ({c['url']})")

        if not categorias:
            _log.error("Nenhuma categoria encontrada na página índice.")
            browser.close()
            return []

        # ------------------------------------------------------------------
        # Passo 2: itera cada categoria e extrai produtos
        # ------------------------------------------------------------------
        _log.info("Passo 2/3 — raspando produtos por categoria...")
        ts = datetime.now().isoformat(timespec="seconds")

        for idx, cat in enumerate(categorias, start=1):
            cat_nome = cat["nome"]
            cat_url  = cat["url"]

            _log.info(f"  [{idx}/{len(categorias)}] {cat_nome} ...")
            try:
                page.goto(cat_url, wait_until="networkidle", timeout=20_000)
            except PWTimeout:
                _log.warning(f"    Timeout em {cat_url} — pulando categoria.")
                continue

            try:
                page.wait_for_selector("li.list-unstyled span.mr-auto", timeout=8_000)
            except PWTimeout:
                _log.warning(f"    Sem produtos visíveis em {cat_nome} — categoria vazia ou estrutura diferente.")
                continue

            entradas = page.evaluate(_JS_EXTRATOR_CATEGORIA)
            _log.info(f"    {len(entradas)} produtos capturados.")

            for entrada in entradas:
                nome, principio = _parse_nome_principio(entrada["raw_text"])
                todos_os_rows.append({
                    "fonte":              FONTE,
                    "nome_produto":       nome,
                    "principio_ativo":    principio or None,
                    # apresentacao: ausente na listagem; segunda passagem via bulas
                    "apresentacao":       None,
                    "fabricante":         FABRICANTE,
                    "grupo_tag":          GRUPO_TAG,
                    "categoria_site":     cat_nome,
                    "sub_categoria_site": entrada["sub_categoria"] or None,
                    "url_bula_paciente":  entrada["url_bula_paciente"],
                    "url_bula_medico":    entrada["url_bula_medico"],
                    "raw_text":           entrada["raw_text"],
                    "data_raspagem":      ts,
                    "processado":         0,
                })

            # Pausa curta entre categorias para não sobrecarregar o servidor
            time.sleep(0.5)

        browser.close()

    _log.info(f"Passo 3/3 — extração concluída: {len(todos_os_rows)} produtos no total.")
    return todos_os_rows


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scraper Blau Farmacêutica → staging importacao_raw"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extrai e imprime sem gravar no banco",
    )
    args = parser.parse_args()

    rows = scrape()

    if not rows:
        _log.error("Nenhum produto capturado. Encerrando sem gravar.")
        sys.exit(1)

    if args.dry_run:
        # Agrupa por categoria para o relatório
        por_cat: dict[str, int] = {}
        for r in rows:
            key = r["categoria_site"] or "(sem categoria)"
            por_cat[key] = por_cat.get(key, 0) + 1

        print(f"\n{'='*62}")
        print(f"DRY-RUN — {len(rows)} produtos capturados (primeiros 20):")
        print(f"{'='*62}")
        for r in rows[:20]:
            sub = r["sub_categoria_site"] or "—"
            print(
                f"  [{r['categoria_site']} / {sub}] "
                f"{r['nome_produto']} | PA: {r['principio_ativo'] or '—'}"
            )

        print(f"\nResumo por categoria:")
        for cat, qtd in sorted(por_cat.items()):
            print(f"  {qtd:>3}x  {cat}")
        print(f"\nTotal: {len(rows)} produtos | Sem gravar (--dry-run).")
        return

    if not DB_PATH.exists():
        _log.error(f"Banco não encontrado: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        _setup_staging(conn)
        _limpar_staging_anterior(conn)
        _salvar_em_lote(rows, conn)
    finally:
        conn.close()

    _log.info(f"Concluído. {len(rows)} produtos na staging importacao_raw (processado=0).")


if __name__ == "__main__":
    main()
