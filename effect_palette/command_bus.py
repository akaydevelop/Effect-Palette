from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


PROTOCOL_VERSION = 2
HEARTBEAT_READY_SECONDS = 3.0
HEARTBEAT_STALE_SECONDS = 5.0
RESULT_RETENTION_COUNT = 200


class CommandState(str, Enum):
    IDLE = "idle"
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CommandPaths:
    root: Path
    pending: Path
    processing: Path
    results: Path
    archive: Path
    heartbeat: Path

    @classmethod
    def from_data_dir(cls, data_dir: Path) -> "CommandPaths":
        root = data_dir / "commands"
        return cls(
            root=root,
            pending=root / "pending",
            processing=root / "processing",
            results=root / "results",
            archive=root / "archive",
            heartbeat=root / "worker_heartbeat.json",
        )

    def ensure(self) -> None:
        for directory in (self.root, self.pending, self.processing, self.results, self.archive):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class CommandEnvelope:
    command_id: str
    created_at: float
    command: str
    payload: dict
    schema_version: int = PROTOCOL_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "command_id": self.command_id,
            "created_at": self.created_at,
            "command": self.command,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "CommandEnvelope":
        return cls(
            schema_version=int(value.get("schema_version", 0)),
            command_id=str(value["command_id"]),
            created_at=float(value["created_at"]),
            command=str(value["command"]),
            payload=dict(value.get("payload") or {}),
        )


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    status: str
    started_at: float | None
    finished_at: float
    detail: str = ""
    schema_version: int = PROTOCOL_VERSION

    @property
    def succeeded(self) -> bool:
        return self.status == "done"

    @classmethod
    def from_dict(cls, value: dict) -> "CommandResult":
        started_at = value.get("started_at")
        return cls(
            schema_version=int(value.get("schema_version", 0)),
            command_id=str(value["command_id"]),
            status=str(value["status"]),
            started_at=float(started_at) if started_at is not None else None,
            finished_at=float(value.get("finished_at") or time.time()),
            detail=str(value.get("detail") or ""),
        )


@dataclass(frozen=True)
class CommandSnapshot:
    state: CommandState
    envelope: CommandEnvelope | None = None
    result: CommandResult | None = None
    worker_ready: bool = False
    worker_detail: str = ""

    @property
    def active(self) -> bool:
        return self.state in {CommandState.QUEUED, CommandState.PROCESSING, CommandState.UNKNOWN}


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def safe_read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def command_from_effect(effect: dict) -> tuple[str, dict]:
    effect_type = effect.get("type", "video")
    if effect_type == "preset":
        return "applyPreset", {
            "effect": effect["name"],
            "filterPresetsJSON": json.dumps(effect.get("filterPresets", [])),
        }
    if effect_type == "project_item":
        return "insertProjectItem", {
            "itemName": effect["name"],
            "nodeId": effect.get("nodeId", ""),
            "itemType": effect.get("itemType", ""),
        }
    if effect_type == "generic_item":
        return "insertGenericItem", {
            "itemName": effect["name"],
            "genericKey": effect.get("genericKey", ""),
        }
    if effect_type == "favorite_item":
        return "insertFavoriteItem", {
            "itemName": effect["name"],
            "mediaPath": effect.get("mediaPath", ""),
            "sequenceID": effect.get("sequenceID", ""),
            "itemType": effect.get("itemType", ""),
            "isSequence": bool(effect.get("isSequence", False)),
            "favoriteType": effect.get("favoriteType", ""),
            "sourceProjectPath": effect.get("sourceProjectPath", ""),
        }
    if effect_type in {"transition_video", "transition_audio"}:
        return "applyTransition", {
            "transitionName": effect["name"],
            "transitionType": "audio" if effect_type == "transition_audio" else "video",
            "transitionPlacement": effect.get("transitionPlacement", "auto"),
        }
    return "applyEffect", {
        "effect": effect["name"],
        "category": effect.get("category", ""),
        "type": effect_type,
    }


