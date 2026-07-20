#!/usr/bin/env python3
"""Discover Dula assets and strictly validate script.story drafts.

This tool is intentionally offline and read-only. Story generation is performed by the
agent using the skill; this script supplies deterministic repository context and gates.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REGISTRATIONS = {
    "characters": "registerCharacter",
    "animations": "registerAnimation",
    "scenes": "registerScene",
    "cameras": "registerCameraMove",
    "transitions": "registerTransition",
    "directors": "registerDirector",
    "combat_actions": "registerCombatAction",
}

ANIMATION_GROUP_OWNERS = {
    "doraemon": {"Doraemon"},
    "nobita": {"Nobita"},
    "rocklee": {"RockLee"},
    "shera": {"Adora", "Catra", "Hordak", "ShadowWeaver", "SheRa"},
    "shizuka": {"Shizuka"},
    "ultraman": {"Gabura", "Shota", "Ultraman"},
    "xingzai": {"Xingzai"},
    "xiaoyue": {"Xiaoyue"},
    "yuyuhakusho": {"Kuwabara", "Yokai", "Yusuke"},
}

KNOWN_NAMESPACES = {
    "Animation",
    "Ball",
    "Camera",
    "Combat",
    "Dunk",
    "Event",
    "Exaggeration",
    "Hitstop",
    "Music",
    "Position",
    "Prop",
    "SceneDirector",
    "SFX",
    "Transition",
    "Voice",
}

FACING_LITERALS = {"back", "camera", "center", "forward", "left", "right"}
SCENE_DIRECTOR_ACTIONS = {"Formation", "Gaze"}
COMBAT_COMMANDS = {
    "Action",
    "AdHoc",
    "Attack",
    "BulletTime",
    "Combo",
    "Emotion",
    "Override",
    "Reaction",
    "Setup",
    "Staging",
}
TAG_RE = re.compile(r"\{([^{}]+)\}")
SCENE_RE = re.compile(r"(?m)^@([A-Za-z0-9_]+)")
SPEAKER_RE = re.compile(r"\[([^\]\s]+)\]")
TIME_RE = re.compile(
    r"(?P<sh>\d{2}):(?P<sm>\d{2}):(?P<ss>\d{2}),(?P<sms>\d{3})"
    r"\s+-->\s+"
    r"(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2}),(?P<ems>\d{3})"
)
MODULE_STATEMENT_RE = re.compile(r"(?ms)^[ \t]*(import|export)\b(.*?)(?:;|\Z)")


@dataclass(frozen=True)
class StoryEntry:
    index: int | None
    start: float | None
    end: float | None
    content: str
    line: int


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    line: int | None = None
    entry: int | None = None


def _strip_js_comments_and_templates(text: str) -> str:
    """Mask JS comments and template literals while preserving lines and quoted strings."""
    output: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        next_char = text[i + 1] if i + 1 < len(text) else ""
        if char in {"'", '"'}:
            quote = char
            output.append(char)
            i += 1
            while i < len(text):
                output.append(text[i])
                if text[i] == "\\" and i + 1 < len(text):
                    i += 1
                    output.append(text[i])
                elif text[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if char == "`":
            output.append(" ")
            i += 1
            while i < len(text):
                if text[i] == "\\" and i + 1 < len(text):
                    output.extend((" ", " "))
                    i += 2
                    continue
                if text[i] == "`":
                    output.append(" ")
                    i += 1
                    break
                output.append("\n" if text[i] == "\n" else " ")
                i += 1
            continue
        if char == "/" and next_char == "/":
            output.extend((" ", " "))
            i += 2
            while i < len(text) and text[i] != "\n":
                output.append(" ")
                i += 1
            continue
        if char == "/" and next_char == "*":
            output.extend((" ", " "))
            i += 2
            while i < len(text):
                if text[i] == "*" and i + 1 < len(text) and text[i + 1] == "/":
                    output.extend((" ", " "))
                    i += 2
                    break
                output.append("\n" if text[i] == "\n" else " ")
                i += 1
            continue
        output.append(char)
        i += 1
    return "".join(output)


def _module_imports(text: str) -> list[tuple[str, str]]:
    """Return (statement body, module specifier) for static or dynamic imports."""
    cleaned = _strip_js_comments_and_templates(text)
    imports: list[tuple[str, str]] = []
    for match in MODULE_STATEMENT_RE.finditer(cleaned):
        keyword = match.group(1)
        body = match.group(2)
        specifier_match = re.search(r"\bfrom\s*['\"]([^'\"]+)['\"]", body)
        if specifier_match is None and keyword == "import":
            specifier_match = re.search(r"(?:^\s*|\(\s*)['\"]([^'\"]+)['\"]", body)
        if specifier_match is not None:
            imports.append((body, specifier_match.group(1)))
    return imports


def _bootstrap_calls_register_all(bootstrap: Path) -> bool:
    try:
        text = bootstrap.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    cleaned = _strip_js_comments_and_templates(text)
    call_names: set[str] = set()
    namespace_names: set[str] = set()
    for body, specifier in _module_imports(text):
        if specifier != "dula-assets":
            continue
        named_match = re.search(r"\{(.*?)\}", body, re.DOTALL)
        if named_match:
            for item in named_match.group(1).split(","):
                alias_match = re.fullmatch(
                    r"\s*registerAll(?:\s+as\s+([A-Za-z_][A-Za-z0-9_]*))?\s*", item
                )
                if alias_match:
                    call_names.add(alias_match.group(1) or "registerAll")
        namespace_match = re.search(r"\*\s+as\s+([A-Za-z_][A-Za-z0-9_]*)", body)
        if namespace_match:
            namespace_names.add(namespace_match.group(1))

    for name in call_names:
        if re.search(rf"(?m)^[ \t]*{re.escape(name)}\s*\(", cleaned):
            return True
    for name in namespace_names:
        if re.search(rf"(?m)^[ \t]*{re.escape(name)}\.registerAll\s*\(", cleaned):
            return True
    return False


def find_project_root(*hints: Path | None) -> Path:
    """Find the repository root without depending on git metadata."""
    candidates: list[Path] = []
    for hint in hints:
        if hint is None:
            continue
        resolved = hint.resolve()
        candidates.append(resolved if resolved.is_dir() else resolved.parent)

    candidates.extend([Path.cwd().resolve(), Path(__file__).resolve().parent])
    checked: set[Path] = set()
    for start in candidates:
        for candidate in (start, *start.parents):
            if candidate in checked:
                continue
            checked.add(candidate)
            if (candidate / "dula-assets" / "index.js").is_file() and (
                candidate / "dula-engine" / "lib" / "StoryParser.js"
            ).is_file():
                return candidate
    raise FileNotFoundError(
        "Could not find the project root containing dula-assets/index.js and "
        "dula-engine/lib/StoryParser.js"
    )


def _episode_sources(episode_dir: Path | None) -> list[Path]:
    if episode_dir is None or not episode_dir.is_dir():
        return []

    bootstrap = episode_dir / "bootstrap.js"
    if not bootstrap.is_file():
        return []

    def resolve_local_import(source: Path, specifier: str) -> Path | None:
        if not specifier.startswith("."):
            return None
        base = (source.parent / specifier).resolve()
        candidates = [base]
        if base.suffix == "":
            candidates.extend(base.with_suffix(suffix) for suffix in (".js", ".mjs", ".cjs"))
            candidates.extend(base / f"index{suffix}" for suffix in (".js", ".mjs", ".cjs"))
        for candidate in candidates:
            if candidate.is_file() and candidate.is_relative_to(episode_dir.resolve()):
                return candidate
        return None

    visited: set[Path] = set()
    queue = [bootstrap.resolve()]
    while queue:
        source = queue.pop()
        if source in visited:
            continue
        visited.add(source)
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for _, specifier in _module_imports(text):
            imported = resolve_local_import(source, specifier)
            if imported is not None and imported not in visited:
                queue.append(imported)
    return sorted(visited)


def _scan_registrations(paths: Iterable[Path]) -> dict[str, set[str]]:
    found = {key: set() for key in REGISTRATIONS}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        text = _strip_js_comments_and_templates(text)
        for key, function_name in REGISTRATIONS.items():
            pattern = re.compile(
                rf"(?m)^[ \t]*{re.escape(function_name)}\s*\(\s*(['\"])([^'\"]+)\1"
            )
            found[key].update(match.group(2) for match in pattern.finditer(text))
    return found


def _discover_animation_groups(asset_index: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    try:
        text = asset_index.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}, {}
    text = _strip_js_comments_and_templates(text)

    imported_groups: dict[str, str] = {}
    import_pattern = re.compile(
        r"\bimport\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\s*from\s*"
        r"['\"]\./animations/([^/'\"]+)/[^'\"]+['\"]"
    )
    for match in import_pattern.finditer(text):
        imported_groups[match.group(1)] = match.group(2)

    group_by_name: dict[str, str] = {}
    registration_pattern = re.compile(
        r"(?m)^[ \t]*registerAnimation\s*\(\s*(['\"])([^'\"]+)\1\s*,\s*([A-Za-z_][A-Za-z0-9_]*)"
    )
    for match in registration_pattern.finditer(text):
        registered_name = match.group(2)
        implementation = match.group(3)
        group = imported_groups.get(implementation)
        if group:
            group_by_name[registered_name] = group

    grouped: dict[str, list[str]] = {}
    for name, group in group_by_name.items():
        grouped.setdefault(group, []).append(name)
    return {group: sorted(names) for group, names in sorted(grouped.items())}, group_by_name


def _discover_exaggerations(paths: Iterable[Path]) -> set[str]:
    names: set[str] = set()
    registration_pattern = re.compile(
        r"(?m)^[ \t]*registerExaggeration\s*\(\s*(['\"])([^'\"]+)\1"
    )
    preset_block_pattern = re.compile(
        r"(?ms)^[ \t]*export\s+const\s+EXAGGERATION_PRESETS\s*=\s*\{(.*?)^[ \t]*\};"
    )
    preset_name_pattern = re.compile(r"(?m)^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\s*:")
    for path in paths:
        try:
            text = _strip_js_comments_and_templates(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        names.update(match.group(2) for match in registration_pattern.finditer(text))
        for block in preset_block_pattern.finditer(text):
            names.update(match.group(1) for match in preset_name_pattern.finditer(block.group(1)))
    return names


def _read_audio_names(project_root: Path, episode_dir: Path | None) -> dict[str, set[str]]:
    result = {"music": set(), "sfx": set(), "ambient": set(), "procedural_sfx": set()}
    category_map = {"bgm": "music", "sfx": "sfx", "ambient": "ambient"}
    registry_root = project_root / "dula-assets" / "audio-registry"
    for directory_name, result_key in category_map.items():
        for path in (registry_root / directory_name).glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            name = payload.get("name") if isinstance(payload, dict) else None
            if isinstance(name, str) and name:
                result[result_key].add(name)

    if episode_dir is not None:
        media_dirs = {
            "music": [episode_dir / "materials" / "bgm", episode_dir / "assets" / "audio" / "music"],
            "sfx": [episode_dir / "materials" / "sfx", episode_dir / "assets" / "audio" / "sfx"],
            "ambient": [episode_dir / "materials" / "ambient", episode_dir / "assets" / "audio" / "ambient"],
        }
        media_suffixes = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}
        for result_key, directories in media_dirs.items():
            for directory in directories:
                if directory.is_dir():
                    result[result_key].update(
                        path.stem for path in directory.rglob("*") if path.is_file() and path.suffix.lower() in media_suffixes
                    )

    procedural_registry = project_root / "dula-engine" / "tools" / "procedural_audio" / "registry.py"
    if procedural_registry.is_file():
        try:
            tree = ast.parse(procedural_registry.read_text(encoding="utf-8"))
            for node in tree.body:
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                    continue
                if not any(isinstance(target, ast.Name) and target.id == "REGISTRY" for target in node.targets):
                    continue
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        result["procedural_sfx"].add(key.value)
        except (OSError, UnicodeDecodeError, SyntaxError):
            pass
    return result


def _discover_props(paths: Iterable[Path]) -> set[str]:
    props: set[str] = set()
    pattern = re.compile(r"\b(?:p|prop)\.type\s*===\s*['\"]([^'\"]+)['\"]")
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        props.update(match.group(1) for match in pattern.finditer(text))
    return props


def discover_catalog(project_root: Path, episode_dir: Path | None = None) -> dict[str, object]:
    """Return names registered globally and directly in an episode."""
    global_source = project_root / "dula-assets" / "index.js"
    episode_sources = _episode_sources(episode_dir)
    registrations = _scan_registrations([global_source, *episode_sources])
    animation_groups, animation_group_by_name = _discover_animation_groups(global_source)
    exaggeration_source = project_root / "dula-engine" / "lib" / "ExaggerationRegistry.js"
    exaggerations = _discover_exaggerations([exaggeration_source, *episode_sources])
    audio = _read_audio_names(project_root, episode_dir)
    prop_sources = [project_root / "dula-engine" / "storyboard" / "Storyboard.js", *episode_sources]
    props = _discover_props(prop_sources)

    voice_speakers: set[str] = set()
    if episode_dir is not None:
        voice_path = episode_dir / "config" / "voice_config.json"
        if voice_path.is_file():
            try:
                voice_config = json.loads(voice_path.read_text(encoding="utf-8"))
                if isinstance(voice_config, dict):
                    voice_speakers.update(str(name) for name in voice_config)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                pass

    speakers = set(registrations["characters"]) | voice_speakers | {"Narrator"}
    return {
        **{key: sorted(values) for key, values in registrations.items()},
        "animation_groups": animation_groups,
        "animation_group_by_name": animation_group_by_name,
        "exaggerations": sorted(exaggerations),
        "scene_director_actions": sorted(SCENE_DIRECTOR_ACTIONS),
        "combat_commands": sorted(COMBAT_COMMANDS),
        **{key: sorted(values) for key, values in audio.items()},
        "props": sorted(props),
        "speakers": sorted(speakers),
        "sources": [
            str(path.relative_to(project_root) if path.is_relative_to(project_root) else path)
            for path in [global_source, *episode_sources]
        ],
    }


def _timestamp_seconds(match: re.Match[str], prefix: str) -> float:
    return (
        int(match.group(f"{prefix}h")) * 3600
        + int(match.group(f"{prefix}m")) * 60
        + int(match.group(f"{prefix}s"))
        + int(match.group(f"{prefix}ms")) / 1000
    )


def parse_story(text: str) -> tuple[list[StoryEntry], list[Issue]]:
    """Parse strict SRT-style blocks while retaining all structural errors."""
    normalized = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    entries: list[StoryEntry] = []
    issues: list[Issue] = []
    i = 0

    while i < len(lines):
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines):
            break

        entry_line = i + 1
        index_text = lines[i].strip()
        index = int(index_text) if index_text.isdigit() else None
        if index is None:
            issues.append(Issue("error", "entry-index", f"Expected an integer index, got {index_text!r}", entry_line))
        i += 1

        if i >= len(lines):
            issues.append(Issue("error", "timestamp-missing", "Entry has no timestamp line", entry_line, index))
            entries.append(StoryEntry(index, None, None, "", entry_line))
            break

        time_line_number = i + 1
        time_text = lines[i].strip()
        time_match = TIME_RE.fullmatch(time_text)
        start: float | None = None
        end: float | None = None
        if time_match is None:
            issues.append(
                Issue("error", "timestamp-format", f"Invalid timestamp line {time_text!r}", time_line_number, index)
            )
        else:
            minute_second_values = (
                int(time_match.group("sm")),
                int(time_match.group("ss")),
                int(time_match.group("em")),
                int(time_match.group("es")),
            )
            if any(value >= 60 for value in minute_second_values):
                issues.append(
                    Issue("error", "timestamp-range", "Minutes and seconds must be between 00 and 59", time_line_number, index)
                )
            else:
                start = _timestamp_seconds(time_match, "s")
                end = _timestamp_seconds(time_match, "e")
        i += 1

        content_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            content_lines.append(lines[i].strip())
            i += 1
        content = "\n".join(content_lines)
        if not content:
            issues.append(Issue("error", "content-empty", "Entry has no content", entry_line, index))
        entries.append(StoryEntry(index, start, end, content, entry_line))

    if not entries:
        issues.append(Issue("error", "story-empty", "Story has no entries"))

    seen_indices: set[int] = set()
    previous_end: float | None = None
    previous_had_speaker = False
    for position, entry in enumerate(entries, start=1):
        if entry.index is not None:
            if entry.index in seen_indices:
                issues.append(Issue("error", "entry-duplicate", f"Duplicate entry index {entry.index}", entry.line, entry.index))
            seen_indices.add(entry.index)
            if entry.index != position:
                issues.append(
                    Issue("error", "entry-sequence", f"Expected entry index {position}, got {entry.index}", entry.line, entry.index)
                )

        if entry.start is not None and entry.end is not None:
            if entry.end <= entry.start:
                issues.append(Issue("error", "timestamp-order", "Entry end must be after its start", entry.line, entry.index))
            if position == 1 and entry.start != 0:
                issues.append(Issue("error", "story-start", "The first entry must start at 00:00:00,000", entry.line, entry.index))
            if previous_end is not None:
                if entry.start < previous_end:
                    issues.append(
                        Issue(
                            "error",
                            "timestamp-overlap",
                            f"Entry starts at {entry.start:.3f}s before the previous entry ends at {previous_end:.3f}s",
                            entry.line,
                            entry.index,
                        )
                    )
                elif entry.start == previous_end and previous_had_speaker and SPEAKER_RE.search(entry.content):
                    issues.append(
                        Issue("warning", "dialogue-gap", "Back-to-back spoken entries have no reaction or breath gap", entry.line, entry.index)
                    )
            previous_end = entry.end
        previous_had_speaker = bool(SPEAKER_RE.search(entry.content))

    return entries, issues


def _split_tag(inner: str) -> tuple[str | None, str, list[str]]:
    parts = [part.strip() for part in inner.split("|")]
    head = parts[0]
    if ":" in head:
        namespace, name = head.split(":", 1)
        return namespace.strip(), name.strip(), parts[1:]
    return None, head.strip(), parts[1:]


def _option_map(options: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for option in options:
        if "=" in option:
            key, value = option.split("=", 1)
            parsed[key.strip()] = value.strip()
    return parsed


def _unknown_asset_issue(
    kind: str, name: str, entry: StoryEntry, known: set[str]
) -> Issue | None:
    if not name:
        return Issue("error", f"{kind}-name-empty", f"{kind.capitalize()} name must not be empty", entry.line, entry.index)
    if name not in known:
        return Issue("error", f"unknown-{kind}", f"Unregistered {kind} {name!r}", entry.line, entry.index)
    return None


def _animation_character_issue(
    animation: str, character: str | None, entry: StoryEntry, group_by_name: dict[str, str]
) -> Issue | None:
    if not character:
        return None
    group = group_by_name.get(animation)
    owners = ANIMATION_GROUP_OWNERS.get(group or "")
    if owners is not None and character not in owners:
        return Issue(
            "warning",
            "animation-character",
            f"Animation {animation!r} comes from the {group!r} group, not a group for {character!r}",
            entry.line,
            entry.index,
        )
    return None


def _estimate_speech_seconds(text: str) -> float:
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", text))
    word_count = len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text))
    punctuation_pause = min(0.8, len(re.findall(r"[，。！？?!…]", text)) * 0.1)
    return cjk_count / 4.0 + word_count / 2.5 + punctuation_pause


def _dialogue_after_speaker(content: str, speaker_match: re.Match[str]) -> str:
    dialogue = content[speaker_match.end() :]
    dialogue = TAG_RE.sub("", dialogue)
    dialogue = SCENE_RE.sub("", dialogue)
    return " ".join(part.strip() for part in dialogue.splitlines() if part.strip())


def validate_story(
    text: str,
    catalog: dict[str, object],
    *,
    allow_characters: Iterable[str] = (),
    allow_animations: Iterable[str] = (),
    allow_scenes: Iterable[str] = (),
    allow_cameras: Iterable[str] = (),
    allow_transitions: Iterable[str] = (),
    allow_props: Iterable[str] = (),
    allow_exaggerations: Iterable[str] = (),
    allow_combat_actions: Iterable[str] = (),
    allow_music: Iterable[str] = (),
    allow_sfx: Iterable[str] = (),
) -> tuple[list[StoryEntry], list[Issue]]:
    entries, issues = parse_story(text)
    characters = set(catalog.get("characters", [])) | set(allow_characters)
    speakers = set(catalog.get("speakers", [])) | characters | {"Narrator"}
    animations = set(catalog.get("animations", [])) | set(allow_animations)
    scenes = set(catalog.get("scenes", [])) | set(allow_scenes)
    cameras = set(catalog.get("cameras", [])) | set(allow_cameras)
    transitions = set(catalog.get("transitions", [])) | set(allow_transitions)
    props = set(catalog.get("props", [])) | {name.lower() for name in allow_props}
    animation_group_by_name = dict(catalog.get("animation_group_by_name", {}))
    exaggerations = set(catalog.get("exaggerations", [])) | set(allow_exaggerations)
    scene_director_actions = set(catalog.get("scene_director_actions", []))
    combat_commands = set(catalog.get("combat_commands", []))
    combat_actions = set(catalog.get("combat_actions", [])) | set(allow_combat_actions)
    music = set(catalog.get("music", [])) | set(allow_music)
    sfx = (
        set(catalog.get("sfx", []))
        | set(catalog.get("ambient", []))
        | set(allow_sfx)
    )
    procedural_sfx = set(catalog.get("procedural_sfx", []))

    current_scene: str | None = None
    recent_speakers: list[str] = []
    narrator_count = 0
    spoken_count = 0

    for entry in entries:
        content = entry.content
        entry_speaker: str | None = None
        if content.count("{") != content.count("}"):
            issues.append(Issue("error", "tag-braces", "Unbalanced tag braces", entry.line, entry.index))

        scene_matches = SCENE_RE.findall(content)
        if len(scene_matches) > 1:
            issues.append(Issue("error", "scene-multiple", "An entry may switch to only one scene", entry.line, entry.index))
        if scene_matches:
            current_scene = scene_matches[0]
            issue = _unknown_asset_issue("scene", current_scene, entry, scenes)
            if issue:
                issues.append(issue)

        speaker_matches = list(SPEAKER_RE.finditer(content))
        legacy_speaker_matches = list(
            re.finditer(r"(?m)^\{([A-Z][A-Za-z0-9]*)\}\s+([^{}\n]+)", content)
        )
        if legacy_speaker_matches:
            issues.append(
                Issue(
                    "error",
                    "legacy-speaker",
                    "Use [Speaker] dialogue syntax; legacy {Speaker} lines are not accepted for new stories",
                    entry.line,
                    entry.index,
                )
            )
        if len(speaker_matches) > 1:
            issues.append(Issue("error", "speaker-multiple", "Use at most one [Speaker] per entry", entry.line, entry.index))
        speaker_match = speaker_matches[0] if speaker_matches else None
        if speaker_match:
            speaker = speaker_match.group(1)
            entry_speaker = speaker if speaker != "Narrator" else None
            spoken_count += 1
            narrator_count += int(speaker == "Narrator")
            recent_speakers.append(speaker)
            if speaker not in speakers:
                issues.append(Issue("error", "unknown-speaker", f"Unregistered speaker {speaker!r}", entry.line, entry.index))
            if current_scene is None:
                issues.append(Issue("error", "scene-not-set", "Establish a registered scene before dialogue", entry.line, entry.index))

            dialogue = _dialogue_after_speaker(content, speaker_match)
            if not dialogue:
                issues.append(Issue("error", "dialogue-empty", "Speaker tag has no dialogue", entry.line, entry.index))
            elif entry.start is not None and entry.end is not None:
                estimate = _estimate_speech_seconds(dialogue)
                available = entry.end - entry.start
                if estimate + 0.25 > available:
                    issues.append(
                        Issue(
                            "warning",
                            "dialogue-timing",
                            f"Estimated speech is {estimate:.2f}s but the entry provides {available:.2f}s",
                            entry.line,
                            entry.index,
                        )
                    )

        targeted_character_starts = {
            match.start()
            for match in re.finditer(
                r"\{([A-Z][A-Za-z0-9]*)\}\{([A-Z][A-Za-z0-9]*)(?:\|[^{}]*)?\}", content
            )
        }
        legacy_speaker_starts = {
            match.start(1) - 1
            for match in re.finditer(r"(?m)^\{([A-Z][A-Za-z0-9]*)\}\s+[^{}\n]+", content)
        }

        for tag_match in TAG_RE.finditer(content):
            namespace, name, raw_options = _split_tag(tag_match.group(1))
            for option in raw_options:
                if option and "=" not in option:
                    issues.append(
                        Issue(
                            "error",
                            "tag-option",
                            f"Tag option {option!r} must use key=value syntax",
                            entry.line,
                            entry.index,
                        )
                    )
            options = _option_map(raw_options)

            if namespace is None:
                if tag_match.start() in targeted_character_starts or tag_match.start() in legacy_speaker_starts:
                    if name not in characters:
                        issues.append(
                            Issue("error", "unknown-character", f"Unregistered character {name!r}", entry.line, entry.index)
                        )
                    continue
                if name == "Hitstop":
                    continue
                issue = _unknown_asset_issue("animation", name, entry, animations)
                if issue:
                    issues.append(issue)
                compatibility_issue = _animation_character_issue(name, entry_speaker, entry, animation_group_by_name)
                if compatibility_issue:
                    issues.append(compatibility_issue)
                continue

            if namespace not in KNOWN_NAMESPACES:
                issues.append(
                    Issue("error", "unknown-namespace", f"Unsupported tag namespace {namespace!r}", entry.line, entry.index)
                )
                continue

            if namespace == "Animation":
                issue = _unknown_asset_issue("animation", name, entry, animations)
                if issue:
                    issues.append(issue)
                character = options.get("character")
                compatibility_issue = _animation_character_issue(
                    name, character or entry_speaker, entry, animation_group_by_name
                )
                if compatibility_issue:
                    issues.append(compatibility_issue)
                if character and character not in characters:
                    issues.append(
                        Issue(
                            "error",
                            "unknown-character",
                            f"Animation references unregistered character {character!r}",
                            entry.line,
                            entry.index,
                        )
                    )
            elif namespace == "Camera":
                issue = _unknown_asset_issue("camera", name, entry, cameras)
                if issue:
                    issues.append(issue)
            elif namespace == "Transition":
                issue = _unknown_asset_issue("transition", name, entry, transitions)
                if issue:
                    issues.append(issue)
            elif namespace == "Exaggeration":
                issue = _unknown_asset_issue("exaggeration", name, entry, exaggerations)
                if issue:
                    issues.append(issue)
            elif namespace == "SceneDirector":
                issue = _unknown_asset_issue("scene-director-action", name, entry, scene_director_actions)
                if issue:
                    issues.append(issue)
                for key in ("focus", "focusChar", "target"):
                    referenced = options.get(key)
                    if referenced and referenced not in characters:
                        issues.append(
                            Issue(
                                "error",
                                "unknown-character",
                                f"SceneDirector {key} references unregistered character {referenced!r}",
                                entry.line,
                                entry.index,
                            )
                        )
            elif namespace == "Music":
                if name != "Play":
                    issues.append(
                        Issue("error", "unknown-music-action", f"Unsupported Music action {name!r}", entry.line, entry.index)
                    )
                track = options.get("name")
                if not track:
                    issues.append(Issue("error", "music-name-missing", "Music:Play requires name=...", entry.line, entry.index))
                elif track not in music:
                    issues.append(Issue("error", "unknown-music", f"Unknown music cue {track!r}", entry.line, entry.index))
            elif namespace == "SFX":
                if name == "Play":
                    sound_name = options.get("name")
                    if not sound_name:
                        issues.append(Issue("error", "sfx-name-missing", "SFX:Play requires name=...", entry.line, entry.index))
                    elif sound_name not in sfx:
                        issues.append(Issue("error", "unknown-sfx", f"Unknown SFX {sound_name!r}", entry.line, entry.index))
                elif name == "Procedural":
                    sound_type = options.get("type")
                    if not sound_type:
                        issues.append(
                            Issue("error", "sfx-type-missing", "SFX:Procedural requires type=...", entry.line, entry.index)
                        )
                    elif sound_type not in procedural_sfx:
                        issues.append(
                            Issue("error", "unknown-procedural-sfx", f"Unknown procedural SFX {sound_type!r}", entry.line, entry.index)
                        )
                else:
                    issues.append(
                        Issue("error", "unknown-sfx-action", f"Unsupported SFX action {name!r}", entry.line, entry.index)
                    )
            elif namespace == "Combat":
                issue = _unknown_asset_issue("combat-command", name, entry, combat_commands)
                if issue:
                    issues.append(issue)
                for key in ("attacker", "defender", "character", "charA", "charB", "target"):
                    referenced = options.get(key)
                    if referenced and referenced not in characters:
                        issues.append(
                            Issue(
                                "error",
                                "unknown-character",
                                f"Combat {key} references unregistered character {referenced!r}",
                                entry.line,
                                entry.index,
                            )
                        )
                if name == "Action":
                    action_name = options.get("name") or options.get("action")
                    if not action_name:
                        issues.append(
                            Issue("error", "combat-action-missing", "Combat:Action requires name=...", entry.line, entry.index)
                        )
                    elif action_name not in combat_actions:
                        issues.append(
                            Issue("error", "unknown-combat-action", f"Unregistered combat action {action_name!r}", entry.line, entry.index)
                        )
                if name in {"Attack", "Reaction"}:
                    animation_name = options.get("anim")
                    if not animation_name:
                        issues.append(
                            Issue("error", "combat-animation-missing", f"Combat:{name} requires anim=...", entry.line, entry.index)
                        )
                    else:
                        animation_issue = _unknown_asset_issue("animation", animation_name, entry, animations)
                        if animation_issue:
                            issues.append(animation_issue)
                if name == "Override" and options.get("camera"):
                    camera_issue = _unknown_asset_issue("camera", options["camera"], entry, cameras)
                    if camera_issue:
                        issues.append(camera_issue)
            elif namespace == "Position":
                if name not in characters:
                    issues.append(
                        Issue("error", "unknown-character", f"Position targets unregistered character {name!r}", entry.line, entry.index)
                    )
                for coordinate in ("x", "y", "z"):
                    if coordinate in options:
                        try:
                            float(options[coordinate])
                        except ValueError:
                            issues.append(
                                Issue(
                                    "error",
                                    "position-number",
                                    f"Position {coordinate} must be numeric, got {options[coordinate]!r}",
                                    entry.line,
                                    entry.index,
                                )
                            )
                face = options.get("face")
                if face and face not in FACING_LITERALS and face not in characters:
                    issues.append(
                        Issue("error", "position-face", f"Unknown face target {face!r}", entry.line, entry.index)
                    )
            elif namespace == "Prop":
                if name.lower() not in props:
                    issues.append(
                        Issue("error", "unknown-prop", f"Unsupported prop {name!r}", entry.line, entry.index)
                    )
                character = options.get("character")
                if character and character not in characters:
                    issues.append(
                        Issue(
                            "error",
                            "unknown-character",
                            f"Prop references unregistered character {character!r}",
                            entry.line,
                            entry.index,
                        )
                    )
            elif namespace == "Event":
                character = options.get("character")
                if character and character not in characters:
                    issues.append(
                        Issue(
                            "error",
                            "unknown-character",
                            f"Event references unregistered character {character!r}",
                            entry.line,
                            entry.index,
                        )
                    )

    for i in range(2, len(recent_speakers)):
        if recent_speakers[i] == recent_speakers[i - 1] == recent_speakers[i - 2] != "Narrator":
            issues.append(
                Issue(
                    "warning",
                    "speaker-monologue",
                    f"{recent_speakers[i]!r} speaks in at least three consecutive dialogue entries",
                )
            )
            break
    if spoken_count >= 4 and narrator_count / spoken_count > 0.5:
        issues.append(
            Issue("warning", "narration-heavy", "More than half of spoken entries are narration; favor playable scenes")
        )

    return entries, issues


def _print_catalog(catalog: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
        return
    for key in (
        "characters",
        "speakers",
        "scenes",
        "cameras",
        "transitions",
        "directors",
        "exaggerations",
        "scene_director_actions",
        "combat_commands",
        "combat_actions",
        "props",
        "music",
        "sfx",
        "ambient",
        "procedural_sfx",
    ):
        values = catalog.get(key, [])
        print(f"{key} ({len(values)}):")
        print("  " + ", ".join(values))
    groups = catalog.get("animation_groups", {})
    if groups:
        print("animations_by_group:")
        grouped_names: set[str] = set()
        for group, names in groups.items():
            grouped_names.update(names)
            print(f"  {group} ({len(names)}): {', '.join(names)}")
        unclassified = sorted(set(catalog.get("animations", [])) - grouped_names)
        if unclassified:
            print(f"  episode_or_unclassified ({len(unclassified)}): {', '.join(unclassified)}")


def _print_validation(entries: list[StoryEntry], issues: list[Issue], as_json: bool) -> None:
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    if as_json:
        print(
            json.dumps(
                {
                    "entries": len(entries),
                    "errors": len(errors),
                    "warnings": len(warnings),
                    "issues": [asdict(issue) for issue in issues],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    for issue in issues:
        location = []
        if issue.line is not None:
            location.append(f"line {issue.line}")
        if issue.entry is not None:
            location.append(f"entry {issue.entry}")
        suffix = f" ({', '.join(location)})" if location else ""
        print(f"{issue.severity.upper():7} [{issue.code}] {issue.message}{suffix}")
    print(f"Validated {len(entries)} entries: {len(errors)} error(s), {len(warnings)} warning(s)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    catalog_parser = subparsers.add_parser("catalog", help="List registered Dula assets")
    catalog_parser.add_argument("--episode-dir", type=Path, help="Target episode directory")
    catalog_parser.add_argument("--project-root", type=Path, help="Repository root; normally auto-detected")
    catalog_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_parser = subparsers.add_parser("validate", help="Strictly validate a script.story file")
    validate_parser.add_argument("--story", required=True, type=Path, help="Path to script.story")
    validate_parser.add_argument("--episode-dir", type=Path, help="Target episode; defaults to the story parent")
    validate_parser.add_argument("--project-root", type=Path, help="Repository root; normally auto-detected")
    validate_parser.add_argument("--allow-character", action="append", default=[], help="Allow a dynamically registered character")
    validate_parser.add_argument("--allow-animation", action="append", default=[], help="Allow a dynamically registered animation")
    validate_parser.add_argument("--allow-scene", action="append", default=[], help="Allow a dynamically registered scene")
    validate_parser.add_argument("--allow-camera", action="append", default=[], help="Allow a dynamically registered camera")
    validate_parser.add_argument("--allow-transition", action="append", default=[], help="Allow a dynamically registered transition")
    validate_parser.add_argument("--allow-prop", action="append", default=[], help="Allow a custom prop handled by episode code")
    validate_parser.add_argument("--allow-exaggeration", action="append", default=[], help="Allow a custom exaggeration")
    validate_parser.add_argument("--allow-combat-action", action="append", default=[], help="Allow a dynamically registered combat action")
    validate_parser.add_argument("--allow-music", action="append", default=[], help="Allow a planned or externally supplied music cue")
    validate_parser.add_argument("--allow-sfx", action="append", default=[], help="Allow a planned or externally supplied SFX cue")
    validate_parser.add_argument("--warnings-as-errors", action="store_true", help="Return nonzero when warnings exist")
    validate_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "catalog":
            episode_dir = args.episode_dir.resolve() if args.episode_dir else None
            project_root = args.project_root.resolve() if args.project_root else find_project_root(episode_dir)
            catalog = discover_catalog(project_root, episode_dir)
            _print_catalog(catalog, args.json)
            return 0

        story_path = args.story.resolve()
        if not story_path.is_file():
            parser.error(f"Story file not found: {story_path}")
        episode_dir = args.episode_dir.resolve() if args.episode_dir else story_path.parent
        project_root = args.project_root.resolve() if args.project_root else find_project_root(episode_dir, story_path)
        catalog = discover_catalog(project_root, episode_dir)
        text = story_path.read_text(encoding="utf-8")
        entries, issues = validate_story(
            text,
            catalog,
            allow_characters=args.allow_character,
            allow_animations=args.allow_animation,
            allow_scenes=args.allow_scene,
            allow_cameras=args.allow_camera,
            allow_transitions=args.allow_transition,
            allow_props=args.allow_prop,
            allow_exaggerations=args.allow_exaggeration,
            allow_combat_actions=args.allow_combat_action,
            allow_music=args.allow_music,
            allow_sfx=args.allow_sfx,
        )
        bootstrap_path = episode_dir / "bootstrap.js"
        if not bootstrap_path.is_file():
            issues.append(
                Issue(
                    "error",
                    "bootstrap-missing",
                    f"Episode bootstrap.js not found in {episode_dir}",
                )
            )
        elif not _bootstrap_calls_register_all(bootstrap_path):
            issues.append(
                Issue(
                    "error",
                    "bootstrap-register-all",
                    "bootstrap.js must import registerAll from dula-assets and call it",
                )
            )
        _print_validation(entries, issues, args.json)
        has_errors = any(issue.severity == "error" for issue in issues)
        has_warnings = any(issue.severity == "warning" for issue in issues)
        return int(has_errors or (args.warnings_as_errors and has_warnings))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
