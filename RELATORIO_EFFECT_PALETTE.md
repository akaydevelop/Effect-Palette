# FX.palette - Relatorio Atual do Projeto

## Visao Geral

O **FX.palette** e uma paleta flutuante para Adobe Premiere Pro, controlada por um app Python, que permite buscar e aplicar:

- efeitos de video
- efeitos de audio
- presets do usuario
- itens do projeto
- assets favoritos e itens genericos

O projeto hoje funciona com uma arquitetura hibrida:

- **Python** para a paleta principal, hotkeys globais e UX
- **CEP worker headless** para a ponte com o Premiere
- **ExtendScript** para executar as acoes dentro do Premiere

O objetivo atual nao e mudar a UX principal. A paleta Python continua sendo o core do produto.

---

## Arquitetura Atual

### Componentes

```text
FX.palette
|- app.py
|- bridge.js
|- scripts/host.jsx
|- CSXS/manifest.xml
|- worker.html
|- EffectPalette.bat
|- EffectPalette.pyw
|- beta_report.py
|- installer/
|- packaging/
|- data/
|- template_project/
```

### Responsabilidade de cada parte

- [app.py](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/app.py)
  App Python com a paleta flutuante, hotkeys globais, watcher de arquivos e janela de debug.

- [EffectPalette.pyw](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/EffectPalette.pyw)
  Launcher para iniciar o app com `pythonw.exe`, sem janela de prompt no uso normal.

- [beta_report.py](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/beta_report.py)
  Coleta local de logs, eventos leves, informacoes do PC/Premiere e feedback para a beta fechada.

- [packaging](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/packaging)
  Estrutura para empacotar o app com PyInstaller e gerar instalador `.exe` com Inno Setup.

- [bridge.js](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/bridge.js)
  Worker CEP headless que faz polling, exporta dados do Premiere, le a fila de comandos e chama o host ExtendScript.

- [scripts/host.jsx](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/scripts/host.jsx)
  Camada Premiere-side com a logica de:
  - exportar efeitos, itens, favoritos e sequencias
  - aplicar efeitos e presets
  - inserir itens na timeline
  - criar/organizar genericos
  - importar Adjustment Layers por template

### Comunicacao atual

O sistema se comunica principalmente via JSON em disco dentro de [data](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/data):

- `premiere_effects.json`
- `premiere_presets.json`
- `premiere_project_items.json`
- `premiere_favorites.json`
- `premiere_sequences.json`
- `current_selection.json`
- `premiere_cmd.json`
- `worker.log`

O app Python escreve comandos em `premiere_cmd.json`, o worker le, executa no Premiere e atualiza os demais arquivos exportados.

---

## Estado Atual das Funcionalidades

### Funciona hoje

- Paleta flutuante em Python com `Ctrl+Espaco`
- Debug window com `Ctrl+D`
- Encerramento rapido com `Ctrl+Q`
- Hotkeys com debounce, sem toggle repetido por tecla presa
- Primeiro foco da paleta corrigido
- Export dinamico de efeitos do Premiere
- Parse do arquivo `.prfpset` do usuario
- Aplicacao de efeitos de video
- Aplicacao de efeitos de audio
- Aplicacao de presets do usuario
- Aplicacao de transicoes de video e audio
- Insercao de itens do projeto direto na timeline
- Reconstrucao do conteudo interno de sequencias do projeto em muitos casos reais
- Insercao inteligente na proxima track livre
- Criacao de nova track quando necessario
- Suporte a video e audio nesse fluxo de insercao
- Suporte a span da selecao para Adjustment Layer inserida
- Aba `Favoritos`
- Itens genericos built-in
- Favoritos customizados vindos do `template_project`
- Organizacao de assets em `EffectPalette_Assets`
- Limpeza de logs no startup e por comando
- Refresh manual e refresh automatico de itens do projeto
- Relatorio local para beta fechada em `Documents/FX.palette_Beta_Report`
- Execucao sem prompt via `EffectPalette.pyw`
- System tray com acoes rapidas quando `pystray` e `Pillow` estao disponiveis

