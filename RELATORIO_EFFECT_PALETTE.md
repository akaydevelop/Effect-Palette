# Effect Palette — Relatório Completo do Projeto

## Visão Geral

O **Effect Palette** é uma extensão para o Adobe Premiere Pro que permite buscar e aplicar efeitos e presets via uma paleta flutuante com atalho de teclado global (Ctrl+Espaço). O projeto é composto por três componentes principais que se comunicam via arquivos JSON em disco.

---

## Arquitetura

### Componentes

```
Effect Palette
├── app.py                          ← App Python com UI flutuante
├── cep_extension/
│   ├── bridge.js                   ← Worker headless CEP (roda dentro do Premiere)
│   ├── scripts/host.jsx            ← ExtendScript (executa ações no Premiere)
│   ├── CSXS/manifest.xml           ← Manifesto da extensão CEP
│   ├── worker.html                 ← HTML do worker headless
│   └── index.html                  ← Painel de debug (manter como backup, não referenciado)
└── requirements.txt
```

### Fluxo de Comunicação

```
app.py  ──writeSafe()──>  premiere_cmd.json  <──poll() 300ms──  bridge.js
                                                                      │
                                             premiere_effects.json    │ cs.evalScript()
                                             premiere_presets.json    │
                                                                      ↓
                                                                  host.jsx
                                                              (ExtendScript)
```

### Caminhos importantes (Windows)

