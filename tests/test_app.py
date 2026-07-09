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