### Concluido recentemente

- Aba `Transicoes`
- Aplicacao de transicoes no inicio do clip
- Aplicacao de transicoes no fim do clip
- Aplicacao automatica entre dois clips quando o Premiere consegue resolver o corte
- Dialog de escolha com mouse e teclado
- Pacote local de feedback/logs para beta fechada
- Launcher `.pyw` para uso sem console
- Primeira versao de system tray
- Instalador beta em PowerShell para copiar a extensao, criar `.venv`, instalar dependencias e criar atalhos
- Estrutura inicial para gerar `FX.palette.exe` com PyInstaller e `FX.palette_Setup_*.exe` com Inno Setup

### Modo beta fechada

O app agora grava logs e eventos leves localmente em:

- `Documents/FX.palette_Beta_Report`

Esse fluxo nao envia nada automaticamente. A ideia e o usuario revisar e mandar manualmente o `.zip` gerado.

O pacote pode incluir:

- feedback do usuario
- log do app Python
- eventos locais da sessao
- informacoes de hardware, sistema, tela, disco e localidade do PC
- versao e idioma/locale do Premiere quando o CEP/ExtendScript conseguem reportar
- `worker.log`
- `premiere_host_info.json`
- `premiere_diagnose.txt`
- manifests pequenos do Premiere usados para debug
- resumo do arquivo de presets, sem copiar o `premiere_presets.json` completo

Quando o app detecta que o Premiere ficou aberto pelo tempo minimo configurado e depois foi fechado, ele abre um formulario simples pedindo:

- nome
- impressao geral
- bugs encontrados
- sugestoes de feature
- comentarios adicionais

### Instalacao beta / release

O caminho recomendado para testers e usuarios finais e um instalador `.exe`, nao um `.ps1`.

A estrutura de build fica em:

- [packaging/build_release.ps1](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/packaging/build_release.ps1)
- [packaging/pyinstaller/EffectPalette.spec](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/packaging/pyinstaller/EffectPalette.spec)
- [packaging/inno/EffectPalette.iss](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/packaging/inno/EffectPalette.iss)

O fluxo planejado:

- PyInstaller gera `FX.palette.exe` sem console
- o build cria uma pasta limpa em `release/staging/EffectPalette`
- Inno Setup gera `FX.palette_Setup_<versao>.exe`
- o instalador copia tudo para `%APPDATA%\Adobe\CEP\extensions\EffectPalette`
- o instalador habilita `PlayerDebugMode` em `HKCU\Software\Adobe\CSXS.*` para evitar configuracao manual de CEP durante a beta
- o instalador cria atalhos no Menu Iniciar/Desktop
- iniciar junto com o Windows fica como opcao do instalador

O script antigo:

- [installer/install_beta.ps1](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/installer/install_beta.ps1)

fica apenas como fallback tecnico interno. Ele nao deve ser o fluxo principal de beta tester ou usuario final.


### Built-ins atuais da aba Favoritos

- `Adjustment Layer`
- `Bars and Tone`
- `Black Video`
- `Color Matte`
- `Transparent Video`

### Favoritos customizados

A aba `Favoritos` tambem le assets curados do bin `EffectPalette_Favorites` dentro do `template_project`.

Esse fluxo ja suporta:

- subpastas
- export para `premiere_favorites.json`
- exibicao na paleta
- insercao/importacao no projeto atual

---

## Adjustment Layer por Template

O fluxo de `Adjustment Layer` hoje esta funcional e estabilizado.

### Como funciona

1. O sistema tenta encontrar no projeto atual uma `Adjustment Layer_WxH` compativel com a resolucao da sequencia ativa.
2. Se nao encontrar, usa o `template_project`.
3. O template e resolvido via [data/generic_item_templates.json](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/data/generic_item_templates.json).
4. A sequencia-template correta e importada seletivamente.
5. A `Adjustment Layer_WxH` correspondente e localizada.
6. A sequencia `AL_TEMPLATE_WxH` e apagada depois, ficando apenas o asset util.
7. O asset e organizado em `EffectPalette_Assets`.