- **Extensão instalada:** `C:\Users\Paulo\AppData\Roaming\Adobe\CEP\extensions\EffectPalette\`
- **Pasta de dados:** `...EffectPalette\data\` (criada automaticamente)
- **Arquivo de presets do usuário:** `C:\Users\Paulo\Documents\Adobe\Premiere Pro\26.0\Profile-Paulo\Effect Presets and Custom Items.prfpset`
- **Arquivos de dados gerados:**
  - `data\premiere_effects.json` — lista de efeitos exportada do Premiere
  - `data\premiere_presets.json` — presets parseados do .prfpset
  - `data\premiere_cmd.json` — fila de comandos entre Python e CEP
  - `data\worker.log` — log do worker headless
  - `data\premiere_diagnose.txt` — diagnóstico do ExtendScript

---

## Estado Atual das Funcionalidades

### ✅ Implementado e Funcionando

- Paleta de busca com atalho global **Ctrl+Espaço** (só abre quando o Premiere está em foco via `pygetwindow` — verifica se `"Adobe Premiere"` está no título da janela ativa)
- Lista dinâmica de **1612+ efeitos** exportados do Premiere (Boris FX, Sapphire, Magic Bullet, etc.)
- Aplicar **efeitos de vídeo** nos clipes selecionados
- Aplicar **efeitos de áudio** nos clipes selecionados
- Pills de categoria: **Todos | Vídeo | Áudio | Presets**
- Worker **headless CEP** (sem painel obrigatório no Premiere — não aparece em Janela → Extensões)
- Janela de debug no Python (**Ctrl+D**) com botões: Exportar efeitos, Diagnóstico, Limpar logs/bridge
- **Presets do usuário:** parseamento do `.prfpset` XML, listagem na paleta com ícone `◈`
- **Aplicação de presets** com valores corretos para a maioria dos casos
- **Escrita segura de arquivos** com `writeSafe()` / `write_safe()` — grava em `.tmp` e renomeia atomicamente, eliminando race conditions com BSODs
- **Foco inicial da janela Python corrigido** — a primeira abertura da paleta agora já entra pronta para digitação sem exigir clique manual
- **Limpeza de logs no startup e por comando** — `worker.log` agora é podado automaticamente na inicialização quando cresce demais, e o comando de limpeza também apaga os logs
- **Hotkey global estabilizado** — `Ctrl+Espaço`, `Ctrl+D` e `Ctrl+Q` agora usam guarda por combinação, evitando toggles repetidos por repetição de tecla/estado preso
- **Aba Genéricos funcional**:
  - `Adjustment Layer` com seleção automática por resolução
  - fallback por `template_project` quando a layer não existe no projeto atual
  - sequência-template usada só como veículo e apagada depois da importação
  - `Bars and Tone`, `Black Video`, `Color Matte` e `Transparent Video` criados via API
  - assets organizados no bin `EffectPalette_Assets`

### ⚠️ Parcialmente Funcionando (Bugs Conhecidos)

1. **Preset anterior resetando** — ao aplicar um segundo preset do mesmo tipo de efeito num clipe que já tem esse efeito, o primeiro volta aos valores padrão. Causa raiz: a Fase 2 da aplicação usa `effectIndices[f]` que aponta para `stdClip.components[idx]`, mas quando já havia um efeito igual antes, o índice está errado. O bug é que `stdClip.components.numItems` antes da Fase 1 já inclui efeitos de presets anteriores, então para o segundo preset o índice registrado pode apontar para o efeito antigo.

2. **Keyframes não aplicados** — a função `_applyKeyframes` está implementada mas não testada. Presets com animações (ex: ELASTIC SLIDE IN UP) terão keyframes ignorados.

3. **Efeitos de áudio em presets** — presets que incluem efeitos de áudio (ex: PITCH SHIFTER) não têm os efeitos de áudio aplicados. O preset é detectado como vídeo e os efeitos de áudio são ignorados.

4. **Checkboxes de plugins de terceiros** — Mocha Pro e S_Shake (Sapphire) têm checkboxes com problema, provavelmente o mesmo bug do apóstrofo Unicode que já foi resolvido para o Transform — precisam do mapeamento `knownNames` no `bridge.js`.

5. **Transform com valores padrão em preset com múltiplos efeitos** — quando um preset tem Transform + múltiplos Mirrors, o Transform às vezes é aplicado com valores padrão. Isso acontece porque o `effectIndices[0]` na Fase 2 aponta para um componente errado.

---

## Estado Atual — Itens do Projeto e Genéricos

### Itens do Projeto

- A paleta exporta e lista itens inseríveis do projeto ativo em `premiere_project_items.json`
- A categoria **Projeto** permite inserir clips/sequências do bin diretamente na timeline
- A inserção procura a próxima track livre no ponto atual
- Se necessário, cria nova track via QE DOM
- Para `Adjustment Layer` já existente no projeto, a inserção pode cobrir toda a seleção quando múltiplos clips estão selecionados

### Genéricos

- A categoria **Genéricos** atualmente expõe:
  - `Adjustment Layer`
  - `Bars and Tone`
  - `Black Video`
  - `Color Matte`
  - `Transparent Video`
- `Bars and Tone`, `Black Video`, `Color Matte` e `Transparent Video` são criados via API/QE
- `Adjustment Layer` usa:
  1. busca por `Adjustment Layer_WxH` já existente no projeto
  2. fallback por template (`template_project/template_project.prproj`)
  3. importação seletiva por `importSequences(...)`
  4. remoção da sequência-template após localizar a layer
- Os assets criados/importados são organizados em `EffectPalette_Assets`

### Template de Adjustment Layer

- O arquivo `data/generic_item_templates.json` define os templates disponíveis
- O projeto-template fica dentro da própria extensão, em `template_project/template_project.prproj`
- O sistema já suporta múltiplas resoluções e proporções:
  - horizontal
  - vertical
  - `1:1`
  - `4:3`
- A escolha do template é feita por resolução mais próxima da sequência ativa

### Próximo refinamento sugerido

- Evoluir a aba **Genéricos** para uma aba de **assets/favoritos**, permitindo que o usuário mantenha assets curados no `template_project` além dos genéricos nativos

---

## Decisões Técnicas Importantes

### ExtendScript / QE DOM

- **Adicionar efeitos:** Só é possível via QE DOM (`qeClip.addVideoEffect()` / `qeClip.addAudioEffect()`). A API padrão não tem esse método para clips na timeline.
- **Setar parâmetros:** Só é possível via API padrão (`stdClip.components[n].properties[n].setValue()`). O QE DOM não tem acesso a propriedades de efeitos já aplicados.
- **Portanto:** precisamos dos dois — QE DOM para adicionar, API padrão para setar valores.
- **`stdClip.components`** é a propriedade correta para acessar efeitos de um clip. **Não** usar `videoComponents` ou `audioComponents` — essas não existem no trackItem.
- **Ticks:** QE DOM usa ticks para posição temporal. `ticksPerSecond = 4233600000`.
- **Seleção:** `sequence.getSelection()` + `clip.parentTrackIndex` para identificar clipes. O `parentTrackIndex` inclui tracks de vídeo e áudio concatenadas — subtrair `numVideoTracks` para obter o índice correto de tracks de áudio.

### Formato de Parâmetros no XML (.prfpset)

O arquivo `.prfpset` é XML. Estrutura relevante:

```xml
<TreeItem>           → preset individual (tem <Name>)
  <FilterPresetItem> → dados do preset
    <FilterPreset>   → um efeito dentro do preset (pode haver múltiplos)
      <FilterMatchName>  → nome interno do efeito (ex: "AE.ADBE Gaussian Blur 2")
      <Component>        → parâmetros do efeito
        <DisplayName>    → nome exibido (ex: "Gaussian Blur (Legacy)")
        <Params>
          <Param> → referência para VideoComponentParam ou PointComponentParam