class CommandManager:
    """Durable, single-flight command state independent of palette visibility."""

    def __init__(self, data_dir: Path):
        self.paths = CommandPaths.from_data_dir(data_dir)
        self.paths.ensure()
        self._lock = threading.RLock()
        self._listeners: list[Callable[[CommandSnapshot], None]] = []
        self._snapshot = CommandSnapshot(CommandState.IDLE)
        self._adopt_existing()
        self.poll(notify=False)

    @property
    def snapshot(self) -> CommandSnapshot:
        with self._lock:
            return self._snapshot

    def subscribe(self, callback: Callable[[CommandSnapshot], None]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def unsubscribe(self, callback: Callable[[CommandSnapshot], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def worker_status(self) -> tuple[bool, str]:
        heartbeat = safe_read_json(self.paths.heartbeat)
        if not heartbeat:
            return False, "Bridge offline"
        if int(heartbeat.get("protocol_version", 0)) != PROTOCOL_VERSION:
            return False, "Bridge desatualizado - reinicie o Premiere"
        try:
            age = time.time() - float(heartbeat.get("last_heartbeat_at", 0))
        except (TypeError, ValueError):
            return False, "Heartbeat invalido"
        if age > HEARTBEAT_READY_SECONDS:
            return False, "Bridge offline"
        return True, ""

    def submit_effect(self, effect: dict) -> CommandEnvelope:
        command, payload = command_from_effect(effect)
        return self.submit(command, payload)

    def submit(self, command: str, payload: dict | None = None) -> CommandEnvelope:
        with self._lock:
            if self._snapshot.active:
                raise RuntimeError("Ja existe um comando em andamento")
            ready, detail = self.worker_status()
            if not ready:
                raise RuntimeError(detail)
            envelope = CommandEnvelope(
                command_id=str(uuid.uuid4()),
                created_at=time.time(),
                command=command,
                payload=dict(payload or {}),
            )
            path = self.paths.pending / f"{envelope.command_id}.json"
            atomic_write_json(path, envelope.to_dict())
            self._set_snapshot(CommandSnapshot(
                CommandState.QUEUED,
                envelope=envelope,
                worker_ready=True,
            ))
            return envelope

    def poll(self, *, notify: bool = True) -> CommandSnapshot:
        with self._lock:
            ready, detail = self.worker_status()
            snapshot = self._snapshot
            envelope = snapshot.envelope
            if envelope is None:
                self._adopt_existing()
                snapshot = self._snapshot
                envelope = snapshot.envelope

            if envelope is not None:
                command_id = envelope.command_id
                result_value = safe_read_json(self.paths.results / f"{command_id}.json")
                if result_value:
                    try:
                        result = CommandResult.from_dict(result_value)
                    except (KeyError, TypeError, ValueError):
                        result = None
                    if result and result.command_id == command_id:
                        state = CommandState.SUCCEEDED if result.succeeded else CommandState.FAILED
                        snapshot = CommandSnapshot(state, envelope, result, ready, detail)
                    else:
                        snapshot = CommandSnapshot(CommandState.UNKNOWN, envelope, None, ready, "Resultado invalido")
                elif (self.paths.processing / f"{command_id}.json").exists():
                    processing_value = safe_read_json(self.paths.processing / f"{command_id}.json") or {}
                    heartbeat = safe_read_json(self.paths.heartbeat) or {}
                    claimed_worker = processing_value.get("claimed_worker_started_at")
                    active_worker = heartbeat.get("worker_started_at")
                    worker_restarted = claimed_worker is None or active_worker is None or claimed_worker != active_worker
                    if worker_restarted:
                        snapshot = CommandSnapshot(CommandState.UNKNOWN, envelope, None, ready, "Resposta perdida - confira a timeline")
                    elif not ready and self._heartbeat_age() > HEARTBEAT_STALE_SECONDS:
                        snapshot = CommandSnapshot(CommandState.UNKNOWN, envelope, None, False, "Resposta perdida - confira a timeline")
                    else:
                        snapshot = CommandSnapshot(CommandState.PROCESSING, envelope, None, ready, detail)
                elif (self.paths.pending / f"{command_id}.json").exists():
                    snapshot = CommandSnapshot(CommandState.QUEUED, envelope, None, ready, detail)
                elif snapshot.state not in {CommandState.SUCCEEDED, CommandState.FAILED}:
                    snapshot = CommandSnapshot(CommandState.UNKNOWN, envelope, None, ready, "Estado do comando desconhecido")
            else:
                snapshot = CommandSnapshot(CommandState.IDLE, worker_ready=ready, worker_detail=detail)

            self._set_snapshot(snapshot, notify=notify)
            return snapshot

    def clear_terminal(self) -> None:
        with self._lock:
            if self._snapshot.state not in {CommandState.SUCCEEDED, CommandState.FAILED}:
                return
            if self._snapshot.envelope is not None:
                command_id = self._snapshot.envelope.command_id
                source = self.paths.results / f"{command_id}.json"
                destination = self.paths.archive / f"{command_id}.result.json"
                try:
                    if source.exists():
                        source.replace(destination)
                except OSError:
                    pass
            self._snapshot = CommandSnapshot(CommandState.IDLE, worker_ready=self.worker_status()[0])
        self._notify()

    def acknowledge_unknown(self) -> None:
        with self._lock:
            if self._snapshot.state != CommandState.UNKNOWN or self._snapshot.envelope is None:
                return
            command_id = self._snapshot.envelope.command_id
            for source_dir in (self.paths.pending, self.paths.processing):
                source = source_dir / f"{command_id}.json"
                if source.exists():
                    destination = self.paths.archive / f"{command_id}.abandoned.json"
                    try:
                        source.replace(destination)
                    except OSError:
                        pass
            self._snapshot = CommandSnapshot(CommandState.IDLE, worker_ready=self.worker_status()[0])
        self._notify()

    def stop_active(self) -> CommandState | None:
        """Stop tracking an active command without claiming host-side interruption."""
        with self._lock:
            snapshot = self._snapshot
            if snapshot.state not in {CommandState.QUEUED, CommandState.PROCESSING} or snapshot.envelope is None:
                return None
            command_id = snapshot.envelope.command_id
            marker = self.paths.archive / f"{command_id}.cancelled.json"
            source_dir = self.paths.pending if snapshot.state == CommandState.QUEUED else self.paths.processing
            source = source_dir / f"{command_id}.json"
            try:
                if source.exists():
                    source.replace(marker)
                else:
                    atomic_write_json(marker, snapshot.envelope.to_dict())
            except OSError:
                atomic_write_json(marker, snapshot.envelope.to_dict())
            result_source = self.paths.results / f"{command_id}.json"
            if result_source.exists():
                try:
                    result_source.replace(self.paths.archive / f"{command_id}.late-result.json")
                except OSError:
                    pass
            previous_state = snapshot.state
            ready, detail = self.worker_status()
            self._snapshot = CommandSnapshot(CommandState.IDLE, worker_ready=ready, worker_detail=detail)
        self._notify()
        return previous_state

    def cleanup(self) -> None:
        files = sorted(self.paths.results.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in files[RESULT_RETENTION_COUNT:]:
            try:
                path.unlink()
            except OSError:
                pass

    def _heartbeat_age(self) -> float:
        heartbeat = safe_read_json(self.paths.heartbeat)
        if not heartbeat:
            return float("inf")
        try:
            return max(0.0, time.time() - float(heartbeat.get("last_heartbeat_at", 0)))
        except (TypeError, ValueError):
            return float("inf")

    def _adopt_existing(self) -> None:
        candidates: list[tuple[float, Path, CommandState]] = []
        for directory, state in (
            (self.paths.processing, CommandState.PROCESSING),
            (self.paths.pending, CommandState.QUEUED),
        ):
            for path in directory.glob("*.json"):
                try:
                    candidates.append((path.stat().st_mtime, path, state))
                except OSError:
                    continue
        if not candidates:
            result_candidates = []
            for path in self.paths.results.glob("*.json"):
                command_id = path.stem
                if (self.paths.archive / f"{command_id}.cancelled.json").exists():
                    try:
                        path.replace(self.paths.archive / f"{command_id}.late-result.json")
                    except OSError:
                        pass
                    continue
                value = safe_read_json(path)
                if not value or not isinstance(value.get("envelope"), dict):
                    continue
                try:
                    result = CommandResult.from_dict(value)
                    envelope = CommandEnvelope.from_dict(value["envelope"])
                except (KeyError, TypeError, ValueError):
                    continue
                if result.command_id != envelope.command_id:
                    continue
                result_candidates.append((result.finished_at, envelope, result))
            if not result_candidates:
                return
            _, envelope, result = min(result_candidates, key=lambda item: item[0])
            ready, detail = self.worker_status()
            state = CommandState.SUCCEEDED if result.succeeded else CommandState.FAILED
            self._snapshot = CommandSnapshot(state, envelope, result, ready, detail)
            return
        _, path, state = min(candidates, key=lambda item: item[0])
        value = safe_read_json(path)
        if not value:
            return
        try:
            envelope = CommandEnvelope.from_dict(value)
        except (KeyError, TypeError, ValueError):
            return
        ready, detail = self.worker_status()
        self._snapshot = CommandSnapshot(state, envelope, worker_ready=ready, worker_detail=detail)

    def _set_snapshot(self, snapshot: CommandSnapshot, *, notify: bool = True) -> None:
        changed = snapshot != self._snapshot
        self._snapshot = snapshot
        if changed and notify:
            self._notify()

    def _notify(self) -> None:
        with self._lock:
            listeners = tuple(self._listeners)
            snapshot = self._snapshot
        for listener in listeners:
            try:
                listener(snapshot)
            except Exception:
                pass
