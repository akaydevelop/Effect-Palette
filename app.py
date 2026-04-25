"""
Premiere Pro FX.palette
Atalho: Ctrl+Espaco - abre a paleta de efeitos
"""

import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import unicodedata
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox
from typing import Callable

import beta_report

try:
    from pynput import keyboard
    HAS_PYNPUT = True
except Exception:
    keyboard = None
    HAS_PYNPUT = False

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    FileSystemEventHandler = object
    Observer = None
    HAS_WATCHDOG = False

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False
    print("[Aviso] pygetwindow nao instalado - atalho funcionara em qualquer janela")

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except Exception:
    pystray = None
    Image = None
    ImageDraw = None
    HAS_TRAY = False


TEMP = Path(os.environ.get("TEMP", "C:/Temp"))
APPDATA = Path(os.environ.get("APPDATA", ""))

def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = get_app_dir()
APP_DIR = BASE_DIR
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

EXT_DATA = APPDATA / "Adobe" / "CEP" / "extensions" / "EffectPalette" / "data"
EFFECTS_FILE = EXT_DATA / "premiere_effects.json"
PRESETS_FILE = EXT_DATA / "premiere_presets.json"
PROJECT_ITEMS_FILE = EXT_DATA / "premiere_project_items.json"
FAVORITES_FILE = EXT_DATA / "premiere_favorites.json"
BRIDGE_FILE = EXT_DATA / "premiere_cmd.json"
SELECTION_FILE = EXT_DATA / "current_selection.json"
GOOGLE_SANS_FLEX_REGULAR = FONTS_DIR / "GoogleSansFlex-Regular.ttf"
GOOGLE_SANS_FLEX_MEDIUM = FONTS_DIR / "GoogleSansFlex-Medium.ttf"

WATCH_INTERVAL = 3.0
ENABLE_DEBUG_HOTKEY = os.environ.get("EFFECT_PALETTE_ENABLE_DEBUG_HOTKEY", "").lower() in {"1", "true", "yes", "on"}
BETA_FEEDBACK_MIN_OPEN_SECONDS = int(os.environ.get(
    "EFFECT_PALETTE_BETA_FEEDBACK_MIN_OPEN_SECONDS",
    os.environ.get("EFFECT_PALETTE_BETA_FEEDBACK_SECONDS", "300"),
))
PREMIERE_MONITOR_INTERVAL_MS = 30000
PREMIERE_PROCESS_NAMES = (
    "Adobe Premiere Pro.exe",
)
PROCESSENTRY32W_MAX_PATH = 260
RESULT_LIMIT = 150
SEARCH_DEBOUNCE_MS = 20
RELOAD_COALESCE_MS = 80
WIDTH_MEASURE_SAMPLE = 12
RESULTS_COLLAPSED_HEIGHT = 0
RESULTS_MESSAGE_HEIGHT = 54
RESULTS_EXPANDED_HEIGHT = 248
OPEN_ANIMATION_MS = 140
CLOSE_ANIMATION_MS = 110
STATE_ANIMATION_MS = 100
PILL_ANIMATION_MS = 120
INTERACTIVE_SETTLE_MS = 120
DEBUG_PERF = False
RESULTS_RENDER_OVERSCAN = 4
USE_WINDOW_ALPHA = False
FIXED_SEARCH_WINDOW_WIDTH = 760
POINTER_WINDOW_MARGIN = 12
POINTER_VERTICAL_GAP = 18
OPEN_FOCUS_ATTEMPTS = 6
FOCUS_OUT_REBIND_MS = 850
FOCUS_GRACE_SECONDS = 1.2
HEADER_PAD_X = 14
HEADER_PAD_Y = 8
SEARCH_PAD_X = 14
SEARCH_PAD_Y = 10
SEARCH_ICON_PAD_Y = 10
SEARCH_FONT_SIZE = 14
SEARCH_ICON_SIZE = 15
REFRESH_FONT_SIZE = 12
TITLE_FONT_SIZE = 8
STATUS_FONT_SIZE = 8
CHIP_PAD_X = 12
CHIP_PAD_Y = 5
CHIP_GAP_X = 4
ROW_ACCENT_WIDTH = 3
ROW_ICON_WIDTH = 2
ROW_BADGE_PAD_X = 8
ROW_BADGE_PAD_Y = 1
BODY_OUTER_BORDER = 1
BODY_SEAM_HEIGHT = 1

WATCHED_DATA_FILES = {
    EFFECTS_FILE.name,
    PRESETS_FILE.name,
    PROJECT_ITEMS_FILE.name,
    FAVORITES_FILE.name,
}

FALLBACK_EFFECTS = [
    {"name": "Lumetri Color", "category": "Color", "type": "video"},
    {"name": "Gaussian Blur", "category": "Blur", "type": "video"},
    {"name": "Warp Stabilizer", "category": "Distort", "type": "video"},
    {"name": "Ultra Key", "category": "Keying", "type": "video"},
    {"name": "Parametric EQ", "category": "Audio", "type": "audio"},
    {"name": "Multiband Compressor", "category": "Audio", "type": "audio"},
]

GENERIC_ITEMS = [
    {"name": "Adjustment Layer", "category": "Favoritos", "type": "generic_item", "genericKey": "adjustment_layer"},
    {"name": "Bars and Tone", "category": "Favoritos", "type": "generic_item", "genericKey": "bars_and_tone"},
    {"name": "Black Video", "category": "Favoritos", "type": "generic_item", "genericKey": "black_video"},
    {"name": "Color Matte", "category": "Favoritos", "type": "generic_item", "genericKey": "color_matte"},
    {"name": "Transparent Video", "category": "Favoritos", "type": "generic_item", "genericKey": "transparent_video"},
]

BG = "#0F0F11"
BG2 = "#1A1A1F"
BORDER = "#2A2A35"
TEXT = "#E8E8F0"
TEXT_MUTED = "#88889B"
ACCENT = "#5B6BF8"
SEL_BG = "#1E2040"
GREEN = "#3DD68C"
ORANGE = "#F5A623"
OFFLINE = "#7E8698"
SURFACE = "#151520"
SURFACE_ALT = "#191928"
SURFACE_HOVER = "#202033"
SURFACE_SELECTED = "#2A2C44"
SURFACE_FAVORITE = "#1C1A2C"
SURFACE_FAVORITE_HOVER = "#232038"
SURFACE_FAVORITE_SELECTED = "#2E2A45"
ROW_BORDER = "#232335"
ROW_BORDER_ACTIVE = "#5B6BF8"
ICON_BG = "#2A2742"
ICON_BG_FAVORITE = "#4E3A89"
ICON_FG = "#BFC6F3"
TYPE_BG = "#212033"
TYPE_FG = "#AAA8BE"
CHIP_BG = "#181826"
CHIP_HOVER = "#25233C"
CHIP_ACTIVE = "#4752C8"
CHIP_BORDER = "#2E2C40"
STAR_ACCENT = "#FFD66B"
REFRESH_BUTTON_BG = "#171724"
REFRESH_BUTTON_BORDER = "#2B2A3C"
REFRESH_BUTTON_HOVER_BG = "#212033"
REFRESH_BUTTON_ACTIVE_BG = "#161523"
WINDOW_MASK_COLOR = "#00F0B6"

FILTER_PALETTE = {
    "Todos": "#AEB8C7",
    "Video": "#A9E5D1",
    "Audio": "#F5C3A9",
    "Presets": "#D8C2F3",
    "Projeto": "#B7D7F6",
    "Favoritos": "#F2DA8A",
}

ITEM_TYPE_FILTER_KEYS = {
    "video": "Video",
    "audio": "Audio",
    "preset": "Presets",
    "project_item": "Projeto",
    "generic_item": "Favoritos",
    "favorite_item": "Favoritos",
    "favorite": "Favoritos",
}

for _generic_item in GENERIC_ITEMS:
    _generic_item["category"] = "Favoritos"

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


@dataclass(frozen=True)
class DataPaths:
    effects_file: Path = EFFECTS_FILE
    presets_file: Path = PRESETS_FILE
    project_items_file: Path = PROJECT_ITEMS_FILE
    favorites_file: Path = FAVORITES_FILE
    bridge_file: Path = BRIDGE_FILE
    selection_file: Path = SELECTION_FILE
    data_dir: Path = EXT_DATA


@dataclass(frozen=True)
class IndexedItem:
    payload: dict
    normalized_name: str
    tokens: tuple[str, ...]
    item_type: str
    load_order: int


@dataclass(frozen=True)
class SearchResultSet:
    items: tuple[dict, ...]
    total_count: int
    visible_count: int
    query: str


@dataclass(frozen=True)
class ResultRowModel:
    payload: dict
    title: str
    subtitle: str
    type_label: str
    icon_kind: str
    is_favorite: bool
    accent_kind: str


@dataclass
class ResultRowWidgets:
    index: int
    frame: tk.Frame
    background_canvas: tk.Canvas
    background_id: int
    accent_id: int
    icon_label: tk.Label
    title_label: tk.Label
    subtitle_label: tk.Label
    type_canvas: tk.Canvas
    type_bg_id: int
    type_text_id: int
    model: ResultRowModel


@dataclass
class CategoryPillWidgets:
    key: str
    canvas: tk.Canvas
    background_id: int
    text_id: int


@dataclass
class IconButtonWidgets:
    canvas: tk.Canvas
    background_id: int
    text_id: int


@dataclass(frozen=True)
class PaletteLayoutMetrics:
    row_height: int = 50
    row_gap: int = 4
    row_radius: int = 14
    row_pad_x: int = 8
    row_pad_y: int = 6
    icon_size: int = 22
    type_badge_height: int = 18
    type_badge_radius: int = 10
    chip_height: int = 26
    chip_radius: int = 13
    chip_pad_x: int = 12
    results_outer_pad: int = 6
    max_visible_rows: int = 5


def compute_results_height_for_count(count: int, metrics: PaletteLayoutMetrics | None = None) -> int:
    local_metrics = metrics or PaletteLayoutMetrics()
    if count <= 0:
        return 0
    visible_rows = min(count, local_metrics.max_visible_rows)
    content_height = visible_rows * local_metrics.row_height
    content_height += max(0, visible_rows - 1) * local_metrics.row_gap
    content_height += local_metrics.results_outer_pad * 2
    return content_height


def compute_target_width_for_models(
    row_models: list[ResultRowModel] | tuple[ResultRowModel, ...],
    *,
    title_measure: Callable[[str], int],
    subtitle_measure: Callable[[str], int],
    type_measure: Callable[[str], int],
    min_width: int,
    max_width: int,
    screen_cap: int,
    metrics: PaletteLayoutMetrics | None = None,
    sample_size: int = WIDTH_MEASURE_SAMPLE,
    selected_index: int | None = None,
    row_keys: list[str] | tuple[str, ...] | None = None,
    width_cache: dict[str, int] | None = None,
) -> int:
    if not row_models:
        return min_width

    local_metrics = metrics or PaletteLayoutMetrics()
    widest_px = 0
    candidate_indexes: list[int] = list(range(min(len(row_models), sample_size)))
    if selected_index is not None and 0 <= selected_index < len(row_models) and selected_index not in candidate_indexes:
        candidate_indexes.insert(0, selected_index)
    favorite_index = next((idx for idx, model in enumerate(row_models) if model.is_favorite), None)
    if favorite_index is not None and favorite_index not in candidate_indexes:
        candidate_indexes.append(favorite_index)

    for index in candidate_indexes:
        model = row_models[index]
        row_key = row_keys[index] if row_keys is not None and index < len(row_keys) else None
        cached_width = width_cache.get(row_key) if width_cache is not None and row_key else None
        if cached_width is None:
            title_width = title_measure(model.title)
            subtitle_width = subtitle_measure(model.subtitle)
            type_width = type_measure(model.type_label)
            cached_width = (
                local_metrics.results_outer_pad * 2
                + local_metrics.row_pad_x * 2
                + local_metrics.icon_size
                + 14
                + max(title_width, subtitle_width)
                + 18
                + type_width
                + 26
            )
            if width_cache is not None and row_key:
                width_cache[row_key] = cached_width
        content_width = cached_width
        widest_px = max(widest_px, content_width)

    lower_bound = max(min_width, widest_px + 32)
    return min(lower_bound, max_width, screen_cap)


def should_hide_to_tray(tray_enabled: bool) -> bool:
    return tray_enabled


def build_result_row_key(payload: dict) -> str:
    item_type = payload.get("type", "video")
    identity = payload.get("nodeId") or payload.get("genericKey") or payload.get("mediaPath") or payload.get("sequenceID") or ""
    return f"{item_type}:{payload.get('name', '')}:{identity}"


def should_reconfigure_row(previous_key: str | None, previous_model: ResultRowModel | None, next_key: str, next_model: ResultRowModel) -> bool:
    return previous_key != next_key or previous_model != next_model


def choose_results_width(*, interactive: bool, stable_width: int, computed_width: int, min_width: int, entering_results: bool) -> int:
    if entering_results:
        return max(min_width, computed_width)
    if interactive:
        return max(min_width, stable_width)
    return max(min_width, computed_width)


def is_body_shell_visible(state: str) -> bool:
    return state != "idle_empty"


def choose_search_shell_dimensions(*, fixed_width: int, expanded_window_height: int) -> tuple[int, int]:
    return fixed_width, expanded_window_height