<VideoComponentParam> ou <PointComponentParam> ou <AudioComponentParam>
  <StartKeyframe>    → "-91445760000000000,VALOR,0,0,..." — o VALOR é o que interessa
  <CurrentValue>     → valor atual (menos confiável para alguns tipos)
  <ParameterControlType>  → 2=float, 3=angle, 4=checkbox, 6=Point, 7=enum
  <IsTimeVarying>    → true se tem keyframes
  <Keyframes>        → dados de keyframes (formato: "TICKS,VALOR:VALOR,...;TICKS,...")
  <Name>             → nome da propriedade (pode estar vazio para alguns params)
  <ParameterID>      → ID interno (não é índice direto)
```

**Tipos de parâmetro (`ParameterControlType`):**
- `2` — float/número
- `3` — ângulo (float)
- `4` — checkbox (boolean, `"true"` / `"false"` no StartKeyframe)
- `6` — Point (formato `"x:y"` normalizados 0-1)
- `7` — enum/dropdown

**Valores de Point:** estão normalizados de 0 a 1. **NÃO multiplicar pela resolução.** O `prop.setValue([x, y], true)` aceita valores normalizados diretamente.

**Apóstrofo Unicode:** O Premiere usa `'` (U+2019, charCode 8217) nos `displayName`, enquanto o XML usa `'` (ASCII 39). A função `_normName()` normaliza isso para comparação.

**Parâmetros sem `<Name>`:** Alguns parâmetros do Transform não têm nome no XML (ex: `Uniform Scale`, `Use Composition's Shutter Angle`). O `bridge.js` mapeia esses via `knownNames` usando o `ParameterID`:
```javascript
var knownNames = {
  "11": "Uniform Scale",
  "9":  "Use Composition's Shutter Angle",
};
```

**MediaType de áudio:** `"80b8e3d5-6dca-4195-aefb-cb5f407ab009"` — identifica FilterPresets de áudio.

### Escrita de Arquivos (`writeSafe` / `write_safe`)

Para evitar race conditions que causavam BSODs (`POOL_CORRUPTION_IN_FILE_AREA`, `KERNEL_MODE_HEAP_CORRUPTION`, `PFN_LIST_CORRUPT`):

**JavaScript (`bridge.js`):**
```javascript
function writeSafe(filePath, content) {
  const tmp = filePath + ".tmp";
  fs.writeFileSync(tmp, content, "utf8");
  fs.renameSync(tmp, filePath); // rename é atômico no Windows
}
```

**Python (`app.py`):**
```python
def write_safe(file_path: Path, content: str):
    tmp = file_path.with_suffix(file_path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(file_path)  # atômico no Windows e Linux
```

