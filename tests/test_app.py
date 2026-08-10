import json

import pytest

import app


def test_bridge_status_requires_matching_timestamp(tmp_path, monkeypatch):
    bridge_file = tmp_path / "premiere_cmd.json"
    monkeypatch.setattr(app, "BRIDGE_FILE", bridge_file)
    bridge_file.write_text(json.dumps({"timestamp": 12.5, "status": "processing"}), encoding="utf-8")

    assert app.read_bridge_status(12.5) == "processing"
    assert app.read_bridge_status(12.6) is None


def test_send_command_returns_written_timestamp(tmp_path, monkeypatch):
    bridge_file = tmp_path / "premiere_cmd.json"
    monkeypatch.setattr(app, "BRIDGE_FILE", bridge_file)

    timestamp = app.send_command({"name": "Test Effect", "type": "video"})
    payload = json.loads(bridge_file.read_text(encoding="utf-8"))

    assert timestamp == payload["timestamp"]
    assert payload["status"] == "pending"
    assert payload["command"] == "applyEffect"


def test_parse_premiere_nest_shortcut(tmp_path):
    kys_file = tmp_path / "Custom.kys"
    kys_file.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<keysets>
  <item>
    <virtualkey>2147483726</virtualkey>
    <modifier.ctrl>false</modifier.ctrl>
    <modifier.alt>false</modifier.alt>
    <modifier.shift>true</modifier.shift>
    <commandname>cmd.clip.nestify</commandname>
  </item>
