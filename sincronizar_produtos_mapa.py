from core.mapa_precos_clientes import sincronizar_produtos_itens_mapa_precos

resultado = sincronizar_produtos_itens_mapa_precos()

print("===== SINCRONIZAÇÃO MAPA -> PRODUTOS =====")
print("OK:", resultado.get("ok"))
print("Itens verificados:", resultado.get("itens_verificados"))
print("Produtos criados/localizados:", resultado.get("produtos_criados_ou_localizados"))
print("Itens vinculados:", resultado.get("itens_vinculados"))