### Foco no Premiere (`app.py`)

```python
def premiere_is_focused() -> bool:
    active = gw.getActiveWindow()
    return "Adobe Premiere" in active.title  # cobre todas as versões
```

---

## Estrutura do `premiere_presets.json`

```json
{
  "version": 1,
  "exported_at": 1234567890.0,
  "presets": [
    {
      "name": "ELASTIC SLIDE IN UP - KAINE KNIGHT",
      "category": "Presets - Kaine Knight",
      "type": "preset",
      "filterPresets": [
        {
          "matchName": "AE.ADBE Geometry2",
          "displayName": "Transform",
          "isAudio": false,
          "params": [
            {
              "name": "Anchor Point",
              "value": "0.5:0.5",
              "keyframes": null,
              "paramId": "1"
            },
            {
              "name": "Position",
              "value": "0.5:0.5",
              "keyframes": "914457600000000,0.5:1.19...; ...",
              "paramId": "2"
            },
            {
              "name": "Uniform Scale",
              "value": "true",
              "keyframes": null,
              "paramId": "11"
            }
          ]
        }
      ]
    }
  ]
}
```

---

## Estrutura do `premiere_effects.json`

```json
{
  "version": 1,
  "exported_at": 1234567890.0,
  "premiere_version": "26.0",
  "effects": [
    {"name": "Gaussian Blur (Legacy)", "category": "Video", "type": "video"},
    {"name": "Pitch Shifter",          "category": "Audio", "type": "audio"}
  ]
}
```

---

## Estrutura do `premiere_cmd.json`

**Aplicar efeito:**
```json
{
  "command": "applyEffect",
  "effect": "Gaussian Blur (Legacy)",
  "category": "Video",
  "type": "video",
  "timestamp": 1234567890.123,
  "status": "pending"
}
```

**Aplicar preset:**
```json
{
  "command": "applyPreset",
  "effect": "ELASTIC SLIDE IN UP",
  "filterPresetsJSON": "[{\"matchName\":\"AE.ADBE Geometry2\",\"displayName\":\"Transform\",...}]",
  "timestamp": 1234567890.123,
  "status": "pending"
}
```

**Status possíveis:** `pending` → `processing` → `done` / `error` / `error_no_selection` / `error_not_found`

---

## Bugs Pendentes e Como Investigar

### Bug 1: Preset anterior resetando

**Descrição:** Aplica Preset A (Blur 150) → aplica Preset B (Blur 60) no mesmo clipe → Preset A volta para valor padrão (25).

**Causa confirmada:** Durante a Fase 2 da `applyPresetWithSelection`, `stdClip.components[idx]` aponta para o efeito errado quando já havia um efeito do mesmo tipo no clipe antes do preset atual.

**O que foi tentado:**
- `componentsBeforePreset` com busca `>= idx` — resolvia o reset mas quebrava presets com múltiplos efeitos iguais (ex: 4 Mirrors)
- `skipCount/foundCount` — resolvia os Mirrors mas causava o reset
- Abordagem de duas fases (Fase 1 adiciona tudo, Fase 2 seta valores) — parcialmente funcional mas ainda com problemas

**Estado atual do código:** usa duas fases com `effectIndices[f] = stdClip.components.numItems` antes de cada adição. O problema é que quando já existe um efeito igual no clipe, `effectIndices[f]` aponta para o efeito antigo em vez do recém adicionado.

**Próximo passo sugerido:** investigar se `stdClip.components.numItems` atualiza imediatamente após `qeClip.addVideoEffect()` dentro do mesmo script, ou se há um delay. Se houver delay, a Fase 1 não consegue registrar índices corretos. Uma alternativa seria usar o `nodeId` do clip para identificar unicamente cada efeito.

### Bug 2: Keyframes

**Descrição:** Presets com animações (keyframes) são aplicados sem os keyframes.

