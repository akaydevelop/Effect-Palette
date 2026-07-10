import json
import threading
import time

import pytest

import app
from effect_palette import native_windows
from effect_palette.command_bus import (
    CommandManager,
    CommandState,
    atomic_write_json,
    command_from_effect,
)


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
        def IsWindow(self, *args):
            return True

        def IsIconic(self, *args):
            return False

        def ShowWindow(self, *args):
            calls.append(("restore", args))

        def BringWindowToTop(self, *args):
            calls.append(("top", args))

        def SetForegroundWindow(self, *args):
            calls.append(("foreground", args))

    monkeypatch.setattr(native_windows, "USER32", FakeUser32())

    app.activate_window_handle_native(123)

    assert not any(kind == "restore" for kind, _args in calls)
    assert {kind for kind, _args in calls} == {"top", "foreground"}


def write_heartbeat(manager, *, worker_started_at=100.0):
    atomic_write_json(manager.paths.heartbeat, {
        "protocol_version": 2,
        "worker_started_at": worker_started_at,
        "last_heartbeat_at": time.time(),
        "premiere_version": "test",
    })


def test_command_manager_serializes_and_completes(tmp_path):
    manager = CommandManager(tmp_path)
    write_heartbeat(manager)
    envelope = manager.submit_effect({"name": "Blur", "type": "video"})

    with pytest.raises(RuntimeError):
        manager.submit_effect({"name": "Sharpen", "type": "video"})

    pending = manager.paths.pending / f"{envelope.command_id}.json"
    processing = manager.paths.processing / pending.name
    pending.replace(processing)
    value = json.loads(processing.read_text(encoding="utf-8"))
    value.update({"claimed_worker_started_at": 100.0, "claimed_at": time.time()})
    atomic_write_json(processing, value)
    assert manager.poll().state == CommandState.PROCESSING

    atomic_write_json(manager.paths.results / pending.name, {
        "schema_version": 2,
        "command_id": envelope.command_id,
        "status": "done",
        "started_at": time.time(),
        "finished_at": time.time(),
    })
    assert manager.poll().state == CommandState.SUCCEEDED


def test_command_from_previous_worker_becomes_unknown(tmp_path):
    manager = CommandManager(tmp_path)
    write_heartbeat(manager, worker_started_at=200.0)
    envelope = manager.submit_effect({"name": "Blur", "type": "video"})
    pending = manager.paths.pending / f"{envelope.command_id}.json"
    processing = manager.paths.processing / pending.name
    pending.replace(processing)
    value = json.loads(processing.read_text(encoding="utf-8"))
    value["claimed_worker_started_at"] = 100.0
    atomic_write_json(processing, value)

    assert manager.poll().state == CommandState.UNKNOWN


def test_pending_command_is_adopted_after_python_restart(tmp_path):
    first = CommandManager(tmp_path)
    write_heartbeat(first)
    envelope = first.submit_effect({"name": "Blur", "type": "video"})

    restarted = CommandManager(tmp_path)

    assert restarted.snapshot.state == CommandState.QUEUED
    assert restarted.snapshot.envelope.command_id == envelope.command_id


def test_completed_command_is_adopted_once_after_python_restart(tmp_path):
    first = CommandManager(tmp_path)
    write_heartbeat(first)
    envelope = first.submit_effect({"name": "Blur", "type": "video"})
    (first.paths.pending / f"{envelope.command_id}.json").unlink()
    atomic_write_json(first.paths.results / f"{envelope.command_id}.json", {
        "schema_version": 2,
        "command_id": envelope.command_id,
        "envelope": envelope.to_dict(),
        "status": "done",
        "started_at": time.time(),
        "finished_at": time.time(),
    })

    restarted = CommandManager(tmp_path)
    assert restarted.snapshot.state == CommandState.SUCCEEDED
    assert restarted.snapshot.envelope.command_id == envelope.command_id

    restarted.clear_terminal()
    assert restarted.snapshot.state == CommandState.IDLE
    assert not (restarted.paths.results / f"{envelope.command_id}.json").exists()
    assert CommandManager(tmp_path).snapshot.state == CommandState.IDLE


