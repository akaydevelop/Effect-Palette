"""
Premiere Pro Effect Palette
Atalho: Ctrl+Espaço — abre a paleta de efeitos

A lista de efeitos é lida dinamicamente de um JSON exportado pela CEP Extension,
incluindo plugins de terceiros (Boris FX, Maxon, etc.) e presets customizados.
"""

import tkinter as tk
import threading
import json
import os
import time
import ctypes
from pathlib import Path
from tkinter import messagebox
from pynput import keyboard

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False
    print("[Aviso] pygetwindow não instalado — atalho funcionará em qualquer janela")

# ─── Configurações ────────────────────────────────────────────────────────────

TEMP = Path(os.environ.get("TEMP", "C:/Temp"))
APPDATA = Path(os.environ.get("APPDATA", ""))

# Pasta de dados dentro da extensão CEP — mesmo lugar que o bridge.js grava
EXT_DATA = APPDATA / "Adobe" / "CEP" / "extensions" / "EffectPalette" / "data"

# JSON gravado pela CEP Extension com todos os efeitos do Premiere
EFFECTS_FILE = EXT_DATA / "premiere_effects.json"

# JSON com presets do usuário parseados do .prfpset
PRESETS_FILE = EXT_DATA / "premiere_presets.json"

# JSON com itens do projeto exportados do Premiere
PROJECT_ITEMS_FILE = EXT_DATA / "premiere_project_items.json"

# JSON de comando (lido pela CEP Extension para aplicar efeito)
BRIDGE_FILE  = EXT_DATA / "premiere_cmd.json"
SELECTION_FILE = EXT_DATA / "current_selection.json"

# Intervalo de verificação de mudanças no arquivo de efeitos (segundos)
WATCH_INTERVAL = 3.0

# Efeitos de fallback — usados quando o Premiere não está aberto
FALLBACK_EFFECTS = [
    {"name": "Lumetri Color",       "category": "Color"},
    {"name": "Gaussian Blur",       "category": "Blur"},
    {"name": "Warp Stabilizer",     "category": "Distort"},
    {"name": "Ultra Key",           "category": "Keying"},
    {"name": "Parametric EQ",       "category": "Audio"},
    {"name": "Multiband Compressor","category": "Audio"},
]

GENERIC_ITEMS = [
    {"name": "Adjustment Layer", "category": "Genéricos", "type": "generic_item", "genericKey": "adjustment_layer"},
    {"name": "Bars and Tone", "category": "Genéricos", "type": "generic_item", "genericKey": "bars_and_tone"},
    {"name": "Black Video", "category": "Genéricos", "type": "generic_item", "genericKey": "black_video"},
    {"name": "Color Matte", "category": "Genéricos", "type": "generic_item", "genericKey": "color_matte"},
    {"name": "Transparent Video", "category": "Genéricos", "type": "generic_item", "genericKey": "transparent_video"},
]

# ─── Cores da UI ──────────────────────────────────────────────────────────────

BG         = "#0F0F11"
BG2        = "#1A1A1F"
BORDER     = "#2A2A35"
TEXT       = "#E8E8F0"
TEXT_MUTED = "#6B6B80"
ACCENT     = "#5B6BF8"
SEL_BG     = "#1E2040"
GREEN      = "#3DD68C"
ORANGE     = "#F5A623"

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    try:
        USER32 = ctypes.windll.user32
        SW_SHOWNORMAL = 1
        SW_RESTORE = 9
    except Exception:
        USER32 = None
        SW_SHOWNORMAL = 1
        SW_RESTORE = 9
else:
    USER32 = None
    SW_SHOWNORMAL = 1
    SW_RESTORE = 9


# ─── Carregamento dinâmico de efeitos ─────────────────────────────────────────