**Causa:** A função `_applyKeyframes` está implementada mas pode ter erros. No `_applyKeyframes` para parâmetros de Point (dentro de keyframes), o código chama `prop.setValue([x, y], true)` em vez de `prop.setValueAtKey()` — isso é incorreto para keyframes.

**Próximo passo:** corrigir `_applyKeyframes` para Point params — deve usar `prop.setValueAtKey(time, [x, y], true)` não `prop.setValue`.

### Bug 3: Efeitos de áudio em presets

**Descrição:** Presets que incluem efeitos de áudio (identificados por `isAudio: true` no filterPreset) não têm os efeitos de áudio aplicados.

**Causa:** A busca do track usa `saved.isAudio` do clipe selecionado. Se o clipe selecionado é de vídeo, `useAudio = false` e o código usa `qeSequence.getVideoTrackAt()` — nunca aplicando efeitos de áudio mesmo que o preset os inclua.

**Próximo passo:** Para cada `filterPreset` do preset, se `fp.isAudio === true`, buscar o track de áudio correspondente ao clipe selecionado (geralmente o clip de vídeo tem um clip de áudio vinculado na track imediatamente abaixo).

---

## Roadmap Pendente (por prioridade)

1. ~~Abrir paleta só quando Premiere em foco~~ ✅
2. **Presets** — manter estabilidade geral, melhorar UX dos avisos e seguir validando edge cases em beta
3. **Inserir itens do projeto na timeline** — listar `app.project.rootItem` e inserir via ExtendScript na posição do playhead
4. **System tray** — `pystray` com ícone na bandeja e menu de contexto
5. **Adicionar transições** — QE DOM tem suporte via `addVideoTransition()`
6. **Mudar parâmetros de clipes** — modo na paleta para digitar parâmetro, ver valor atual, digitar novo
7. **Mudança de UI** — redesign do app Python
8. **Gerar `.exe`** — PyInstaller, deixar para o final
9. **Integração com After Effects** — baixa prioridade
10. **Investigar migração de CEP para UXP** — avaliar suporte real do Premiere Pro, paridade de APIs com o fluxo atual (`bridge.js` + `host.jsx` + app Python), impacto em worker/headless/debug, empacotamento e distribuição antes de considerar uma migração futura
11. ~~Corrigir foco inicial da janela Python~~ ✅

---

12. **Corrigir keyframes em camadas "infinitas"** â€” imagens, adjustment layers e outros clips sem duraÃ§Ã£o finita tradicional ainda podem receber keyframes muito longe do inÃ­cio esperado
13. **Corrigir keyframes em Nest** â€” presets com keyframes aplicados em clips nested ainda podem posicionar a animaÃ§Ã£o fora do trecho visÃ­vel/esperado

**AtualizaÃ§Ã£o recente sobre keyframes:** o bug em camadas "infinitas" (imagens / adjustment layers) continua pendente, enquanto a aplicaÃ§Ã£o em Nest melhorou e agora funciona melhor nos testes recentes.

## Ambiente de Desenvolvimento

- **Hardware:** Ryzen 5 5500, Gigabyte B550M Aorus Elite, 2×16GB DDR4 Asgard nos slots A1+B1 a 2666MHz (3 pentes causavam instabilidade; 3200MHz/3133MHz/3000MHz causavam BSODs de RAM)
- **SO:** Windows (dualboot com Nobara Linux)
- **Premiere Pro:** versão 26.0
- **CEP:** versão 12 (manifesto `Version="12.0"`, `CSXS.Version="12.0"`)
- **Python:** 3.x com tkinter, pynput, pygetwindow
- **Node.js:** embutido no CEP (via `window.require`)

### Como habilitar extensões não assinadas (PlayerDebugMode)

Necessário para desenvolver sem assinar a extensão:
```
HKEY_CURRENT_USER\Software\Adobe\CSXS.12
PlayerDebugMode = 1
```

---

## Atualizacao do Estado Real

Observacao: algumas secoes antigas deste relatorio ficaram desatualizadas depois das ultimas iteracoes e devem ser lidas junto com esta atualizacao.

### O que ja foi corrigido