</keysets>
""",
        encoding="utf-8",
    )

    shortcut = app.parse_premiere_command_shortcut(kys_file, "cmd.clip.nestify")

    assert shortcut == app.PremiereCommandShortcut(vk=ord("N"), shift=True)



def test_parse_premiere_shortcut_normalizes_lowercase_virtual_key(tmp_path):
    kys_file = tmp_path / "Custom.kys"
    kys_file.write_text(
        """<keysets><item><virtualkey>2147483760</virtualkey><modifier.ctrl>true</modifier.ctrl><modifier.alt>true</modifier.alt><modifier.shift>true</modifier.shift><commandname>cmd.sequence.edit.label.0</commandname></item></keysets>""",
        encoding="utf-8",
    )

    shortcut = app.parse_premiere_command_shortcut(kys_file, "cmd.sequence.edit.label.0")

    assert shortcut == app.PremiereCommandShortcut(vk=ord("P"), ctrl=True, alt=True, shift=True)


def test_native_nest_dialog_fills_custom_name(monkeypatch):
    sent = []
    monkeypatch.setattr(
        app,
        "send_native_shortcut",
        lambda shortcut: sent.append(("key", shortcut)) or True,
    )
    monkeypatch.setattr(
        app,
        "send_native_unicode_text",
        lambda text: sent.append(("text", text)) or True,
    )

    assert app.fill_and_confirm_native_nest_dialog("Cena São João")
    assert sent == [
        ("key", app.PremiereCommandShortcut(vk=0x41, ctrl=True)),
        ("text", "Cena São João"),
        ("key", app.PremiereCommandShortcut(vk=0x0D)),
    ]


def test_native_nest_dialog_without_name_only_confirms(monkeypatch):
    sent = []
    monkeypatch.setattr(
        app,
        "send_native_shortcut",
        lambda shortcut: sent.append(shortcut) or True,
    )

    assert app.fill_and_confirm_native_nest_dialog("")
    assert sent == [app.PremiereCommandShortcut(vk=0x0D)]

def test_send_nest_command(tmp_path, monkeypatch):
    bridge_file = tmp_path / "premiere_cmd.json"
    monkeypatch.setattr(app, "BRIDGE_FILE", bridge_file)

    timestamp = app.send_command({
        "name": "Nest / Aninhar clipes",
        "category": "Timeline",
        "type": "timeline_action",
        "action": "nest",
        "nestMode": "premiere",
        "nestName": "Interview selects",
        "nestBin": "Nested Sequences",
    })
    payload = json.loads(bridge_file.read_text(encoding="utf-8"))

    assert timestamp == payload["timestamp"]
    assert payload["status"] == "pending"
    assert payload["command"] == "nestSelection"
    assert payload["action"] == "nest"
    assert payload["nestName"] == "Interview selects"
    assert payload["nestBin"] == "Nested Sequences"


def test_send_nest_api_command(tmp_path, monkeypatch):
    bridge_file = tmp_path / "premiere_cmd.json"
    monkeypatch.setattr(app, "BRIDGE_FILE", bridge_file)

    timestamp = app.send_command({
        "name": "Nest / Aninhar clipes",
        "category": "Timeline",
        "type": "timeline_action",
        "action": "nest",
        "nestMode": "api",
        "nestName": "",
        "nestBin": "Organizacao/Nests",
    })
    payload = json.loads(bridge_file.read_text(encoding="utf-8"))

    assert timestamp == payload["timestamp"]
    assert payload["status"] == "pending"
    assert payload["command"] == "nestSelectionApi"
    assert payload["action"] == "nest"
    assert payload["nestBin"] == "Nested Sequences"


def test_label_command_accepts_slash_and_plain_aliases():
    assert app.parse_label_command("/label") == ""
    assert app.parse_label_command("label") == ""
    assert app.parse_label_command("labels crimson") == "crimson"
    assert app.parse_label_command("etiqueta pink") == "pink"
    assert app.parse_label_command("rótulos cyan") == "cyan"
    assert app.parse_label_command("color") is None


def test_nest_action_is_searchable(tmp_path):
    loader = app.EffectsLoader(app.DataPaths(
        effects_file=tmp_path / "effects.json",
        presets_file=tmp_path / "presets.json",
        project_items_file=tmp_path / "project_items.json",
        favorites_file=tmp_path / "favorites.json",
    ))

    assert loader.search("nest").items[0]["action"] == "nest"
    assert loader.search("aninhar").items[0]["action"] == "nest"
    assert len([item for item in app.TIMELINE_ACTIONS if item["action"] == "nest"]) == 1


def test_automatic_nest_prefers_api_for_multiple_audio_tracks(tmp_path, monkeypatch):
    selection_file = tmp_path / "selection.json"
    selection_file.write_text(json.dumps([
        {"isAudio": False, "trackIndex": 0},
        {"isAudio": True, "trackIndex": 0},
        {"isAudio": True, "trackIndex": 2},
    ]), encoding="utf-8")
    monkeypatch.setattr(app, "SELECTION_FILE", selection_file)
    monkeypatch.setattr(app, "find_premiere_command_shortcut", lambda _command: (app.PremiereCommandShortcut(vk=78), None))

    assert app.resolve_nest_mode("auto") == "api"


def test_automatic_nest_prefers_native_for_simple_selection(tmp_path, monkeypatch):
    selection_file = tmp_path / "selection.json"
    selection_file.write_text(json.dumps([
        {"isAudio": False, "trackIndex": 0},
        {"isAudio": True, "trackIndex": 0},
    ]), encoding="utf-8")
    monkeypatch.setattr(app, "SELECTION_FILE", selection_file)
    monkeypatch.setattr(app, "find_premiere_command_shortcut", lambda _command: (app.PremiereCommandShortcut(vk=78), None))

    assert app.resolve_nest_mode("auto") == "premiere"


def test_nest_preferences_preserve_language(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"language": "pt"}), encoding="utf-8")
    monkeypatch.setattr(app, "SETTINGS_FILE", settings_file)

    app.save_nest_preferences("api")

    assert json.loads(settings_file.read_text(encoding="utf-8")) == {
        "language": "pt",
        "nest": {"mode": "api"},
    }


def test_bridge_terminal_statuses():
    assert not app.bridge_status_is_terminal("pending")
    assert not app.bridge_status_is_terminal("processing")
    assert app.bridge_status_is_terminal("done")
    assert app.bridge_status_is_terminal("error_no_selection")
    assert app.bridge_status_is_success("done")
    assert not app.bridge_status_is_success("error")


class FakeRoot:
    def __init__(self):
        self.posts = []
        self.after_calls = []

    def winfo_exists(self):
        return True

    def post(self, callback):
        self.posts.append(callback)

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))
        return len(self.after_calls)


class FakePalette:
    def __init__(self):
        self.root = FakeRoot()
        self.toggles = []

    def toggle(self, **kwargs):
        self.toggles.append(kwargs)

    def request_exit(self):
        pass


class FakeDebug:
    def toggle(self):
        pass


def test_hotkey_dispatch_uses_direct_post(monkeypatch):
    palette = FakePalette()
    listener = app.HotkeyListener(palette, FakeDebug())
    spec = next(spec for spec in listener._specs if spec.name == "quit")

    listener._schedule_dispatch(spec)

    assert len(palette.root.posts) == 1
    assert palette.root.after_calls == []


def test_main_hotkey_is_ignored_when_premiere_is_not_focused(monkeypatch):
    palette = FakePalette()
    listener = app.HotkeyListener(palette, FakeDebug())
    spec = next(spec for spec in listener._specs if spec.name == "toggle_palette")
    monkeypatch.setattr(app, "premiere_is_focused", lambda: False)

    listener._dispatch_hotkey(spec)

    assert palette.toggles == []


def test_native_activation_does_not_restore_maximized_window(monkeypatch):
    calls = []

    class FakeUser32:
        def ShowWindow(self, *args):
            calls.append(("restore", args))

        def BringWindowToTop(self, *args):
            calls.append(("top", args))

        def SetForegroundWindow(self, *args):
            calls.append(("foreground", args))

        def SetActiveWindow(self, *args):
            calls.append(("active", args))

        def SetFocus(self, *args):
            calls.append(("focus", args))

    monkeypatch.setattr(app, "USER32", FakeUser32())
    monkeypatch.setattr(app, "window_is_minimized_native", lambda hwnd: False)

    app.activate_window_handle_native(123)

    assert not any(kind == "restore" for kind, _args in calls)
    assert {kind for kind, _args in calls} == {"top", "foreground", "active", "focus"}


@pytest.mark.skipif(not app.HAS_QT, reason="PySide6 is not installed")
def test_qt_root_post_runs_on_application_thread():
    qt_app = app.QtWidgets.QApplication.instance() or app.QtWidgets.QApplication([])
    root = app.QtRootAdapter(qt_app)
    calls = []

    root.post(lambda: calls.append("called"))
    qt_app.processEvents()

    assert calls == ["called"]
    root._destroyed = True
