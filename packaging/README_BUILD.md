# Build do Instalador .exe

Este fluxo gera o app empacotado e o instalador final para Windows.

## Ferramentas necessarias

- Python 3
- PyInstaller
- Inno Setup 6

Se o PyInstaller ainda nao estiver instalado, o script pode instalar as dependencias de build:

```powershell
.\packaging\build_release.ps1 -InstallBuildDeps
```

## Gerar instalador final

```powershell
.\packaging\build_release.ps1 -Version "0.1.0-beta"
```

Saida esperada:

- `release/FX.palette_Setup_0.1.0-beta.exe`: instalador para enviar aos testers

Durante o build, o staging temporario e criado em `%TEMP%\EffectPalette_Installer_Staging`.

## Gerar apenas o app empacotado

Use isto quando quiser validar o PyInstaller antes do instalador:

```powershell
.\packaging\build_release.ps1 -SkipInstaller
```

Depois disso, teste:

```powershell
.\release\staging\EffectPalette\FX.palette.exe
```

## O que vai no instalador

- `FX.palette.exe`, gerado pelo PyInstaller sem console
- `app.py`, copia legivel do codigo principal para facilitar auditoria/leitura no install
- arquivos CEP: `CSXS`, `bridge.js`, `worker.html`, `index.html`, `lib`, `scripts`
- `template_project`
- `data/generic_item_templates.json`
- documentacao principal
- chaves `PlayerDebugMode=1` em `HKCU/Software/Adobe/CSXS.8` ate `CSXS.14`

Arquivos de runtime, caches, logs, comandos temporarios e presets exportados nao entram no instalador.