class EffectsLoader:
    """
    Lê e monitora o arquivo premiere_effects.json gerado pela CEP Extension.

    Formato esperado do JSON:
    {
      "version": 1,
      "exported_at": 1712345678.0,
      "premiere_version": "24.0",
      "effects": [
        {"name": "Gaussian Blur",  "category": "Blur",  "type": "video"},
        {"name": "Boris FX Mocha", "category": "Boris", "type": "video"},
        {"name": "My LUT Preset",  "category": "Presets","type": "preset"},
        ...
      ]
    }
    """

    def __init__(self):
        self._effects: list = []
        self._presets: list = []
        self._project_items: list = []
        self._generic_items: list = list(GENERIC_ITEMS)
        self._all: list = []
        self._last_mtime: float = 0
        self._last_preset_mtime: float = 0
        self._last_project_items_mtime: float = 0
        self._lock = threading.Lock()
        self._source = "fallback"
        self._load()

    def _load(self):
        """Carrega efeitos + presets dos arquivos ou usa fallback."""
        self._last_preset_mtime = 0
        self._last_project_items_mtime = 0
        if not EFFECTS_FILE.exists():
            with self._lock:
                self._effects = FALLBACK_EFFECTS
                self._presets = []
                self._project_items = []
                self._generic_items = list(GENERIC_ITEMS)
                self._all = FALLBACK_EFFECTS + list(GENERIC_ITEMS)
                self._source = "fallback"
            return

        try:
            mtime = EFFECTS_FILE.stat().st_mtime
            with open(EFFECTS_FILE, encoding="utf-8") as f:
                data = json.load(f)

            effects = data.get("effects", [])
            if not effects:
                raise ValueError("Lista vazia")

            # Carrega presets se disponível
            presets = []
            project_items = []
            if PRESETS_FILE.exists():
                try:
                    pmtime = PRESETS_FILE.stat().st_mtime
                    with open(PRESETS_FILE, encoding="utf-8") as pf:
                        pdata = json.load(pf)
                    # Converte para o mesmo formato dos efeitos
                    for p in pdata.get("presets", []):
                        presets.append({
                            "name":          p["name"],
                            "category":      p.get("category", "Presets"),
                            "type":          "preset",
                            "filterPresets": p.get("filterPresets", []),
                        })
                    self._last_preset_mtime = pmtime
                    print(f"[Presets] {len(presets)} carregados")
                except Exception as e:
                    print(f"[Presets] Erro ao ler: {e}")

            if PROJECT_ITEMS_FILE.exists():
                try:
                    imtime = PROJECT_ITEMS_FILE.stat().st_mtime
                    with open(PROJECT_ITEMS_FILE, encoding="utf-8") as inf:
                        idata = json.load(inf)
                    for item in idata.get("items", []):
                        project_items.append({
                            "name":       item["name"],
                            "category":   item.get("category", "Projeto"),
                            "type":       "project_item",
                            "nodeId":     item.get("nodeId", ""),
                            "itemType":   item.get("itemType", ""),
                            "isSequence": item.get("isSequence", False),
                            "treePath":   item.get("treePath", ""),
                            "mediaPath":  item.get("mediaPath", ""),
                        })
                    self._last_project_items_mtime = imtime
                    print(f"[Projeto] {len(project_items)} itens carregados")
                except Exception as e:
                    print(f"[Projeto] Erro ao ler: {e}")

            with self._lock:
                self._effects = effects
                self._presets = presets
                self._project_items = project_items
                self._generic_items = list(GENERIC_ITEMS)
                self._all     = effects + presets + project_items + list(GENERIC_ITEMS)
                self._last_mtime = mtime
                self._source = "premiere"

            print(f"[Efeitos] {len(effects)} efeitos + {len(presets)} presets + {len(project_items)} itens do projeto")

        except Exception as e:
            print(f"[Efeitos] Erro ao ler arquivo: {e} — usando fallback")
            with self._lock:
                self._effects = FALLBACK_EFFECTS
                self._presets = []
                self._project_items = []
                self._generic_items = list(GENERIC_ITEMS)
                self._all = FALLBACK_EFFECTS + list(GENERIC_ITEMS)
                self._source = "fallback"

    def check_for_updates(self) -> bool:
        """Retorna True se algum arquivo mudou e foi recarregado."""
        if not EFFECTS_FILE.exists():
            if self._source != "fallback":
                with self._lock:
                    self._effects = FALLBACK_EFFECTS
                    self._presets = []
                    self._project_items = []
                    self._generic_items = list(GENERIC_ITEMS)
                    self._all = FALLBACK_EFFECTS + list(GENERIC_ITEMS)
                    self._source = "fallback"
                return True
            return False

        try:
            mtime  = EFFECTS_FILE.stat().st_mtime
            pmtime = PRESETS_FILE.stat().st_mtime if PRESETS_FILE.exists() else 0
            imtime = PROJECT_ITEMS_FILE.stat().st_mtime if PROJECT_ITEMS_FILE.exists() else 0
            if mtime != self._last_mtime or pmtime != self._last_preset_mtime or imtime != self._last_project_items_mtime:
                self._load()
                return True
        except Exception:
            pass
        return False

    def get_all(self) -> list:
        with self._lock:
            return list(self._all)

    def get_by_type(self, type_filter: str) -> list:
        """Retorna itens filtrados por tipo: 'video', 'audio', 'preset', 'project_item', 'generic_item'."""
        with self._lock:
            return [e for e in self._all if e.get("type") == type_filter]

    def search(self, query: str, type_filter: str = None) -> list:
        """Busca com prioridade: começa com > contém, case-insensitive."""
        q = query.lower().strip()
        base = self.get_by_type(type_filter) if type_filter else self.get_all()
        if not q:
            return base

        starts   = [e for e in base if e["name"].lower().startswith(q)]
        contains = [e for e in base if q in e["name"].lower() and e not in starts]
        return starts + contains

    @property
    def source(self) -> str:
        return self._source

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._effects)

    @property
    def preset_count(self) -> int:
        with self._lock:
            return len(self._presets)

    @property
    def project_item_count(self) -> int:
        with self._lock:
            return len(self._project_items)

    @property
    def generic_item_count(self) -> int:
        with self._lock:
            return len(self._generic_items)

    @property
    def categories(self) -> list:
        with self._lock:
            seen = []
            for e in self._effects:
                cat = e.get("category", "")
                if cat and cat not in seen:
                    seen.append(cat)
            return seen


