# EffectPalette

Extensão CEP para Adobe Premiere Pro com uma paleta em Python para:

- aplicar efeitos de vídeo e áudio
- aplicar presets do Premiere
- inserir itens do projeto na timeline
- inserir itens genéricos do Premiere, como `Bars and Tone`, `Black Video`, `Color Matte` e `Transparent Video`

## Estrutura

- `app.py`: app Python da paleta
- `bridge.js`: worker CEP que conversa com o Premiere
- `scripts/host.jsx`: lógica ExtendScript/QE DOM
- `data/`: arquivos gerados em runtime
- `CSXS/manifest.xml`: manifesto CEP

## Requisitos

- Adobe Premiere Pro
- Python 3
- Dependências em [requirements.txt](C:\Users\Paulo\AppData\Roaming\Adobe\CEP\extensions\EffectPalette\requirements.txt)

## Observações

- Os arquivos gerados em `data/` não entram no Git.
- A configuração local para importar `Adjustment Layer` por template fica em `data/generic_item_templates.json`, com múltiplas entradas por resolução.
- `projectPath` pode ser relativo à pasta da extensão, o que facilita distribuição pública.
- Um exemplo dessa configuração está em [data/generic_item_templates.example.json](C:\Users\Paulo\AppData\Roaming\Adobe\CEP\extensions\EffectPalette\data\generic_item_templates.example.json).

## Status atual

- Aplicação de efeitos: funcionando
- Aplicação de presets: funcionando na maior parte dos casos
- Keyframes em imagens / adjustment layers: limitação conhecida do Premiere, com aviso na UI
- Inserção de itens do projeto: funcionando
- Inserção de itens genéricos: base implementada
