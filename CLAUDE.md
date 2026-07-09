# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**FX.palette** is a floating effect palette for Adobe Premiere Pro (Windows). It lets editors search and apply video/audio effects, user presets, transitions, project items, and custom favorites — all from a hotkey-triggered overlay without leaving the timeline.

## Running the app

```powershell
# Normal launch (no terminal window)
pythonw EffectPalette.pyw

# Launch with terminal (debug)
python app.py
```

Dependencies must be installed first:

```powershell
pip install -r requirements.txt
```

Optional dependencies (`pynput`, `watchdog`, `pygetwindow`, `pystray`, `Pillow`) are all soft — the app starts without them with degraded functionality.

## Building the installer

```powershell
# Generate full installer .exe
.\packaging\build_release.ps1 -Version "0.1.0-beta"

# Only package the app (skips Inno Setup step)
.\packaging\build_release.ps1 -SkipInstaller

# Install build dependencies first if needed
.\packaging\build_release.ps1 -InstallBuildDeps
```

Output: `release/FX.palette_Setup_<version>.exe`  
Intermediate build: `release/staging/EffectPalette/FX.palette.exe`

## Architecture

The system has three layers that communicate through JSON files on disk (`data/`):

```
Python app (app.py)
    ↕ reads/writes JSON in data/
CEP worker headless (bridge.js inside Premiere's browser)
    ↕ calls via cs.evalScript()
ExtendScript host (scripts/host.jsx runs inside Premiere)
```

### Layer responsibilities

**[app.py](app.py)** — The Python UI layer (tkinter):
- Floating overlay window that opens on `Ctrl+Space`
- Reads effect/preset/project data from `data/*.json` files written by the CEP bridge
- Sends commands by writing `data/premiere_cmd.json` with `status: "pending"`
- Watches file changes with `watchdog` to reload data live
- Monitors Premiere process (alive/dead) to show status and trigger beta feedback
- System tray support via `pystray`

**[bridge.js](bridge.js)** — The CEP worker (runs headless inside Premiere via `worker.html`):
- Polls every 300ms for new commands in `premiere_cmd.json`
- Exports effects, presets, project items, sequences, and favorites to `data/*.json` on startup and when the project changes
- Reads `Effect Presets and Custom Items.prfpset` (Premiere's preset XML) and parses it in-browser using DOMParser
- Calls `host.jsx` functions via `cs.evalScript()` — it re-evals the `.jsx` file on every call so changes to `host.jsx` take effect without reloading the extension
- Uses `writeSafe()` (write to `.tmp` + rename) to avoid race conditions with Python reading the files simultaneously

**[scripts/host.jsx](scripts/host.jsx)** — ExtendScript running inside Premiere's QE DOM:
- `getEffectsList()` — queries `qe.project.getVideoEffectList()` / `getAudioEffectList()`
- `getSelectionJSON()` — captures active sequence selection and metadata per clip
- `applyEffectWithSelection()` / `applyPresetWithSelection()` / `applyTransitionWithSelection()` — applies effects to selected clips
- `insertProjectItemAtPlayhead()` / `insertGenericItemAtPlayhead()` / `insertFavoriteItemAtPlayhead()` — inserts items at the playhead position
- Adjustment Layer insertion uses a pre-built `template_project.prproj` as a source, selecting the correct resolution by matching sequence dimensions

### Command flow (Python → Premiere)

1. User picks an item in the Python UI
2. `app.py` writes `data/premiere_cmd.json`: `{ "command": "applyEffect", "effect": "...", "status": "pending", "timestamp": ... }`
3. `bridge.js` poll detects `status: "pending"` with a new timestamp
4. `bridge.js` calls the appropriate `host.jsx` function via `evalHostScript()`
5. `host.jsx` executes inside Premiere and returns a result string (`"ok"`, `"no_selection"`, `"not_found"`, etc.)
6. `bridge.js` updates `premiere_cmd.json` with `status: "done"` or `status: "error_*"`
7. `app.py` reads the status back

### Data files (runtime, not committed)

All written to `%APPDATA%/Adobe/CEP/extensions/EffectPalette/data/`:

| File | Written by | Read by |
|---|---|---|
| `premiere_effects.json` | bridge.js | app.py |
| `premiere_presets.json` | bridge.js | app.py |
| `premiere_project_items.json` | bridge.js | app.py |
| `premiere_favorites.json` | bridge.js | app.py |
| `premiere_sequences.json` | bridge.js | app.py |
| `current_selection.json` | bridge.js | app.py |
| `premiere_cmd.json` | app.py | bridge.js |
| `worker.log` | bridge.js | index.html debug panel |

### CEP extension structure

The manifest (`CSXS/manifest.xml`) registers a single **headless worker** extension (`com.effectpalette.bridge.worker`) that:
- Loads `worker.html` (which only includes `bridge.js`)
- Auto-starts on `ApplicationActivate`
- Never shows UI (1×1px, `AutoVisible: false`)
- Has NodeJS enabled via `--enable-nodejs` (allows `fs`, `path`, `os` access in bridge.js)

`index.html` is a **debug panel** (optional, not in the manifest) — it shows the bridge log and effect count when opened manually.

`PlayerDebugMode` must be set in `HKCU\Software\Adobe\CSXS.8` through `CSXS.14` for unsigned extensions to load. The installer sets this automatically.

### Favorites via template_project

Custom favorites come from `template_project/template_project.prproj`. The bridge checks if the currently open Premiere project is the template project, then reads the `EffectPalette_Favorites` bin from it. Each item in that bin (sequences or media files) becomes a favorite in the palette.

Adjustment Layers are inserted by importing a sequence from the template project that matches the active sequence's resolution (defined in `data/generic_item_templates.json`).

### Beta reporting

`beta_report.py` handles the closed beta: writes logs to `Documents/FX.palette_Beta_Report/`, tracks telemetry events in a `.jsonl` file, and can zip the report for manual submission. The app requests feedback after Premiere has been open for at least `BETA_FEEDBACK_MIN_OPEN_SECONDS` (default 300s) and is then closed.

## Key constraints

- **ExtendScript is ES3**: `host.jsx` runs in the legacy ExtendScript engine inside Premiere. No `const`/`let`, no arrow functions, no template literals, no `Array.prototype.forEach`. Use `var` and `for` loops. Every property access on Premiere objects must be wrapped in `try/catch` because most throw on failure rather than returning null.
- **QE DOM**: `app.enableQE()` must be called before using `qe.*`. The QE DOM is Premiere's internal API and is not officially documented.
- **Race conditions**: Python and the bridge both read/write the data files simultaneously. Always use `writeSafe()` in `bridge.js` (write `.tmp` then rename) to keep reads atomic.
- **bridge.js re-evals host.jsx on every call**: This is intentional — `evalHostScript()` runs `$.evalFile(HOST_JSX)` before each script call. Editing `host.jsx` takes effect immediately without reloading the extension.
