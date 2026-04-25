# FX.palette

Paleta flutuante para Adobe Premiere Pro, controlada por um app Python, com backend CEP + ExtendScript.

## O que a extensao faz

- aplica efeitos de video
- aplica efeitos de audio
- aplica presets do usuario
- aplica transicoes de video e audio
- insere itens do projeto na timeline
- insere built-ins do Premiere, como `Adjustment Layer`, `Bars and Tone`, `Black Video`, `Color Matte` e `Transparent Video`
- insere favoritos customizados vindos do `template_project`

## Estrutura principal

- [app.py](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/app.py): app Python da paleta
- [bridge.js](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/bridge.js): worker CEP headless
- [scripts/host.jsx](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/scripts/host.jsx): logica ExtendScript / QE DOM
- [CSXS/manifest.xml](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/CSXS/manifest.xml): manifesto CEP
- [template_project](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/template_project): assets de template e favoritos
- [data](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/data): arquivos gerados em runtime

## Requisitos

- Adobe Premiere Pro
- Python 3
- dependencias em [requirements.txt](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/requirements.txt)

## Instalacao beta / release

- O caminho recomendado para testers e usuarios finais e gerar um instalador `.exe`.
- A estrutura de build fica em [packaging](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/packaging).
- [packaging/build_release.ps1](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/packaging/build_release.ps1) empacota o app com PyInstaller e gera o setup com Inno Setup.
- O instalador final copia a extensao para `%APPDATA%/Adobe/CEP/extensions/EffectPalette`, cria atalhos e usa `FX.palette.exe` sem terminal aberto.
- O instalador tambem habilita `PlayerDebugMode` para CEP no usuario atual, evitando configuracao manual no Regedit durante a beta.
- O antigo [installer/install_beta.ps1](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/installer/install_beta.ps1) fica apenas como fallback tecnico interno.
- Mais detalhes em [packaging/README_BUILD.md](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/packaging/README_BUILD.md).

## Estado atual

- aplicacao de efeitos: funcionando
- aplicacao de presets: funcionando na maior parte dos casos
- aplicacao de transicoes: funcionando
- insercao de itens do projeto: funcionando
- favoritos e built-ins: funcionando
- `Adjustment Layer` por template: funcionando
- sequencias do projeto: funcionando com reconstrucao do conteudo interno em muitos casos reais
- presets animados em `Adjustment Layer` e imagens: funcionando via helper clip temporario + clonagem de componentes/keyframes
- modo beta fechada: gera relatorios locais em `Documents/FX.palette_Beta_Report`

## Beta fechada

- Logs, telemetria local e feedback ficam apenas no PC do usuario.
- Se o Premiere ficou aberto pelo tempo minimo configurado e depois foi fechado, o app pede feedback e gera um `.zip`.
- O usuario pode revisar e enviar manualmente o arquivo gerado em `Documents/FX.palette_Beta_Report`.
- A janela de debug tambem tem uma acao para gerar relatorio beta manualmente.
- O relatorio inclui informacoes locais do PC, versao/locale do Premiere quando disponivel, logs e manifestos pequenos de debug.

## App em segundo plano

- [EffectPalette.pyw](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/EffectPalette.pyw) inicia o app sem janela de prompt quando usado com `pythonw`.
- Quando `pystray` e `Pillow` estao instalados, o app aparece na system tray.
- A tray permite abrir a paleta, abrir debug, gerar relatorio beta, abrir a pasta de relatorios e encerrar o app.

## Limitacoes conhecidas

- Em clips normais, os keyframes principais do preset sao aplicados, mas o easing original do preset nao e preservado com fidelidade total.
- No fluxo atual, keyframes temporais usam a interpolacao nativa do Premiere e um bezier padrao/aproximado quando necessario, em vez de tentar reconstruir exatamente a curva original do preset.
- Em presets animados aplicados em clips "infinitos" como `Adjustment Layer` e imagens, o fallback atual funciona bem, mas ainda pode haver pequeno deslocamento residual de `1-2` frames em alguns casos.

## Templates

- A configuracao da `Adjustment Layer` por template fica em [data/generic_item_templates.json](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/data/generic_item_templates.json)
- `projectPath` pode ser relativo a pasta da extensao
- o `template_project` tambem pode conter favoritos customizados no bin `EffectPalette_Favorites`

## Direcao futura

- A paleta Python continua sendo o core do produto.
- No futuro, a evolucao de backend pode seguir um modelo:
  - `Full`: `Python + UXP` para Premiere Pro `25.6+`
  - `Lite`: `Python + CEP` para versoes antigas

Para mais contexto tecnico e estado atual do projeto, veja [RELATORIO_EFFECT_PALETTE.md](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/RELATORIO_EFFECT_PALETTE.md).
