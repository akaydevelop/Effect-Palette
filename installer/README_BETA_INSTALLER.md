# Effect Palette Beta Installer Interno

> Observacao: este script e uma ferramenta tecnica interna. Para beta testers e usuarios finais, o caminho recomendado e gerar um instalador `.exe` usando o fluxo em `packaging/`.

Este instalador prepara a extensao para testes fechados no Windows.

## Como instalar

1. Clique com o botao direito em `install_beta.ps1`.
2. Escolha `Run with PowerShell`.
3. Aguarde a copia dos arquivos, criacao do ambiente Python e instalacao das dependencias.

Por padrao, o instalador cria atalhos no Menu Iniciar e na Area de Trabalho.

Para iniciar junto com o Windows, execute:

```powershell
.\install_beta.ps1 -CreateStartupShortcut
```

## O que ele faz

- Copia a extensao para `%APPDATA%\Adobe\CEP\extensions\EffectPalette`.
- Cria um ambiente Python em `.venv`.
- Instala as dependencias de `requirements.txt`.
- Cria atalhos usando `pythonw.exe`, sem janela de terminal durante o uso normal.
- Mantem logs e relatorios locais em `Documents\EffectPalette_Beta_Report`.

## Observacoes

- Os arquivos de runtime dentro de `data/`, como caches, logs e comandos temporarios, nao sao copiados.
- O projeto template e os arquivos essenciais da extensao sao copiados normalmente.
- Esta e uma base de beta. Para lancamento final, o ideal e empacotar este fluxo em um instalador `.exe`.
