#!/usr/bin/env python3
"""Inventory, scaffold, and validate Dula scene contracts."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - handled as an input/tooling error
    Draft202012Validator = None


CONTRACT_VERSION = "1.0"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "references" / "scene-contract.schema.json"
DEFAULT_CONTRACT = Path("config") / "scene_contract.json"

ENGINE_EVENTS = {
    "Move",
    "Animate",
    "Face",
    "Hide",
    "Show",
    "ShowAura",
    "HideAura",
    "ShowBeam",
    "HideBeam",
    "JointMarkers",
    "DoorEvent",
}

ENGINE_SPECIAL_EVENTS = {
    "SharkAppear",
    "SharkOrbit",
    "SplashStart",
    "SplashStop",
    "KnockHurdle",
    "ShowHurdleMarkers",
    "HideHurdleMarkers",
    "RescueTakecopter",
    "OpenDrawer",
    "ExtinguishZodiacFlame",
}

COLLISION_GUARDED_CAMERAS = {
    "Static",
    "CloseUp",
    "OverShoulder",
    "TrackingCloseUp",
}

REGISTER_SCENE_RE = re.compile(
    r"registerScene\(\s*['\"](?P<name>[^'\"]+)['\"]\s*,\s*(?P<export>[A-Za-z_$][\w$]*)"
)
REGISTER_CHARACTER_RE = re.compile(
    r"registerCharacter\(\s*['\"](?P<name>[^'\"]+)['\"]\s*,\s*(?P<export>[A-Za-z_$][\w$]*)"
)
METHOD_RE = re.compile(r"(?m)^[ \t]{2}(?![ \t])([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{")
CLASS_RE = re.compile(r"export\s+class\s+([A-Za-z_$][\w$]*)\s+extends\s+SceneBase")


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    path: str | None = None
    entry: int | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.path is not None:
            result["path"] = self.path
        if self.entry is not None:
            result["entry"] = self.entry
        return result


class SceneToolInputError(RuntimeError):
    pass


def _load_story_tool(project_root: Path):
    tool_path = project_root / "dula-skills" / "story-writer" / "scripts" / "story_tool.py"
    if not tool_path.is_file():
        raise SceneToolInputError(f"Story tool not found: {tool_path}")
    module_name = "_dula_story_tool_for_scene_designer"
    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    if spec is None or spec.loader is None:
        raise SceneToolInputError(f"Unable to load story tool: {tool_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _find_project_root(episode_dir: Path) -> Path:
    current = episode_dir.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "dula-story").is_dir() and (candidate / "dula-skills").is_dir():
            return candidate
    raise SceneToolInputError(f"Could not find project root from {episode_dir}")


def _resolve_episode_dir(value: str) -> Path:
    episode_dir = Path(value).resolve()
    if not episode_dir.is_dir():
        raise SceneToolInputError(f"Episode directory does not exist: {episode_dir}")
    return episode_dir


def _resolve_story(episode_dir: Path, value: str | None, contract: dict[str, Any] | None = None) -> Path:
    if value:
        story = Path(value)
        if not story.is_absolute():
            story = (Path.cwd() / story).resolve()
    else:
        source = contract.get("sourceStory") if isinstance(contract, dict) else None
        story = (episode_dir / (source or "script.story")).resolve()
    if not story.is_file():
        raise SceneToolInputError(f"Story file does not exist: {story}")
    return story


def _resolve_contract(episode_dir: Path, value: str | None) -> Path:
    if value:
        path = Path(value)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        return path
    return (episode_dir / DEFAULT_CONTRACT).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SceneToolInputError(f"JSON file does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SceneToolInputError(f"Unable to read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SceneToolInputError(f"Expected a JSON object in {path}")
    return data


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _vec_from_options(options: dict[str, str], *, default_y: float = 0.0) -> list[float] | None:
    x = _number(options.get("x"))
    z = _number(options.get("z"))
    if x is None or z is None:
        return None
    y = _number(options.get("y"))
    return [x, default_y if y is None else y, z]


def _camera_subjects(options: dict[str, str]) -> list[str]:
    subjects: list[str] = []
    for key in ("characterName", "character", "characterA", "characterB", "target", "subject"):
        value = options.get(key)
        if value and value not in subjects:
            subjects.append(value)
    return subjects


def _lower_first(value: str) -> str:
    return value[:1].lower() + value[1:] if value else value


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _explicit_registrations(bootstrap: Path) -> dict[str, dict[str, str]]:
    if not bootstrap.is_file():
        return {"scenes": {}, "characters": {}}
    text = bootstrap.read_text(encoding="utf-8")
    return {
        "scenes": {match.group("name"): match.group("export") for match in REGISTER_SCENE_RE.finditer(text)},
        "characters": {
            match.group("name"): match.group("export") for match in REGISTER_CHARACTER_RE.finditer(text)
        },
    }


def _scene_source_for_name(project_root: Path, episode_dir: Path, name: str) -> Path | None:
    candidates = [
        episode_dir / "scenes" / f"{name}.js",
        project_root / "dula-assets" / "scenes" / f"{name}.js",
    ]
    return next((path.resolve() for path in candidates if path.is_file()), None)


def _resolve_module(project_root: Path, episode_dir: Path, module: str) -> Path:
    raw = Path(module)
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.extend((episode_dir / raw, project_root / raw))
    return next((path.resolve() for path in candidates if path.is_file()), candidates[0].resolve())


def _scene_methods(source: Path | None) -> set[str]:
    if source is None or not source.is_file():
        return set()
    return set(METHOD_RE.findall(source.read_text(encoding="utf-8")))


def _story_facts(story_tool: Any, story: Path) -> dict[str, Any]:
    text = story.read_text(encoding="utf-8")
    entries, parse_issues = story_tool.parse_story(text)
    current_scene: str | None = None
    scene_order: list[str] = []
    characters: set[str] = set()
    events: list[dict[str, Any]] = []
    cameras: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    moves: list[dict[str, Any]] = []
    dialogue: list[dict[str, Any]] = []
    entry_facts: list[dict[str, Any]] = []
    sfx: list[dict[str, Any]] = []
    order = 0

    for entry in entries:
        scene_match = story_tool.SCENE_RE.search(entry.content)
        if scene_match:
            current_scene = scene_match.group(1)
            if current_scene not in scene_order:
                scene_order.append(current_scene)

        speakers = story_tool.SPEAKER_RE.findall(entry.content)
        for speaker in speakers:
            characters.add(speaker)
            dialogue.append(
                {
                    "character": speaker,
                    "entry": entry.index,
                    "start": entry.start,
                    "scene": current_scene,
                }
            )

        entry_cameras: list[str] = []
        entry_events: list[str] = []
        for tag_match in story_tool.TAG_RE.finditer(entry.content):
            namespace, name, option_parts = story_tool._split_tag(tag_match.group(1))
            options = story_tool._option_map(option_parts)
            order += 1
            if namespace == "Event":
                occurrence = {
                    "tag": name,
                    "options": options,
                    "entry": entry.index,
                    "start": entry.start,
                    "scene": current_scene,
                    "order": order,
                }
                events.append(occurrence)
                entry_events.append(name)
                character = options.get("character")
                if character:
                    characters.add(character)
                if name == "Move":
                    target = _vec_from_options(options)
                    moves.append({**occurrence, "character": character, "target": target})
            elif namespace == "Position":
                characters.add(name)
                positions.append(
                    {
                        "character": name,
                        "position": _vec_from_options(options),
                        "face": options.get("face"),
                        "entry": entry.index,
                        "start": entry.start,
                        "scene": current_scene,
                        "order": order,
                    }
                )
            elif namespace == "Camera":
                camera = {
                    "type": name,
                    "options": options,
                    "subjects": _camera_subjects(options),
                    "entry": entry.index,
                    "start": entry.start,
                    "end": entry.end,
                    "scene": current_scene,
                    "order": order,
                }
                cameras.append(camera)
                entry_cameras.append(name)
            elif namespace == "SFX":
                sfx.append(
                    {
                        "action": name,
                        "name": options.get("name"),
                        "entry": entry.index,
                        "scene": current_scene,
                    }
                )

        entry_facts.append(
            {
                "index": entry.index,
                "start": entry.start,
                "end": entry.end,
                "duration": (entry.end - entry.start) if entry.start is not None and entry.end is not None else None,
                "scene": current_scene,
                "speakers": speakers,
                "events": entry_events,
                "cameras": entry_cameras,
            }
        )

    custom_events = [
        event for event in events if event["tag"] not in ENGINE_EVENTS and event["tag"] not in ENGINE_SPECIAL_EVENTS
    ]
    engine_events = [event for event in events if event not in custom_events]
    return {
        "story": str(story),
        "scenes": scene_order,
        "characters": sorted(characters),
        "entries": entry_facts,
        "events": events,
        "customEvents": custom_events,
        "engineEvents": engine_events,
        "cameras": cameras,
        "positions": positions,
        "moves": moves,
        "dialogue": dialogue,
        "sfx": sfx,
        "parseIssues": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "message": issue.message,
                "line": issue.line,
                "entry": issue.entry,
            }
            for issue in parse_issues
        ],
    }


def build_inventory(episode_dir: Path, story: Path) -> dict[str, Any]:
    project_root = _find_project_root(episode_dir)
    story_tool = _load_story_tool(project_root)
    facts = _story_facts(story_tool, story)
    catalog = story_tool.discover_catalog(project_root, episode_dir)
    bootstrap = episode_dir / "bootstrap.js"
    explicit = _explicit_registrations(bootstrap)
    sources: dict[str, Any] = {}
    for scene_name in facts["scenes"]:
        source = _scene_source_for_name(project_root, episode_dir, scene_name)
        sources[scene_name] = {
            "file": _relative(source, project_root) if source else None,
            "methods": sorted(_scene_methods(source)),
            "episodeLocal": bool(source and source.is_relative_to(episode_dir)),
        }

    return {
        "inventoryVersion": 1,
        "episode": episode_dir.name,
        "episodeDir": _relative(episode_dir, project_root),
        "story": _relative(story, project_root),
        "scenes": facts["scenes"],
        "characters": facts["characters"],
        "entries": facts["entries"],
        "events": {
            "custom": facts["customEvents"],
            "engine": facts["engineEvents"],
        },
        "cameras": facts["cameras"],
        "positions": facts["positions"],
        "moves": facts["moves"],
        "dialogue": facts["dialogue"],
        "sfx": facts["sfx"],
        "registrations": {
            "explicit": explicit,
            "reachableScenes": catalog.get("scenes", []),
            "reachableCharacters": catalog.get("characters", []),
        },
        "sceneSources": sources,
        "storyIssues": facts["parseIssues"],
        "runtime": {
            "engineEvents": sorted(ENGINE_EVENTS),
            "engineSpecialEvents": sorted(ENGINE_SPECIAL_EVENTS),
            "collisionGuardedCameras": sorted(COLLISION_GUARDED_CAMERAS),
            "customEventArgumentMode": "none",
            "sceneConstructorArguments": 0,
        },
    }


def _scene_characters(inventory: dict[str, Any], scene_name: str) -> list[str]:
    found: set[str] = set()
    for category in ("positions", "moves", "dialogue"):
        for item in inventory.get(category, []):
            if item.get("scene") == scene_name and item.get("character"):
                found.add(item["character"])
    return sorted(found)


def _first_position(inventory: dict[str, Any], scene_name: str, character: str) -> list[float]:
    for item in inventory.get("positions", []):
        if item.get("scene") == scene_name and item.get("character") == character and item.get("position"):
            return item["position"]
    return [0.0, 0.0, 0.0]


def scaffold_contract(inventory: dict[str, Any], project_root: Path, episode_dir: Path) -> dict[str, Any]:
    scenes: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    blocking: list[dict[str, Any]] = []
    entity_by_runtime_scene: dict[tuple[str, str], str] = {}

    multiple_scene_chars: dict[str, int] = defaultdict(int)
    for scene_name in inventory["scenes"]:
        for character in _scene_characters(inventory, scene_name):
            multiple_scene_chars[character] += 1

    for scene_name in inventory["scenes"]:
        source_info = inventory["sceneSources"].get(scene_name) or {}
        local = bool(source_info.get("episodeLocal"))
        source_file = source_info.get("file")
        if local and source_file:
            module = Path(source_file).relative_to(Path(inventory["episodeDir"])).as_posix()
        elif source_file:
            module = source_file
        else:
            module = f"scenes/{scene_name}.js"
        scenes.append(
            {
                "registryName": scene_name,
                "implementation": {
                    "kind": "episode-local" if local else "official",
                    "name": scene_name,
                    "module": module,
                    "export": scene_name,
                    "bootstrap": "bootstrap.js",
                    "readiness": "synchronous",
                },
                "intent": {
                    "location": "TODO: name the physical location",
                    "timeOfDay": "TODO: name the time and light condition",
                    "tone": ["TODO: define the visual tone"],
                    "storyFunction": "TODO: state what dramatic work this scene performs",
                    "visualRules": ["TODO: state one concrete readability rule"],
                },
                "coordinates": {
                    "unit": "meter",
                    "upAxis": "+Y",
                    "horizontalAxes": ["X", "Z"],
                    "groundY": 0.0,
                },
                "stage": {
                    "bounds": {"min": [-10.0, 0.0, -10.0], "max": [10.0, 6.0, 10.0]},
                    "zones": [
                        {
                            "id": "mainStage",
                            "bounds": {"min": [-8.0, 0.0, -8.0], "max": [8.0, 3.0, 8.0]},
                            "walkable": True,
                            "purpose": ["TODO: define the performance purpose"],
                        }
                    ],
                    "anchors": {},
                },
                "lighting": {
                    "mood": "TODO: define lighting mood",
                    "readabilityRules": ["TODO: define face and prop readability"],
                },
                "cameraObstacles": [],
                "audioAnchors": [],
                "dependencies": [],
            }
        )

        for character in _scene_characters(inventory, scene_name):
            entity_id = character if multiple_scene_chars[character] == 1 else f"{character}_{scene_name}"
            entity_by_runtime_scene[(character, scene_name)] = entity_id
            position = _first_position(inventory, scene_name, character)
            entities.append(
                {
                    "id": entity_id,
                    "scene": scene_name,
                    "kind": "character",
                    "runtimeName": character,
                    "binding": f"character:{character}",
                    "parent": "$scene",
                    "initialPresence": "onstage",
                    "visualForwardAxis": "unknown",
                    "focusPoints": {"body": [0.0, 1.0, 0.0], "face": [0.0, 1.6, 0.0]},
                    "initial": {
                        "visible": True,
                        "transform": {"space": "world", "relativeTo": "$scene", "position": position},
                    },
                }
            )

    last_position: dict[tuple[str, str], list[float]] = {}
    movement_items = sorted(
        [*inventory.get("positions", []), *inventory.get("moves", [])], key=lambda item: item.get("order") or 0
    )
    for index, item in enumerate(movement_items, start=1):
        character = item.get("character")
        scene_name = item.get("scene")
        if not character or not scene_name:
            continue
        entity_id = entity_by_runtime_scene.get((character, scene_name))
        if not entity_id:
            continue
        target = item.get("position") or item.get("target")
        if not target:
            continue
        key = (character, scene_name)
        start = last_position.get(key, target)
        blocking.append(
            {
                "id": f"block{index}",
                "scene": scene_name,
                "character": entity_id,
                "entry": item.get("entry") or 1,
                "from": start,
                "to": target,
                "zone": "mainStage",
                "clearance": 0.25,
                "purpose": "TODO: explain the dramatic purpose of this placement or move",
            }
        )
        last_position[key] = target

    custom_events: list[dict[str, Any]] = []
    seen_event_keys: set[tuple[str, str]] = set()
    for event in inventory.get("events", {}).get("custom", []):
        key = (event.get("scene"), event["tag"])
        if key in seen_event_keys:
            continue
        seen_event_keys.add(key)
        custom_events.append(
            {
                "tag": event["tag"],
                "scene": event.get("scene"),
                "handler": _lower_first(event["tag"]),
                "argumentMode": "none",
                "durationSeconds": 0.0,
                "requires": [],
                "effects": [],
            }
        )

    return {
        "$schema": "../../../../../dula-skills/scene-designer/references/scene-contract.schema.json",
        "contractVersion": CONTRACT_VERSION,
        "episode": episode_dir.name,
        "sourceStory": "script.story",
        "intent": {
            "premise": "TODO: summarize the physical scene problem in one sentence",
            "audience": "TODO: define the audience",
            "designPriorities": ["TODO: define the first scene-design priority"],
        },
        "registrations": {
            "bootstrap": "bootstrap.js",
            "scenes": inventory["scenes"],
            "characters": inventory["characters"],
        },
        "scenes": scenes,
        "entities": entities,
        "state": {},
        "events": custom_events,
        "blocking": blocking,
        "shotChecks": [],
        "acceptance": {
            "staticChecks": ["scene-tool", "story-tool", "node-check"],
            "runtimeChecks": ["dula-inspect-team", "dula-verify", "visual-review"],
        },
    }


def _schema_diagnostics(contract: dict[str, Any]) -> list[Diagnostic]:
    if Draft202012Validator is None:
        raise SceneToolInputError("The project requires the 'jsonschema' Python package for scene validation")
    schema = _load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema)
    diagnostics: list[Diagnostic] = []
    for error in sorted(
        validator.iter_errors(contract),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    ):
        path = "/".join(str(part) for part in error.absolute_path) or "$"
        diagnostics.append(Diagnostic("error", "SCHEMA", error.message, path=path))
    return diagnostics


def _unique_diagnostics(items: Iterable[dict[str, Any]], key: str, code: str, label: str) -> list[Diagnostic]:
    seen: set[Any] = set()
    diagnostics: list[Diagnostic] = []
    for index, item in enumerate(items):
        value = item.get(key) if isinstance(item, dict) else None
        if value in seen:
            diagnostics.append(
                Diagnostic("error", code, f"Duplicate {label} {value!r}", path=f"{label}[{index}]")
            )
        seen.add(value)
    return diagnostics


def _inside(point: Any, bounds: Any, epsilon: float = 1e-6) -> bool:
    if not (
        isinstance(point, list)
        and len(point) == 3
        and isinstance(bounds, dict)
        and isinstance(bounds.get("min"), list)
        and isinstance(bounds.get("max"), list)
        and len(bounds["min"]) == 3
        and len(bounds["max"]) == 3
    ):
        return False
    try:
        return all(bounds["min"][i] - epsilon <= point[i] <= bounds["max"][i] + epsilon for i in range(3))
    except TypeError:
        return False


def _bounds_valid(bounds: Any) -> bool:
    if not isinstance(bounds, dict):
        return False
    minimum, maximum = bounds.get("min"), bounds.get("max")
    return bool(
        isinstance(minimum, list)
        and isinstance(maximum, list)
        and len(minimum) == 3
        and len(maximum) == 3
        and all(isinstance(value, (int, float)) for value in [*minimum, *maximum])
        and all(minimum[index] < maximum[index] for index in range(3))
    )


def _point_inside_obstacle(point: list[float], obstacle: dict[str, Any]) -> bool:
    kind = obstacle.get("type")
    if kind == "sphere":
        center = obstacle.get("center")
        radius = obstacle.get("radius")
        if isinstance(center, list) and isinstance(radius, (int, float)):
            return sum((point[i] - center[i]) ** 2 for i in range(3)) <= radius**2
    if kind == "box":
        center = obstacle.get("center")
        size = obstacle.get("size")
        if isinstance(center, list) and isinstance(size, list):
            return all(abs(point[i] - center[i]) <= size[i] / 2 for i in range(3))
    if kind == "capsule":
        start, end, radius = obstacle.get("start"), obstacle.get("end"), obstacle.get("radius")
        if isinstance(start, list) and isinstance(end, list) and isinstance(radius, (int, float)):
            ab = [end[i] - start[i] for i in range(3)]
            ap = [point[i] - start[i] for i in range(3)]
            denom = sum(value * value for value in ab)
            t = 0.0 if denom == 0 else max(0.0, min(1.0, sum(ap[i] * ab[i] for i in range(3)) / denom))
            closest = [start[i] + ab[i] * t for i in range(3)]
            return sum((point[i] - closest[i]) ** 2 for i in range(3)) <= radius**2
    return False


def _entry_map(facts: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {item["index"]: item for item in facts.get("entries", []) if isinstance(item.get("index"), int)}


def _scene_source_map(
    project_root: Path, episode_dir: Path, scenes: list[dict[str, Any]]
) -> dict[str, tuple[Path, str, set[str]]]:
    result: dict[str, tuple[Path, str, set[str]]] = {}
    for scene in scenes:
        if not isinstance(scene, dict) or not isinstance(scene.get("registryName"), str):
            continue
        implementation = scene.get("implementation") or {}
        module = implementation.get("module")
        if not isinstance(module, str):
            continue
        source = _resolve_module(project_root, episode_dir, module)
        text = source.read_text(encoding="utf-8") if source.is_file() else ""
        result[scene["registryName"]] = (source, text, _scene_methods(source))
    return result


def semantic_diagnostics(
    contract: dict[str, Any], project_root: Path, episode_dir: Path, story: Path
) -> tuple[list[Diagnostic], dict[str, Any]]:
    story_tool = _load_story_tool(project_root)
    facts = _story_facts(story_tool, story)
    catalog = story_tool.discover_catalog(project_root, episode_dir)
    diagnostics: list[Diagnostic] = []

    for issue in facts["parseIssues"]:
        diagnostics.append(
            Diagnostic(issue["severity"], f"STORY-{issue['code']}", issue["message"], entry=issue.get("entry"))
        )

    scenes = contract.get("scenes") if isinstance(contract.get("scenes"), list) else []
    entities = contract.get("entities") if isinstance(contract.get("entities"), list) else []
    events = contract.get("events") if isinstance(contract.get("events"), list) else []
    blocking = contract.get("blocking") if isinstance(contract.get("blocking"), list) else []
    shots = contract.get("shotChecks") if isinstance(contract.get("shotChecks"), list) else []
    state_defs = contract.get("state") if isinstance(contract.get("state"), dict) else {}
    registrations = contract.get("registrations") if isinstance(contract.get("registrations"), dict) else {}

    diagnostics.extend(_unique_diagnostics(scenes, "registryName", "SCN000", "scene"))
    diagnostics.extend(_unique_diagnostics(entities, "id", "REF000", "entity"))
    diagnostics.extend(_unique_diagnostics(shots, "id", "SHOT000", "shotCheck"))
    diagnostics.extend(_unique_diagnostics(blocking, "id", "BLK000", "blocking"))

    scene_by_name = {
        scene["registryName"]: scene
        for scene in scenes
        if isinstance(scene, dict) and isinstance(scene.get("registryName"), str)
    }
    entity_by_id = {
        entity["id"]: entity
        for entity in entities
        if isinstance(entity, dict) and isinstance(entity.get("id"), str)
    }
    event_by_key = {
        (event.get("scene"), event.get("tag")): event
        for event in events
        if isinstance(event, dict) and isinstance(event.get("tag"), str)
    }
    source_map = _scene_source_map(project_root, episode_dir, scenes)
    story_scene_set = set(facts["scenes"])
    contract_scene_set = set(scene_by_name)

    for name in sorted(story_scene_set - contract_scene_set):
        diagnostics.append(Diagnostic("error", "SCN001", f"Story scene {name!r} has no contract entry"))
    for name in sorted(contract_scene_set - story_scene_set):
        diagnostics.append(Diagnostic("warning", "SCN002", f"Contract scene {name!r} is not used by the story"))

    registered_contract = set(registrations.get("scenes") or [])
    for name in sorted(contract_scene_set - registered_contract):
        diagnostics.append(Diagnostic("error", "SCN003", f"Scene {name!r} is missing from registrations.scenes"))

    reachable_scenes = set(catalog.get("scenes") or [])
    reachable_characters = set(catalog.get("characters") or [])
    bootstrap_path = episode_dir / str(registrations.get("bootstrap") or "bootstrap.js")
    explicit = _explicit_registrations(bootstrap_path)
    for name, scene in scene_by_name.items():
        if name not in reachable_scenes:
            diagnostics.append(
                Diagnostic("error", "SCN004", f"Scene {name!r} is not reachable from official or episode registration")
            )
        implementation = scene.get("implementation") if isinstance(scene.get("implementation"), dict) else {}
        if implementation.get("name") != name:
            diagnostics.append(
                Diagnostic("error", "SCN005", f"Scene {name!r} implementation.name must match registryName")
            )
        source, text, methods = source_map.get(name, (Path(), "", set()))
        if not source.is_file():
            diagnostics.append(
                Diagnostic("error", "SCN006", f"Scene module for {name!r} does not exist: {source}")
            )
        elif implementation.get("kind") in {"episode-local", "extend", "alias"}:
            export_name = implementation.get("export")
            classes = set(CLASS_RE.findall(text))
            if export_name not in classes:
                diagnostics.append(
                    Diagnostic("error", "SCN007", f"Scene export {export_name!r} was not found in {source}")
                )
            constructor = re.search(r"constructor\s*\(([^)]*)\)", text)
            if constructor:
                required_args = [part.strip() for part in constructor.group(1).split(",") if part.strip() and "=" not in part]
                if required_args:
                    diagnostics.append(
                        Diagnostic(
                            "error",
                            "SCN008",
                            f"Scene {name!r} constructor requires arguments, but Storyboard constructs scenes with zero arguments",
                        )
                    )
            if name not in explicit["scenes"]:
                diagnostics.append(
                    Diagnostic("error", "SCN009", f"Custom scene {name!r} is not explicitly registered in {bootstrap_path}")
                )

        stage = scene.get("stage") if isinstance(scene.get("stage"), dict) else {}
        bounds = stage.get("bounds")
        if bounds is not None and not _bounds_valid(bounds):
            diagnostics.append(Diagnostic("error", "GEO001", f"Scene {name!r} has invalid stage bounds"))
        zones = stage.get("zones") if isinstance(stage.get("zones"), list) else []
        diagnostics.extend(_unique_diagnostics(zones, "id", "GEO002", f"{name}.zone"))
        for zone in zones:
            zone_bounds = zone.get("bounds") if isinstance(zone, dict) else None
            if bounds and _bounds_valid(zone_bounds):
                if not _inside(zone_bounds["min"], bounds) or not _inside(zone_bounds["max"], bounds):
                    diagnostics.append(
                        Diagnostic("error", "GEO003", f"Zone {zone.get('id')!r} extends outside scene {name!r} bounds")
                    )
        anchors = stage.get("anchors") if isinstance(stage.get("anchors"), dict) else {}
        for anchor_name, anchor in anchors.items():
            if not isinstance(anchor, dict):
                continue
            if anchor.get("space") == "world" and bounds and not _inside(anchor.get("position"), bounds):
                diagnostics.append(
                    Diagnostic("error", "GEO004", f"World anchor {anchor_name!r} is outside scene {name!r} bounds")
                )

        obstacles = scene.get("cameraObstacles") if isinstance(scene.get("cameraObstacles"), list) else []
        diagnostics.extend(_unique_diagnostics(obstacles, "id", "CAM000", f"{name}.cameraObstacle"))
        source_obstacle_count = text.count("registerCameraObstacle(") if text else 0
        if len(obstacles) > source_obstacle_count:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "CAM001",
                    f"Scene {name!r} contracts {len(obstacles)} camera obstacles but source registers {source_obstacle_count}",
                )
            )
        if implementation.get("kind") in {"episode-local", "extend"} and not obstacles:
            diagnostics.append(
                Diagnostic("warning", "CAM002", f"Custom scene {name!r} declares no camera obstacles")
            )

        dependencies = scene.get("dependencies") if isinstance(scene.get("dependencies"), list) else []
        has_async_asset = any(
            str(dep.get("path", "")).lower().endswith((".gltf", ".glb")) for dep in dependencies if isinstance(dep, dict)
        )
        if has_async_asset and implementation.get("readiness") != "readyPromise":
            diagnostics.append(
                Diagnostic("error", "SCN010", f"Scene {name!r} has async model dependencies without readyPromise")
            )
        if implementation.get("readiness") == "readyPromise" and "readyPromise" not in text:
            diagnostics.append(
                Diagnostic("error", "SCN011", f"Scene {name!r} promises readiness but source has no readyPromise")
            )

    for character in registrations.get("characters") or []:
        if character not in reachable_characters:
            diagnostics.append(
                Diagnostic("error", "REG001", f"Character {character!r} is not reachable from official or episode registration")
            )

    for entity_id, entity in entity_by_id.items():
        scene_name = entity.get("scene")
        if scene_name not in scene_by_name:
            diagnostics.append(Diagnostic("error", "REF001", f"Entity {entity_id!r} references unknown scene {scene_name!r}"))
            continue
        parent = entity.get("parent")
        if parent != "$scene" and parent not in entity_by_id:
            diagnostics.append(Diagnostic("error", "REF002", f"Entity {entity_id!r} has unknown parent {parent!r}"))
        elif parent in entity_by_id and entity_by_id[parent].get("scene") != scene_name:
            diagnostics.append(Diagnostic("error", "REF003", f"Entity {entity_id!r} parent is in another scene"))

        initial = entity.get("initial") if isinstance(entity.get("initial"), dict) else {}
        transform = initial.get("transform") if isinstance(initial.get("transform"), dict) else {}
        space, relative_to = transform.get("space"), transform.get("relativeTo")
        if space == "world" and relative_to != "$scene":
            diagnostics.append(
                Diagnostic("error", "SPACE001", f"Entity {entity_id!r} world transform must be relativeTo '$scene'")
            )
        if space == "local" and relative_to != parent:
            diagnostics.append(
                Diagnostic("error", "SPACE001", f"Entity {entity_id!r} local transform must be relative to parent {parent!r}")
            )
        scene_bounds = (scene_by_name[scene_name].get("stage") or {}).get("bounds")
        if space == "world" and scene_bounds and not _inside(transform.get("position"), scene_bounds):
            diagnostics.append(Diagnostic("error", "GEO005", f"Entity {entity_id!r} starts outside scene bounds"))
        if entity.get("kind") == "character":
            runtime_name = entity.get("runtimeName")
            if not runtime_name:
                diagnostics.append(Diagnostic("error", "REF004", f"Character entity {entity_id!r} has no runtimeName"))
            if entity.get("initialPresence") == "onstage" and initial.get("visible") is False:
                diagnostics.append(
                    Diagnostic("warning", "PRES001", f"Character {entity_id!r} is onstage but initially invisible")
                )
        else:
            source, text, _ = source_map.get(scene_name, (Path(), "", set()))
            binding = entity.get("binding")
            root_match = re.match(r"([A-Za-z_$][\w$]*)", str(binding or ""))
            if root_match and f"this.{root_match.group(1)}" not in text:
                diagnostics.append(
                    Diagnostic("error", "PROP001", f"Prop {entity_id!r} binding {binding!r} was not found in {source}")
                )
            object_name = entity.get("objectName")
            if object_name and object_name not in text:
                # Generated collections commonly use names such as `Fork${index + 1}`.
                # Accept the stable textual prefix while still catching unrelated names.
                generated_prefix = re.sub(r"\d+$", "", object_name)
                if len(generated_prefix) < 3 or generated_prefix not in text:
                    diagnostics.append(
                        Diagnostic("warning", "PROP002", f"Prop {entity_id!r} objectName {object_name!r} was not found in source")
                    )
            states = entity.get("states") if isinstance(entity.get("states"), list) else []
            if states and entity.get("initialState") not in states:
                diagnostics.append(
                    Diagnostic("error", "STATE001", f"Prop {entity_id!r} initialState is not in states")
                )

    story_custom_keys = {(item.get("scene"), item.get("tag")) for item in facts["customEvents"]}
    contract_event_keys = set(event_by_key)
    for key in sorted(story_custom_keys - contract_event_keys, key=str):
        diagnostics.append(Diagnostic("error", "EVT001", f"Story custom event {key[1]!r} in scene {key[0]!r} is not contracted"))
    for key in sorted(contract_event_keys - story_custom_keys, key=str):
        diagnostics.append(Diagnostic("warning", "EVT005", f"Contract event {key[1]!r} in scene {key[0]!r} is unused"))

    first_event_order: dict[tuple[str, str], int] = {}
    for occurrence in facts["customEvents"]:
        first_event_order.setdefault((occurrence.get("scene"), occurrence["tag"]), occurrence["order"])

    for key, event in event_by_key.items():
        scene_name, tag = key
        if scene_name not in scene_by_name:
            diagnostics.append(Diagnostic("error", "EVT006", f"Event {tag!r} references unknown scene {scene_name!r}"))
            continue
        handler = event.get("handler")
        methods = source_map.get(scene_name, (Path(), "", set()))[2]
        if handler not in methods:
            diagnostics.append(
                Diagnostic("error", "EVT002", f"Event {tag!r} handler {handler!r} is missing from scene {scene_name!r}")
            )
        expected = _lower_first(tag)
        if event.get("argumentMode") == "none" and handler not in {expected, tag}:
            diagnostics.append(
                Diagnostic("error", "EVT003", f"Event {tag!r} will dispatch to {expected!r} or exact name, not {handler!r}")
            )
        occurrences = [item for item in facts["customEvents"] if (item.get("scene"), item["tag"]) == key]
        if event.get("argumentMode") == "none" and any(item.get("options") for item in occurrences):
            diagnostics.append(
                Diagnostic("warning", "EVT004", f"Custom event {tag!r} has story options, but generic dispatch passes no arguments")
            )
        current_order = first_event_order.get(key)
        for requirement in event.get("requires") or []:
            required_key = (scene_name, requirement)
            required_order = first_event_order.get(required_key)
            if required_order is None:
                diagnostics.append(
                    Diagnostic("error", "EVT007", f"Event {tag!r} requires missing event {requirement!r}")
                )
            elif current_order is not None and required_order >= current_order:
                diagnostics.append(
                    Diagnostic("error", "EVT008", f"Event {tag!r} requires {requirement!r}, but story order does not satisfy it")
                )

    entry_by_index = _entry_map(facts)
    zone_by_scene: dict[str, dict[str, dict[str, Any]]] = {}
    for name, scene in scene_by_name.items():
        zones = ((scene.get("stage") or {}).get("zones") or []) if isinstance(scene.get("stage"), dict) else []
        zone_by_scene[name] = {zone.get("id"): zone for zone in zones if isinstance(zone, dict)}

    movement_keys = {
        (item.get("scene"), item.get("character"), item.get("entry"))
        for item in [*facts.get("positions", []), *facts.get("moves", [])]
    }
    blocking_keys: set[tuple[Any, Any, Any]] = set()
    for block in blocking:
        scene_name, character_id, entry_index = block.get("scene"), block.get("character"), block.get("entry")
        character = entity_by_id.get(character_id)
        runtime_name = character.get("runtimeName") if isinstance(character, dict) else None
        blocking_keys.add((scene_name, runtime_name, entry_index))
        if scene_name not in scene_by_name:
            diagnostics.append(Diagnostic("error", "BLK001", f"Blocking {block.get('id')!r} references unknown scene"))
            continue
        if not character or character.get("kind") != "character":
            diagnostics.append(Diagnostic("error", "BLK002", f"Blocking {block.get('id')!r} character is not a character entity"))
        if entry_index not in entry_by_index:
            diagnostics.append(Diagnostic("error", "BLK003", f"Blocking {block.get('id')!r} references missing story entry"))
        bounds = (scene_by_name[scene_name].get("stage") or {}).get("bounds")
        for label in ("from", "to"):
            if bounds and not _inside(block.get(label), bounds):
                diagnostics.append(
                    Diagnostic("error", "BLK004", f"Blocking {block.get('id')!r} {label} position is outside scene bounds")
                )
        zone = zone_by_scene.get(scene_name, {}).get(block.get("zone"))
        if not zone:
            diagnostics.append(Diagnostic("error", "BLK005", f"Blocking {block.get('id')!r} references unknown zone"))
        elif not _inside(block.get("to"), zone.get("bounds")):
            diagnostics.append(Diagnostic("warning", "BLK006", f"Blocking {block.get('id')!r} target is outside its declared zone"))
        if (scene_name, runtime_name, entry_index) not in movement_keys:
            diagnostics.append(
                Diagnostic("warning", "BLK007", f"Blocking {block.get('id')!r} is not materialized by Position/Move in its story entry")
            )
    for movement_key in sorted(movement_keys - blocking_keys, key=str):
        diagnostics.append(
            Diagnostic(
                "warning",
                "BLK008",
                f"Story placement/move for {movement_key[1]!r} at entry {movement_key[2]} has no blocking contract",
                entry=movement_key[2],
            )
        )

    presence: dict[str, str] = {
        entity_id: str(entity.get("initialPresence"))
        for entity_id, entity in entity_by_id.items()
        if entity.get("kind") == "character"
    }
    parents: dict[str, str] = {entity_id: str(entity.get("parent")) for entity_id, entity in entity_by_id.items()}
    entity_states: dict[str, Any] = {
        entity_id: entity.get("initialState") for entity_id, entity in entity_by_id.items() if entity.get("initialState")
    }
    runtime_state: dict[str, Any] = {
        name: definition.get("initial") for name, definition in state_defs.items() if isinstance(definition, dict)
    }
    presence_snapshots: dict[int, dict[str, str]] = {}
    occurrence_by_entry: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for occurrence in facts["customEvents"]:
        if isinstance(occurrence.get("entry"), int):
            occurrence_by_entry[occurrence["entry"]].append(occurrence)

    for entry in facts["entries"]:
        entry_index = entry.get("index")
        if not isinstance(entry_index, int):
            continue
        for occurrence in sorted(occurrence_by_entry.get(entry_index, []), key=lambda item: item["order"]):
            event = event_by_key.get((occurrence.get("scene"), occurrence.get("tag")))
            if not event:
                continue
            reparented: set[str] = set()
            for effect in event.get("effects") or []:
                if not isinstance(effect, dict):
                    continue
                operation = effect.get("op")
                if operation == "presence":
                    character = effect.get("character")
                    if character not in presence:
                        diagnostics.append(Diagnostic("error", "REF005", f"Presence effect references unknown character {character!r}"))
                        continue
                    if presence[character] != effect.get("from"):
                        diagnostics.append(
                            Diagnostic(
                                "error",
                                "PRES002",
                                f"Event {event.get('tag')!r} expects {character!r} presence {effect.get('from')!r}, got {presence[character]!r}",
                                entry=entry_index,
                            )
                        )
                    if effect.get("to") == "concealed":
                        concealer = entity_by_id.get(effect.get("by"))
                        if not concealer or concealer.get("kind") != "prop":
                            diagnostics.append(
                                Diagnostic("error", "PRES003", f"Concealment of {character!r} has no valid prop occluder")
                            )
                    presence[character] = effect.get("to")
                elif operation == "setState":
                    state_name = effect.get("state")
                    if state_name not in state_defs:
                        diagnostics.append(Diagnostic("error", "STATE002", f"Effect references unknown state {state_name!r}"))
                    else:
                        expected_type = state_defs[state_name].get("type")
                        value = effect.get("value")
                        type_ok = (
                            (expected_type == "boolean" and isinstance(value, bool))
                            or (expected_type == "number" and isinstance(value, (int, float)) and not isinstance(value, bool))
                            or (expected_type == "string" and isinstance(value, str))
                        )
                        if not type_ok:
                            diagnostics.append(Diagnostic("error", "STATE003", f"State {state_name!r} value has wrong type"))
                        runtime_state[state_name] = value
                elif operation == "setEntityState":
                    entity_id = effect.get("entity")
                    if entity_id not in entity_by_id:
                        diagnostics.append(Diagnostic("error", "REF006", f"Entity-state effect references {entity_id!r}"))
                        continue
                    if entity_states.get(entity_id) != effect.get("from"):
                        diagnostics.append(
                            Diagnostic("error", "STATE004", f"Entity {entity_id!r} state transition starts from the wrong state")
                        )
                    allowed = entity_by_id[entity_id].get("states") or []
                    if effect.get("to") not in allowed:
                        diagnostics.append(Diagnostic("error", "STATE005", f"Entity {entity_id!r} transition targets an undeclared state"))
                    entity_states[entity_id] = effect.get("to")
                elif operation == "reparent":
                    entity_id = effect.get("entity")
                    target = effect.get("to")
                    if entity_id not in entity_by_id:
                        diagnostics.append(Diagnostic("error", "REF007", f"Reparent effect references {entity_id!r}"))
                        continue
                    if target != "$scene" and target not in entity_by_id:
                        diagnostics.append(Diagnostic("error", "REF008", f"Reparent target {target!r} does not exist"))
                    if effect.get("preserveWorld") is not True:
                        diagnostics.append(
                            Diagnostic("warning", "SPACE003", f"Reparent of {entity_id!r} does not preserve world transform")
                        )
                    parents[entity_id] = target
                    reparented.add(entity_id)
                elif operation == "motion":
                    entity_id = effect.get("entity")
                    if entity_id not in entity_by_id:
                        diagnostics.append(Diagnostic("error", "REF009", f"Motion effect references {entity_id!r}"))
                        continue
                    parent = parents.get(entity_id)
                    if effect.get("space") == "world" and parent != "$scene" and not effect.get("conversion"):
                        diagnostics.append(
                            Diagnostic(
                                "error",
                                "SPACE002",
                                f"World-space motion for {entity_id!r} remains under parent {parent!r} without reparent/conversion",
                                entry=entry_index,
                            )
                        )
                    if effect.get("space") == "local" and effect.get("relativeTo") != parent:
                        diagnostics.append(
                            Diagnostic("error", "SPACE001", f"Local motion for {entity_id!r} is not relative to current parent {parent!r}")
                        )
                    for endpoint in (effect.get("from"), effect.get("to")):
                        if isinstance(endpoint, dict) and endpoint.get("entity") not in entity_by_id:
                            diagnostics.append(
                                Diagnostic("error", "REF010", f"Motion target references unknown entity {endpoint.get('entity')!r}")
                            )

        presence_snapshots[entry_index] = dict(presence)
        for speaker in entry.get("speakers") or []:
            matching = [
                entity_id
                for entity_id, entity in entity_by_id.items()
                if entity.get("kind") == "character"
                and entity.get("runtimeName") == speaker
                and entity.get("scene") == entry.get("scene")
            ]
            if matching and presence.get(matching[0]) != "onstage":
                diagnostics.append(
                    Diagnostic(
                        "warning",
                        "PRES004",
                        f"Speaker {speaker!r} is {presence.get(matching[0])!r} at dialogue entry",
                        entry=entry_index,
                    )
                )

    for character, value in presence.items():
        if value == "concealed":
            diagnostics.append(Diagnostic("warning", "PRES005", f"Character {character!r} remains concealed at story end"))

    shot_by_entry: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for shot in shots:
        entry_index = shot.get("entry")
        if isinstance(entry_index, int):
            shot_by_entry[entry_index].append(shot)
        entry = entry_by_index.get(entry_index)
        if not entry:
            diagnostics.append(Diagnostic("error", "SHOT001", f"Shot check {shot.get('id')!r} references missing entry"))
            continue
        if shot.get("scene") != entry.get("scene"):
            diagnostics.append(Diagnostic("error", "SHOT002", f"Shot check {shot.get('id')!r} scene does not match story entry"))
        duration = entry.get("duration")
        if isinstance(duration, (int, float)) and shot.get("offsetSeconds", 0) > duration:
            diagnostics.append(Diagnostic("error", "SHOT003", f"Shot check {shot.get('id')!r} offset exceeds entry duration"))
        if not entry.get("cameras"):
            diagnostics.append(Diagnostic("warning", "SHOT004", f"Shot check {shot.get('id')!r} entry has no explicit camera"))
        snapshot = presence_snapshots.get(entry_index, {})
        for visible in shot.get("mustSee") or []:
            entity_id = visible.get("entity")
            entity = entity_by_id.get(entity_id)
            if not entity:
                diagnostics.append(Diagnostic("error", "REF011", f"Shot check references unknown entity {entity_id!r}"))
                continue
            focus = visible.get("focus")
            if focus and focus not in (entity.get("focusPoints") or {}):
                diagnostics.append(Diagnostic("error", "SHOT005", f"Entity {entity_id!r} has no focus point {focus!r}"))
            if entity.get("kind") == "character" and snapshot.get(entity_id) != "onstage":
                diagnostics.append(
                    Diagnostic("error", "PRES006", f"Shot requires visible character {entity_id!r} while presence is {snapshot.get(entity_id)!r}")
                )
        for presence_check in shot.get("mustHavePresence") or []:
            character = presence_check.get("character")
            if character not in snapshot:
                diagnostics.append(Diagnostic("error", "REF012", f"Shot presence check references {character!r}"))
            elif snapshot[character] != presence_check.get("value"):
                diagnostics.append(
                    Diagnostic("error", "PRES007", f"Shot presence for {character!r} does not match event state")
                )
        for entity_id in shot.get("mustShowTogether") or []:
            if entity_id not in entity_by_id:
                diagnostics.append(Diagnostic("error", "REF013", f"Shot grouping references unknown entity {entity_id!r}"))

    for camera in facts["cameras"]:
        entry_index = camera.get("entry")
        if camera.get("type") not in COLLISION_GUARDED_CAMERAS and not shot_by_entry.get(entry_index):
            diagnostics.append(
                Diagnostic(
                    "warning",
                    "SHOT006",
                    f"Unguarded camera {camera.get('type')!r} at entry {entry_index} has no critical shot check",
                    entry=entry_index,
                )
            )
        position_text = camera.get("options", {}).get("position")
        if position_text:
            try:
                position = [float(part.strip()) for part in position_text.split(",")]
            except ValueError:
                position = []
            scene = scene_by_name.get(camera.get("scene"))
            if len(position) == 3 and scene:
                for obstacle in scene.get("cameraObstacles") or []:
                    if _point_inside_obstacle(position, obstacle):
                        diagnostics.append(
                            Diagnostic(
                                "error",
                                "CAM003",
                                f"Camera at entry {entry_index} starts inside obstacle {obstacle.get('id')!r}",
                                entry=entry_index,
                            )
                        )

    return diagnostics, facts


def validate_contract(
    contract: dict[str, Any], project_root: Path, episode_dir: Path, story: Path
) -> tuple[list[Diagnostic], dict[str, Any]]:
    diagnostics = _schema_diagnostics(contract)
    if diagnostics:
        # Semantic validation assumes the schema's object shapes. Keep malformed
        # hand-written contracts diagnostic-driven instead of raising TypeError.
        story_tool = _load_story_tool(project_root)
        return diagnostics, _story_facts(story_tool, story)
    semantic, facts = semantic_diagnostics(contract, project_root, episode_dir, story)
    diagnostics.extend(semantic)
    diagnostics.sort(key=lambda item: (0 if item.severity == "error" else 1, item.code, item.entry or 0, item.message))
    return diagnostics, facts


def _diagnostic_counts(diagnostics: list[Diagnostic]) -> tuple[int, int]:
    return (
        sum(item.severity == "error" for item in diagnostics),
        sum(item.severity == "warning" for item in diagnostics),
    )


def _print_diagnostics(diagnostics: list[Diagnostic], *, as_json: bool) -> None:
    errors, warnings = _diagnostic_counts(diagnostics)
    if as_json:
        print(
            json.dumps(
                {
                    "valid": errors == 0,
                    "errors": errors,
                    "warnings": warnings,
                    "diagnostics": [item.as_dict() for item in diagnostics],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    for item in diagnostics:
        location = f" entry={item.entry}" if item.entry is not None else ""
        path = f" path={item.path}" if item.path else ""
        print(f"{item.severity.upper():7} [{item.code}]{location}{path} {item.message}")
    print(f"Scene contract: {errors} error(s), {warnings} warning(s)")


def _print_inventory(inventory: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
        return
    print(f"Episode: {inventory['episode']}")
    print(f"Story: {inventory['story']}")
    print(f"Scenes ({len(inventory['scenes'])}): {', '.join(inventory['scenes']) or '-'}")
    print(f"Characters ({len(inventory['characters'])}): {', '.join(inventory['characters']) or '-'}")
    custom = inventory["events"]["custom"]
    engine = inventory["events"]["engine"]
    print(f"Custom events ({len(custom)}): {', '.join(dict.fromkeys(item['tag'] for item in custom)) or '-'}")
    print(f"Engine events ({len(engine)}): {', '.join(dict.fromkeys(item['tag'] for item in engine)) or '-'}")
    print(f"Camera cues: {len(inventory['cameras'])}")
    print(f"Positions: {len(inventory['positions'])}; moves: {len(inventory['moves'])}")
    if inventory["storyIssues"]:
        print(f"Story parse issues: {len(inventory['storyIssues'])}")


def _inspect_summary(contract: dict[str, Any], diagnostics: list[Diagnostic], facts: dict[str, Any]) -> None:
    errors, warnings = _diagnostic_counts(diagnostics)
    scenes = [item for item in (contract.get("scenes") or []) if isinstance(item, dict)]
    entities = [item for item in (contract.get("entities") or []) if isinstance(item, dict)]
    events = [item for item in (contract.get("events") or []) if isinstance(item, dict)]
    characters = [item for item in entities if item.get("kind") == "character"]
    props = [item for item in entities if item.get("kind") == "prop"]
    contracted_events = {(item.get("scene"), item.get("tag")) for item in events}
    story_events = {(item.get("scene"), item.get("tag")) for item in facts.get("customEvents") or []}
    print(f"Episode: {contract.get('episode', '-')}")
    print(f"Scenes: {len(scenes)}; characters: {len(characters)}; props: {len(props)}")
    print(f"Custom event coverage: {len(contracted_events & story_events)}/{len(story_events)}")
    print(f"Blocking beats: {len(contract.get('blocking') or [])}")
    print(f"Critical shots: {len(contract.get('shotChecks') or [])}")
    print(f"Audio anchors: {sum(len(scene.get('audioAnchors') or []) for scene in scenes)}")
    print(f"Diagnostics: {errors} error(s), {warnings} warning(s)")
    for item in diagnostics[:12]:
        entry = f" entry {item.entry}" if item.entry else ""
        print(f"- {item.severity.upper()} {item.code}{entry}: {item.message}")
    if len(diagnostics) > 12:
        print(f"- ... {len(diagnostics) - 12} more; run validate for the full list")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="Extract read-only scene facts from an episode")
    inventory.add_argument("--episode-dir", required=True)
    inventory.add_argument("--story")
    inventory.add_argument("--json", action="store_true")

    scaffold = subparsers.add_parser("scaffold", help="Create a non-overwriting scene contract scaffold")
    scaffold.add_argument("--episode-dir", required=True)
    scaffold.add_argument("--story")
    scaffold.add_argument("--output")
    scaffold.add_argument("--force", action="store_true")

    validate = subparsers.add_parser("validate", help="Validate schema and runtime semantics")
    validate.add_argument("--episode-dir", required=True)
    validate.add_argument("--story")
    validate.add_argument("--contract")
    validate.add_argument("--warnings-as-errors", action="store_true")
    validate.add_argument("--json", action="store_true")

    inspect = subparsers.add_parser("inspect", help="Summarize a contract and its highest-signal risks")
    inspect.add_argument("--episode-dir", required=True)
    inspect.add_argument("--story")
    inspect.add_argument("--contract")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        episode_dir = _resolve_episode_dir(args.episode_dir)
        project_root = _find_project_root(episode_dir)
        if args.command == "inventory":
            story = _resolve_story(episode_dir, args.story)
            inventory = build_inventory(episode_dir, story)
            _print_inventory(inventory, as_json=args.json)
            return 1 if any(item.get("severity") == "error" for item in inventory["storyIssues"]) else 0

        if args.command == "scaffold":
            story = _resolve_story(episode_dir, args.story)
            output = _resolve_contract(episode_dir, args.output)
            if output.exists() and not args.force:
                raise SceneToolInputError(f"Refusing to overwrite existing contract without --force: {output}")
            inventory = build_inventory(episode_dir, story)
            contract = scaffold_contract(inventory, project_root, episode_dir)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"Created scene contract scaffold: {output}")
            print("Resolve every TODO before validation; inventory does not infer creative semantics.")
            return 0

        contract_path = _resolve_contract(episode_dir, args.contract)
        contract = _load_json(contract_path)
        story = _resolve_story(episode_dir, args.story, contract)
        diagnostics, facts = validate_contract(contract, project_root, episode_dir, story)
        errors, warnings = _diagnostic_counts(diagnostics)
        if args.command == "validate":
            _print_diagnostics(diagnostics, as_json=args.json)
            return 1 if errors or (args.warnings_as_errors and warnings) else 0
        _inspect_summary(contract, diagnostics, facts)
        return 1 if errors else 0
    except SceneToolInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