### Estado atual

- funciona com multiplas resolucoes
- funciona com multiplas proporcoes
- importa apenas o necessario
- nao deixa a sequencia-template sobrando no projeto

### Estrutura atual esperada no template

O [template_project](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/template_project) hoje suporta assets nomeados assim:

- `Adjustment Layer_1280x720`
- `Adjustment Layer_1920x1080`
- `Adjustment Layer_1080x1920`
- etc.

E sequencias-template nomeadas assim:

- `AL_TEMPLATE_1280x720`
- `AL_TEMPLATE_1920x1080`
- `AL_TEMPLATE_1080x1920`
- etc.

---

## Itens do Projeto na Timeline

O fluxo de insercao de itens do projeto esta funcionando.

### Comportamento atual

- usa a selecao atual para escolher track-base quando fizer sentido
- se o ponto atual estiver ocupado, sobe para a proxima track livre
- se nao houver track disponivel, cria nova track
- funciona para video e audio
- se o item for uma `Adjustment Layer` e houver multiplos clips selecionados, a layer cobre a selecao inteira
- se o item do projeto for uma sequencia, a extensao tenta reconstruir o conteudo interno dela na timeline ativa, em vez de depender apenas do comportamento de nest do Premiere
- nesse fluxo, efeitos extras e keyframes basicos desses clips internos tambem podem ser clonados para o destino

### Observacao

A busca por track livre e a criacao de track usam mistura de API padrao e QE DOM, porque esse ainda e o caminho mais pragmatico no CEP atual.

---

## Presets

### Estado atual

A base de presets esta bem melhor do que no inicio do projeto.

Hoje o sistema ja resolve:

- reaplicar presets do mesmo tipo sem resetar o preset anterior
- presets com multiplos efeitos iguais
- aplicacao de efeitos de audio dentro de presets
- varios casos de toggles e checkboxes de plugins de terceiros
- exportacao e aplicacao diferenciando efeitos Legacy e nao-Legacy

### Limitacoes atuais

1. **Keyframes em imagens e Adjustment Layers**
   O fluxo melhorou bastante. A extensao agora usa um helper clip temporario para presets animados em clips "infinitos" e depois clona componentes e keyframes para o alvo real. Ainda assim, pode haver pequeno offset residual de `1-2` frames em alguns casos.

2. **Curvas Bezier / Speed nao 100% fieis**
   A extensao aplica os keyframes principais em clips normais, mas nao tenta mais reconstruir agressivamente a curva original do preset com helper keys no fluxo padrao. O comportamento atual prioriza estabilidade: usa a interpolacao nativa do Premiere e um bezier padrao/aproximado quando necessario.

3. **Validacao gradual de edge cases**
   Ainda faz sentido continuar validando presets diferentes ao longo do uso real e de testes com usuarios.

### Fallback atual para clips "infinitos"

Se o preset tiver keyframes e a selecao atual incluir:

- `Adjustment Layer`
- imagem / still

a extensao agora tenta este fluxo:

1. criar um helper clip finito temporario
2. aplicar o preset nesse helper
3. clonar os componentes e keyframes resultantes para o alvo real
4. limpar o helper

Na pratica, esse fallback passou a funcionar muito melhor em casos reais e deixou de ser apenas uma mitigacao teorica.

### Direcao futura para easing

Uma reconstrucao aproximada de easing por helper keys continua sendo uma ideia valida, mas hoje fica fora do fluxo estavel da extensao.

Se esse caminho voltar no futuro, a direcao mais provavel e trata-lo como:

- recurso experimental
- focado primeiro em presets onde a aproximacao realmente compense
- possivelmente reavaliado quando houver um backend UXP mais maduro

---

## Favoritos

### Direcao atual

A antiga ideia de aba `Genericos` evoluiu para `Favoritos`.

Isso hoje combina dois mundos:

- built-ins da extensao
- assets customizados do usuario dentro do `template_project`

### Bin esperado

No `template_project`, o bin raiz esperado e:

