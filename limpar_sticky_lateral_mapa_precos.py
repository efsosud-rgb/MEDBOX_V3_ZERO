from pathlib import Path
from datetime import datetime
import re

ARQUIVO = Path("templates/mapa_precos_clientes.html")

if not ARQUIVO.exists():
    raise FileNotFoundError(f"Arquivo não encontrado: {ARQUIVO}")

texto = ARQUIVO.read_text(encoding="utf-8")

backup = ARQUIVO.with_name(
    ARQUIVO.name + ".bak_limpa_sticky_lateral_" + datetime.now().strftime("%Y%m%d_%H%M%S")
)
backup.write_text(texto, encoding="utf-8")

original = texto

# Remove bloco antigo: MAPA ERP - CONGELAMENTO + FILTROS
texto = re.sub(
    r'\n\s*/\*\s*=+\s*MAPA ERP - CONGELAMENTO \+ FILTROS.*?(?=\n\s*/\*\s*=+\s*MAPA ERP - FIX FINAL STICKY \+ FILTROS)',
    '\n',
    texto,
    flags=re.DOTALL
)

# Remove bloco antigo: MAPA ERP - FIX FINAL STICKY + FILTROS
texto = re.sub(
    r'\n\s*/\*\s*=+\s*MAPA ERP - FIX FINAL STICKY \+ FILTROS.*?(?=\n\s*/\*\s*=+\s*MAPA ERP - SCROLL ESTÁVEL FINAL)',
    '\n',
    texto,
    flags=re.DOTALL
)

# Segurança extra: remove regras CSS antigas soltas de sticky lateral, se tiverem sobrado
texto = re.sub(
    r'\n\s*\.mpc-table th\.mpc-sticky-col,\s*\n\s*\.mpc-table td\.mpc-sticky-col\s*\{.*?\}',
    '\n',
    texto,
    flags=re.DOTALL
)

texto = re.sub(
    r'\n\s*\.mpc-table th\.mpc-sticky-col\s*\{.*?\}',
    '\n',
    texto,
    flags=re.DOTALL
)

texto = re.sub(
    r'\n\s*\.mpc-table td\.mpc-sticky-col\s*\{.*?\}',
    '\n',
    texto,
    flags=re.DOTALL
)

# Garante que o bloco final continue existindo
if "MAPA ERP - SCROLL ESTÁVEL FINAL" not in texto:
    raise RuntimeError("ERRO: bloco MAPA ERP - SCROLL ESTÁVEL FINAL não encontrado após limpeza.")

if "MAPA ERP - FILTROS SEM STICKY LATERAL" not in texto:
    raise RuntimeError("ERRO: script MAPA ERP - FILTROS SEM STICKY LATERAL não encontrado após limpeza.")

# Garante que sticky lateral não continue ativo
if re.search(r'\.mpc-table\s+(?:th|td)\.mpc-sticky-col\s*\{[^}]*position\s*:\s*sticky', texto, flags=re.I | re.DOTALL):
    raise RuntimeError("ERRO: ainda existe sticky lateral ativo para .mpc-sticky-col.")

ARQUIVO.write_text(texto, encoding="utf-8")

print(f"Backup criado: {backup}")
print("OK: blocos antigos de sticky lateral removidos.")
print("OK: bloco de scroll estável preservado.")
print("OK: script de filtros preservado.")