def test_stale_processing_heartbeat_becomes_unknown(tmp_path):
    manager = CommandManager(tmp_path)
    write_heartbeat(manager)
    envelope = manager.submit_effect({"name": "Blur", "type": "video"})
    pending = manager.paths.pending / f"{envelope.command_id}.json"
    processing = manager.paths.processing / pending.name
    pending.replace(processing)
    value = json.loads(processing.read_text(encoding="utf-8"))
    value.update({"claimed_worker_started_at": 100.0, "claimed_at": time.time()})
    atomic_write_json(processing, value)
    atomic_write_json(manager.paths.heartbeat, {
        "protocol_version": 2,
        "worker_started_at": 100.0,
        "last_heartbeat_at": time.time() - 30,
    })

    assert manager.poll().state == CommandState.UNKNOWN
    with pytest.raises(RuntimeError):
        manager.submit_effect({"name": "Sharpen", "type": "video"})


def test_unknown_command_requires_explicit_release(tmp_path):
    manager = CommandManager(tmp_path)
    write_heartbeat(manager, worker_started_at=200.0)
    envelope = manager.submit_effect({"name": "Blur", "type": "video"})
    pending = manager.paths.pending / f"{envelope.command_id}.json"
    processing = manager.paths.processing / pending.name
    pending.replace(processing)
    value = json.loads(processing.read_text(encoding="utf-8"))
    value["claimed_worker_started_at"] = 100.0
    atomic_write_json(processing, value)
    assert manager.poll().state == CommandState.UNKNOWN

    manager.acknowledge_unknown()

    assert manager.snapshot.state == CommandState.IDLE
    assert not processing.exists()
    assert (manager.paths.archive / f"{envelope.command_id}.abandoned.json").exists()


def test_queued_command_can_be_cancelled_safely(tmp_path):
    manager = CommandManager(tmp_path)
    write_heartbeat(manager)
    envelope = manager.submit_effect({"name": "Blur", "type": "video"})

    previous_state = manager.stop_active()

    assert previous_state == CommandState.QUEUED
    assert manager.snapshot.state == CommandState.IDLE
    assert not (manager.paths.pending / f"{envelope.command_id}.json").exists()
    assert (manager.paths.archive / f"{envelope.command_id}.cancelled.json").exists()


def test_stopped_processing_command_does_not_reappear_from_late_result(tmp_path):
    manager = CommandManager(tmp_path)
    write_heartbeat(manager)
    envelope = manager.submit_effect({"name": "Blur", "type": "video"})
    pending = manager.paths.pending / f"{envelope.command_id}.json"
    processing = manager.paths.processing / pending.name
    pending.replace(processing)
    value = json.loads(processing.read_text(encoding="utf-8"))
    value.update({"claimed_worker_started_at": 100.0, "claimed_at": time.time()})
    atomic_write_json(processing, value)
    assert manager.poll().state == CommandState.PROCESSING
    assert manager.stop_active() == CommandState.PROCESSING

    atomic_write_json(manager.paths.results / f"{envelope.command_id}.json", {
        "schema_version": 2,
        "command_id": envelope.command_id,
        "envelope": envelope.to_dict(),
        "status": "done",
        "started_at": time.time(),
        "finished_at": time.time(),
    })

    assert CommandManager(tmp_path).snapshot.state == CommandState.IDLE
    assert not (manager.paths.results / f"{envelope.command_id}.json").exists()
    assert (manager.paths.archive / f"{envelope.command_id}.late-result.json").exists()


def test_protocol_mismatch_disables_submission(tmp_path):
    manager = CommandManager(tmp_path)
    atomic_write_json(manager.paths.heartbeat, {
        "protocol_version": 1,
        "worker_started_at": 100.0,
        "last_heartbeat_at": time.time(),
    })

    with pytest.raises(RuntimeError, match="Bridge desatualizado"):
        manager.submit_effect({"name": "Blur", "type": "video"})


@pytest.mark.parametrize(
    ("effect", "expected_command"),
    [
        ({"name": "Blur", "type": "video"}, "applyEffect"),
        ({"name": "Preset", "type": "preset"}, "applyPreset"),
        ({"name": "Clip", "type": "project_item"}, "insertProjectItem"),
        ({"name": "Asset", "type": "generic_item"}, "insertGenericItem"),
        ({"name": "Favorite", "type": "favorite_item"}, "insertFavoriteItem"),
        ({"name": "Dissolve", "type": "transition_video"}, "applyTransition"),
    ],
)
def test_effect_commands_use_protocol_v2_payloads(effect, expected_command):
    command, payload = command_from_effect(effect)

    assert command == expected_command
    assert isinstance(payload, dict)


