from __future__ import annotations

import copy
import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]


def find_workspace_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "dula-story" / "episodes").is_dir():
            return candidate
    raise RuntimeError("Unable to locate the Dula multi-repository workspace")


PROJECT_ROOT = find_workspace_root()
TOOL_PATH = SKILL_DIR / "scripts" / "scene_tool.py"

spec = importlib.util.spec_from_file_location("scene_tool", TOOL_PATH)
scene_tool = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = scene_tool
spec.loader.exec_module(scene_tool)


STORY = """1
00:00:00,000 --> 00:00:04,000
@TestScene{Event:RevealHero}{Camera:Static|position=0,3,8|lookAt=0,1,0}
[Hero]我到了。

2
00:00:04,000 --> 00:00:07,000
{Event:DetachToken}

3
00:00:07,000 --> 00:00:10,000
{Event:LiftToken}

4
00:00:10,000 --> 00:00:14,000
{Event:Move|character=Hero|x=1|y=0|z=1}{Camera:Static|position=2,3,8|lookAt=1,1,1}
[Hero]完成了。
"""


SCENE_SOURCE = """import { SceneBase } from 'dula-engine';

export class TestScene extends SceneBase {
  constructor() {
    super('TestScene');
    this.table = null;
    this.token = null;
  }

  build() {
    this.registerCameraObstacle({ type: 'box' });
  }

  revealHero() {
    return true;
  }

  detachToken() {
    return true;
  }

  liftToken() {
    return true;
  }
}
"""


BOOTSTRAP = """import { registerAll } from 'dula-assets';
import { registerCharacter, registerScene } from 'dula-engine';
import { TestScene } from './scenes/TestScene.js';

registerAll();
registerCharacter('Hero', Hero);
registerScene('TestScene', TestScene);
"""