def choose_window_position_near_pointer(
    *,
    pointer_x: int,
    pointer_y: int,
    window_width: int,
    window_height: int,
    screen_width: int,
    screen_height: int,
    margin: int = POINTER_WINDOW_MARGIN,
    vertical_gap: int = POINTER_VERTICAL_GAP,
) -> tuple[int, int]:
    min_x = margin
    max_x = max(margin, screen_width - window_width - margin)
    x = max(min_x, min(pointer_x - (window_width // 2), max_x))

    preferred_y = pointer_y - window_height - vertical_gap
    below_y = pointer_y + vertical_gap
    min_y = margin
    max_y = max(margin, screen_height - window_height - margin)
    if preferred_y >= min_y:
        y = preferred_y
    else:
        y = min(below_y, max_y)
    y = max(min_y, min(y, max_y))
    return x, y


def should_focus_on_invocation(first_open: bool) -> bool:
    return True


class PerfTimer:
    def __init__(self, label: str, *, enabled: bool):
        self.label = label
        self.enabled = enabled
        self._start = time.perf_counter()
        self._marks: list[tuple[str, float]] = []

    def mark(self, name: str):
        if not self.enabled:
            return
        now = time.perf_counter()
        self._marks.append((name, now - self._start))

    def report(self):
        if not self.enabled:
            return
        parts = [f"{self.label}"]
        previous = 0.0
        for name, total in self._marks:
            parts.append(f"{name}={((total - previous) * 1000):.1f}ms")
            previous = total
        total_ms = (time.perf_counter() - self._start) * 1000
        parts.append(f"total={total_ms:.1f}ms")
        print("[Perf] " + "  ".join(parts))


@dataclass(frozen=True)
class LoaderSnapshot:
    effects: tuple[dict, ...]
    presets: tuple[dict, ...]
    project_items: tuple[dict, ...]
    favorite_items: tuple[dict, ...]
    generic_items: tuple[dict, ...]
    all_items: tuple[dict, ...]
    indexed_items: tuple[IndexedItem, ...]
    exact_name_map: dict[str, tuple[int, ...]]
    prefix_map: dict[str, tuple[int, ...]]
    token_prefix_map: dict[str, tuple[int, ...]]
    trigram_map: dict[str, tuple[int, ...]]
    source: str
    mtimes: dict[str, float]
    connection_state: str
    load_issues: tuple[str, ...]

    @property
    def count(self) -> int:
        return len(self.effects)

    @property
    def preset_count(self) -> int:
        return len(self.presets)

    @property
    def project_item_count(self) -> int:
        return len(self.project_items)

    @property
    def favorite_item_count(self) -> int:
        return len(self.favorite_items)

    @property
    def generic_item_count(self) -> int:
        return len(self.generic_items)


def normalize_search_text(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_value.lower()).strip()


def tokenize_search_text(value: str) -> tuple[str, ...]:
    normalized = normalize_search_text(value)
    if not normalized:
        return ()
    return tuple(token for token in re.split(r"[^a-z0-9]+", normalized) if token)


def iter_prefixes(value: str, max_len: int = 4):
    normalized = normalize_search_text(value)
    if not normalized:
        return
    for length in range(1, min(len(normalized), max_len) + 1):
        yield normalized[:length]


def make_trigrams(value: str) -> tuple[str, ...]:
    normalized = normalize_search_text(value)
    if len(normalized) < 3:
        return ()
    return tuple(normalized[idx:idx + 3] for idx in range(len(normalized) - 2))


def freeze_id_lists(mapping: dict[str, list[int]]) -> dict[str, tuple[int, ...]]:
    return {key: tuple(values) for key, values in mapping.items()}


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[idx:idx + 2], 16) for idx in (0, 2, 4))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def blend_colors(start: str, end: str, progress: float) -> str:
    start_rgb = hex_to_rgb(start)
    end_rgb = hex_to_rgb(end)
    rgb = tuple(int(start_rgb[idx] + ((end_rgb[idx] - start_rgb[idx]) * progress)) for idx in range(3))
    return rgb_to_hex(rgb)


def filter_key_for_item_type(item_type: str) -> str:
    if item_type in FILTER_PALETTE:
        return item_type
    return ITEM_TYPE_FILTER_KEYS.get(item_type, "Todos")


def get_filter_palette_color(filter_key: str) -> str:
    return FILTER_PALETTE.get(filter_key, FILTER_PALETTE["Todos"])


def get_pill_visual_tokens(filter_key: str, *, active: bool) -> dict[str, str]:
    pastel = get_filter_palette_color(filter_key)
    if active:
        return {
            "bg": pastel,
            "fg": BG,
            "border": blend_colors(pastel, "#FFFFFF", 0.18),
        }
    return {
        "bg": CHIP_BG,
        "fg": TEXT_MUTED,
        "border": blend_colors(CHIP_BORDER, pastel, 0.26),
    }


def get_row_visual_tokens(accent_kind: str, *, selected: bool, hovered: bool) -> dict[str, str]:
    filter_key = filter_key_for_item_type(accent_kind)
    pastel = get_filter_palette_color(filter_key)
    if selected:
        bg = blend_colors(SURFACE_ALT, pastel, 0.22)
        border = blend_colors(ROW_BORDER, pastel, 0.75)
        badge_bg = blend_colors(TYPE_BG, pastel, 0.42)
        icon_fg = blend_colors(ICON_FG, pastel, 0.50)
        subtitle_fg = blend_colors(TEXT_MUTED, "#FFFFFF", 0.42)
    elif hovered:
        bg = blend_colors(SURFACE_ALT, pastel, 0.16)
        border = blend_colors(ROW_BORDER, pastel, 0.54)
        badge_bg = blend_colors(TYPE_BG, pastel, 0.32)
        icon_fg = blend_colors(ICON_FG, pastel, 0.34)
        subtitle_fg = blend_colors(TEXT_MUTED, "#FFFFFF", 0.28)
    else:
        bg = blend_colors(SURFACE_ALT, pastel, 0.10)
        border = blend_colors(ROW_BORDER, pastel, 0.34)
        badge_bg = blend_colors(TYPE_BG, pastel, 0.24)
        icon_fg = blend_colors(ICON_FG, pastel, 0.20)
        subtitle_fg = TEXT_MUTED
    return {
        "bg": bg,
        "accent": pastel,
        "icon_fg": icon_fg,
        "border": border,
        "subtitle_fg": subtitle_fg,
        "type_bg": badge_bg,
        "type_fg": TEXT,
        "title_fg": TEXT,
    }


def get_reload_button_tokens(*, hovered: bool, pressed: bool) -> dict[str, str]:
    if pressed:
        return {
            "bg": REFRESH_BUTTON_ACTIVE_BG,
            "fg": ACCENT,
            "border": blend_colors(REFRESH_BUTTON_BORDER, ACCENT, 0.56),
        }
    if hovered:
        return {
            "bg": REFRESH_BUTTON_HOVER_BG,
            "fg": ACCENT,
            "border": blend_colors(REFRESH_BUTTON_BORDER, ACCENT, 0.42),
        }
    return {
        "bg": REFRESH_BUTTON_BG,
        "fg": TEXT_MUTED,
        "border": REFRESH_BUTTON_BORDER,
    }


def derive_connection_state(*, source: str, load_issues: tuple[str, ...]) -> str:
    if source == "fallback":
        if load_issues:
            return "problem"
        return "offline"
    if load_issues:
        return "problem"
    return "connected"


def get_connection_state_tokens(state: str) -> dict[str, str]:
    if state == "connected":
        color = GREEN
    elif state == "problem":
        color = ORANGE
    else:
        color = OFFLINE
    return {
        "fill": color,
        "outline": blend_colors(BORDER, color, 0.45),
    }


def rounded_rect_points(x1: int, y1: int, x2: int, y2: int, radius: int) -> list[int]:
    radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    return [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]


def draw_rounded_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs) -> int:
    return canvas.create_polygon(
        rounded_rect_points(x1, y1, x2, y2, radius),
        smooth=True,
        splinesteps=20,
        **kwargs,
    )


def update_rounded_rect(canvas: tk.Canvas, item_id: int, x1: int, y1: int, x2: int, y2: int, radius: int):
    canvas.coords(item_id, *rounded_rect_points(x1, y1, x2, y2, radius))


def get_icon_glyph(icon_kind: str, *, ascii_only: bool = False) -> str:
    glyphs = {
        "effect": "✦",
        "preset": "✎",
        "project": "▣",
        "favorite": "★",
    }
    fallback = {
        "effect": "FX",
        "preset": "PR",
        "project": "PJ",
        "favorite": "*",
    }
    if ascii_only:
        return fallback.get(icon_kind, "•")
    return glyphs.get(icon_kind, fallback.get(icon_kind, "•"))


def get_reload_icon_glyph() -> str:
    return "\u21bb"


def load_private_font(font_path: Path) -> bool:
    if not IS_WINDOWS or not font_path.exists():
        return False
    try:
        return bool(ctypes.windll.gdi32.AddFontResourceExW(str(font_path), 0x10, 0))
    except Exception:
        return False


def load_app_fonts():
    load_private_font(GOOGLE_SANS_FLEX_REGULAR)
    load_private_font(GOOGLE_SANS_FLEX_MEDIUM)


def choose_ui_font_family(available_families: tuple[str, ...] | list[str]) -> str:
    families = set(available_families)
    if "Google Sans Flex" in families:
        return "Google Sans Flex"
    return "Segoe UI"


def apply_window_mask(window: tk.Misc) -> bool:
    if not IS_WINDOWS:
        return False
    try:
        window.wm_attributes("-transparentcolor", WINDOW_MASK_COLOR)
        return True
    except Exception:
        return False


def ease_out_expo(progress: float) -> float:
    if progress <= 0:
        return 0.0
    if progress >= 1:
        return 1.0
    return 1 - pow(2, -10 * progress)


def ease_in_expo(progress: float) -> float:
    if progress <= 0:
        return 0.0
    if progress >= 1:
        return 1.0
    return pow(2, 10 * progress - 10)


def ease_in_out_expo(progress: float) -> float:
    if progress <= 0:
        return 0.0
    if progress >= 1:
        return 1.0
    if progress < 0.5:
        return pow(2, 20 * progress - 10) / 2
    return (2 - pow(2, -20 * progress + 10)) / 2


class TweenRunner:
    def __init__(self, root: tk.Misc):
        self.root = root
        self._jobs: dict[str, str] = {}

    def cancel(self, key: str):
        job = self._jobs.pop(key, None)
        if job is None:
            return
        try:
            self.root.after_cancel(job)
        except Exception:
            pass

    def tween(self, key: str, duration_ms: int, step, *, easing=ease_in_out_expo, on_complete=None):
        self.cancel(key)
        start = time.perf_counter()

        def tick():
            if not self.root.winfo_exists():
                self._jobs.pop(key, None)
                return
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            progress = min(1.0, elapsed_ms / max(1, duration_ms))
            step(easing(progress))
            if progress >= 1.0:
                self._jobs.pop(key, None)
                if on_complete is not None:
                    on_complete()
                return
            self._jobs[key] = self.root.after(16, tick)

        step(easing(0.0))
        self._jobs[key] = self.root.after(16, tick)

    def finish(self):
        for key in list(self._jobs.keys()):
            self.cancel(key)


