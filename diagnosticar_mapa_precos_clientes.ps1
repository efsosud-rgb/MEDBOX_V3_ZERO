$OutputDir = "DIAG_MAPA_PRECOS_CLIENTES"
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Export-FileWithLines {
    param(
        [string]$PathFile,
        [string]$OutFile
    )

    if (Test-Path $PathFile) {
        $i = 1
        Get-Content $PathFile | ForEach-Object {
            "{0,5}: {1}" -f $i, $_
            $i++
        } | Set-Content $OutFile -Encoding UTF8
        Write-Host "OK:" $OutFile
    }
    else {
        "ARQUIVO NÃO ENCONTRADO: $PathFile" | Set-Content $OutFile -Encoding UTF8
        Write-Host "NÃO ENCONTRADO:" $PathFile
    }
}

function Export-Search {
    param(
        [string]$PathFile,
        [string[]]$Patterns,
        [string]$OutFile
    )

    if (Test-Path $PathFile) {
        $resultados = Select-String -Path $PathFile -Pattern $Patterns -SimpleMatch
        if ($resultados) {
            $resultados | ForEach-Object {
                "[Linha $($_.LineNumber)] $($_.Line)"
            } | Set-Content $OutFile -Encoding UTF8
        }
        else {
            "Nenhum padrão encontrado em $PathFile" | Set-Content $OutFile -Encoding UTF8
        }
        Write-Host "OK:" $OutFile
    }
    else {
        "ARQUIVO NÃO ENCONTRADO: $PathFile" | Set-Content $OutFile -Encoding UTF8
        Write-Host "NÃO ENCONTRADO:" $PathFile
    }
}

# 1) Estrutura de arquivos relevantes
Get-ChildItem -Recurse -File |
Where-Object {
    $_.FullName -match "mapa|cotacao_cliente|cotacoes_cliente|sku|lances|style\.css|template"
} |
Select-Object FullName |
Out-File "$OutputDir\00_arquivos_relacionados.txt" -Encoding UTF8

# 2) app.py completo numerado
Export-FileWithLines "app.py" "$OutputDir\01_app_py_completo.txt"

# 3) core mapa preços
Export-FileWithLines "core\mapa_precos_clientes.py" "$OutputDir\02_core_mapa_precos_clientes.txt"

# 4) procurar rotas e palavras-chave no app.py
Export-Search "app.py" @(
    "mapa-precos-clientes",
    "mapa_precos_clientes",
    "importar_cotacao_cliente",
    "cotacao_cliente",
    "sku_master",
    "autocomplete",
    "sugest"
) "$OutputDir\03_app_buscas.txt"

# 5) procurar templates prováveis
$templates = Get-ChildItem "templates" -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match "mapa|cotacao|cliente"
}
$templates | Select-Object Name, FullName | Out-File "$OutputDir\04_templates_encontrados.txt" -Encoding UTF8

foreach ($tpl in $templates) {
    $out = Join-Path $OutputDir ("TPL_" + $tpl.Name + ".txt")
    Export-FileWithLines $tpl.FullName $out
}

# 6) CSS principal
Export-FileWithLines "static\style.css" "$OutputDir\05_style_css.txt"

# 7) Procurar autocomplete / sugestão SKU em templates e core
Get-ChildItem -Recurse -Include *.py,*.html,*.js |
Select-String -Pattern "sku_master","autocomplete","sugest","fetch(","axios","XMLHttpRequest","/api/" -SimpleMatch |
ForEach-Object {
    "$($_.Path) [Linha $($_.LineNumber)] $($_.Line)"
} | Set-Content "$OutputDir\06_busca_global_sku_autocomplete.txt" -Encoding UTF8

Write-Host ""
Write-Host "DIAGNÓSTICO CONCLUÍDO."
Write-Host "Pasta gerada:" (Resolve-Path $OutputDir)