- Reaplicar presets do mesmo tipo no mesmo clipe sem resetar o preset anterior
- Ordem correta de efeitos duplicados no mesmo preset
- Aplicacao de efeitos de audio dentro de presets
- Checkboxes / toggles de varios plugins de terceiros
- Valores de cor de presets
- Keyframes em clips normais de video
- Diferenciacao entre efeitos Legacy e nao-Legacy na exportacao e aplicacao
- Insercao de itens do projeto na timeline
- Fallback para proxima track livre ao inserir item do projeto, com criacao de nova track quando necessario
- Insercao de Adjustment Layer existente cobrindo a selecao quando multiplos clips estao selecionados
- Categoria de itens genericos na paleta (`Adjustment Layer`, `Bars and Tone`, `Black Video`, `Color Matte`, `Transparent Video`)
- Criacao/insercao de itens genericos do Premiere
  - `Bars and Tone` via API oficial
  - `Black Video`, `Color Matte` e `Transparent Video` via QE DOM

### O que ainda esta pendente

1. **Keyframes em imagens / adjustment layers / clips "infinitos"** - ainda nao aplicam corretamente.
2. **Curvas Bezier / Speed** - a extensao aproxima a curva e esta usavel, mas ainda nao replica 100% a curva interna do Premiere.
3. **Criacao de Adjustment Layer do zero por template** - a extensao ja tem o caminho preparado para importar de um projeto-template, mas ainda depende de configurar `data/generic_item_templates.json` com o `.prproj` e os `sequenceIDs` corretos do template.
4. **Validacao ampla em closed beta** - ainda falta testar em diferentes versoes do Premiere, plugins e bibliotecas de presets.

### Mitigacao atual para o bug de keyframes em clips "infinitos"

- A aplicacao continua funcionando normalmente em clips de video comuns.
- Para presets com keyframes, a UI agora mostra um aviso antes de aplicar se a selecao atual incluir uma imagem ou Adjustment Layer.
- O aviso existe para reduzir confusao do usuario enquanto essa limitacao do Premiere continua sem workaround confiavel.

---

## To-Do Futuro

- **Preparar closed beta** â€” quando as funcionalidades planejadas estiverem completas, rodar uma beta fechada com amigos usando diferentes versÃµes do Premiere Pro, coleÃ§Ãµes de presets e plugins instalados, para validar compatibilidade em ambientes reais.
- **Pacote de diagnÃ³stico para beta** â€” antes da closed beta, criar um fluxo simples para coletar informaÃ§Ãµes Ãºteis de suporte, como versÃ£o do Premiere, versÃ£o da extensÃ£o, quantidade de efeitos exportados e logs relevantes (`worker.log`, erros de aplicaÃ§Ã£o, etc.).
- **RelatÃ³rio de compatibilidade** â€” no futuro, considerar uma tela ou exportaÃ§Ã£o simples mostrando ambiente detectado (versÃ£o do Premiere, extensÃ£o, efeitos/presets exportados) para facilitar feedback dos testers.

---

## Notas Finais

- O `index.html` (painel de debug visual) foi removido do `manifest.xml` mas pode ser mantido em pasta separada como backup
- O worker não aparece em Janela → Extensões por ser headless (`AutoVisible=false`, sem `<Menu>`)
- O arquivo `.prfpset` tem ~600k linhas / 30MB — o parsing é feito uma vez na inicialização e cacheado; só re-parseia se o arquivo mudar (verificação por `mtime`)
- O Premiere usa apóstrofo tipográfico U+2019 (`'`) em `displayName` de propriedades — sempre normalizar para ASCII `'` antes de comparar
- `frameSizeHorizontal` e `frameSizeVertical` estão **invertidos** no Premiere API — `frameSizeHorizontal` retorna a altura e `frameSizeVertical` retorna a largura. Para Point params que precisam de pixels, usar `frameSizeVertical` para X e `frameSizeHorizontal` para Y (mas na prática Point params usam valores normalizados 0-1 e não precisam de conversão)