class EffectsLoader:
    def __init__(self, paths: DataPaths | None = None):
        self.paths = paths or DataPaths()
        self._lock = threading.Lock()
        self._reload_lock = threading.Lock()
        self._reload_inflight = False
        self._reload_pending = False
        self._reload_force = False
        self._snapshot = self._build_snapshot(force_reload=True)

    @property
    def snapshot(self) -> LoaderSnapshot:
        with self._lock:
            return self._snapshot

    @property
    def source(self) -> str:
        return self.snapshot.source

    @property
    def count(self) -> int:
        return self.snapshot.count

    @property
    def preset_count(self) -> int:
        return self.snapshot.preset_count

    @property
    def project_item_count(self) -> int:
        return self.snapshot.project_item_count

    @property
    def favorite_item_count(self) -> int:
        return self.snapshot.favorite_item_count

    @property
    def generic_item_count(self) -> int:
        return self.snapshot.generic_item_count

    def current_mtimes(self) -> dict[str, float]:
        return {
            "effects": self._safe_mtime(self.paths.effects_file),
            "presets": self._safe_mtime(self.paths.presets_file),
            "project_items": self._safe_mtime(self.paths.project_items_file),
            "favorites": self._safe_mtime(self.paths.favorites_file),
        }

    def needs_reload(self) -> bool:
        return self.current_mtimes() != self.snapshot.mtimes

    def check_for_updates(self) -> bool:
        if not self.needs_reload():
            return False
        snapshot = self._build_snapshot(force_reload=True)
        self._publish_snapshot(snapshot)
        return True

    def request_refresh(self, root: tk.Misc, on_ready, *, force: bool = False):
        with self._reload_lock:
            if self._reload_inflight:
                self._reload_pending = True
                self._reload_force = self._reload_force or force
                return
            if not force and not self.needs_reload():
                return
            self._reload_inflight = True
            self._reload_force = False

        def worker(force_reload: bool):
            snapshot = self._build_snapshot(force_reload=force_reload)

            def publish():
                try:
                    if self._publish_snapshot(snapshot):
                        on_ready(snapshot)
                finally:
                    self._finish_refresh(root, on_ready)

            root.after(0, publish)

        threading.Thread(target=worker, args=(force,), daemon=True).start()

    def _finish_refresh(self, root: tk.Misc, on_ready):
        with self._reload_lock:
            pending = self._reload_pending
            force = self._reload_force
            self._reload_inflight = False
            self._reload_pending = False
            self._reload_force = False

        if pending:
            self.request_refresh(root, on_ready, force=force)

    def _publish_snapshot(self, snapshot: LoaderSnapshot) -> bool:
        with self._lock:
            if (
                snapshot.mtimes == self._snapshot.mtimes
                and snapshot.all_items == self._snapshot.all_items
                and snapshot.source == self._snapshot.source
                and snapshot.connection_state == self._snapshot.connection_state
                and snapshot.load_issues == self._snapshot.load_issues
            ):
                return False
            self._snapshot = snapshot
            return True

    def _build_snapshot(self, *, force_reload: bool = False) -> LoaderSnapshot:
        previous = self.snapshot if hasattr(self, "_snapshot") else None
        mtimes = self.current_mtimes()
        if not force_reload and previous and mtimes == previous.mtimes:
            return previous

        effects, source, effect_issues = self._load_effects()
        load_issues = list(effect_issues)
        if source == "fallback":
            presets = ()
            project_items = ()
            favorite_items = ()
            mtimes = {"effects": 0.0, "presets": 0.0, "project_items": 0.0, "favorites": 0.0}
        else:
            presets, preset_issues = self._load_presets()
            project_items, project_item_issues = self._load_project_items()
            favorite_items, favorite_issues = self._load_favorites()
            load_issues.extend(preset_issues)
            load_issues.extend(project_item_issues)
            load_issues.extend(favorite_issues)

        generic_items = tuple(dict(item) for item in GENERIC_ITEMS)
        all_items = effects + presets + project_items + favorite_items + generic_items
        indexed_items, exact_name_map, prefix_map, token_prefix_map, trigram_map = self._build_indexes(all_items)

        return LoaderSnapshot(
            effects=effects,
            presets=presets,
            project_items=project_items,
            favorite_items=favorite_items,
            generic_items=generic_items,
            all_items=all_items,
            indexed_items=indexed_items,
            exact_name_map=exact_name_map,
            prefix_map=prefix_map,
            token_prefix_map=token_prefix_map,
            trigram_map=trigram_map,
            source=source,
            mtimes=mtimes,
            connection_state=derive_connection_state(source=source, load_issues=tuple(load_issues)),
            load_issues=tuple(load_issues),
        )

    def _load_effects(self) -> tuple[tuple[dict, ...], str, tuple[str, ...]]:
        if not self.paths.effects_file.exists():
            return tuple(dict(item, type=item.get("type", "video")) for item in FALLBACK_EFFECTS), "fallback", ()

        try:
            with open(self.paths.effects_file, encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            effects = []
            for effect in data.get("effects", []):
                effects.append({
                    "name": effect["name"],
                    "category": effect.get("category", ""),
                    "type": effect.get("type", "video"),
                })
            if not effects:
                raise ValueError("Lista vazia")
            print(f"[Efeitos] {len(effects)} efeitos carregados")
            return tuple(effects), "premiere", ()
        except Exception as exc:
            print(f"[Efeitos] Erro ao ler arquivo: {exc} — usando fallback")
            return tuple(dict(item, type=item.get("type", "video")) for item in FALLBACK_EFFECTS), "fallback", (f"effects:{exc}",)

    def _load_presets(self) -> tuple[tuple[dict, ...], tuple[str, ...]]:
        if not self.paths.presets_file.exists():
            return (), ()
        try:
            with open(self.paths.presets_file, encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            presets = []
            for preset in data.get("presets", []):
                presets.append({
                    "name": preset["name"],
                    "category": preset.get("category", "Presets"),
                    "type": "preset",
                    "filterPresets": preset.get("filterPresets", []),
                })
            print(f"[Presets] {len(presets)} carregados")
            return tuple(presets), ()
        except Exception as exc:
            print(f"[Presets] Erro ao ler: {exc}")
            return (), (f"presets:{exc}",)

    def _load_project_items(self) -> tuple[tuple[dict, ...], tuple[str, ...]]:
        if not self.paths.project_items_file.exists():
            return (), ()
        try:
            with open(self.paths.project_items_file, encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            items = []
            for item in data.get("items", []):
                items.append({
                    "name": item["name"],
                    "category": item.get("category", "Projeto"),
                    "type": "project_item",
                    "nodeId": item.get("nodeId", ""),
                    "itemType": item.get("itemType", ""),
                    "isSequence": item.get("isSequence", False),
                    "treePath": item.get("treePath", ""),
                    "mediaPath": item.get("mediaPath", ""),
                })
            print(f"[Projeto] {len(items)} itens carregados")
            return tuple(items), ()
        except Exception as exc:
            print(f"[Projeto] Erro ao ler: {exc}")
            return (), (f"project_items:{exc}",)

    def _load_favorites(self) -> tuple[tuple[dict, ...], tuple[str, ...]]:
        if not self.paths.favorites_file.exists():
            return (), ()
        try:
            with open(self.paths.favorites_file, encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            items = []
            for item in data.get("items", []):
                items.append({
                    "name": item["name"],
                    "category": item.get("category", "Favoritos"),
                    "type": "favorite_item",
                    "favoriteType": item.get("favoriteType", ""),
                    "sourceProjectPath": item.get("sourceProjectPath", ""),
                    "sourceTreePath": item.get("sourceTreePath", ""),
                    "mediaPath": item.get("mediaPath", ""),
                    "sequenceID": item.get("sequenceID", ""),
                    "isSequence": item.get("isSequence", False),
                    "itemType": item.get("itemType", ""),
                })
            print(f"[Favoritos] {len(items)} itens carregados")
            return tuple(items), ()
        except Exception as exc:
            print(f"[Favoritos] Erro ao ler: {exc}")
            return (), (f"favorites:{exc}",)

    def _build_indexes(self, items: tuple[dict, ...]):
        indexed_items: list[IndexedItem] = []
        exact_name_map: dict[str, list[int]] = {}
        prefix_map: dict[str, list[int]] = {}
        token_prefix_map: dict[str, list[int]] = {}
        trigram_map: dict[str, list[int]] = {}

        for idx, item in enumerate(items):
            normalized_name = normalize_search_text(item.get("name", ""))
            tokens = tokenize_search_text(item.get("name", ""))
            indexed = IndexedItem(
                payload=item,
                normalized_name=normalized_name,
                tokens=tokens,
                item_type=item.get("type", ""),
                load_order=idx,
            )
            indexed_items.append(indexed)
            exact_name_map.setdefault(normalized_name, []).append(idx)
            for prefix in iter_prefixes(normalized_name):
                prefix_map.setdefault(prefix, []).append(idx)
            for token in tokens:
                for prefix in iter_prefixes(token):
                    token_prefix_map.setdefault(prefix, []).append(idx)
            for trigram in set(make_trigrams(normalized_name)):
                trigram_map.setdefault(trigram, []).append(idx)

        return (
            tuple(indexed_items),
            freeze_id_lists(exact_name_map),
            freeze_id_lists(prefix_map),
            freeze_id_lists(token_prefix_map),
            freeze_id_lists(trigram_map),
        )

    def search(self, query: str, *, type_filters: set[str] | None = None, limit: int = RESULT_LIMIT) -> SearchResultSet:
        snapshot = self.snapshot
        normalized_query = normalize_search_text(query)
        if not normalized_query:
            return SearchResultSet(items=(), total_count=0, visible_count=0, query="")

        allowed_types = set(type_filters) if type_filters else None
        prefix_key = normalized_query[:4]
        seen: set[int] = set()
        ranked_ids: list[int] = []
        sort_key = lambda idx: (snapshot.indexed_items[idx].normalized_name, snapshot.indexed_items[idx].load_order)

        def allowed(idx: int) -> bool:
            if allowed_types is None:
                return True
            return snapshot.indexed_items[idx].item_type in allowed_types

        def append_group(candidate_ids, predicate):
            group = []
            for idx in candidate_ids:
                if idx in seen or not allowed(idx):
                    continue
                indexed = snapshot.indexed_items[idx]
                if not predicate(indexed):
                    continue
                group.append(idx)
            if not group:
                return
            group.sort(key=sort_key)
            seen.update(group)
            ranked_ids.extend(group)

        append_group(snapshot.exact_name_map.get(normalized_query, ()), lambda item: item.normalized_name == normalized_query)
        append_group(snapshot.prefix_map.get(prefix_key, ()), lambda item: item.normalized_name.startswith(normalized_query))
        append_group(snapshot.token_prefix_map.get(prefix_key, ()), lambda item: any(token.startswith(normalized_query) for token in item.tokens))

        if len(normalized_query) >= 3:
            trigram_groups = []
            for trigram in set(make_trigrams(normalized_query)):
                ids = snapshot.trigram_map.get(trigram)
                if not ids:
                    trigram_groups = []
                    break
                trigram_groups.append(set(ids))
            contains_candidates = list(set.intersection(*trigram_groups)) if trigram_groups else []
        else:
            contains_candidates = list(range(len(snapshot.indexed_items)))

        append_group(contains_candidates, lambda item: normalized_query in item.normalized_name)
        visible_ids = ranked_ids[:limit]
        return SearchResultSet(
            items=tuple(snapshot.indexed_items[idx].payload for idx in visible_ids),
            total_count=len(ranked_ids),
            visible_count=len(visible_ids),
            query=normalized_query,
        )

    @staticmethod
    def _safe_mtime(file_path: Path) -> float:
        try:
            return file_path.stat().st_mtime
        except Exception:
            return 0.0


def write_safe(file_path: Path, content: str):
    tmp = file_path.with_suffix(file_path.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(file_path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def send_command(effect: dict):
    beta_report.write_event("command_queued", {
        "name": effect.get("name", ""),
        "type": effect.get("type", "video"),
        "category": effect.get("category", ""),
    })

    if effect.get("type") == "preset":
        payload = {
            "command": "applyPreset",
            "effect": effect["name"],
            "filterPresetsJSON": json.dumps(effect.get("filterPresets", [])),
            "timestamp": time.time(),
            "status": "pending",
        }
    elif effect.get("type") == "project_item":
        payload = {
            "command": "insertProjectItem",
            "itemName": effect["name"],
            "nodeId": effect.get("nodeId", ""),
            "itemType": effect.get("itemType", ""),
            "timestamp": time.time(),
            "status": "pending",
        }
    elif effect.get("type") == "generic_item":
        payload = {
            "command": "insertGenericItem",
            "itemName": effect["name"],
            "genericKey": effect.get("genericKey", ""),
            "timestamp": time.time(),
            "status": "pending",
        }
    elif effect.get("type") == "favorite_item":
        payload = {
            "command": "insertFavoriteItem",
            "itemName": effect["name"],
            "mediaPath": effect.get("mediaPath", ""),
            "sequenceID": effect.get("sequenceID", ""),
            "itemType": effect.get("itemType", ""),
            "isSequence": effect.get("isSequence", False),
            "favoriteType": effect.get("favoriteType", ""),
            "sourceProjectPath": effect.get("sourceProjectPath", ""),
            "timestamp": time.time(),
            "status": "pending",
        }
    elif effect.get("type") in {"transition_video", "transition_audio"}:
        payload = {
            "command": "applyTransition",
            "transitionName": effect["name"],
            "transitionType": "audio" if effect.get("type") == "transition_audio" else "video",
            "transitionPlacement": effect.get("transitionPlacement", "auto"),
            "timestamp": time.time(),
            "status": "pending",
        }
    else:
        payload = {
            "command": "applyEffect",
            "effect": effect["name"],
            "category": effect.get("category", ""),
            "type": effect.get("type", "video"),
            "timestamp": time.time(),
            "status": "pending",
        }
    BRIDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_safe(BRIDGE_FILE, json.dumps(payload, indent=2))
    print(f"[Bridge] Enviado: {effect['name']}")


def _premiere_process_via_toolhelp() -> bool | None:
    if not IS_WINDOWS:
        return None

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * PROCESSENTRY32W_MAX_PATH),
        ]

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32FirstW.restype = wintypes.BOOL
        kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32NextW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
        if snapshot == wintypes.HANDLE(-1).value:
            return None

        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

        found = False
        has_entry = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        target_names = {name.lower() for name in PREMIERE_PROCESS_NAMES}

        while has_entry:
            if str(entry.szExeFile).lower() in target_names:
                found = True
                break
            has_entry = kernel32.Process32NextW(snapshot, ctypes.byref(entry))

        kernel32.CloseHandle(snapshot)
        return found
    except Exception as exc:
        beta_report.log_exception("Premiere Toolhelp process check failed", exc)
        return None


def _premiere_process_via_tasklist() -> bool | None:
    if not IS_WINDOWS:
        return None

    try:
        startupinfo = None
        creationflags = 0
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Adobe Premiere Pro.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    except Exception as exc:
        beta_report.log_exception("Premiere tasklist process check failed", exc)
        return None

    if result.returncode != 0:
        beta_report.write_event("premiere_tasklist_process_check_failed", {
            "returncode": result.returncode,
            "stderr": (result.stderr or "").strip()[:500],
            "stdout": (result.stdout or "").strip()[:500],
        })
        return None

    output = (result.stdout or "").lower()
    for process_name in PREMIERE_PROCESS_NAMES:
        if process_name.lower() in output:
            return True

    return False


def premiere_process_is_running() -> bool | None:
    """Checks the Premiere process directly. Returns None if checks cannot run."""
    toolhelp_running = _premiere_process_via_toolhelp()
    if toolhelp_running is not None:
        return toolhelp_running

    return _premiere_process_via_tasklist()


def premiere_is_running() -> bool:
    """Best-effort check used only for closed beta feedback prompts."""
    process_running = premiere_process_is_running()
    if process_running is not None:
        return process_running

    if not HAS_PYGETWINDOW:
        return True

    try:
        titles = gw.getAllTitles()
    except Exception:
        return True

    for title in titles:
        title_text = str(title or "")
        if "Adobe Premiere" in title_text or "Premiere Pro" in title_text:
            return True
    return False


def send_debug_command(command: str):
    payload = {
        "command": command,
        "timestamp": time.time(),
        "status": "pending",
    }
    BRIDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_safe(BRIDGE_FILE, json.dumps(payload, indent=2))
    print(f"[Bridge] Comando enviado: {command}")


def preset_has_keyframes(effect: dict) -> bool:
    if effect.get("type") != "preset":
        return False
    for filter_preset in effect.get("filterPresets", []):
        for param in filter_preset.get("params", []):
            if param.get("keyframes"):
                return True
    return False


def load_current_selection(paths: DataPaths | None = None) -> list:
    data_paths = paths or DataPaths()
    if not data_paths.selection_file.exists():
        return []
    try:
        with open(data_paths.selection_file, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
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
    if not HAS_PYGETWINDOW:
        return True
    try:
        active = gw.getActiveWindow()
        if active is None:
            return False
        return "Adobe Premiere" in active.title
    except Exception:
        return True


class DataFilesChangeHandler(FileSystemEventHandler):
    def __init__(self, palette):
        self.palette = palette

    def on_any_event(self, event):
        if getattr(event, "is_directory", False):
            return
        for raw_path in (getattr(event, "src_path", ""), getattr(event, "dest_path", "")):
            if raw_path and Path(raw_path).name in WATCHED_DATA_FILES:
                self.palette.schedule_data_refresh()
                return


class PaletteResultsController:
    def __init__(self, palette: "EffectPalette", parent: tk.Frame):
        self.palette = palette
        self.parent = parent
        self.metrics = PaletteLayoutMetrics()
        self.container = tk.Frame(parent, bg=BG)
        self.canvas = tk.Canvas(self.container, bg=BG, highlightthickness=0, bd=0, relief="flat")
        self.scrollbar = tk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview, width=4)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True, padx=(self.metrics.results_outer_pad, 2), pady=self.metrics.results_outer_pad)
        self.scrollbar.pack(side="right", fill="y", padx=(0, self.metrics.results_outer_pad), pady=self.metrics.results_outer_pad)

        self.rows_frame = tk.Frame(self.canvas, bg=BG)
        self.rows_window_id = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.rows_frame.bind("<Configure>", self._on_rows_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.row_widgets: list[ResultRowWidgets] = []
        self.row_models: list[ResultRowModel] = []
        self.row_keys: list[str] = []
        self._previous_row_keys: list[str] = []
        self._previous_selected_key: str | None = None
        self._render_window_size = self.metrics.max_visible_rows + (RESULTS_RENDER_OVERSCAN * 2) + 1
        self._visible_range: tuple[int, int] = (0, 0)
        self.selected_index = -1
        self.hover_index = -1

    def show(self):
        if not self.container.winfo_manager():
            self.container.pack(fill="both", expand=True)

    def hide(self):
        if self.container.winfo_manager():
            self.container.pack_forget()

    def clear(self):
        self._previous_row_keys = list(self.row_keys)
        self._previous_selected_key = self.selected_key()
        self.row_models = []
        self.row_keys = []
        self.selected_index = -1
        self.hover_index = -1
        for row in self.row_widgets:
            row.frame.place_forget()
        self._visible_range = (0, 0)
        self.canvas.configure(scrollregion=(0, 0, 0, 0))
        self.canvas.yview_moveto(0.0)

    def render(self, row_models: list[ResultRowModel]):
        previous_selected_key = self.selected_key()
        self.row_models = list(row_models)
        self.row_keys = [self.palette._result_row_key(model.payload) for model in self.row_models]
        self.hover_index = -1
        if self.row_keys:
            if previous_selected_key in self.row_keys:
                self.selected_index = self.row_keys.index(previous_selected_key)
            else:
                self.selected_index = 0
        else:
            self.selected_index = -1
        self._ensure_row_capacity(min(len(self.row_models), self._render_window_size))
        self._update_scrollregion()
        self._refresh_visible_rows(force=True)
        self._previous_selected_key = previous_selected_key

    def move_selection(self, direction: int):
        if not self.row_models:
            return
        new_index = max(0, min(self.selected_index + direction, len(self.row_models) - 1))
        self.set_selected(new_index)

    def set_selected(self, index: int, *, ensure_visible: bool = True):
        if not self.row_models:
            self.selected_index = -1
            return
        new_index = max(0, min(index, len(self.row_models) - 1))
        previous = self.selected_index
        self.selected_index = new_index
        previous_widget = self._widget_for_model_index(previous)
        if previous_widget is not None:
            self._apply_row_state(previous_widget)
        new_widget = self._widget_for_model_index(new_index)
        if new_widget is not None:
            self._apply_row_state(new_widget)
        if ensure_visible:
            self._scroll_row_into_view(new_index)

    def selected_payload(self):
        if 0 <= self.selected_index < len(self.row_models):
            return self.row_models[self.selected_index].payload
        return None

    def selected_key(self):
        if 0 <= self.selected_index < len(self.row_keys):
            return self.row_keys[self.selected_index]
        return None

    def visible_count(self) -> int:
        return len(self.row_models)

    def compute_results_height(self, row_count: int | None = None) -> int:
        count = self.visible_count() if row_count is None else row_count
        return compute_results_height_for_count(count, self.metrics)

    def compute_target_width(self) -> int:
        screen_cap = max(self.palette._min_window_width, int(self.palette.root.winfo_screenwidth() * 0.84))
        return compute_target_width_for_models(
            self.row_models,
            title_measure=self.palette.row_title_font.measure,
            subtitle_measure=self.palette.row_meta_font.measure,
            type_measure=self.palette.row_type_font.measure,
            min_width=self.palette._min_window_width,
            max_width=self.palette._max_window_width,
            screen_cap=screen_cap,
            metrics=self.metrics,
            sample_size=WIDTH_MEASURE_SAMPLE,
            selected_index=self.selected_index,
            row_keys=self.row_keys,
            width_cache=self.palette._row_width_cache,
        )

    def _ensure_row_capacity(self, count: int):
        while len(self.row_widgets) < count:
            self.row_widgets.append(self._create_row_widget(len(self.row_widgets)))

    def _row_step(self) -> int:
        return self.metrics.row_height + self.metrics.row_gap

    def _content_height(self) -> int:
        if not self.row_models:
            return 0
        return (
            self.metrics.results_outer_pad * 2
            + len(self.row_models) * self.metrics.row_height
            + max(0, len(self.row_models) - 1) * self.metrics.row_gap
        )

    def _update_scrollregion(self):
        width = max(self.canvas.winfo_width(), 1)
        self.rows_frame.configure(width=width, height=self._content_height())
        self.canvas.configure(scrollregion=(0, 0, width, self._content_height()))

    def _widget_for_model_index(self, index: int) -> ResultRowWidgets | None:
        for row in self.row_widgets:
            if row.frame.winfo_ismapped() and row.index == index:
                return row
        return None

    def _visible_start_index(self) -> int:
        row_step = max(1, self._row_step())
        visible_top = max(0, int(self.canvas.canvasy(0)) - self.metrics.results_outer_pad)
        return max(0, (visible_top // row_step) - RESULTS_RENDER_OVERSCAN)

    def _refresh_visible_rows(self, *, force: bool = False):
        total = len(self.row_models)
        if total <= 0:
            for row in self.row_widgets:
                row.frame.place_forget()
            self._visible_range = (0, 0)
            return

        start = min(self._visible_start_index(), max(0, total - 1))
        end = min(total, start + len(self.row_widgets))
        visible_range = (start, end)
        canvas_width = max(self.canvas.winfo_width(), 1)
        row_width = max(1, canvas_width - ((self.metrics.results_outer_pad * 2) + 2))

        for slot, actual_index in enumerate(range(start, end)):
            widgets = self.row_widgets[slot]
            model = self.row_models[actual_index]
            row_key = self.row_keys[actual_index]
            previous_model = widgets.model if widgets.index == actual_index else None
            previous_key = self.row_keys[widgets.index] if 0 <= widgets.index < len(self.row_keys) and widgets.index == actual_index else None
            widgets.index = actual_index
            if force or should_reconfigure_row(previous_key, previous_model, row_key, model):
                widgets.model = model
                self._render_row_content(widgets)
            else:
                widgets.model = model
            y = self.metrics.results_outer_pad + (actual_index * self._row_step())
            widgets.frame.place(x=self.metrics.results_outer_pad, y=y, width=row_width, height=self.metrics.row_height)
            widgets.frame.configure(width=row_width, height=self.metrics.row_height)
            self._layout_row_widget(widgets, row_width)
            self._apply_row_state(widgets)

        for slot in range(end - start, len(self.row_widgets)):
            self.row_widgets[slot].frame.place_forget()

        self._visible_range = visible_range

    def _create_row_widget(self, index: int) -> ResultRowWidgets:
        frame = tk.Frame(
            self.rows_frame,
            bg=BG,
            height=self.metrics.row_height,
            cursor="hand2",
            bd=0,
            relief="flat",
            highlightthickness=0,
        )
        background_canvas = tk.Canvas(
            frame,
            bg=BG,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        background_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        background_id = draw_rounded_rect(
            background_canvas,
            1,
            1,
            10,
            self.metrics.row_height - 1,
            self.metrics.row_radius,
            fill=SURFACE_ALT,
            outline=ROW_BORDER,
            width=1,
        )
        accent_id = draw_rounded_rect(
            background_canvas,
            8,
            7,
            14,
            self.metrics.row_height - 7,
            4,
            fill=FILTER_PALETTE["Video"],
            outline="",
            state="hidden",
        )
        icon_label = tk.Label(
            frame,
            text="",
            font=self.palette.row_icon_font,
            bg=SURFACE_ALT,
            fg=ICON_FG,
            width=ROW_ICON_WIDTH,
            bd=0,
            relief="flat",
            highlightthickness=0,
            padx=0,
            pady=0,
        )
        title_label = tk.Label(
            frame,
            text="",
            font=self.palette.row_title_font,
            bg=SURFACE_ALT,
            fg=TEXT,
            anchor="w",
            bd=0,
            relief="flat",
            highlightthickness=0,
            padx=0,
            pady=0,
        )
        subtitle_label = tk.Label(
            frame,
            text="",
            font=self.palette.row_meta_font,
            bg=SURFACE_ALT,
            fg=TEXT_MUTED,
            anchor="w",
            bd=0,
            relief="flat",
            highlightthickness=0,
            padx=0,
            pady=0,
        )
        type_canvas = tk.Canvas(
            frame,
            bg=BG,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        type_bg_id = draw_rounded_rect(
            type_canvas,
            0,
            0,
            10,
            self.metrics.type_badge_height,
            self.metrics.type_badge_radius,
            fill=TYPE_BG,
            outline="",
        )
        type_text_id = type_canvas.create_text(
            0,
            self.metrics.type_badge_height // 2,
            anchor="w",
            text="",
            font=self.palette.row_type_font,
            fill=TEXT,
        )
        row = ResultRowWidgets(
            index=index,
            frame=frame,
            background_canvas=background_canvas,
            background_id=background_id,
            accent_id=accent_id,
            icon_label=icon_label,
            title_label=title_label,
            subtitle_label=subtitle_label,
            type_canvas=type_canvas,
            type_bg_id=type_bg_id,
            type_text_id=type_text_id,
            model=ResultRowModel({}, "", "", "", "effect", False, "effect"),
        )
        self._bind_row_widget(frame, row)
        self._bind_row_widget(background_canvas, row)
        self._bind_row_widget(icon_label, row)
        self._bind_row_widget(title_label, row)
        self._bind_row_widget(subtitle_label, row)
        self._bind_row_widget(type_canvas, row)
        return row

    def _bind_row_widget(self, widget: tk.Misc, row: ResultRowWidgets):
        widget.bind("<Enter>", lambda e, r=row: self._on_row_enter(r.index))
        widget.bind("<Leave>", lambda e, r=row: self._on_row_leave(r.index))
        widget.bind("<Button-1>", lambda e, r=row: self._on_row_click(r.index))
        widget.bind("<Double-Button-1>", lambda e, r=row: self._on_row_double_click(r.index))
        widget.bind("<MouseWheel>", self._on_mouse_wheel)

    def _render_row_content(self, row: ResultRowWidgets):
        model = row.model
        row.icon_label.config(text=get_icon_glyph(model.icon_kind))
        row.title_label.config(text=model.title)
        row.subtitle_label.config(text=model.subtitle)
        row.type_canvas.itemconfigure(row.type_text_id, text=model.type_label)
        self._layout_row_widget(row)

    def _layout_row_widget(self, row: ResultRowWidgets, width: int | None = None):
        row_width = width or row.frame.winfo_width() or int(row.frame.cget("width") or 0) or 1
        row_height = self.metrics.row_height
        row.background_canvas.configure(width=row_width, height=row_height)
        update_rounded_rect(
            row.background_canvas,
            row.background_id,
            1,
            1,
            max(2, row_width - 1),
            row_height - 1,
            self.metrics.row_radius,
        )
        badge_text = row.model.type_label or ""
        badge_width = max(52, self.palette.row_type_font.measure(badge_text) + (ROW_BADGE_PAD_X * 2))
        badge_height = self.metrics.type_badge_height
        row.type_canvas.configure(width=badge_width, height=badge_height)
        update_rounded_rect(
            row.type_canvas,
            row.type_bg_id,
            0,
            0,
            max(2, badge_width - 1),
            badge_height - 1,
            self.metrics.type_badge_radius,
        )
        row.type_canvas.coords(row.type_text_id, badge_width / 2, badge_height / 2)
        row.type_canvas.itemconfigure(row.type_text_id, anchor="center")

        badge_x = row_width - badge_width - 10
        row.type_canvas.place(x=badge_x, y=(row_height - badge_height) // 2, width=badge_width, height=badge_height)
        row.icon_label.place(x=28, y=row_height // 2, anchor="center")
        row.title_label.place(x=48, y=14, anchor="w")
        row.subtitle_label.place(x=48, y=34, anchor="w")

    def _apply_row_state(self, row: ResultRowWidgets):
        model = row.model
        selected = row.index == self.selected_index
        hovered = row.index == self.hover_index
        colors = get_row_visual_tokens(model.accent_kind, selected=selected, hovered=hovered)
        row.background_canvas.itemconfigure(
            row.background_id,
            fill=colors["bg"],
            outline=colors["border"],
        )
        row.icon_label.config(bg=colors["bg"], fg=colors["icon_fg"])
        row.title_label.config(bg=colors["bg"], fg=colors["title_fg"])
        row.subtitle_label.config(bg=colors["bg"], fg=colors["subtitle_fg"])
        row.type_canvas.config(bg=colors["bg"])
        row.type_canvas.itemconfigure(row.type_bg_id, fill=colors["type_bg"], outline="")
        row.type_canvas.itemconfigure(row.type_text_id, fill=colors["type_fg"])

    def _scroll_row_into_view(self, index: int):
        if not (0 <= index < len(self.row_models)):
            return
        row_y = self.metrics.results_outer_pad + (index * (self.metrics.row_height + self.metrics.row_gap))
        row_bottom = row_y + self.metrics.row_height
        total_height = self.metrics.results_outer_pad * 2
        total_height += len(self.row_models) * self.metrics.row_height
        total_height += max(0, len(self.row_models) - 1) * self.metrics.row_gap
        total_height = max(total_height, 1)
        visible_top = self.canvas.canvasy(0)
        visible_bottom = visible_top + self.canvas.winfo_height()
        if row_y < visible_top:
            self.canvas.yview_moveto(max(0.0, row_y / total_height))
        elif row_bottom > visible_bottom:
            self.canvas.yview_moveto(max(0.0, (row_bottom - self.canvas.winfo_height()) / total_height))
        self._refresh_visible_rows()

    def _on_rows_frame_configure(self, event):
        self._update_scrollregion()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.rows_window_id, width=event.width)
        self._update_scrollregion()
        self._refresh_visible_rows(force=True)

    def _on_mouse_wheel(self, event):
        if self._content_height() <= self.canvas.winfo_height():
            return
        direction = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(direction, "units")
        self._refresh_visible_rows()

    def _on_row_enter(self, index: int):
        self.hover_index = index
        widget = self._widget_for_model_index(index)
        if widget is not None:
            self._apply_row_state(widget)

    def _on_row_leave(self, index: int):
        if self.hover_index == index:
            self.hover_index = -1
        widget = self._widget_for_model_index(index)
        if widget is not None:
            self._apply_row_state(widget)

    def _on_row_click(self, index: int):
        self.set_selected(index, ensure_visible=False)

    def _on_row_double_click(self, index: int):
        self.set_selected(index, ensure_visible=False)
        self.palette._apply_selected()


class EffectPalette:
    CATEGORY_TYPE_FILTERS = {
        "Video": {"video"},
        "Audio": {"audio"},
        "Transicoes": {"transition_video", "transition_audio"},
        "Presets": {"preset"},
        "Projeto": {"project_item"},
        "Favoritos": {"generic_item", "favorite_item"},
    }

    def __init__(self):
        self.loader = EffectsLoader()
        self.root = None
        self.body_win = None
        self.is_open = False
        self._window_width = 580
        self._min_window_width = 580
        self._max_window_width = 1180
        self._fixed_search_window_width = max(self._min_window_width, FIXED_SEARCH_WINDOW_WIDTH)
        self._results_collapsed_height = RESULTS_COLLAPSED_HEIGHT
        self._results_expanded_height = RESULTS_EXPANDED_HEIGHT
        self._window_height = 0
        self._collapsed_window_height = 0
        self._message_window_height = 0
        self._expanded_window_height = 0
        self._body_window_height = 0
        self._results_height = 0
        self._window_anchor_x = 0
        self._window_anchor_y = 0
        self._window_y_offset = 0
        self._focus_primed = False
        self._has_shown_once = False
        self._prime_finish_job = None
        self._active_category = None
        self._watch_job = None
        self._data_refresh_job = None
        self._data_observer = None
        self._search_job = None
        self._settle_job = None
        self._focus_out_job = None
        self._focus_out_grace_until = 0.0
        self._interactive_until = 0.0
        self._suspend_search_trace = False
        self._category_pills: dict[str, CategoryPillWidgets] = {}
        self._category_pill_state: dict[str, tuple[str, str]] = {}
        self._refresh_btn_hovered = False
        self._refresh_btn_pressed = False
        self._row_width_cache: dict[str, int] = {}
        self._current_results: list[dict] = []
        self._current_row_models: list[ResultRowModel] = []
        self._current_result_set = SearchResultSet(items=(), total_count=0, visible_count=0, query="")
        self._stable_results_width = self._fixed_search_window_width
        self._view_state = "idle_empty"
        self._results_region_visible = False
        self._footer_visible = False
        self._prepared_for_show = False
        self._is_closing = False
        self._exiting = False
        self.tray_controller = None
        self._premiere_seen = False
        self._premiere_seen_since = None
        self._premiere_missing_since = None
        self._premiere_monitor_job = None
        self._feedback_prompt_shown = False
        self._build()
        self._start_file_watcher()
        self._start_premiere_monitor()
        self.root.after(0, self._prime_first_show)

    def _build(self):
        load_app_fonts()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_root_close)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 1.0)
        self.root.configure(bg=WINDOW_MASK_COLOR)
        self._root_mask_enabled = apply_window_mask(self.root)
        self._root_host_bg = WINDOW_MASK_COLOR if self._root_mask_enabled else BG
        self.tweens = TweenRunner(self.root)
        self.ui_font_family = choose_ui_font_family(tkfont.families())
        self.row_icon_font = ("Segoe UI Symbol", 11, "bold")
        self.row_title_font = tkfont.Font(family=self.ui_font_family, size=10, weight="bold")
        self.row_meta_font = tkfont.Font(family=self.ui_font_family, size=8)
        self.row_type_font = tkfont.Font(family=self.ui_font_family, size=8, weight="bold")
        self.chip_font = tkfont.Font(family=self.ui_font_family, size=8, weight="bold")
        self.refresh_icon_font = tkfont.Font(family="Segoe UI Symbol", size=11)

        main_shell = tk.Frame(self.root, bg=self._root_host_bg)
        main_shell.pack(fill="both", expand=True)
        self.main_shell_canvas = tk.Canvas(main_shell, bg=self._root_host_bg, highlightthickness=0, bd=0, relief="flat")
        self.main_shell_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.main_shell_bg_id = draw_rounded_rect(
            self.main_shell_canvas,
            1,
            1,
            self._fixed_search_window_width - 1,
            48,
            16,
            fill=BG2,
            outline=BORDER,
            width=1,
        )
        main_shell.bind("<Configure>", lambda event: self._update_shell_surface(self.main_shell_canvas, self.main_shell_bg_id, event.width, event.height, 16))

        inner = tk.Frame(main_shell, bg=BG2)
        inner.pack(fill="both", expand=True, padx=8, pady=8)

        search_frame = tk.Frame(inner, bg=BG2, padx=SEARCH_PAD_X)
        search_frame.pack(fill="x")
        tk.Label(search_frame, text=">", bg=BG2, fg=ACCENT, font=(self.ui_font_family, SEARCH_ICON_SIZE)).pack(side="left", pady=SEARCH_ICON_PAD_Y)

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        self.entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg=BG2,
            fg=TEXT,
            insertbackground=ACCENT,
            relief="flat",
            font=(self.ui_font_family, SEARCH_FONT_SIZE),
            highlightthickness=0,
            bd=0,
        )
        self.entry.pack(side="left", fill="x", expand=True, pady=SEARCH_PAD_Y, padx=(8, 0))

        self.refresh_btn = self._create_refresh_button(search_frame)
        self.refresh_btn.canvas.pack(side="right", padx=(0, 4), pady=SEARCH_PAD_Y - 1)
        self._set_refresh_button_visual()

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x")

        self.cat_frame = tk.Frame(inner, bg=BG2, pady=6)
        self.cat_frame.pack(fill="x")
        self.cat_pills_frame = tk.Frame(self.cat_frame, bg=BG2)
        self.cat_pills_frame.pack(side="left", fill="x", expand=True, padx=(HEADER_PAD_X, 0))
        self.conn_state_canvas = tk.Canvas(self.cat_frame, width=18, height=24, bg=BG2, highlightthickness=0, bd=0, relief="flat")
        self.conn_state_canvas.pack(side="right", padx=(10, HEADER_PAD_X), pady=1)
        self.conn_state_dot_id = self.conn_state_canvas.create_oval(4, 7, 14, 17, fill=OFFLINE, outline=blend_colors(BORDER, OFFLINE, 0.45), width=1)
        self._build_category_pills()
        self._update_connection_indicator()

        self.body_win = tk.Toplevel(self.root)
        self.body_win.withdraw()
        self.body_win.overrideredirect(True)
        self.body_win.attributes("-topmost", True)
        self.body_win.configure(bg=WINDOW_MASK_COLOR)
        self._body_mask_enabled = apply_window_mask(self.body_win)
        self._body_host_bg = WINDOW_MASK_COLOR if self._body_mask_enabled else BG
        self.body_win.bind("<FocusIn>", self._on_focus_in)
        self.body_win.bind("<FocusOut>", self._on_focus_out)
        self.body_win.bind("<Escape>", lambda e: self.hide())

        body_outer = tk.Frame(self.body_win, bg=self._body_host_bg)
        body_outer.pack(fill="both", expand=True)
        self.body_shell_canvas = tk.Canvas(body_outer, bg=self._body_host_bg, highlightthickness=0, bd=0, relief="flat")
        self.body_shell_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.body_shell_bg_id = draw_rounded_rect(
            self.body_shell_canvas,
            1,
            1,
            self._fixed_search_window_width - 1,
            self._results_expanded_height,
            16,
            fill=BG,
            outline=BORDER,
            width=1,
        )
        body_outer.bind("<Configure>", lambda event: self._update_shell_surface(self.body_shell_canvas, self.body_shell_bg_id, event.width, event.height, 16))

        self.body_shell = tk.Frame(body_outer, bg=BG)
        self.body_shell.pack(fill="both", expand=True, padx=8, pady=(1, 8))
        self.body_inner = tk.Frame(self.body_shell, bg=BG, padx=BODY_OUTER_BORDER, pady=BODY_OUTER_BORDER)
        self.body_inner.pack(fill="both", expand=True)

        self.results_top_divider = tk.Frame(self.body_inner, bg=ROW_BORDER, height=BODY_SEAM_HEIGHT)
        self.results_top_divider.pack(fill="x")

        self.results_shell = tk.Frame(self.body_inner, bg=BG, height=self._results_expanded_height)
        self.results_shell.pack(fill="both", expand=True)
        self.results_shell.pack_propagate(False)

        self.results_state_label = tk.Label(self.results_shell, text="", bg=BG, fg=TEXT_MUTED, font=(self.ui_font_family, 11), anchor="center", justify="center", padx=18, pady=10)
        self.results_state_label.pack(fill="both", expand=True)

        self.results_controller = PaletteResultsController(self, self.results_shell)

        self.results_bottom_divider = tk.Frame(self.body_inner, bg=ROW_BORDER, height=1)
        self.results_bottom_divider.pack(fill="x")

        self.footer = tk.Frame(self.body_inner, bg=BG, padx=HEADER_PAD_X + 2, pady=9)
        self.footer.pack(fill="x")
        tk.Label(
            self.footer,
            text="Up/Down navegar   Enter aplicar   ESC fechar",
            bg=BG,
            fg=TEXT_MUTED,
            font=(self.ui_font_family, 8),
            anchor="w",
        ).pack(side="left", pady=1)
        self.status_label = tk.Label(self.footer, text="", bg=BG, fg=ACCENT, font=(self.ui_font_family, 8, "bold"))
        self.status_label.pack(side="right")

        self.entry.bind("<Escape>", lambda e: self.hide())
        self.entry.bind("<Control-w>", lambda e: self.hide())
        self.entry.bind("<Return>", lambda e: self._apply_selected())
        self.entry.bind("<Down>", lambda e: self._move_selection(1))
        self.entry.bind("<Up>", lambda e: self._move_selection(-1))
        self.root.bind("<FocusIn>", self._on_focus_in)
        self.root.bind("<FocusOut>", self._on_focus_out)
        self.root.bind_all("<Alt-F4>", self._on_alt_f4, add="+")

        self.root.update_idletasks()
        self._collapsed_window_height = self.root.winfo_reqheight()
        self._set_results_height(self._results_expanded_height)
        self.body_win.update_idletasks()
        self._body_window_height = self.body_win.winfo_reqheight()
        self._set_results_chrome_visibility(False)
        self._message_window_height = self._measure_window_height(
            self._results_collapsed_height,
            results_visible=False,
            footer_visible=True,
        )
        self._set_results_chrome_visibility(True)
        self._expanded_window_height = self._collapsed_window_height
        self._results_window_chrome = self._body_window_height - self._results_expanded_height
        self._results_height = self._results_expanded_height
        self._set_results_visibility(False, footer_visible=False)
        self._window_width, self._window_height = choose_search_shell_dimensions(
            fixed_width=self._fixed_search_window_width,
            expanded_window_height=self._expanded_window_height,
        )
        self._apply_window_geometry()
        self._prepare_for_next_show(force=True)

    def _set_results_chrome_visibility(self, visible: bool):
        widgets = [self.results_top_divider, self.results_shell, self.results_bottom_divider]
        if visible:
            if not self.results_top_divider.winfo_manager():
                self.results_top_divider.pack(fill="x", before=self.footer)
            if not self.results_shell.winfo_manager():
                self.results_shell.pack(fill="both", expand=True, before=self.footer)
            if not self.results_bottom_divider.winfo_manager():
                self.results_bottom_divider.pack(fill="x", before=self.footer)
            return
        for widget in widgets:
            if widget.winfo_manager():
                widget.pack_forget()

    def _set_results_visibility(self, results_visible: bool, *, footer_visible: bool):
        self._results_region_visible = results_visible
        self._footer_visible = footer_visible
        body_visible = results_visible or footer_visible
        if body_visible:
            self._show_body_window()
        else:
            self.results_controller.hide()
            self._hide_body_window()

    def _measure_window_height(self, results_height: int, *, results_visible: bool, footer_visible: bool) -> int:
        self._set_results_visibility(results_visible, footer_visible=footer_visible)
        self.results_shell.configure(height=results_height)
        self.body_win.update_idletasks()
        return self.body_win.winfo_reqheight()

    def _set_results_height(self, results_height: int):
        self._results_height = int(results_height)
        self.results_shell.configure(height=self._results_height)
        self._window_height = self._expanded_window_height

    def _show_body_window(self):
        if not self.body_win.winfo_exists():
            return
        self._apply_body_geometry()
        self.body_win.deiconify()
        self.body_win.lift()
        self.body_win.attributes("-topmost", True)

    def _hide_body_window(self):
        if self.body_win is not None and self.body_win.winfo_exists():
            self.body_win.withdraw()

    def _anchor_window_to_pointer(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        try:
            px, py = self.root.winfo_pointerxy()
        except Exception:
            px, py = sw // 2, sh // 2
        self._window_anchor_x, self._window_anchor_y = choose_window_position_near_pointer(
            pointer_x=px,
            pointer_y=py,
            window_width=self._window_width,
            window_height=self._window_height,
            screen_width=sw,
            screen_height=sh,
        )

    def _apply_window_geometry(self, *, alpha: float | None = None, y_offset: int | None = None):
        if USE_WINDOW_ALPHA:
            if alpha is not None:
                self.root.attributes("-alpha", alpha)
        else:
            self.root.attributes("-alpha", 1.0)
        if y_offset is not None:
            self._window_y_offset = y_offset

        x = self._window_anchor_x
        y = self._window_anchor_y + int(self._window_y_offset)
        self.root.geometry(f"{self._window_width}x{self._window_height}+{x}+{y}")
        self._apply_body_geometry()

    def _apply_body_geometry(self):
        if self.body_win is None or not self.body_win.winfo_exists():
            return
        if not self._results_region_visible and not self._footer_visible:
            return
        x = self.root.winfo_x()
        y = self.root.winfo_y() + self.root.winfo_height() - 1
        body_height = self._body_window_height if self._results_region_visible else self._message_window_height
        self.body_win.geometry(f"{self._window_width}x{body_height}+{x}+{y}")

    def _animate_results_height(self, target_height: int, *, immediate: bool = False):
        target = int(target_height)
        self.tweens.cancel("results_shell")
        self._set_results_height(target)

    def _update_shell_surface(self, canvas: tk.Canvas, item_id: int, width: int, height: int, radius: int):
        canvas.configure(width=width, height=height)
        update_rounded_rect(canvas, item_id, 1, 1, max(2, width - 1), max(2, height - 1), radius)

    def _create_refresh_button(self, parent: tk.Misc) -> IconButtonWidgets:
        size = 28
        canvas = tk.Canvas(
            parent,
            width=size,
            height=size,
            bg=BG2,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor="hand2",
        )
        background_id = draw_rounded_rect(
            canvas,
            0,
            0,
            size - 1,
            size - 1,
            10,
            fill=REFRESH_BUTTON_BG,
            outline=REFRESH_BUTTON_BORDER,
            width=1,
        )
        text_id = canvas.create_text(
            size / 2,
            size / 2,
            text=get_reload_icon_glyph(),
            font=self.refresh_icon_font,
            fill=TEXT_MUTED,
        )

        canvas.bind("<Button-1>", self._on_refresh_press)
        canvas.bind("<ButtonRelease-1>", self._on_refresh_release)
        canvas.bind("<Enter>", self._on_refresh_enter)
        canvas.bind("<Leave>", self._on_refresh_leave)
        return IconButtonWidgets(canvas=canvas, background_id=background_id, text_id=text_id)

    def _set_refresh_button_visual(self):
        tokens = get_reload_button_tokens(hovered=self._refresh_btn_hovered, pressed=self._refresh_btn_pressed)
        self.refresh_btn.canvas.itemconfigure(
            self.refresh_btn.background_id,
            fill=tokens["bg"],
            outline=tokens["border"],
        )
        self.refresh_btn.canvas.itemconfigure(self.refresh_btn.text_id, fill=tokens["fg"])

    def _on_refresh_enter(self, event=None):
        self._refresh_btn_hovered = True
        self._set_refresh_button_visual()

    def _on_refresh_leave(self, event=None):
        self._refresh_btn_hovered = False
        self._refresh_btn_pressed = False
        self._set_refresh_button_visual()

    def _on_refresh_press(self, event=None):
        self._refresh_btn_pressed = True
        self._set_refresh_button_visual()

    def _on_refresh_release(self, event=None):
        was_pressed = self._refresh_btn_pressed
        self._refresh_btn_pressed = False
        self._set_refresh_button_visual()
        if was_pressed:
            self._manual_refresh()

    def _create_category_pill(self, cat: str) -> CategoryPillWidgets:
        metrics = PaletteLayoutMetrics()
        width = self.chip_font.measure(cat) + (CHIP_PAD_X * 2)
        height = metrics.chip_height
        canvas = tk.Canvas(
            self.cat_pills_frame,
            width=width,
            height=height,
            bg=BG2,
            highlightthickness=0,
            bd=0,
            relief="flat",
            cursor="hand2",
        )
        background_id = draw_rounded_rect(
            canvas,
            0,
            0,
            width - 1,
            height - 1,
            metrics.chip_radius,
            fill=CHIP_BG,
            outline=CHIP_BORDER,
            width=1,
        )
        text_id = canvas.create_text(
            width / 2,
            height / 2,
            text=cat,
            font=self.chip_font,
            fill=TEXT_MUTED,
        )
        pill = CategoryPillWidgets(key=cat, canvas=canvas, background_id=background_id, text_id=text_id)
        canvas.bind("<Button-1>", lambda e, c=cat: self._on_category_click(c))
        return pill

    def _build_category_pills(self):
        for cat in ["Todos", "Video", "Audio", "Transicoes", "Presets", "Projeto", "Favoritos"]:
            if cat in self._category_pills:
                continue
            pill = self._create_category_pill(cat)
            pill.canvas.pack(side="left", padx=CHIP_GAP_X, pady=1)
            self._category_pills[cat] = pill
            self._category_pill_state[cat] = (CHIP_BG, TEXT_MUTED)
        self._update_category_pills(immediate=True)

    def _update_connection_indicator(self):
        snapshot = self.loader.snapshot
        tokens = get_connection_state_tokens(snapshot.connection_state)
        self.conn_state_canvas.itemconfigure(
            self.conn_state_dot_id,
            fill=tokens["fill"],
            outline=tokens["outline"],
        )

    def _animate_pill_to(self, cat: str, bg_target: str, fg_target: str, *, immediate: bool = False):
        pill = self._category_pills[cat]
        pill.canvas.itemconfigure(pill.background_id, fill=bg_target, outline=blend_colors(CHIP_BORDER, bg_target, 0.35))
        pill.canvas.itemconfigure(pill.text_id, fill=fg_target)
        self._category_pill_state[cat] = (bg_target, fg_target)

    def _update_category_pills(self, *, immediate: bool = False):
        for cat in self._category_pills:
            active = (cat == "Todos" and self._active_category is None) or (cat == self._active_category)
            tokens = get_pill_visual_tokens(cat, active=active)
            self._animate_pill_to(cat, tokens["bg"], tokens["fg"], immediate=immediate)

    def _on_category_click(self, cat: str):
        new_category = None if cat == "Todos" else cat
        if new_category == self._active_category:
            return
        self._active_category = new_category
        self._prepared_for_show = False
        self._enter_interactive_search()
        self._update_category_pills(immediate=True)
        self._refresh_list()

    def _start_file_watcher(self):
        self.loader.paths.data_dir.mkdir(parents=True, exist_ok=True)
        if HAS_WATCHDOG:
            handler = DataFilesChangeHandler(self)
            self._data_observer = Observer()
            self._data_observer.schedule(handler, str(self.loader.paths.data_dir), recursive=False)
            self._data_observer.start()
            return

        def watch():
            if self.loader.needs_reload():
                self.loader.request_refresh(self.root, self._on_loader_snapshot_ready)
            self._watch_job = self.root.after(int(WATCH_INTERVAL * 1000), watch)

        self._watch_job = self.root.after(int(WATCH_INTERVAL * 1000), watch)

    def schedule_data_refresh(self):
        if not self.root or not self.root.winfo_exists():
            return
        if self._data_refresh_job is not None:
            self.root.after_cancel(self._data_refresh_job)
        self._data_refresh_job = self.root.after(RELOAD_COALESCE_MS, self._consume_data_refresh)

    def _consume_data_refresh(self):
        self._data_refresh_job = None
        self.loader.request_refresh(self.root, self._on_loader_snapshot_ready)

    def _start_premiere_monitor(self):
        self._premiere_monitor_job = self.root.after(5000, self._monitor_premiere_shutdown)

    def _monitor_premiere_shutdown(self):
        self._premiere_monitor_job = None

        try:
            running = premiere_is_running()
            now = time.time()

            if running:
                if not self._premiere_seen:
                    self._premiere_seen_since = now
                    beta_report.write_event("premiere_detected")
                self._premiere_seen = True
                self._premiere_missing_since = None
            elif self._premiere_seen and not self._feedback_prompt_shown:
                open_seconds = now - (self._premiere_seen_since or now)
                self._premiere_missing_since = now
                self._premiere_seen = False
                self._premiere_seen_since = None

                beta_report.write_event("premiere_closed_detected", {
                    "open_seconds": open_seconds,
                    "minimum_open_seconds": BETA_FEEDBACK_MIN_OPEN_SECONDS,
                })

                if open_seconds >= BETA_FEEDBACK_MIN_OPEN_SECONDS:
                    self._feedback_prompt_shown = True
                    beta_report.write_event("feedback_prompt_opened", {
                        "open_seconds": open_seconds,
                        "minimum_open_seconds": BETA_FEEDBACK_MIN_OPEN_SECONDS,
                    })
                    self._show_beta_feedback_dialog()
                else:
                    beta_report.write_event("feedback_prompt_skipped_short_session", {
                        "open_seconds": open_seconds,
                        "minimum_open_seconds": BETA_FEEDBACK_MIN_OPEN_SECONDS,
                    })
        except Exception as exc:
            beta_report.log_exception("Premiere monitor failed", exc)
        finally:
            if self.root.winfo_exists():
                self._premiere_monitor_job = self.root.after(
                    PREMIERE_MONITOR_INTERVAL_MS,
                    self._monitor_premiere_shutdown,
                )

    def _on_loader_snapshot_ready(self, snapshot: LoaderSnapshot):
        print(f"[Watcher] Lista atualizada — {snapshot.count} efeitos")
        self._row_width_cache.clear()
        self.results_controller._previous_row_keys = []
        self.results_controller._previous_selected_key = None
        self._update_connection_indicator()
        if self.is_open:
            self._refresh_list()
        else:
            self._prepare_for_next_show(force=True)

    def _manual_refresh(self):
        send_debug_command("exportEffects")
        self.status_label.config(text="Solicitando atualizacao ao Premiere...")
        self.loader.request_refresh(self.root, self._on_loader_snapshot_ready, force=True)

    def _resolve_type_filters(self) -> set[str] | None:
        if self._active_category is None:
            return None
        return self.CATEGORY_TYPE_FILTERS.get(self._active_category)

    def _build_result_row_model(self, effect: dict) -> ResultRowModel:
        item_type = effect.get("type", "video")
        is_favorite = item_type in {"generic_item", "favorite_item"}
        if item_type == "preset":
            type_label = "Preset"
            icon_kind = "preset"
            subtitle = effect.get("category", "Presets")
        elif item_type in {"transition_video", "transition_audio"}:
            type_label = "Transition"
            icon_kind = "effect"
            subtitle = effect.get("category", "Transicoes")
        elif item_type == "project_item":
            type_label = "Project"
            icon_kind = "project"
            subtitle = effect.get("treePath") or effect.get("category", "Projeto")
        elif is_favorite:
            type_label = "Favorite"
            icon_kind = "favorite"
            subtitle = effect.get("sourceTreePath") or effect.get("category", "Favoritos")
        else:
            type_label = "Effect"
            icon_kind = "effect"
            subtitle = effect.get("category", "Effects")
        return ResultRowModel(
            payload=effect,
            title=effect.get("name", ""),
            subtitle=subtitle,
            type_label=type_label,
            icon_kind=icon_kind,
            is_favorite=is_favorite,
            accent_kind=filter_key_for_item_type(item_type),
        )

    def _result_row_key(self, payload: dict) -> str:
        return build_result_row_key(payload)

    def _estimate_row_width(self, model: ResultRowModel) -> int:
        row_key = self._result_row_key(model.payload)
        cached_width = self._row_width_cache.get(row_key)
        if cached_width is not None:
            return cached_width
        title_width = self.row_title_font.measure(model.title)
        subtitle_width = self.row_meta_font.measure(model.subtitle)
        type_width = self.row_type_font.measure(model.type_label)
        cached_width = (
            self.results_controller.metrics.results_outer_pad * 2
            + self.results_controller.metrics.row_pad_x * 2
            + self.results_controller.metrics.icon_size
            + 14
            + max(title_width, subtitle_width)
            + 18
            + type_width
            + 26
        )
        self._row_width_cache[row_key] = cached_width
        return cached_width

    def _target_width_for_state(self, row_models: list[ResultRowModel], *, interactive: bool, entering_results: bool) -> int:
        if row_models:
            if interactive and not entering_results:
                return self._stable_results_width
            return self.results_controller.compute_target_width()
        return self._min_window_width

    def _enter_interactive_search(self):
        self._interactive_until = time.monotonic() + (INTERACTIVE_SETTLE_MS / 1000.0)
        if self._settle_job is not None:
            self.root.after_cancel(self._settle_job)
        self._settle_job = self.root.after(INTERACTIVE_SETTLE_MS, self._settle_interactive_search)

    def _settle_interactive_search(self):
        self._settle_job = None
        self._interactive_until = 0.0
        if self.is_open:
            self._refresh_list(settled_pass=True)

    def _is_interactive_search(self) -> bool:
        return time.monotonic() < self._interactive_until

    def _resolve_query_state(self) -> tuple[str, SearchResultSet]:
        query = self.search_var.get().strip()
        result_set = self.loader.search(query, type_filters=self._resolve_type_filters())
        return query, result_set

    def _build_visible_row_models(self, items: list[dict]) -> list[ResultRowModel]:
        return [self._build_result_row_model(effect) for effect in items]

    def _apply_results_models(self, row_models: list[ResultRowModel]):
        self._current_row_models = list(row_models)
        if row_models:
            self.results_controller.render(row_models)
        else:
            self.results_controller.clear()

    def _should_animate_settled_geometry(self, target_width: int, target_height: int) -> bool:
        return (
            abs(target_width - self._window_width) >= 24
            or abs(target_height - self._results_height) >= self.results_controller.metrics.row_height
        )

    def _apply_results_geometry(self, previous_state: str, row_models: list[ResultRowModel], *, interactive: bool, settled_pass: bool):
        if not row_models:
            self._stable_results_width = self._fixed_search_window_width
            self._set_view_state("no_results", helper_text="No results", immediate=interactive and not settled_pass)
            return

        self._set_view_state("showing_results")
        target_height = self._results_expanded_height
        self._stable_results_width = self._fixed_search_window_width
        self._set_results_height(target_height)

    def _update_status_line(self):
        self.status_label.config(text=f"{self._current_result_set.visible_count}/{self._current_result_set.total_count} resultados")

    def _animate_results_geometry(self, target_results_height: int, target_width: int, *, immediate: bool = False, duration: int = STATE_ANIMATION_MS, easing=ease_in_out_expo):
        target_results_height = int(target_results_height)
        self._set_results_height(target_results_height)

    def _animate_window_size(self, target_width: int, target_height: int, *, immediate: bool = False, duration: int = STATE_ANIMATION_MS, easing=ease_in_out_expo):
        target_width = int(target_width)
        target_height = int(target_height)
        if immediate or not self.root.winfo_exists():
            self.tweens.cancel("window_resize")
            self._window_width = target_width
            self._window_height = target_height
            self._apply_window_geometry()
            return

        start_width = self._window_width
        start_height = self._window_height

        def step(progress: float):
            self._window_width = round(start_width + ((target_width - start_width) * progress))
            self._window_height = round(start_height + ((target_height - start_height) * progress))
            self._apply_window_geometry()

        self.tweens.tween("window_resize", duration, step, easing=easing)

    def _set_view_state(self, state: str, *, helper_text: str = "", immediate: bool = False):
        if state == "showing_results":
            self._set_results_chrome_visibility(True)
            self._set_results_visibility(True, footer_visible=True)
            self._set_results_height(self._results_expanded_height)
            self.results_state_label.pack_forget()
            self.results_controller.show()
            self._view_state = state
            return

        self._view_state = state
        self.results_controller.hide()
        if state == "idle_empty":
            self._set_results_chrome_visibility(False)
            self._set_results_height(self._results_collapsed_height)
            self._set_results_visibility(False, footer_visible=self.is_open)
            if self.results_state_label.winfo_ismapped():
                self.results_state_label.pack_forget()
            return

        self._set_results_chrome_visibility(True)
        self._set_results_visibility(True, footer_visible=True)
        self._set_results_height(self._results_expanded_height)
        self.results_state_label.config(text=helper_text, fg=TEXT_MUTED)
        if not self.results_state_label.winfo_ismapped():
            self.results_state_label.pack(fill="both", expand=True)

    def _refresh_list(self, *, settled_pass: bool = False):
        perf = PerfTimer("refresh_list", enabled=DEBUG_PERF)
        previous_state = self._view_state
        query, self._current_result_set = self._resolve_query_state()
        perf.mark("search")
        self._current_results = list(self._current_result_set.items)

        if not query:
            self._current_row_models = []
            self.results_controller.clear()
            self._stable_results_width = self._min_window_width
            self._set_view_state("idle_empty", immediate=self._is_interactive_search())
            self.status_label.config(text="")
            perf.mark("idle_empty")
            perf.report()
            return

        row_models = self._build_visible_row_models(self._current_results)
        perf.mark("row_models")
        self._apply_results_models(row_models)
        perf.mark("render")
        self._apply_results_geometry(previous_state, row_models, interactive=self._is_interactive_search(), settled_pass=settled_pass)
        perf.mark("geometry")
        self._update_status_line()
        perf.mark("status")
        perf.report()

    def _on_search_change(self, *_):
        if self._suspend_search_trace:
            return
        self._prepared_for_show = False
        self._enter_interactive_search()
        if self._search_job is not None:
            self.root.after_cancel(self._search_job)
        self._search_job = self.root.after(SEARCH_DEBOUNCE_MS, self._refresh_from_search)

    def _refresh_from_search(self):
        self._search_job = None
        self._refresh_list()

    def _results_visible(self) -> bool:
        return self._view_state == "showing_results" and self.results_controller.visible_count() > 0

    def _move_selection(self, direction):
        if not self._results_visible():
            return
        self.results_controller.move_selection(direction)

    def _apply_selected(self):
        if not self._results_visible():
            return
        effect = self.results_controller.selected_payload()
        if not effect:
            return

        if effect.get("type") in {"transition_video", "transition_audio"}:
            placement = self._choose_transition_placement()
            if not placement:
                self.status_label.config(text="Aplicacao cancelada")
                return
            effect = dict(effect)
            effect["transitionPlacement"] = placement

        send_command(effect)
        if effect.get("type") in {"project_item", "generic_item", "favorite_item"}:
            self.status_label.config(text=f"[Inserido] {effect['name']}")
        elif effect.get("type") in {"transition_video", "transition_audio"}:
            self.status_label.config(text=f"[Transicao] {effect['name']}")
        else:
            self.status_label.config(text=f"[Aplicado] {effect['name']}")
        self.root.update()
        self.root.after(900, self.hide)

    def _choose_transition_placement(self) -> str | None:
        choice = {"value": None}
        self._suspend_focus_out = True

        dialog = tk.Toplevel(self.root)
        dialog.title("Posicao da transicao")
        dialog.transient(self.root)
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        body = tk.Frame(dialog, bg=BG, padx=18, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="Onde voce quer aplicar a transicao?",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            body,
            text="Automatico usa o comportamento atual do Premiere: entre dois clips quando houver corte, ou no fim do clip quando fizer sentido.",
            bg=BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=360,
            anchor="w",
        ).pack(fill="x", pady=(8, 14))

        buttons = tk.Frame(body, bg=BG)
        buttons.pack(fill="x")

        def choose(value: str):
            choice["value"] = value
            dialog.destroy()

        button_widgets = []

        def move_focus(delta: int):
            if not button_widgets:
                return "break"
            focused = dialog.focus_get()
            try:
                current_index = button_widgets.index(focused)
            except ValueError:
                current_index = len(button_widgets) - 1
            next_index = (current_index + delta) % len(button_widgets)
            button_widgets[next_index].focus_force()
            return "break"

        start_btn = tk.Button(
            buttons,
            text="Inicio",
            command=lambda: choose("start"),
            bg=BG2,
            fg=TEXT,
            relief="flat",
            padx=12,
            pady=6,
        )
        start_btn.pack(side="left", padx=(0, 8))
        button_widgets.append(start_btn)

        end_btn = tk.Button(
            buttons,
            text="Fim",
            command=lambda: choose("end"),
            bg=BG2,
            fg=TEXT,
            relief="flat",
            padx=12,
            pady=6,
        )
        end_btn.pack(side="left", padx=(0, 8))
        button_widgets.append(end_btn)

        auto_btn = tk.Button(
            buttons,
            text="Automatico",
            command=lambda: choose("auto"),
            bg=ACCENT,
            fg="#FFFFFF",
            relief="flat",
            padx=12,
            pady=6,
        )
        auto_btn.pack(side="left")
        button_widgets.append(auto_btn)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.bind("<Left>", lambda e: move_focus(-1))
        dialog.bind("<Right>", lambda e: move_focus(1))
        dialog.bind("<Tab>", lambda e: move_focus(1))
        dialog.bind("<ISO_Left_Tab>", lambda e: move_focus(-1))
        dialog.bind("<Shift-Tab>", lambda e: move_focus(-1))
        dialog.bind("<Return>", lambda e: (dialog.focus_get().invoke() if dialog.focus_get() in button_widgets else auto_btn.invoke(), "break")[1])
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + max(20, (self._window_width - dialog.winfo_width()) // 2)
        y = self.root.winfo_rooty() + 70
        dialog.geometry(f"+{x}+{y}")
        dialog.grab_set()
        auto_btn.focus_force()
        try:
            self.root.wait_window(dialog)
        finally:
            self._suspend_focus_out = False
            try:
                if self.is_open and self.root.winfo_exists():
                    self._ensure_entry_focus()
            except Exception:
                pass
        return choice["value"]

    # â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _show_beta_feedback_dialog(self):
        self._suspend_focus_out = True

        dialog = tk.Toplevel(self.root)
        dialog.title("FX.palette - Feedback da beta")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        body = tk.Frame(dialog, bg=BG, padx=18, pady=16)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="Obrigado por testar a beta fechada",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            body,
            text=(
                "O Premiere parece ter sido fechado. Se puder, deixe um feedback rapido. "
                "Um relatorio .zip sera salvo em Documents\\FX.palette_Beta_Report para voce enviar ao Paulo."
            ),
            bg=BG,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=520,
            anchor="w",
        ).pack(fill="x", pady=(6, 12))

        name_var = tk.StringVar()

        def add_label(text):
            tk.Label(body, text=text, bg=BG, fg=TEXT_MUTED, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(8, 3))

        add_label("Seu nome")
        name_entry = tk.Entry(
            body,
            textvariable=name_var,
            bg=BG2,
            fg=TEXT,
            insertbackground=ACCENT,
            relief="flat",
            font=("Segoe UI", 10),
            highlightthickness=0,
            bd=0,
        )
        name_entry.pack(fill="x", ipady=5)

        text_widgets = {}

        def add_text_area(key, label, height=3):
            add_label(label)
            widget = tk.Text(
                body,
                bg=BG2,
                fg=TEXT,
                insertbackground=ACCENT,
                relief="flat",
                font=("Segoe UI", 10),
                highlightthickness=0,
                bd=0,
                height=height,
                wrap="word",
            )
            widget.pack(fill="x")
            text_widgets[key] = widget

        add_text_area("impression", "O que voce achou da extensao?", 3)
        add_text_area("bug_report", "Encontrou algum bug?", 3)
        add_text_area("feature_suggestions", "Sugestao de feature para adicionar", 3)
        add_text_area("additional_comments", "Comentarios adicionais", 3)

        status_var = tk.StringVar(value="")
        tk.Label(
            body,
            textvariable=status_var,
            bg=BG,
            fg=ACCENT,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
            wraplength=520,
        ).pack(fill="x", pady=(10, 0))

        buttons = tk.Frame(body, bg=BG, pady=12)
        buttons.pack(fill="x")

        def read_text(key):
            widget = text_widgets[key]
            return widget.get("1.0", "end").strip()

        def submit():
            feedback = {
                "tester_name": name_var.get().strip(),
                "impression": read_text("impression"),
                "bug_report": read_text("bug_report"),
                "feature_suggestions": read_text("feature_suggestions"),
                "additional_comments": read_text("additional_comments"),
                "submitted_at": time.time(),
            }
            try:
                report_path = beta_report.build_report(
                    feedback,
                    EXT_DATA,
                    APP_DIR,
                    reason="feedback_after_premiere_closed",
                )
                status_var.set(f"Relatorio salvo em: {report_path}")
                messagebox.showinfo(
                    "Relatorio salvo",
                    "Feedback salvo com sucesso.\n\nEnvie este arquivo ao Paulo:\n" + str(report_path),
                    parent=dialog,
                )
                dialog.destroy()
            except Exception as exc:
                beta_report.log_exception("Failed to save beta feedback", exc)
                status_var.set("Nao consegui salvar o relatorio. Tente gerar pela janela de debug.")

        def skip():
            beta_report.write_event("feedback_prompt_skipped")
            dialog.destroy()

        skip_btn = tk.Button(
            buttons,
            text="Pular",
            command=skip,
            bg=BG2,
            fg=TEXT,
            relief="flat",
            padx=12,
            pady=6,
        )
        skip_btn.pack(side="left")

        submit_btn = tk.Button(
            buttons,
            text="Salvar feedback e relatorio",
            command=submit,
            bg=ACCENT,
            fg="#FFFFFF",
            relief="flat",
            padx=12,
            pady=6,
        )
        submit_btn.pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", skip)
        dialog.bind("<Escape>", lambda e: skip())
        dialog.update_idletasks()
        sw = dialog.winfo_screenwidth()
        sh = dialog.winfo_screenheight()
        w = dialog.winfo_width()
        h = dialog.winfo_height()
        dialog.geometry(f"+{(sw - w) // 2}+{int(sh * 0.18)}")
        dialog.deiconify()
        dialog.lift()
        dialog.focus_force()
        dialog.grab_set()
        name_entry.focus_force()
        beta_report.write_event("feedback_dialog_visible")

        def release_suspend():
            self._suspend_focus_out = False

        def cleanup_feedback_dialog():
            try:
                dialog.grab_release()
            except Exception:
                pass
            release_suspend()

        dialog.bind("<Destroy>", lambda e: cleanup_feedback_dialog() if e.widget == dialog else None)

    def _set_search_text(self, value: str, *, silent: bool = False):
        if self.search_var.get() == value:
            return
        if silent:
            self._suspend_search_trace = True
        try:
            self.search_var.set(value)
        finally:
            if silent:
                self._suspend_search_trace = False

    def _prepare_for_next_show(self, force: bool = False):
        if not force and self._prepared_for_show:
            return
        if self._search_job is not None:
            self.root.after_cancel(self._search_job)
            self._search_job = None
        if self._settle_job is not None:
            self.root.after_cancel(self._settle_job)
            self._settle_job = None
        self.tweens.cancel("window_resize")
        self._set_search_text("", silent=True)
        self._active_category = None
        self._current_results = []
        self._current_row_models = []
        self._current_result_set = SearchResultSet(items=(), total_count=0, visible_count=0, query="")
        self._interactive_until = 0.0
        self._stable_results_width = self._fixed_search_window_width
        self._window_width, self._window_height = choose_search_shell_dimensions(
            fixed_width=self._fixed_search_window_width,
            expanded_window_height=self._expanded_window_height,
        )
        self.results_controller.clear()
        self._update_category_pills(immediate=True)
        self._set_view_state("idle_empty", immediate=True)
        self.status_label.config(text="")
        self._update_connection_indicator()
        self._prepared_for_show = True

    def _cancel_focus_out_job(self):
        if self._focus_out_job is None:
            return
        try:
            self.root.after_cancel(self._focus_out_job)
        except Exception:
            pass
        self._focus_out_job = None

    def _on_focus_in(self, event):
        self._cancel_focus_out_job()

    def _on_focus_out(self, event):
        if not self.root.winfo_exists() or not self.is_open:
            return
        if time.monotonic() < self._focus_out_grace_until:
            return
        self._cancel_focus_out_job()
        self._focus_out_job = self.root.after(140, self._hide_if_focus_lost)

    def _pointer_inside_window(self) -> bool:
        if not self.root.winfo_exists():
            return False
        try:
            px, py = self.root.winfo_pointerxy()
        except Exception:
            return False

        def inside(win: tk.Misc | None) -> bool:
            if win is None or not win.winfo_exists() or not win.winfo_viewable():
                return False
            rx = win.winfo_rootx()
            ry = win.winfo_rooty()
            rw = win.winfo_width()
            rh = win.winfo_height()
            return rx <= px < (rx + rw) and ry <= py < (ry + rh)

        return inside(self.root) or inside(self.body_win)

    def _hide_if_focus_lost(self):
        self._focus_out_job = None
        if not self.root.winfo_exists() or not self.is_open:
            return
        if time.monotonic() < self._focus_out_grace_until:
            return
        try:
            focused_root = self.root.focus_get()
            if focused_root is not None and focused_root.winfo_toplevel() in {self.root, self.body_win}:
                return
        except Exception:
            pass
        try:
            if self.body_win is not None and self.body_win.winfo_exists():
                focused_body = self.body_win.focus_get()
                if focused_body is not None and focused_body.winfo_toplevel() in {self.root, self.body_win}:
                    return
        except Exception:
            pass
        if self._pointer_inside_window():
            self._focus_out_grace_until = time.monotonic() + 0.25
            self._force_focus_attempt(0)
            return
        self.hide()

    def _activate_window_native(self):
        if USER32 is None:
            return
        try:
            hwnd = int(self.root.winfo_id())
            USER32.ShowWindow(hwnd, SW_SHOWNORMAL)
            USER32.BringWindowToTop(hwnd)
            USER32.SetForegroundWindow(hwnd)
            USER32.SetActiveWindow(hwnd)
            USER32.SetFocus(hwnd)
        except Exception:
            pass

    def _force_focus_attempt(self, attempt=0, max_attempts=5):
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

        self._activate_window_native()
        if attempt < max_attempts:
            self.root.after(35 + (attempt * 35), lambda a=attempt + 1, m=max_attempts: self._force_focus_attempt(a, m))

    def _finish_focus_prime(self):
        self._prime_finish_job = None
        if self.is_open or not self.root.winfo_exists():
            return
        try:
            self.root.withdraw()
            self.root.attributes("-alpha", 0.97)
            self.root.bind("<FocusOut>", self._on_focus_out)
        except Exception:
            pass
        self._focus_primed = True

    def _prime_first_show(self):
        if self._focus_primed or not self.root.winfo_exists():
            return
        try:
            self.root.unbind("<FocusOut>")
            self.root.attributes("-alpha", 0.01)
            self.root.deiconify()
            self.root.update_idletasks()
            self.root.lift()
            self._activate_window_native()
            self.root.update()
        except Exception:
            pass
        if self._prime_finish_job is not None:
            try:
                self.root.after_cancel(self._prime_finish_job)
            except Exception:
                pass
        self._prime_finish_job = self.root.after(140, self._finish_focus_prime)

    def _animate_open(self):
        def step(progress: float):
            self._apply_window_geometry(alpha=0.97 * progress, y_offset=round(-12 + (12 * progress)))

        self.tweens.tween("window_open", OPEN_ANIMATION_MS, step, easing=ease_out_expo)

    def _animate_close(self):
        def step(progress: float):
            self._apply_window_geometry(alpha=0.97 * (1.0 - progress), y_offset=round(-8 * progress))

        def finish():
            if not self.root.winfo_exists():
                return
            self._hide_body_window()
            self.root.withdraw()
            self._apply_window_geometry(alpha=0.97, y_offset=0)
            self.root.after_idle(self._prepare_for_next_show)
            self._is_closing = False

        self.tweens.tween("window_close", CLOSE_ANIMATION_MS, step, easing=ease_in_expo, on_complete=finish)

    def show(self):
        if self.is_open:
            return
        self.tweens.cancel("window_close")
        self._is_closing = False
        self.is_open = True
        self._prepare_for_next_show(force=True)
        self._focus_out_grace_until = time.monotonic() + FOCUS_GRACE_SECONDS
        self._cancel_focus_out_job()

        if self._prime_finish_job is not None:
            try:
                self.root.after_cancel(self._prime_finish_job)
            except Exception:
                pass
            self._prime_finish_job = None

        self.root.unbind("<FocusOut>")
        self._window_width, self._window_height = choose_search_shell_dimensions(
            fixed_width=self._fixed_search_window_width,
            expanded_window_height=self._expanded_window_height,
        )
        self._anchor_window_to_pointer()
        self._apply_window_geometry(alpha=0.0, y_offset=-12)
        self.root.deiconify()
        self.root.update_idletasks()
        if should_focus_on_invocation(not self._has_shown_once):
            self.root.after_idle(lambda m=OPEN_FOCUS_ATTEMPTS: self._force_focus_attempt(0, m))
            self.root.after(140, lambda m=OPEN_FOCUS_ATTEMPTS: self._force_focus_attempt(0, m))
        self._animate_open()
        self.root.after(FOCUS_OUT_REBIND_MS, lambda: self.root.bind("<FocusOut>", self._on_focus_out))
        self._has_shown_once = True

    def hide(self):
        if not self.is_open or self._is_closing:
            return
        self.is_open = False
        self._is_closing = True
        self._cancel_focus_out_job()
        self.tweens.cancel("window_open")
        self._animate_close()

    def hide_to_tray(self):
        self.hide()

    def restore_from_tray(self):
        self.show()

    def _on_root_close(self):
        if should_hide_to_tray(bool(self.tray_controller and self.tray_controller.enabled)):
            self.hide_to_tray()
            return
        self.request_exit()

    def _on_alt_f4(self, event=None):
        self._on_root_close()
        return "break"

    def request_exit(self):
        if self._exiting:
            return
        self._exiting = True
        if self.root.winfo_exists():
            self.root.after(0, self.root.destroy)

    def attach_tray_controller(self, tray_controller):
        self.tray_controller = tray_controller

    def shutdown(self):
        beta_report.write_event("session_shutdown")

        if self._watch_job is not None and self.root.winfo_exists():
            try:
                self.root.after_cancel(self._watch_job)
            except Exception:
                pass
            self._watch_job = None

        if self._data_refresh_job is not None and self.root.winfo_exists():
            try:
                self.root.after_cancel(self._data_refresh_job)
            except Exception:
                pass
            self._data_refresh_job = None

        if self._search_job is not None and self.root.winfo_exists():
            try:
                self.root.after_cancel(self._search_job)
            except Exception:
                pass
            self._search_job = None

        if self._premiere_monitor_job is not None and self.root.winfo_exists():
            try:
                self.root.after_cancel(self._premiere_monitor_job)
            except Exception:
                pass
            self._premiere_monitor_job = None

        self._cancel_focus_out_job()
        self.tweens.finish()

        if self._prime_finish_job is not None and self.root.winfo_exists():
            try:
                self.root.after_cancel(self._prime_finish_job)
            except Exception:
                pass
            self._prime_finish_job = None

        if self._data_observer is not None:
            try:
                self._data_observer.stop()
                self._data_observer.join(timeout=1.0)
            except Exception:
                pass
            self._data_observer = None

        if self.tray_controller is not None:
            try:
                self.tray_controller.stop()
            except Exception:
                pass

    def toggle(self):
        self.hide() if self.is_open else self.show()

    def run(self):
        self.root.mainloop()


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
        self.win.title("FX.palette - Debug")
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

        # â”€â”€ BotÃµes de aÃ§Ã£o â”€â”€
        actions = tk.Frame(self.win, bg=BG, padx=14, pady=8)
        actions.pack(fill="x")

        def make_btn(parent, label, cmd):
            b = tk.Label(parent, text=label, bg=BG2, fg=TEXT_MUTED,
                         font=("Segoe UI", 8), padx=10, pady=4, cursor="hand2")
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda e, c=cmd: self._send(c))
            b.bind("<Enter>",    lambda e, b=b: b.config(fg=ACCENT, bg=BORDER))
            b.bind("<Leave>",    lambda e, b=b: b.config(fg=TEXT_MUTED, bg=BG2))

        make_btn(actions, "Atualizar efeitos", "exportEffects")
        make_btn(actions, "Diagnostico",         "diagnose")
        make_btn(actions, "Limpar logs/bridge", "clearBridge")
        make_btn(actions, "Gerar relatorio beta", "betaReport")

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
                    "worker.log nao encontrado.\n"
                    "O Premiere esta aberto com a extensao carregada?")
                self.text.configure(state="disabled")
                self.status_lbl.config(text="sem arquivo", fg=ORANGE)
        except Exception as e:
            self.status_lbl.config(text=f"erro: {e}", fg=ORANGE)

        self._poll_job = self.root.after(1000, self._refresh_log)

    def _send(self, command: str):
        if command == "betaReport":
            self._create_beta_report()
            return
        send_debug_command(command)
        self.status_lbl.config(text=f"-> {command}", fg=ACCENT)

    def _create_beta_report(self):
        try:
            report_path = beta_report.build_report(
                None,
                EXT_DATA,
                APP_DIR,
                reason="manual_debug_window",
            )
            self.status_lbl.config(text="relatorio beta salvo", fg=GREEN)
            messagebox.showinfo(
                "Relatorio beta salvo",
                "Envie este arquivo ao Paulo:\n" + str(report_path),
                parent=self.win,
            )
        except Exception as exc:
            beta_report.log_exception("Failed to create manual beta report", exc)
            self.status_lbl.config(text=f"erro: {exc}", fg=ORANGE)

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


class SystemTrayController:
    def __init__(self, palette: EffectPalette, debug: DebugWindow):
        self.palette = palette
        self.debug = debug
        self.icon = None
        self._thread = None
        self.available = HAS_TRAY

    def _make_icon_image(self):
        image = Image.new("RGBA", (64, 64), (15, 15, 17, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((6, 6, 58, 58), radius=14, fill=(26, 26, 31, 255), outline=(91, 107, 248, 255), width=3)
        draw.rectangle((20, 16, 44, 24), fill=(61, 214, 140, 255))
        draw.rectangle((20, 30, 44, 38), fill=(91, 107, 248, 255))
        draw.rectangle((20, 44, 36, 50), fill=(245, 166, 35, 255))
        return image

    def _run_on_tk(self, callback):
        try:
            if self.palette.root and self.palette.root.winfo_exists():
                self.palette.root.after(0, callback)
        except Exception as exc:
            beta_report.log_exception("System tray callback failed", exc)

    def _show_palette(self, icon=None, item=None):
        self._run_on_tk(self.palette.show)

    def _toggle_palette(self, icon=None, item=None):
        self._run_on_tk(self.palette.toggle)

    def _show_debug(self, icon=None, item=None):
        self._run_on_tk(self.debug.show)

    def _generate_beta_report(self, icon=None, item=None):
        def create_report():
            try:
                report_path = beta_report.build_report(
                    None,
                    EXT_DATA,
                    APP_DIR,
                    reason="manual_system_tray",
                )
                beta_report.write_event("tray_report_created", {"zip_path": str(report_path)})
                messagebox.showinfo(
                    "Relatorio beta salvo",
                    "Envie este arquivo ao Paulo:\n" + str(report_path),
                    parent=self.palette.root,
                )
            except Exception as exc:
                beta_report.log_exception("Failed to create tray beta report", exc)
                messagebox.showerror(
                    "Erro ao gerar relatorio",
                    "Nao consegui gerar o relatorio beta. Tente pela janela de debug.",
                    parent=self.palette.root,
                )

        self._run_on_tk(create_report)

    def _open_report_folder(self, icon=None, item=None):
        def open_folder():
            try:
                report_dir = beta_report.ensure_report_dir()
                if IS_WINDOWS:
                    os.startfile(str(report_dir))
                else:
                    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(report_dir)])
            except Exception as exc:
                beta_report.log_exception("Failed to open beta report folder", exc)

        self._run_on_tk(open_folder)

    def _quit(self, icon=None, item=None):
        def shutdown():
            beta_report.write_event("tray_quit_requested")
            try:
                self.stop()
            finally:
                self.palette.root.destroy()

        self._run_on_tk(shutdown)

    def start(self):
        if not self.available:
            beta_report.log_app("System tray unavailable: pystray/Pillow not installed", "WARN")
            return

        try:
            menu = pystray.Menu(
                pystray.MenuItem("Abrir paleta", self._show_palette, default=True),
                pystray.MenuItem("Mostrar/Ocultar paleta", self._toggle_palette),
                pystray.MenuItem("Janela de debug", self._show_debug),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Gerar relatorio beta", self._generate_beta_report),
                pystray.MenuItem("Abrir pasta de relatorios", self._open_report_folder),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", self._quit),
            )
            self.icon = pystray.Icon("FX.palette", self._make_icon_image(), "FX.palette", menu)
            self._thread = threading.Thread(target=self.icon.run, daemon=True)
            self._thread.start()
            beta_report.write_event("system_tray_started")
        except Exception as exc:
            self.available = False
            beta_report.log_exception("Failed to start system tray", exc)

    def stop(self):
        if self.icon is None:
            return
        try:
            self.icon.stop()
        except Exception:
            pass
        self.icon = None


# â”€â”€â”€ Listener de atalho global â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class HotkeyListener:
    def __init__(self, palette: EffectPalette, debug: DebugWindow):
        self.palette = palette
        self.debug   = debug
        self.pressed = set()
        self._toggle_combo_active = False
        self._debug_combo_active = False
        self._quit_combo_active = False

    def _combo_state(self):
        ctrl = keyboard.Key.ctrl_l in self.pressed or keyboard.Key.ctrl_r in self.pressed
        space = keyboard.Key.space in self.pressed
        q = keyboard.KeyCode.from_char('\x11') in self.pressed  # Ctrl+Q
        try:
            d = keyboard.KeyCode.from_char('d') in self.pressed or \
                keyboard.KeyCode.from_char('D') in self.pressed or \
                keyboard.KeyCode.from_char('\x04') in self.pressed
        except Exception:
            d = False
        return ctrl, space, d, q

    def _refresh_combo_guards(self):
        ctrl, space, d, q = self._combo_state()
        if not (ctrl and space):
            self._toggle_combo_active = False
        if not (ctrl and d):
            self._debug_combo_active = False
        if not (ctrl and q):
            self._quit_combo_active = False

    def _on_press(self, key):
        self.pressed.add(key)
        ctrl, space, d, q = self._combo_state()

        if ctrl and space and not self._toggle_combo_active:
            self._toggle_combo_active = True
            if premiere_is_focused():
                self.palette.root.after(0, self.palette.toggle)

        if ENABLE_DEBUG_HOTKEY and ctrl and d and not self._debug_combo_active:
            self._debug_combo_active = True
            self.palette.root.after(0, self.debug.toggle)

        if ctrl and q and not self._quit_combo_active:
            self._quit_combo_active = True
            print("[App] Encerrando via Ctrl+Q...")
            self.palette.root.after(0, self.palette.request_exit)

    def _on_release(self, key):
        self.pressed.discard(key)
        self._refresh_combo_guards()

    def start(self):
        if not HAS_PYNPUT:
            print("[Aviso] pynput nao disponivel - hotkeys globais desativadas")
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release)
        self._listener.daemon = True
        self._listener.start()
        print("[Hotkey] Ctrl+Espaco ativo")

    def stop(self):
        if hasattr(self, "_listener"):
            self._listener.stop()


# â”€â”€â”€ Ponto de entrada â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main():
    print("=" * 52)
    print("  Premiere Pro FX.palette")
    print(f"  Atalho     : Ctrl+Espaco")
    print(f"  Debug      : {'Ctrl+D' if ENABLE_DEBUG_HOTKEY else 'menu da system tray'}")
    print(f"  Encerrar   : Ctrl+Q")
    print(f"  Efeitos    : {EFFECTS_FILE}")
    print(f"  Bridge     : {BRIDGE_FILE}")
    print("=" * 52)

    beta_report.start_session(APP_DIR, EXT_DATA)

    palette = EffectPalette()
    debug   = DebugWindow(palette.root)
    tray    = SystemTrayController(palette, debug)
    hotkey  = HotkeyListener(palette, debug)
    hotkey.start()
    tray.start()

    try:
        palette.run()
    except KeyboardInterrupt:
        print("\n[App] Encerrando...")
        beta_report.write_event("keyboard_interrupt")
    except Exception as exc:
        beta_report.log_exception("Unhandled app exception", exc)
        raise
    finally:
        tray.stop()
        palette.shutdown()
        hotkey.stop()


if __name__ == "__main__":
    main()




