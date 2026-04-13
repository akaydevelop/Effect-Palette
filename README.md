# EffectPalette

Paleta flutuante para Adobe Premiere Pro, controlada por um app Python, com backend CEP + ExtendScript.

## O que a extensao faz

- aplica efeitos de video
- aplica efeitos de audio
- aplica presets do usuario
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

## Estado atual

- aplicacao de efeitos: funcionando
- aplicacao de presets: funcionando na maior parte dos casos
- insercao de itens do projeto: funcionando
- favoritos e built-ins: funcionando
- `Adjustment Layer` por template: funcionando

## Limitacoes conhecidas

- Em imagens e `Adjustment Layers`, presets com keyframes continuam sujeitos a limitacoes da API do Premiere.
- Em clips normais, os keyframes principais do preset sao aplicados, mas o easing original do preset nao e preservado com fidelidade total.
- No fluxo atual, keyframes temporais usam a interpolacao nativa do Premiere e um bezier padrao/aproximado quando necessario, em vez de tentar reconstruir exatamente a curva original do preset.

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
