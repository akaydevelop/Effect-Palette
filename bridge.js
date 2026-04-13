/**
 * bridge.js
 * Funciona em dois contextos:
 *   worker.html  — headless, sem UI, carrega automaticamente com o Premiere
 *   index.html   — painel de debug opcional com log visual
 */

const cs   = new CSInterface();
const fs   = window.require("fs");
const os   = window.require("os");
const path = window.require("path");

// ─── Caminhos ─────────────────────────────────────────────────────────────────

const EXT_DIR       = cs.getSystemPath(SystemPath.EXTENSION);
const DATA_DIR      = path.join(EXT_DIR, "data");
const EFFECTS_FILE  = path.join(DATA_DIR, "premiere_effects.json");
const PRESETS_FILE  = path.join(DATA_DIR, "premiere_presets.json");
const PROJECT_ITEMS_FILE = path.join(DATA_DIR, "premiere_project_items.json");
const FAVORITES_FILE = path.join(DATA_DIR, "premiere_favorites.json");
const SEQUENCES_FILE = path.join(DATA_DIR, "premiere_sequences.json");
const CMD_FILE      = path.join(DATA_DIR, "premiere_cmd.json");
const LOG_FILE      = path.join(DATA_DIR, "premiere_diagnose.txt");
const WORKER_LOG_FILE = path.join(DATA_DIR, "worker.log");
const SELECTION_FILE = path.join(DATA_DIR, "current_selection.json");
const HOST_JSX      = path.join(EXT_DIR, "scripts", "host.jsx");
const MAX_WORKER_LOG_BYTES = 256 * 1024;
const PROJECT_IDENTITY_CHECK_INTERVAL_MS = 3000;
const PROJECT_ITEMS_REFRESH_INTERVAL_MS = 45000;

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR);

// ─── Escrita atômica ──────────────────────────────────────────────────────────
// Grava em arquivo temporário e renomeia — elimina race conditions com o Python

function writeSafe(filePath, content) {
  const tmp = filePath + ".tmp";
  try {
    fs.writeFileSync(tmp, content, "utf8");
    // renameSync é atômico no Windows/Linux — substitui o arquivo instantaneamente
    fs.renameSync(tmp, filePath);
  } catch(e) {
    // Limpa o .tmp se algo der errado
    try { fs.unlinkSync(tmp); } catch(_) {}
    throw e;
  }
}