def make_contract(episode: str) -> dict:
    return {
        "$schema": "../references/scene-contract.schema.json",
        "contractVersion": "1.0",
        "episode": episode,
        "sourceStory": "script.story",
        "intent": {
            "premise": "A hidden hero reveals a token and carries it into view.",
            "audience": "Family animation viewers",
            "designPriorities": ["Keep the hero and token readable"],
        },
        "registrations": {
            "bootstrap": "bootstrap.js",
            "scenes": ["TestScene"],
            "characters": ["Hero"],
        },
        "scenes": [
            {
                "registryName": "TestScene",
                "implementation": {
                    "kind": "episode-local",
                    "name": "TestScene",
                    "module": "scenes/TestScene.js",
                    "export": "TestScene",
                    "bootstrap": "bootstrap.js",
                    "readiness": "synchronous",
                },
                "intent": {
                    "location": "A compact test stage",
                    "timeOfDay": "Neutral studio light",
                    "tone": ["Clear", "Playful"],
                    "storyFunction": "Exercise stateful staging rules",
                    "visualRules": ["Keep the hero separated from the token silhouette"],
                },
                "coordinates": {
                    "unit": "meter",
                    "upAxis": "+Y",
                    "horizontalAxes": ["X", "Z"],
                    "groundY": 0,
                },
                "stage": {
                    "bounds": {"min": [-10, 0, -10], "max": [10, 10, 10]},
                    "zones": [
                        {
                            "id": "walkableStage",
                            "bounds": {"min": [-5, 0, -5], "max": [5, 2, 5]},
                            "walkable": True,
                            "purpose": ["Character blocking"],
                        }
                    ],
                    "anchors": {
                        "tokenReveal": {
                            "space": "world",
                            "relativeTo": "$scene",
                            "position": [0, 1, 0],
                            "purpose": "Token reveal focal point",
                        }
                    },
                },
                "lighting": {
                    "mood": "Bright neutral key with gentle fill",
                    "keyDirection": [-1, -2, 1],
                    "fillDirection": [1, -1, 0],
                    "readabilityRules": ["Maintain facial fill throughout the move"],
                },
                "cameraObstacles": [
                    {
                        "id": "rearWall",
                        "type": "box",
                        "space": "world",
                        "center": [9, 5, -9],
                        "size": [1, 10, 1],
                    }
                ],
                "audioAnchors": [],
                "dependencies": [],
            }
        ],
        "entities": [
            {
                "id": "Hero",
                "scene": "TestScene",
                "kind": "character",
                "runtimeName": "Hero",
                "binding": "$characters.Hero",
                "parent": "$scene",
                "initialPresence": "offstage",
                "visualForwardAxis": "+Z",
                "focusPoints": {"head": [0, 1.6, 0]},
                "initial": {
                    "visible": False,
                    "transform": {
                        "space": "world",
                        "relativeTo": "$scene",
                        "position": [0, 0, 0],
                    },
                },
            },
            {
                "id": "Table",
                "scene": "TestScene",
                "kind": "prop",
                "binding": "table",
                "parent": "$scene",
                "initialPresence": "onstage",
                "initial": {
                    "visible": True,
                    "transform": {
                        "space": "world",
                        "relativeTo": "$scene",
                        "position": [0, 0, 0],
                    },
                },
            },
            {
                "id": "Token",
                "scene": "TestScene",
                "kind": "prop",
                "binding": "token",
                "parent": "Table",
                "initialPresence": "onstage",
                "focusPoints": {"center": [0, 0, 0]},
                "initial": {
                    "visible": True,
                    "transform": {
                        "space": "local",
                        "relativeTo": "Table",
                        "position": [0, 1, 0],
                    },
                },
            },
        ],
        "state": {},
        "events": [
            {
                "tag": "RevealHero",
                "scene": "TestScene",
                "handler": "revealHero",
                "argumentMode": "none",
                "durationSeconds": 0.5,
                "requires": [],
                "effects": [
                    {
                        "op": "presence",
                        "character": "Hero",
                        "from": "offstage",
                        "to": "onstage",
                    }
                ],
            },
            {
                "tag": "DetachToken",
                "scene": "TestScene",
                "handler": "detachToken",
                "argumentMode": "none",
                "durationSeconds": 0.25,
                "requires": ["RevealHero"],
                "effects": [
                    {
                        "op": "reparent",
                        "entity": "Token",
                        "to": "$scene",
                        "preserveWorld": True,
                    }
                ],
            },
            {
                "tag": "LiftToken",
                "scene": "TestScene",
                "handler": "liftToken",
                "argumentMode": "none",
                "durationSeconds": 1.0,
                "requires": ["DetachToken"],
                "effects": [
                    {
                        "op": "motion",
                        "entity": "Token",
                        "space": "world",
                        "relativeTo": "$scene",
                        "from": [0, 1, 0],
                        "to": [0, 3, 0],
                        "tolerance": 0.05,
                    }
                ],
            },
        ],
        "blocking": [
            {
                "id": "heroMove",
                "scene": "TestScene",
                "character": "Hero",
                "entry": 4,
                "from": [0, 0, 0],
                "to": [1, 0, 1],
                "zone": "walkableStage",
                "clearance": 0.5,
                "purpose": "Carry the hero into the final composition",
            }
        ],
        "shotChecks": [],
        "acceptance": {
            "staticChecks": ["Scene contract validator reports no diagnostics"],
            "runtimeChecks": ["Hero and token remain readable in the final shot"],
        },
    }