# ─── Bridge: envia comando para o Premiere ────────────────────────────────────

# ─── Bridge: envia comando para o Premiere ────────────────────────────────────

def write_safe(file_path: Path, content: str):
    """Grava em arquivo temporário e renomeia — elimina race conditions."""
    tmp = file_path.with_suffix(file_path.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(file_path)  # atômico no Windows e Linux
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def send_command(effect: dict):
    if effect.get("type") == "preset":
        payload = {
            "command":           "applyPreset",
            "effect":            effect["name"],
            "filterPresetsJSON": json.dumps(effect.get("filterPresets", [])),
            "timestamp":         time.time(),
            "status":            "pending",
        }
    elif effect.get("type") == "project_item":
        payload = {
            "command":   "insertProjectItem",
            "itemName":  effect["name"],
            "nodeId":    effect.get("nodeId", ""),
            "itemType":  effect.get("itemType", ""),
            "timestamp": time.time(),
            "status":    "pending",
        }
    elif effect.get("type") == "generic_item":
        payload = {
            "command":    "insertGenericItem",
            "itemName":   effect["name"],
            "genericKey": effect.get("genericKey", ""),
            "timestamp":  time.time(),
            "status":     "pending",
        }
    else:
        payload = {
            "command":   "applyEffect",
            "effect":    effect["name"],
            "category":  effect.get("category", ""),
            "type":      effect.get("type", "video"),
            "timestamp": time.time(),
            "status":    "pending",
        }
    BRIDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_safe(BRIDGE_FILE, json.dumps(payload, indent=2))
    print(f"[Bridge] Enviado: {effect['name']}")


def preset_has_keyframes(effect: dict) -> bool:
    if effect.get("type") != "preset":
        return False

    for fp in effect.get("filterPresets", []):
        for param in fp.get("params", []):
            if param.get("keyframes"):
                return True
    return False


def load_current_selection() -> list:
    if not SELECTION_FILE.exists():
        return []

    try:
        with open(SELECTION_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def selection_has_infinite_warning_targets(selection: list) -> bool:
    for item in selection:
        if not isinstance(item, dict):
            continue
        if item.get("isAudio"):
            continue
        if item.get("isAdjustmentLike") or item.get("isImageLike"):
            return True
    return False


def premiere_is_focused() -> bool:
    """Retorna True se o Premiere Pro estiver na janela ativa."""
    if not HAS_PYGETWINDOW:
        return True
    try:
        active = gw.getActiveWindow()
        if active is None:
            return False
        return "Adobe Premiere" in active.title
    except Exception:
        return True


def send_debug_command(command: str):
    """Envia um comando de controle ao worker (exportEffects, diagnose, clearBridge)."""
    payload = {
        "command":   command,
        "timestamp": time.time(),
        "status":    "pending",
    }
    BRIDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_safe(BRIDGE_FILE, json.dumps(payload, indent=2))
    print(f"[Bridge] Comando enviado: {command}")


# ─── UI ───────────────────────────────────────────────────────────────────────

class EffectPalette:
    def __init__(self):
        self.loader = EffectsLoader()
        self.root   = None
        self.is_open = False
        self._focus_primed = False
        self._active_category = None
        self._watch_job = None
        self._build()
        self._start_file_watcher()
        self.root.after(0, self._prime_first_show)

    # ── Construção da janela ──────────────────────────────────────────────────

    def _build(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.97)
        self.root.configure(bg=BG)

        outer = tk.Frame(self.root, bg=BORDER, padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg=BG)
        inner.pack(fill="both", expand=True)

        # ── Cabeçalho ──
        header = tk.Frame(inner, bg=BG, padx=18, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="✦  Efeito / Preset",
                 bg=BG, fg=TEXT_MUTED, font=("Segoe UI", 9), anchor="w"
                 ).pack(side="left")
        self.conn_label = tk.Label(header, text="", bg=BG, font=("Segoe UI", 8))
        self.conn_label.pack(side="right")
        self._update_conn_label()

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x")

        # ── Campo de busca ──
        sf = tk.Frame(inner, bg=BG2, padx=16)
        sf.pack(fill="x")
        tk.Label(sf, text="⌕", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 16)).pack(side="left", pady=14)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.entry = tk.Entry(
            sf, textvariable=self.search_var,
            bg=BG2, fg=TEXT, insertbackground=ACCENT,
            relief="flat", font=("Segoe UI", 15),
            highlightthickness=0, bd=0,
        )
        self.entry.pack(side="left", fill="x", expand=True, pady=14, padx=(8, 0))

        # Botão de refresh
        self.refresh_btn = tk.Label(
            sf, text="↺", bg=BG2, fg=TEXT_MUTED,
            font=("Segoe UI", 14), cursor="hand2",
        )
        self.refresh_btn.pack(side="right", padx=(0, 4))
        self.refresh_btn.bind("<Button-1>", lambda e: self._manual_refresh())
        self.refresh_btn.bind("<Enter>",    lambda e: self.refresh_btn.config(fg=ACCENT))
        self.refresh_btn.bind("<Leave>",    lambda e: self.refresh_btn.config(fg=TEXT_MUTED))

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x")

        # ── Filtro por categoria ──
        self.cat_frame = tk.Frame(inner, bg=BG, padx=12, pady=6)
        self.cat_frame.pack(fill="x")
        self._build_category_pills()

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x")

        # ── Lista de resultados ──
        lc = tk.Frame(inner, bg=BG)
        lc.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(
            lc, bg=BG, fg=TEXT,
            selectbackground=SEL_BG, selectforeground="#FFFFFF",
            relief="flat", font=("Segoe UI", 12),
            activestyle="none", highlightthickness=0, borderwidth=0,
            height=8,
        )
        self.listbox.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        sb = tk.Scrollbar(lc, orient="vertical", command=self.listbox.yview, width=4)
        sb.pack(side="right", fill="y", pady=6)
        self.listbox.configure(yscrollcommand=sb.set)

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x")

        # ── Rodapé ──
        footer = tk.Frame(inner, bg=BG, padx=18, pady=8)
        footer.pack(fill="x")
        tk.Label(footer, text="↑↓ navegar   ↵ aplicar   ESC fechar",
                 bg=BG, fg=TEXT_MUTED, font=("Segoe UI", 8), anchor="w"
                 ).pack(side="left")
        self.status_label = tk.Label(footer, text="", bg=BG,
                                     fg=ACCENT, font=("Segoe UI", 8, "bold"))
        self.status_label.pack(side="right")

        # ── Bindings ──
        self.entry.bind("<Escape>",  lambda e: self.hide())
        self.entry.bind("<Control-w>", lambda e: self.hide())
        self.entry.bind("<Return>",  lambda e: self._apply_selected())
        self.entry.bind("<Down>",    lambda e: self._move_selection(1))
        self.entry.bind("<Up>",      lambda e: self._move_selection(-1))
        self.listbox.bind("<Return>",          lambda e: self._apply_selected())
        self.listbox.bind("<Double-Button-1>", lambda e: self._apply_selected())
        self.root.bind("<FocusOut>", self._on_focus_out)

        W, H = 580, 430
        self.root.geometry(f"{W}x{H}")
        self._center_window(W, H)
        self._refresh_list()

    # ── Pills de categoria ────────────────────────────────────────────────────

    def _build_category_pills(self):
        for w in self.cat_frame.winfo_children():
            w.destroy()
        for cat in ["Todos", "Vídeo", "Áudio", "Presets", "Projeto", "Genéricos"]:
            active = (cat == "Todos" and self._active_category is None) or \
                     (cat == self._active_category)
            pill = tk.Label(
                self.cat_frame, text=cat,
                bg=ACCENT if active else BG2,
                fg=TEXT if active else TEXT_MUTED,
                font=("Segoe UI", 8), padx=10, pady=3, cursor="hand2",
            )
            pill.pack(side="left", padx=3)

            def on_click(e, c=cat):
                self._active_category = None if c == "Todos" else c
                self._build_category_pills()
                self._refresh_list()
            pill.bind("<Button-1>", on_click)

    # ── Watcher de arquivo ────────────────────────────────────────────────────

    def _start_file_watcher(self):
        def watch():
            if self.loader.check_for_updates():
                self.root.after(0, self._on_effects_updated)
            self._watch_job = self.root.after(int(WATCH_INTERVAL * 1000), watch)
        self._watch_job = self.root.after(int(WATCH_INTERVAL * 1000), watch)

    def _on_effects_updated(self):
        print(f"[Watcher] Lista atualizada — {self.loader.count} efeitos")
        self._build_category_pills()
        self._refresh_list()
        self._update_conn_label()
        self.status_label.config(text=f"↺ Lista atualizada ({self.loader.count} efeitos)")

    def _manual_refresh(self):
        send_debug_command("exportEffects")
        self.loader.check_for_updates()
        self._build_category_pills()
        self._refresh_list()
        self._update_conn_label()
        self.status_label.config(text="↺ Solicitando atualização ao Premiere...")

    # ── Lista e busca ─────────────────────────────────────────────────────────

    def _get_filtered_effects(self) -> list:
        query = self.search_var.get().strip()
        cat   = self._active_category

        if cat == "Vídeo":
            return self.loader.search(query, type_filter="video")
        elif cat == "Áudio":
            return self.loader.search(query, type_filter="audio")
        elif cat == "Presets":
            return self.loader.search(query, type_filter="preset")
        elif cat == "Projeto":
            return self.loader.search(query, type_filter="project_item")
        elif cat == "Genéricos":
            return self.loader.search(query, type_filter="generic_item")
        else:
            return self.loader.search(query)

    def _refresh_list(self):
        results = self._get_filtered_effects()
        self.listbox.delete(0, "end")
        for e in results:
            is_preset = e.get("type") == "preset"
            is_project_item = e.get("type") == "project_item"
            is_generic_item = e.get("type") == "generic_item"
            icon  = "◈ " if is_preset else ("▣ " if is_project_item else ("◆ " if is_generic_item else "  "))
            cat   = e.get("category", "")
            label = f"{icon}{e['name']}" + (f"  [{cat}]" if cat and not is_preset else "")
            self.listbox.insert("end", label)
        if results:
            self.listbox.selection_set(0)
        q = self.search_var.get().strip()
        self.status_label.config(text=f"{len(results)} resultado(s)" if q else "")

    def _on_search_change(self, *_):
        self._refresh_list()

    # ── Seleção e aplicação ───────────────────────────────────────────────────

    def _move_selection(self, direction):
        cur = self.listbox.curselection()
        idx = max(0, min((cur[0] if cur else -1) + direction, self.listbox.size() - 1))
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(idx)
        self.listbox.see(idx)

    def _apply_selected(self):
        results = self._get_filtered_effects()
        sel = self.listbox.curselection()
        if sel and sel[0] < len(results):
            effect = results[sel[0]]
        elif results:
            effect = results[0]
        else:
            name = self.search_var.get().strip()
            if not name:
                return
            effect = {"name": name, "category": "", "type": "video"}

        if preset_has_keyframes(effect):
            selection = load_current_selection()
            if selection_has_infinite_warning_targets(selection):
                proceed = messagebox.askyesno(
                    "Aviso sobre keyframes",
                    "Este preset possui keyframes e a selecao atual inclui uma Adjustment Layer ou uma imagem.\n\n"
                    "No Premiere, presets animados nesses tipos de layer podem nao funcionar corretamente.\n\n"
                    "Deseja aplicar mesmo assim?",
                    parent=self.root,
                )
                if not proceed:
                    self.status_label.config(text="Aplicacao cancelada")
                    return

        send_command(effect)
        if effect.get("type") in {"project_item", "generic_item"}:
            self.status_label.config(text=f"↳  {effect['name']}")
        else:
            self.status_label.config(text=f"✓  {effect['name']}")
        self.root.update()
        self.root.after(900, self.hide)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _center_window(self, w, h):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{int(sh*0.28)}")

    def _update_conn_label(self):
        if self.loader.source == "premiere":
            self.conn_label.config(
                text=f"● Premiere  {self.loader.count} efeitos  {self.loader.preset_count} presets",
                fg=GREEN)
            if self.loader.project_item_count:
                self.conn_label.config(
                    text=f"● Premiere  {self.loader.count} efeitos  {self.loader.preset_count} presets  {self.loader.project_item_count} itens",
                    fg=GREEN)
        else:
            self.conn_label.config(text="● Offline (fallback)", fg=ORANGE)

    def _on_focus_out(self, event):
        if self.root.winfo_exists():
            self.hide()

    def _force_focus_attempt(self, attempt=0):
        if not self.root.winfo_exists() or not self.is_open:
            return

        try:
            self.root.deiconify()
            self.root.update_idletasks()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            self.entry.focus_force()
            self.entry.icursor("end")
        except Exception:
            pass

        if USER32 is not None:
            try:
                hwnd = int(self.root.winfo_id())
                USER32.ShowWindow(hwnd, SW_RESTORE if attempt == 0 else SW_SHOWNORMAL)
                USER32.BringWindowToTop(hwnd)
                USER32.SetForegroundWindow(hwnd)
                USER32.SetActiveWindow(hwnd)
                USER32.SetFocus(hwnd)
            except Exception:
                pass

        if attempt < 3:
            self.root.after(60 + (attempt * 80), lambda a=attempt + 1: self._force_focus_attempt(a))

    def _restore_borderless(self):
        if not self.root.winfo_exists() or not self.is_open:
            return
        try:
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            self.root.lift()
            self.entry.focus_force()
            self.entry.icursor("end")
        except Exception:
            pass

    def _prime_first_show(self):
        if self._focus_primed or not self.root.winfo_exists():
            return
        try:
            self.root.unbind("<FocusOut>")
            self.root.attributes("-alpha", 0.0)
            self.root.overrideredirect(False)
            self.root.deiconify()
            self.root.update_idletasks()
            self.root.lift()
            self.root.focus_force()
            self.entry.focus_force()
            self.entry.icursor("end")
            self.root.update()
        except Exception:
            pass
        finally:
            try:
                self.root.withdraw()
                self.root.overrideredirect(True)
                self.root.attributes("-alpha", 0.97)
                self.root.bind("<FocusOut>", self._on_focus_out)
            except Exception:
                pass
            self._focus_primed = True

    def show(self):
        if self.is_open:
            return
        self.is_open = True
        self.search_var.set("")
        self._active_category = None
        self._build_category_pills()
        self._refresh_list()
        self.status_label.config(text="")
        self._update_conn_label()

        # Desativa FocusOut temporariamente para não fechar durante a abertura
        self.root.unbind("<FocusOut>")

        try:
            self.root.overrideredirect(False)
        except Exception:
            pass
        self.root.deiconify()
        self.root.update_idletasks()
        self._force_focus_attempt(0)
        self.root.after(120, self._restore_borderless)

        # Reativa FocusOut após a janela estar estável
        self.root.after(500, lambda: self.root.bind("<FocusOut>", self._on_focus_out))

    def hide(self):
        if not self.is_open:
            return
        self.is_open = False
        self.root.withdraw()

    def toggle(self):
        self.hide() if self.is_open else self.show()

    def run(self):
        self.root.mainloop()


# ─── Janela de Debug ──────────────────────────────────────────────────────────

LOG_FILE = EXT_DATA / "worker.log"

class DebugWindow:
    def __init__(self, root: tk.Tk):
        self.root      = root
        self.win       = None
        self.is_open   = False
        self._poll_job = None

    def _has_font(self, name: str) -> bool:
        try:
            import tkinter.font as tkfont
            return name in tkfont.families()
        except Exception:
            return False

    def _build(self):
        self.win = tk.Toplevel(self.root)
        self.win.title("Effect Palette — Debug")
        self.win.attributes("-topmost", True)
        self.win.configure(bg=BG)
        self.win.protocol("WM_DELETE_WINDOW", self.hide)

        header = tk.Frame(self.win, bg=BG, padx=14, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="worker.log",
                 bg=BG, fg=TEXT_MUTED, font=("Segoe UI", 9)).pack(side="left")
        self.status_lbl = tk.Label(header, text="", bg=BG,
                                   fg=GREEN, font=("Segoe UI", 8))
        self.status_lbl.pack(side="right")

        tk.Frame(self.win, bg=BORDER, height=1).pack(fill="x")

        log_frame = tk.Frame(self.win, bg=BG)
        log_frame.pack(fill="both", expand=True, padx=1, pady=1)

        font = ("Cascadia Code", 9) if self._has_font("Cascadia Code") else ("Consolas", 9)
        self.text = tk.Text(
            log_frame, bg=BG, fg="#888899",
            relief="flat", font=font,
            highlightthickness=0, bd=0,
            state="disabled", wrap="none",
        )
        self.text.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        sb = tk.Scrollbar(log_frame, orient="vertical",
                          command=self.text.yview, width=4)
        sb.pack(side="right", fill="y", pady=8)
        self.text.configure(yscrollcommand=sb.set)

        sbx = tk.Scrollbar(self.win, orient="horizontal",
                           command=self.text.xview, width=4)
        sbx.pack(fill="x", padx=8)
        self.text.configure(xscrollcommand=sbx.set)

        tk.Frame(self.win, bg=BORDER, height=1).pack(fill="x")

        # ── Botões de ação ──
        actions = tk.Frame(self.win, bg=BG, padx=14, pady=8)
        actions.pack(fill="x")

        def make_btn(parent, label, cmd):
            b = tk.Label(parent, text=label, bg=BG2, fg=TEXT_MUTED,
                         font=("Segoe UI", 8), padx=10, pady=4, cursor="hand2")
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda e, c=cmd: self._send(c))
            b.bind("<Enter>",    lambda e, b=b: b.config(fg=ACCENT, bg=BORDER))
            b.bind("<Leave>",    lambda e, b=b: b.config(fg=TEXT_MUTED, bg=BG2))

        make_btn(actions, "↺ Exportar efeitos", "exportEffects")
        make_btn(actions, "Diagnóstico",         "diagnose")
        make_btn(actions, "✕ Limpar logs/bridge", "clearBridge")

        tk.Frame(self.win, bg=BORDER, height=1).pack(fill="x")

        footer = tk.Frame(self.win, bg=BG, padx=14, pady=8)
        footer.pack(fill="x")
        tk.Label(footer, text="ESC para fechar",
                 bg=BG, fg=TEXT_MUTED, font=("Segoe UI", 8)).pack(side="left")
        btn = tk.Label(footer, text="Limpar log", bg=BG,
                       fg=TEXT_MUTED, font=("Segoe UI", 8), cursor="hand2")
        btn.pack(side="right")
        btn.bind("<Button-1>", lambda e: self._clear_log())
        btn.bind("<Enter>",    lambda e: btn.config(fg=ACCENT))
        btn.bind("<Leave>",    lambda e: btn.config(fg=TEXT_MUTED))

        self.win.bind("<Escape>", lambda e: self.hide())

        W, H = 640, 380
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{W}x{H}+{(sw-W)//2}+{int(sh*0.55)}")

    def _refresh_log(self):
        if not self.is_open:
            return
        try:
            if LOG_FILE.exists():
                content = LOG_FILE.read_text(encoding="utf-8", errors="replace")
                lines   = content.splitlines()
                recent  = "\n".join(lines[-200:])
                self.text.configure(state="normal")
                self.text.delete("1.0", "end")
                self.text.insert("end", recent)
                self.text.configure(state="disabled")
                self.text.see("end")
                self.status_lbl.config(text=f"{len(lines)} linhas", fg=GREEN)
            else:
                self.text.configure(state="normal")
                self.text.delete("1.0", "end")
                self.text.insert("end",
                    "worker.log não encontrado.\n"
                    "O Premiere está aberto com a extensão carregada?")
                self.text.configure(state="disabled")
                self.status_lbl.config(text="sem arquivo", fg=ORANGE)
        except Exception as e:
            self.status_lbl.config(text=f"erro: {e}", fg=ORANGE)

        self._poll_job = self.root.after(1000, self._refresh_log)

    def _send(self, command: str):
        send_debug_command(command)
        self.status_lbl.config(text=f"→ {command}", fg=ACCENT)

    def _clear_log(self):
        try:
            if LOG_FILE.exists():
                LOG_FILE.write_text("", encoding="utf-8")
        except Exception:
            pass

    def show(self):
        if self.is_open:
            self.win.lift()
            self.win.focus_force()
            return
        self.is_open = True
        self._build()
        self._refresh_log()

    def hide(self):
        if not self.is_open:
            return
        self.is_open = False
        if self._poll_job:
            self.root.after_cancel(self._poll_job)
            self._poll_job = None
        if self.win:
            self.win.destroy()
            self.win = None

    def toggle(self):
        self.hide() if self.is_open else self.show()


# ─── Listener de atalho global ────────────────────────────────────────────────

class HotkeyListener:
    def __init__(self, palette: EffectPalette, debug: DebugWindow):
        self.palette = palette
        self.debug   = debug
        self.pressed = set()

    def _on_press(self, key):
        self.pressed.add(key)
        ctrl  = keyboard.Key.ctrl_l in self.pressed or keyboard.Key.ctrl_r in self.pressed
        space = keyboard.Key.space in self.pressed
        q     = keyboard.KeyCode.from_char('\x11') in self.pressed  # Ctrl+Q
        try:
            d = keyboard.KeyCode.from_char('d') in self.pressed or \
                keyboard.KeyCode.from_char('D') in self.pressed or \
                keyboard.KeyCode.from_char('\x04') in self.pressed
        except Exception:
            d = False

        if ctrl and space:
            if premiere_is_focused():
                self.palette.root.after(0, self.palette.toggle)

        if ctrl and d:
            self.palette.root.after(0, self.debug.toggle)

        if ctrl and q:
            print("[App] Encerrando via Ctrl+Q...")
            self.palette.root.after(0, self.palette.root.destroy)

    def _on_release(self, key):
        self.pressed.discard(key)

    def start(self):
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()
        print("[Hotkey] Ctrl+Espaço ativo")

    def stop(self):
        if hasattr(self, "_listener"):
            self._listener.stop()


# ─── Ponto de entrada ─────────────────────────────────────────────────────────

def main():
    print("=" * 52)
    print("  Premiere Pro Effect Palette")
    print(f"  Atalho     : Ctrl+Espaço")
    print(f"  Debug      : Ctrl+D")
    print(f"  Encerrar   : Ctrl+Q")
    print(f"  Efeitos    : {EFFECTS_FILE}")
    print(f"  Bridge     : {BRIDGE_FILE}")
    print("=" * 52)

    palette = EffectPalette()
    debug   = DebugWindow(palette.root)
    hotkey  = HotkeyListener(palette, debug)
    hotkey.start()

    try:
        palette.run()
    except KeyboardInterrupt:
        print("\n[App] Encerrando...")
    finally:
        hotkey.stop()


if __name__ == "__main__":
    main()