// Caminho do arquivo de presets do usuário
// Tenta encontrar automaticamente na pasta de perfil do Premiere
function findPresetFile() {
  const docsDir = path.join(os.homedir(), "Documents", "Adobe", "Premiere Pro");
  if (!fs.existsSync(docsDir)) return null;

  // Percorre versões do Premiere (26.0, 25.0, etc.)
  const versions = fs.readdirSync(docsDir).sort().reverse();
  for (const ver of versions) {
    const verDir = path.join(docsDir, ver);
    if (!fs.statSync(verDir).isDirectory()) continue;

    // Procura pasta Profile-*
    const profiles = fs.readdirSync(verDir).filter(d => d.startsWith("Profile-"));
    for (const profile of profiles) {
      const candidate = path.join(verDir, profile, "Effect Presets and Custom Items.prfpset");
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return null;
}

// ─── Estado ───────────────────────────────────────────────────────────────────

let appliedCount       = 0;
let pollingActive      = false;
let lastCmdTime        = 0;
let lastSelectionJSON  = "[]";
let lastSelectionWrite = "";
let selectionTimestamp = 0;
let presetFileMtime    = 0;
let lastProjectIdentity = "";
let lastProjectIdentityCheckAt = 0;
let lastProjectItemsRefreshAt = 0;
let projectItemsRefreshPending = false;

// ─── UI helpers ───────────────────────────────────────────────────────────────

const IS_DEBUG_PANEL = !!document.getElementById("status-text");

function setStatus(text, state) {
  if (!IS_DEBUG_PANEL) return;
  document.getElementById("status-text").textContent = text;
  document.getElementById("status-dot").className = state || "";
}

function uiLog(msg, type) {
  if (!IS_DEBUG_PANEL) return;
  const div  = document.getElementById("log");
  const span = document.createElement("span");
  span.className = "entry " + (type || "");
  span.textContent = msg + "\n";
  div.appendChild(span);
  while (div.children.length > 30) div.removeChild(div.firstChild);
  div.scrollTop = div.scrollHeight;
}

function updateCount(id, value) {
  if (!IS_DEBUG_PANEL) return;
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function fileLog(msg) {
  try {
    const line = new Date().toISOString().slice(11,19) + " " + msg + "\n";
    // appendFileSync é mais seguro que writeFileSync para logs — não trunca o arquivo
    fs.appendFileSync(WORKER_LOG_FILE, line, { encoding: "utf8", flag: "a" });
  } catch(e) {}
}

function log(msg, type) {
  uiLog(msg, type);
  fileLog(msg);
}

function trimWorkerLogOnStartup() {
  try {
    if (!fs.existsSync(WORKER_LOG_FILE)) return;
    const stats = fs.statSync(WORKER_LOG_FILE);
    if (!stats || stats.size <= MAX_WORKER_LOG_BYTES) return;

    const keepBytes = Math.floor(MAX_WORKER_LOG_BYTES / 2);
    const content = fs.readFileSync(WORKER_LOG_FILE, "utf8");
    const tail = content.slice(Math.max(0, content.length - keepBytes));
    const trimmed = tail.indexOf("\n") >= 0 ? tail.slice(tail.indexOf("\n") + 1) : tail;
    writeSafe(WORKER_LOG_FILE, trimmed);
  } catch (e) {}
}

function clearLogFiles() {
  try { writeSafe(WORKER_LOG_FILE, ""); } catch (e1) {}
  try { writeSafe(LOG_FILE, ""); } catch (e2) {}
}

function evalHostScript(script, callback) {
  const hostPath = HOST_JSX.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  const loadScript = '$.evalFile("' + hostPath + '")';

  cs.evalScript(loadScript, function(loadResult) {
    if (loadResult && String(loadResult).indexOf("EvalScript error") === 0) {
      log("Erro ao recarregar host.jsx: " + loadResult, "err");
    }
    cs.evalScript(script, callback);
  });
}

// ─── 1. Exportar efeitos ──────────────────────────────────────────────────────

function exportEffects() {
  setStatus("Exportando efeitos...", "waiting");
  log("Buscando efeitos no Premiere...");

  evalHostScript("getEffectsList()", function(result) {
    if (!result || result === "EvalScript error." || result.startsWith("Error")) {
      setStatus("Erro ao buscar efeitos", "error");
      log("Erro: " + result, "err");
      return;
    }

    try {
      const effects = JSON.parse(result);
      const payload = {
        version:          1,
        exported_at:      Date.now() / 1000,
        premiere_version: cs.getHostEnvironment().appVersion,
        effects:          effects,
      };

      writeSafe(EFFECTS_FILE, JSON.stringify(payload, null, 2));
      updateCount("count-effects", effects.length);
      setStatus("Conectado — " + effects.length + " efeitos", "ok");
      log("✓ " + effects.length + " efeitos exportados", "ok");

    } catch (e) {
      setStatus("Erro ao processar lista", "error");
      log("Erro JSON: " + e.message, "err");
    }
  });
}

// ─── 2. Exportar presets do usuário ──────────────────────────────────────────

function exportPresets() {
  const presetPath = findPresetFile();
  if (!presetPath) {
    log("Arquivo de presets não encontrado", "warn");
    return;
  }

  // Só re-parseia se o arquivo mudou
  try {
    const mtime = fs.statSync(presetPath).mtimeMs;
    if (mtime === presetFileMtime && fs.existsSync(PRESETS_FILE)) {
      log("Presets sem alteração — usando cache");
      return;
    }
    presetFileMtime = mtime;
  } catch(e) {}

  log("Parseando presets de " + presetPath + "...");

  try {
    function normName(str) {
      return String(str || "").toLowerCase().replace(/\s+/g, " ").trim();
    }

    function canonicalEffectName(str) {
      return normName(str)
        .replace(/\((legacy|obsolete|obsoleto|legado)\)/g, "")
        .replace(/\blegacy\b/g, "")
        .replace(/\bobsolete\b/g, "")
        .replace(/[()]/g, "")
        .replace(/\s+/g, " ")
        .trim();
    }

    function legacyEffectAlias(displayName, matchName) {
      const normalizedMatch = normName(matchName);
      const aliasByMatch = {
        "ae.adbe motion blur": "Directional Blur (Legacy)",
        "ae.adbe gaussian blur 2": "Gaussian Blur (Legacy)",
        "ae.adbe mosaic": "Mosaic (Legacy)"
      };
      return aliasByMatch[normalizedMatch] || "";
    }

    function loadAvailableEffects() {
      try {
        if (!fs.existsSync(EFFECTS_FILE)) return {};
        const payload = JSON.parse(fs.readFileSync(EFFECTS_FILE, "utf8"));
        const effects = payload && payload.effects ? payload.effects : [];
        const map = {};
        for (const fx of effects) {
          if (fx && fx.name) map[fx.name] = true;
        }
        return map;
      } catch (e) {
        return {};
      }
    }

    function buildPresetEffectMeta(displayName, matchName, isAudio, availableEffects) {
      const candidates = [];
      const addCandidate = (name) => {
        if (!name) return;
        if (candidates.indexOf(name) === -1) candidates.push(name);
      };

      const alias = !isAudio ? legacyEffectAlias(displayName, matchName) : "";
      if (alias) addCandidate(alias);
      addCandidate(displayName);
      if (matchName && normName(matchName) !== normName(displayName)) addCandidate(matchName);

      let resolvedEffectName = "";
      for (const candidate of candidates) {
        if (availableEffects[candidate]) {
          resolvedEffectName = candidate;
          break;
        }
      }

      return {
        isLegacy: !!(
          (!isAudio && alias) ||
          /\blegacy\b/i.test(displayName || "") ||
          /\blegacy\b/i.test(resolvedEffectName || "")
        ),
        legacyAlias: alias,
        resolvedEffectName: resolvedEffectName,
        lookupCandidates: candidates
      };
    }

    const availableEffects = loadAvailableEffects();
    const xml     = fs.readFileSync(presetPath, "utf8");
    const parser  = new DOMParser();
    const doc     = parser.parseFromString(xml, "text/xml");

    // Constrói índice ObjectID → elemento
    const index = {};
    for (const el of doc.querySelectorAll("[ObjectID]")) {
      index[el.getAttribute("ObjectID")] = el;
    }

    // Encontra o BinTreeItem raiz com Name="Presets"
    let rootBin = null;
    for (const bin of doc.querySelectorAll("BinTreeItem")) {
      const nameEl = bin.querySelector("TreeItemBase > Name");
      if (nameEl && nameEl.textContent.trim() === "Presets") {
        rootBin = bin;
        break;
      }
    }

    if (!rootBin) {
      log("Pasta Presets não encontrada no arquivo", "warn");
      return;
    }

    const presets = [];

    // Percorre a árvore recursivamente
    function getText(el) {
      return el ? (el.textContent || "").trim() : "";
    }

    function traverse(binEl, pathParts) {
      const items = binEl.querySelectorAll(":scope > Items > Item");
      for (const item of items) {
        const ref = item.getAttribute("ObjectRef");
        const el  = index[ref];
        if (!el) continue;

        const tag = el.tagName;

        if (tag === "BinTreeItem") {
          const nameEl = el.querySelector("TreeItemBase > Name");
          const folderName = getText(nameEl) || "?";
          traverse(el, [...pathParts, folderName]);

        } else if (tag === "TreeItem") {
          const nameEl    = el.querySelector("TreeItemBase > Name");
          const presetName = getText(nameEl) || "?";

          const dataRef  = el.querySelector("TreeItemBase > Data");
          const dataId   = dataRef ? dataRef.getAttribute("ObjectRef") : null;
          const dataEl   = dataId ? index[dataId] : null;
          if (!dataEl) continue;

          const filterPresets = [];
          for (const fp of dataEl.querySelectorAll("FilterPresets > FilterPreset")) {
            const fpRef = fp.getAttribute("ObjectRef");
            const fpEl  = index[fpRef];
            if (!fpEl) continue;

            const matchName  = fpEl.querySelector("FilterMatchName");
            const compRef    = fpEl.querySelector("Component");
            const compId     = compRef ? compRef.getAttribute("ObjectRef") : null;
            const compEl     = compId ? index[compId] : null;
            const mediaType  = fpEl.querySelector("MediaType");

            if (!compEl) continue;

            const displayName = compEl.querySelector("DisplayName");
            const params      = [];

            for (const param of compEl.querySelectorAll("Params > Param")) {
              const paramRef = param.getAttribute("ObjectRef");
              const paramEl  = index[paramRef];
              if (!paramEl) continue;

              const paramName = paramEl.querySelector("Name");
              const startKF   = paramEl.querySelector("StartKeyframe");
              const isVarying = paramEl.querySelector("IsTimeVarying");
              const keyframes = paramEl.querySelector("Keyframes");
              const currentValueEl = paramEl.querySelector("CurrentValue");
              const controlTypeEl  = paramEl.querySelector("ParameterControlType");
              const lowerBoundEl   = paramEl.querySelector("LowerBound");
              const upperBoundEl   = paramEl.querySelector("UpperBound");

              let value = null;
              const startKFText = getText(startKF);
              if (startKFText) {
                const parts = startKFText.split(",");
                if (parts.length > 1) value = parts[1].trim();
              }

              let kfData = null;
              const kfText = getText(keyframes);
              if (getText(isVarying) === "true" && kfText) {
                kfData = kfText;
              }

              const pidEl = paramEl.querySelector("ParameterID");

              // Parâmetros sem nome — mapeia pelo ParameterID conhecido
              let pName = getText(paramName);
              const pId = getText(pidEl);
              const paramIndex = getText(param.getAttribute("Index"));
              const knownNames = {
                "11": "Uniform Scale",
                "9":  "Use Composition's Shutter Angle",
              };
              if (!pName && knownNames[pId]) pName = knownNames[pId];

              params.push({
                name:         pName,
                value:        value,
                keyframes:    kfData,
                paramId:      pId,
                paramIndex:   param.getAttribute("Index"),
                controlType:  getText(controlTypeEl),
                startKeyframe:getText(startKF),
                currentValue: getText(currentValueEl),
                lowerBound:   getText(lowerBoundEl),
                upperBound:   getText(upperBoundEl),
                xmlTag:       paramEl.tagName || "",
              });
            }

            const isAudio = getText(mediaType) === "80b8e3d5-6dca-4195-aefb-cb5f407ab009";
            const effectMeta = buildPresetEffectMeta(
              getText(displayName),
              getText(matchName),
              isAudio,
              availableEffects
            );

            filterPresets.push({
              matchName:   getText(matchName),
              displayName: getText(displayName),
              isAudio:     isAudio,
              isLegacy:    effectMeta.isLegacy,
              legacyAlias: effectMeta.legacyAlias,
              resolvedEffectName: effectMeta.resolvedEffectName,
              lookupCandidates: effectMeta.lookupCandidates,
              params:      params,
            });
          }

          presets.push({
            name:          presetName,
            category:      pathParts.join(" > "),
            type:          "preset",
            filterPresets: filterPresets,
          });
        }
      }
    }

    traverse(rootBin, []);

    const payload = {
      version:    1,
      exported_at: Date.now() / 1000,
      presets:    presets,
    };

    writeSafe(PRESETS_FILE, JSON.stringify(payload, null, 2));
    log("✓ " + presets.length + " presets exportados", "ok");

  } catch(e) {
    log("Erro ao parsear presets: " + e.message, "err");
  }
}

// ——— 2b. Exportar itens do projeto ————————————————————————————————————————————————

function exportProjectItems(reason) {
  if (projectItemsRefreshPending) return;
  projectItemsRefreshPending = true;

  log("Exportando itens do projeto" + (reason ? " (" + reason + ")" : "") + "...");

  evalHostScript("getProjectItemsListSafe()", function(result) {
    projectItemsRefreshPending = false;
    if (!result || result === "EvalScript error." || result.indexOf("Error") === 0) {
      log("Erro ao exportar itens do projeto: " + result, "err");
      return;
    }

    try {
      const items = JSON.parse(result);
      const payload = {
        version: 1,
        exported_at: Date.now() / 1000,
        items: items,
      };

      writeSafe(PROJECT_ITEMS_FILE, JSON.stringify(payload, null, 2));
      lastProjectItemsRefreshAt = Date.now();
      log("✓ " + items.length + " itens do projeto exportados", "ok");
    } catch (e) {
      log("Erro JSON em itens do projeto: " + e.message, "err");
    }
  });
}

function exportSequences(reason) {
  log("Exportando sequências" + (reason ? " (" + reason + ")" : "") + "...");

  evalHostScript("getSequencesListSafe()", function(result) {
    if (!result || result === "EvalScript error." || result.indexOf("Error") === 0) {
      log("Erro ao exportar sequências: " + result, "err");
      return;
    }

    try {
      const sequences = JSON.parse(result);
      const payload = {
        version: 1,
        exported_at: Date.now() / 1000,
        sequences: sequences,
      };

      writeSafe(SEQUENCES_FILE, JSON.stringify(payload, null, 2));
      log("✓ " + sequences.length + " sequência(s) exportada(s)", "ok");
    } catch (e) {
      log("Erro JSON em sequências: " + e.message, "err");
    }
  });
}

function exportFavorites(reason) {
  log("Exportando favoritos" + (reason ? " (" + reason + ")" : "") + "...");

  evalHostScript("getTemplateFavoritesListSafe()", function(result) {
    if (!result || result === "EvalScript error." || result.indexOf("Error") === 0) {
      log("Erro ao exportar favoritos: " + result, "err");
      return;
    }

    try {
      const payload = JSON.parse(result);
      if (!payload || !payload.rootFound) {
        return;
      }

      writeSafe(FAVORITES_FILE, JSON.stringify({
        version: 1,
        exported_at: Date.now() / 1000,
        sourceProjectPath: payload.sourceProjectPath || "",
        items: payload.items || [],
      }, null, 2));
      log("✓ " + ((payload.items || []).length) + " favorito(s) exportado(s)", "ok");
    } catch (e) {
      log("Erro JSON em favoritos: " + e.message, "err");
    }
  });
}

function maybeRefreshProjectItems() {
  const now = Date.now();
  if (projectItemsRefreshPending) return;

  if (now - lastProjectIdentityCheckAt >= PROJECT_IDENTITY_CHECK_INTERVAL_MS) {
    lastProjectIdentityCheckAt = now;
    evalHostScript("getProjectIdentity()", function(identityJSON) {
      if (identityJSON === "EvalScript error.") return;

      const normalized = identityJSON || "";
      if (normalized !== lastProjectIdentity) {
        lastProjectIdentity = normalized;
        exportProjectItems("projeto alterado");
        exportFavorites("projeto alterado");
        exportSequences("projeto alterado");
        return;
      }

      if (now - lastProjectItemsRefreshAt >= PROJECT_ITEMS_REFRESH_INTERVAL_MS) {
        exportProjectItems("refresh periódico");
        exportFavorites("refresh periódico");
        exportSequences("refresh periódico");
      }
    });
    return;
  }

  if (now - lastProjectItemsRefreshAt >= PROJECT_ITEMS_REFRESH_INTERVAL_MS) {
    exportProjectItems("refresh periódico");
    exportFavorites("refresh periódico");
    exportSequences("refresh periódico");
  }
}

// ─── 3. Polling ───────────────────────────────────────────────────────────────

function startPolling() {
  if (pollingActive) return;
  pollingActive = true;

  function poll() {
    if (!pollingActive) return;

    try {
      evalHostScript("getSelectionJSON()", function(selJSON) {
        if (selJSON && selJSON !== "EvalScript error.") {
          lastSelectionJSON  = selJSON;
          selectionTimestamp = Date.now();
          if (selJSON !== lastSelectionWrite) {
            writeSafe(SELECTION_FILE, selJSON);
            lastSelectionWrite = selJSON;
          }
        }
      });

      maybeRefreshProjectItems();

      if (fs.existsSync(CMD_FILE)) {
        const raw = fs.readFileSync(CMD_FILE, "utf8");
        const cmd = JSON.parse(raw);

        if (cmd.status === "pending" && cmd.timestamp !== lastCmdTime) {
          lastCmdTime = cmd.timestamp;

          const selectionAge = Date.now() - selectionTimestamp;
          if (selectionAge > 10000) lastSelectionJSON = "[]";

          if (cmd.command === "applyEffect") {
            applyEffect(cmd);
          } else if (cmd.command === "applyPreset") {
            applyPreset(cmd);
          } else if (cmd.command === "insertProjectItem") {
            insertProjectItem(cmd);
          } else if (cmd.command === "insertGenericItem") {
            insertGenericItem(cmd);
          } else if (cmd.command === "insertFavoriteItem") {
            insertFavoriteItem(cmd);
          } else if (cmd.command === "exportEffects") {
            markCmdStatus("processing");
            exportEffects();
            exportPresets();
            exportProjectItems("manual");
            exportFavorites("manual");
            exportSequences("manual");
            markCmdStatus("done");
          } else if (cmd.command === "diagnose") {
            markCmdStatus("processing");
            evalHostScript("diagnose()", function(result) {
      writeSafe(LOG_FILE, result);
              log("Diagnóstico gravado", "ok");
              markCmdStatus("done");
            });
          } else if (cmd.command === "clearBridge") {
            markCmdStatus("done");
            try { fs.unlinkSync(CMD_FILE); } catch(e) {}
            clearLogFiles();
            log("Bridge e logs limpos", "ok");
          }
        }
      }
    } catch (e) { /* ignora erros de leitura */ }

    setTimeout(poll, 300);
  }

  poll();
  log("Polling iniciado (300ms)", "ok");
}

// ─── 4. Aplicar efeito ────────────────────────────────────────────────────────

function applyEffect(cmd) {
  const effectName = cmd.effect;
  const effectType = cmd.type || "video";

  log("→ Aplicando efeito: " + effectName, "apply");
  setStatus("Aplicando: " + effectName, "waiting");
  markCmdStatus("processing");

  const script = 'applyEffectWithSelection(' +
    JSON.stringify(effectName) + ', ' +
    JSON.stringify(effectType) + ', ' +
    JSON.stringify(lastSelectionJSON) + ')';

  evalHostScript(script, function(result) {
    if (result === "ok") {
      appliedCount++;
      updateCount("count-applied", appliedCount);
      setStatus("Conectado", "ok");
      log("✓ Aplicado: " + effectName, "ok");
      markCmdStatus("done");
    } else if (result === "no_selection") {
      setStatus("Sem clipes selecionados", "waiting");
      log("⚠ Nenhum clipe selecionado", "warn");
      markCmdStatus("error_no_selection");
    } else if (result === "not_found") {
      setStatus("Efeito não encontrado", "waiting");
      log("⚠ Efeito não encontrado: " + effectName, "warn");
      markCmdStatus("error_not_found");
    } else {
      setStatus("Erro ao aplicar", "error");
      log("Erro: " + result, "err");
      markCmdStatus("error");
    }
  });
}

// ─── 5. Aplicar preset ────────────────────────────────────────────────────────

function applyPreset(cmd) {
  const presetName      = cmd.effect;
  const filterPresetsJSON = cmd.filterPresetsJSON;

  log("→ Aplicando preset: " + presetName, "apply");
  setStatus("Aplicando preset: " + presetName, "waiting");
  markCmdStatus("processing");

  const script = 'applyPresetWithSelection(' +
    JSON.stringify(filterPresetsJSON) + ', ' +
    JSON.stringify(lastSelectionJSON) + ')';

  evalHostScript(script, function(result) {
    if (result === "ok") {
      appliedCount++;
      updateCount("count-applied", appliedCount);
      setStatus("Conectado", "ok");
      log("✓ Preset aplicado: " + presetName, "ok");
      markCmdStatus("done");
    } else if (result === "no_selection") {
      setStatus("Sem clipes selecionados", "waiting");
      log("⚠ Nenhum clipe selecionado", "warn");
      markCmdStatus("error_no_selection");
    } else if (result === "partial") {
      setStatus("Aplicado parcialmente", "waiting");
      log("⚠ Preset aplicado com limitações: " + presetName, "warn");
      markCmdStatus("done");
    } else {
      setStatus("Erro ao aplicar preset", "error");
      log("Erro: " + result, "err");
      markCmdStatus("error");
    }
  });
}

// ——— 6. Inserir item do projeto ————————————————————————————————————————————————

function insertProjectItem(cmd) {
  const itemName = cmd.itemName;
  const nodeId   = cmd.nodeId;

  log("→ Inserindo item: " + itemName, "apply");
  setStatus("Inserindo: " + itemName, "waiting");
  markCmdStatus("processing");

  const script = 'insertProjectItemAtPlayhead(' +
    JSON.stringify(nodeId) + ', ' +
    JSON.stringify(lastSelectionJSON) + ')';

  evalHostScript(script, function(result) {
    let parsed = null;
    try {
      if (result && result.charAt && result.charAt(0) === "{") {
        parsed = JSON.parse(result);
      }
    } catch (e) {}

    if (parsed && parsed.status === "ok") {
      appliedCount++;
      updateCount("count-applied", appliedCount);
      setStatus("Conectado", "ok");
      log("✓ Item inserido: " + itemName, "ok");
      markCmdStatus("done");
    } else if (result === "ok") {
      appliedCount++;
      updateCount("count-applied", appliedCount);
      setStatus("Conectado", "ok");
      log("✓ Item inserido: " + itemName, "ok");
      markCmdStatus("done");
    } else if (result === "not_found") {
      setStatus("Item não encontrado", "waiting");
      log("⚠ Item do projeto não encontrado: " + itemName, "warn");
      markCmdStatus("error_not_found");
    } else if (result === "no_sequence") {
      setStatus("Sem sequência ativa", "waiting");
      log("⚠ Nenhuma sequência ativa para inserir item", "warn");
      markCmdStatus("error_no_sequence");
    } else {
      setStatus("Erro ao inserir item", "error");
      log("Erro: " + result, "err");
      markCmdStatus("error");
    }
  });
}

function insertGenericItem(cmd) {
  const itemName = cmd.itemName;
  const genericKey = cmd.genericKey;

  log("→ Inserindo genérico: " + itemName, "apply");
  setStatus("Inserindo: " + itemName, "waiting");
  markCmdStatus("processing");

  const script = 'insertGenericItemAtPlayhead(' +
    JSON.stringify(genericKey) + ', ' +
    JSON.stringify(lastSelectionJSON) + ')';

  evalHostScript(script, function(result) {
    let parsed = null;
    try {
      if (result && result.charAt && result.charAt(0) === "{") {
        parsed = JSON.parse(result);
      }
    } catch (e) {}

    if (parsed && parsed.status === "ok") {
      appliedCount++;
      updateCount("count-applied", appliedCount);
      setStatus("Conectado", "ok");
      log("✓ Genérico inserido: " + itemName, "ok");
      markCmdStatus("done");
      exportProjectItems("genérico criado");
    } else if (result === "ok") {
      appliedCount++;
      updateCount("count-applied", appliedCount);
      setStatus("Conectado", "ok");
      log("✓ Genérico inserido: " + itemName, "ok");
      markCmdStatus("done");
      exportProjectItems("genérico criado");
    } else if (result === "template_missing") {
      setStatus("Template ausente", "waiting");
      log("⚠ Template de Adjustment Layer não configurado", "warn");
      markCmdStatus("error_template_missing");
    } else if (result === "create_failed") {
      setStatus("Falha ao criar item", "error");
      log("⚠ Premiere não conseguiu criar este item genérico", "warn");
      markCmdStatus("error_create_failed");
    } else if (result === "not_found") {
      setStatus("Item não encontrado", "waiting");
      log("⚠ Item genérico não encontrado após criação/importação: " + itemName, "warn");
      markCmdStatus("error_not_found");
    } else if (result === "no_sequence") {
      setStatus("Sem sequência ativa", "waiting");
      log("⚠ Nenhuma sequência ativa para inserir item", "warn");
      markCmdStatus("error_no_sequence");
    } else {
      setStatus("Erro ao inserir item", "error");
      log("Erro: " + result, "err");
      markCmdStatus("error");
    }
  });
}

function insertFavoriteItem(cmd) {
  const itemName = cmd.itemName;
  const mediaPath = cmd.mediaPath || "";
  const sequenceID = cmd.sequenceID || "";
  const favoriteType = cmd.favoriteType || "";
  const sourceProjectPath = cmd.sourceProjectPath || "";

  log("→ Inserindo favorito: " + itemName, "apply");
  setStatus("Inserindo: " + itemName, "waiting");
  markCmdStatus("processing");

  const script = 'insertFavoriteItemAtPlayhead(' +
    JSON.stringify(itemName) + ', ' +
    JSON.stringify(mediaPath) + ', ' +
    JSON.stringify(sequenceID) + ', ' +
    JSON.stringify(favoriteType) + ', ' +
    JSON.stringify(sourceProjectPath) + ', ' +
    JSON.stringify(lastSelectionJSON) + ')';

  evalHostScript(script, function(result) {
    if (result === "ok") {
      appliedCount++;
      updateCount("count-applied", appliedCount);
      setStatus("Conectado", "ok");
      log("✓ Favorito inserido: " + itemName, "ok");
      markCmdStatus("done");
      exportProjectItems("favorito inserido");
    } else if (result === "template_missing") {
      setStatus("Template ausente", "waiting");
      log("⚠ Projeto template não configurado para favoritos", "warn");
      markCmdStatus("error_template_missing");
    } else if (result === "create_failed") {
      setStatus("Falha ao importar favorito", "error");
      log("⚠ Premiere não conseguiu importar este favorito", "warn");
      markCmdStatus("error_create_failed");
    } else if (result === "not_supported") {
      setStatus("Favorito não suportado", "waiting");
      log("⚠ Este favorito ainda não é suportado pela extensão", "warn");
      markCmdStatus("error_not_supported");
    } else if (result === "not_found") {
      setStatus("Favorito não encontrado", "waiting");
      log("⚠ Favorito não encontrado: " + itemName, "warn");
      markCmdStatus("error_not_found");
    } else if (result === "no_sequence") {
      setStatus("Sem sequência ativa", "waiting");
      log("⚠ Nenhuma sequência ativa para inserir favorito", "warn");
      markCmdStatus("error_no_sequence");
    } else {
      setStatus("Erro ao inserir favorito", "error");
      log("Erro: " + result, "err");
      markCmdStatus("error");
    }
  });
}

function markCmdStatus(status) {
  try {
    if (fs.existsSync(CMD_FILE)) {
      const cmd = JSON.parse(fs.readFileSync(CMD_FILE, "utf8"));
      cmd.status = status;
      writeSafe(CMD_FILE, JSON.stringify(cmd, null, 2));
    }
  } catch (e) {
    fileLog("Erro em markCmdStatus: " + e.message);
  }
}

// ─── Funções públicas ─────────────────────────────────────────────────────────

function clearBridge() {
  try {
    if (fs.existsSync(CMD_FILE)) fs.unlinkSync(CMD_FILE);
    clearLogFiles();
    log("Bridge e logs limpos", "ok");
  } catch (e) {
    log("Erro ao limpar: " + e.message, "err");
  }
}

function runDiagnose() {
  evalHostScript("diagnose()", function(result) {
    writeSafe(LOG_FILE, result);
    log("Diagnóstico gravado em data/premiere_diagnose.txt", "ok");
  });
}

// ─── Inicialização ────────────────────────────────────────────────────────────

function init() {
  trimWorkerLogOnStartup();
  log("Effect Palette " + (IS_DEBUG_PANEL ? "debug panel" : "worker") + " carregado");

  try {
    if (fs.existsSync(CMD_FILE)) {
      fs.unlinkSync(CMD_FILE);
      log("Bridge anterior limpo");
    }
  } catch (e) {}

  setTimeout(function() {
    exportEffects();
    exportPresets();
    exportProjectItems("startup");
    exportFavorites("startup");
    exportSequences("startup");
    startPolling();
  }, 1500);
}

init();