class SceneToolTests(unittest.TestCase):
    def setUp(self) -> None:
        episodes_dir = PROJECT_ROOT / "dula-story" / "episodes"
        self.temp_dir = tempfile.TemporaryDirectory(prefix="scene_tool_test_", dir=episodes_dir)
        self.episode_dir = Path(self.temp_dir.name)
        (self.episode_dir / "scenes").mkdir()
        self.story = self.episode_dir / "script.story"
        self.story.write_text(STORY, encoding="utf-8")
        (self.episode_dir / "bootstrap.js").write_text(BOOTSTRAP, encoding="utf-8")
        (self.episode_dir / "scenes" / "TestScene.js").write_text(SCENE_SOURCE, encoding="utf-8")
        self.contract = make_contract(self.episode_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def validate(self, contract: dict | None = None, story: Path | None = None):
        diagnostics, _ = scene_tool.validate_contract(
            contract or self.contract,
            PROJECT_ROOT,
            self.episode_dir,
            story or self.story,
        )
        return diagnostics

    @staticmethod
    def codes(diagnostics, severity: str | None = None) -> set[str]:
        return {
            item.code
            for item in diagnostics
            if severity is None or item.severity == severity
        }

    def event(self, contract: dict, tag: str) -> dict:
        return next(event for event in contract["events"] if event["tag"] == tag)

    def test_valid_contract_passes_schema_and_semantic_validation(self) -> None:
        diagnostics = self.validate()
        self.assertEqual([], diagnostics, [item.as_dict() for item in diagnostics])

    def test_missing_custom_event_is_evt001(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["events"] = [event for event in contract["events"] if event["tag"] != "LiftToken"]

        self.assertIn("EVT001", self.codes(self.validate(contract), "error"))

    def test_missing_handler_is_evt002(self) -> None:
        contract = copy.deepcopy(self.contract)
        self.event(contract, "LiftToken")["handler"] = "missingHandler"

        self.assertIn("EVT002", self.codes(self.validate(contract), "error"))

    def test_custom_event_options_warn_evt004(self) -> None:
        self.story.write_text(
            STORY.replace("{Event:RevealHero}", "{Event:RevealHero|mood=quiet}"),
            encoding="utf-8",
        )

        self.assertIn("EVT004", self.codes(self.validate(), "warning"))

    def test_requires_must_precede_dependent_event(self) -> None:
        contract = copy.deepcopy(self.contract)
        self.event(contract, "DetachToken")["requires"] = ["LiftToken"]

        self.assertIn("EVT008", self.codes(self.validate(contract), "error"))

    def test_world_motion_under_non_scene_parent_is_space002(self) -> None:
        contract = copy.deepcopy(self.contract)
        self.event(contract, "DetachToken")["effects"] = []

        self.assertIn("SPACE002", self.codes(self.validate(contract), "error"))

    def test_reparent_before_world_motion_is_valid(self) -> None:
        diagnostics = self.validate()

        self.assertNotIn("SPACE002", self.codes(diagnostics))
        self.assertFalse(diagnostics, [item.as_dict() for item in diagnostics])

    def test_presence_transition_must_match_current_presence(self) -> None:
        contract = copy.deepcopy(self.contract)
        self.event(contract, "RevealHero")["effects"][0]["from"] = "onstage"

        self.assertIn("PRES002", self.codes(self.validate(contract), "error"))

    def test_shot_offset_cannot_exceed_entry_duration(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["shotChecks"].append(
            {
                "id": "lateRevealCheck",
                "scene": "TestScene",
                "entry": 1,
                "offsetSeconds": 4.01,
                "purpose": "Verify the revealed hero",
                "mustSee": [
                    {
                        "entity": "Hero",
                        "focus": "head",
                        "minFrameArea": 0.1,
                        "maxOcclusion": 0.1,
                        "safeMargin": 0.05,
                    }
                ],
                "mustHavePresence": [{"character": "Hero", "value": "onstage"}],
                "mustShowTogether": [],
            }
        )

        self.assertIn("SHOT003", self.codes(self.validate(contract), "error"))

    def test_unguarded_camera_without_shot_check_warns_shot006(self) -> None:
        self.story.write_text(
            STORY.replace("{Camera:Static|position=0,3,8", "{Camera:TwoShot|position=0,3,8", 1),
            encoding="utf-8",
        )

        self.assertIn("SHOT006", self.codes(self.validate(), "warning"))

    def test_malformed_contract_returns_schema_diagnostics_without_crashing(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["entities"] = [None, "not-an-entity"]

        diagnostics = self.validate(contract)

        self.assertTrue(diagnostics)
        self.assertEqual({"SCHEMA"}, self.codes(diagnostics, "error"))

    def test_scaffold_refuses_to_overwrite_without_force(self) -> None:
        output = self.episode_dir / "config" / "scene_contract.json"
        argv = ["scaffold", "--episode-dir", str(self.episode_dir)]

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            first_result = scene_tool.main(argv)
        first_bytes = output.read_bytes()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            second_result = scene_tool.main(argv)

        self.assertEqual(0, first_result)
        self.assertEqual(2, second_result)
        self.assertEqual(first_bytes, output.read_bytes())

    def test_inventory_classifies_events_and_reachable_assets(self) -> None:
        inventory = scene_tool.build_inventory(self.episode_dir, self.story)

        self.assertEqual(["TestScene"], inventory["scenes"])
        self.assertEqual(
            ["RevealHero", "DetachToken", "LiftToken"],
            [event["tag"] for event in inventory["events"]["custom"]],
        )
        self.assertEqual(["Move"], [event["tag"] for event in inventory["events"]["engine"]])
        self.assertIn("TestScene", inventory["registrations"]["reachableScenes"])
        self.assertIn("Hero", inventory["registrations"]["reachableCharacters"])
        self.assertIn("liftToken", inventory["sceneSources"]["TestScene"]["methods"])


if __name__ == "__main__":
    unittest.main()