- `EffectPalette_Favorites`

Esse bin pode conter:

- items diretamente
- subpastas
- organizacao livre do usuario

### Estado atual

- leitura recursiva ja funciona
- export de manifesto ja funciona
- exibicao na paleta ja funciona
- insercao basica ja funciona para os tipos suportados pelo fluxo atual

---

## Logs, Diagnostico e Operacao

### Logs principais

- [data/worker.log](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/data/worker.log)
- [data/premiere_diagnose.txt](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/data/premiere_diagnose.txt)

### Comportamento atual

- o `worker.log` e podado no startup se crescer demais
- o comando de limpeza tambem apaga logs auxiliares
- o worker roda headless
- o worker nao aparece como painel normal no menu do Premiere

### Launcher

O projeto tem um launcher em [EffectPalette.bat](/C:/Users/Paulo/AppData/Roaming/Adobe/CEP/extensions/EffectPalette/EffectPalette.bat), pensado para abrir a app Python com menos atrito.

---

## Estado Atual do Backend Premiere

Hoje o backend do Premiere e CEP + ExtendScript.

### O que faz sentido no presente

- manter esse backend como implementacao principal enquanto o produto continua ganhando recursos
- usar QE DOM quando necessario e pragmatico
- manter a paleta Python como experiencia principal

### Direcao futura

A direcao futura nao e abandonar a paleta Python.

O plano mais coerente hoje e:

- **Full:** `Python + UXP` para Premiere Pro `25.6+`
- **Lite:** `Python + CEP` para versoes antigas

Ou seja, se houver evolucao para UXP no futuro, ela deve acontecer como backend alternativo do Premiere, nao como substituicao da paleta Python.

---

## Roadmap Atual

### Prioridade mais alta

1. **Preparar closed beta**
2. **Melhorar README e documentacao publica**
3. **Continuar refinando estabilidade com testes reais**

### Prioridade media

4. **Gerar `.exe`**
5. **Refinar ainda mais presets e keyframes conforme uso real**
6. **Investigar versao para macOS**

### Prioridade baixa

7. **Mudanca de UI**
8. **Polimento da aba Favoritos**
9. **Integracao com After Effects**

### Investigacao macOS

Uma versao para macOS deve ser avaliada depois da beta fechada no Windows. Pontos principais:

- empacotar o app Python para macOS
- adaptar instalador para copiar a extensao em `~/Library/Application Support/Adobe/CEP/extensions/EffectPalette`
- validar hotkeys globais, system tray/menu bar e permissoes de acessibilidade
- habilitar CEP debug quando necessario no ambiente macOS
- avaliar assinatura/notarizacao para reduzir bloqueios do Gatekeeper

### Futuro estrategico

9. **Arquitetura Full/Lite para o backend do Premiere**

---

## O Que Ainda Faz Sentido Monitorar

- compatibilidade de presets complexos
- comportamento de keyframes em clips especiais
- fidelidade de easing
- estabilidade de importacao de assets do template
- compatibilidade entre versoes diferentes do Premiere

Esses pontos hoje nao invalidam o projeto. Sao areas normais de refinamento para uma extensao desse tipo.

---

## Ambiente de Desenvolvimento

- **SO principal:** Windows
- **Premiere Pro atual de referencia:** 26.0
- **CEP:** 12
- **Python:** 3.x
- **Stack atual:** Python + CEP + ExtendScript

### PlayerDebugMode

Para desenvolvimento com extensoes CEP nao assinadas:

```text
HKEY_CURRENT_USER\Software\Adobe\CSXS.12
PlayerDebugMode = 1
```

---

## Notas Finais

- O projeto ja passou da fase de prova de conceito e hoje tem uma base funcional consideravel.
- A parte mais delicada no momento continua sendo fidelidade de keyframes/easing, nao a arquitetura geral.
- A direcao atual do produto prioriza recursos reais e fluxo de uso antes de redesign de UI.
- O relatorio deve refletir o estado presente do projeto, nao o historico de bugs que ja foram resolvidos.