def _reference_search(loader, query, allowed_types=None):
    normalized = app.normalize_search_text(query)
    groups = ([], [], [], [])
    for idx, item in enumerate(loader.snapshot.indexed_items):
        if allowed_types and item.item_type not in allowed_types:
            continue
        if item.normalized_name == normalized:
            groups[0].append(idx)
        elif item.normalized_name.startswith(normalized):
            groups[1].append(idx)
        elif any(token.startswith(normalized) for token in item.tokens):
            groups[2].append(idx)
        elif normalized in item.normalized_name:
            groups[3].append(idx)
    key = lambda idx: (
        loader.snapshot.indexed_items[idx].normalized_name,
        loader.snapshot.indexed_items[idx].load_order,
    )
    ranked = [idx for group in groups for idx in sorted(group, key=key)]
    return tuple(loader.snapshot.indexed_items[idx].payload for idx in ranked)


def test_short_query_index_preserves_ranking(tmp_path):
    effects = [
        {"name": name, "type": "video", "category": "Test"}
        for name in ("S", "Scale", "Blur S", "Fast Blur", "Cross Dissolve", "Sharpen", "Basic 3D")
    ]
    (tmp_path / "effects.json").write_text(json.dumps({"effects": effects}), encoding="utf-8")
    paths = app.DataPaths(
        effects_file=tmp_path / "effects.json",
        presets_file=tmp_path / "presets.json",
        project_items_file=tmp_path / "project.json",
        favorites_file=tmp_path / "favorites.json",
        bridge_file=tmp_path / "legacy.json",
        selection_file=tmp_path / "selection.json",
        data_dir=tmp_path,
    )
    loader = app.EffectsLoader(paths)

    for query in ("s", "bl", "ar", "3d"):
        result = loader.search(query, limit=100)
        expected = _reference_search(loader, query)
        assert result.items == expected[:100]
        assert result.total_count == len(expected)


def test_deferred_loader_starts_with_loading_snapshot(tmp_path):
    paths = app.DataPaths(
        effects_file=tmp_path / "effects.json",
        presets_file=tmp_path / "presets.json",
        project_items_file=tmp_path / "project.json",
        favorites_file=tmp_path / "favorites.json",
        bridge_file=tmp_path / "legacy.json",
        selection_file=tmp_path / "selection.json",
        data_dir=tmp_path,
    )
    loader = app.EffectsLoader(paths, defer_initial_load=True)

    assert loader.snapshot.load_state == "loading"
    assert loader.search("blur").visible_count == 0


@pytest.mark.skipif(not app.HAS_QT, reason="PySide6 is not installed")
def test_qt_root_post_runs_on_application_thread():
    qt_app = app.QtWidgets.QApplication.instance() or app.QtWidgets.QApplication([])
    root = app.QtRootAdapter(qt_app)
    calls = []

    root.post(lambda: calls.append("called"))
    qt_app.processEvents()

    assert calls == ["called"]
    root._destroyed = True


@pytest.mark.skipif(not app.HAS_QT, reason="PySide6 is not installed")
def test_qt_timer_can_be_cancelled_from_worker_thread():
    qt_app = app.QtWidgets.QApplication.instance() or app.QtWidgets.QApplication([])
    root = app.QtRootAdapter(qt_app)
    calls = []
    job = root.after(10, lambda: calls.append("unexpected"))
    thread = threading.Thread(target=lambda: root.after_cancel(job))
    thread.start()
    thread.join()
    deadline = time.time() + 0.05
    while time.time() < deadline:
        qt_app.processEvents()
        time.sleep(0.001)

    assert calls == []
    root._destroyed = True


@pytest.mark.skipif(not app.HAS_QT, reason="PySide6 is not installed")
def test_qt_result_model_replaces_rows_without_widgets():
    model = app.ResultListModel()
    row = app.ResultRowModel(
        payload={"name": "Blur", "type": "video"},
        title="Blur",
        subtitle="Video",
        type_label="Effect",
        icon_kind="effect",
        accent_kind="video",
        is_favorite=False,
    )

    model.set_rows((row,))
    index = model.index(0, 0)

    assert model.rowCount() == 1
    assert model.data(index, app.ResultListModel.TitleRole) == "Blur"
    assert model.data(index, app.ResultListModel.PayloadRole)["type"] == "video"


@pytest.mark.skipif(not app.HAS_QT, reason="PySide6 is not installed")
def test_qt_root_rejects_posts_after_shutdown():
    qt_app = app.QtWidgets.QApplication.instance() or app.QtWidgets.QApplication([])
    root = app.QtRootAdapter(qt_app)
    calls = []
    root._destroyed = True

    root.post(lambda: calls.append("unexpected"))
    qt_app.processEvents()

    assert calls == []
