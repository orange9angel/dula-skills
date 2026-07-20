from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]


def find_workspace_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "dula-story" / "episodes").is_dir():
            return candidate
    raise RuntimeError("Unable to locate the Dula multi-repository workspace")


PROJECT_ROOT = find_workspace_root()
TOOL_PATH = SKILL_DIR / "scripts" / "story_tool.py"

spec = importlib.util.spec_from_file_location("story_tool", TOOL_PATH)
story_tool = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = story_tool
spec.loader.exec_module(story_tool)


VALID_STORY = """1
00:00:00,000 --> 00:00:04,000
@NobitaRoom{Position:Nobita|x=-0.8|y=0.01|z=0.5|face=center}{Camera:Static|position=0,3,7|lookAt=0,1,0}
[Narrator]房间里安静得反常。

2
00:00:04,500 --> 00:00:08,500
[Nobita]{Shrug}今天连叹气都没有回声。
"""


class StoryToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.episode_dir = PROJECT_ROOT / "dula-story" / "episodes" / "doraemon_stone_hat"
        cls.catalog = story_tool.discover_catalog(PROJECT_ROOT, cls.episode_dir)

    def test_catalog_discovers_official_and_episode_assets(self) -> None:
        self.assertIn("Doraemon", self.catalog["characters"])
        self.assertIn("Nobita", self.catalog["characters"])
        self.assertIn("Narrator", self.catalog["speakers"])
        self.assertIn("ParkScene", self.catalog["scenes"])
        self.assertIn("NobitaRoom", self.catalog["scenes"])
        self.assertIn("Shrug", self.catalog["animations"])
        self.assertIn("Scold", self.catalog["animation_groups"]["shizuka"])
        self.assertEqual("doraemon", self.catalog["animation_group_by_name"]["ReachHand"])
        self.assertIn("Static", self.catalog["cameras"])
        self.assertIn("Fade", self.catalog["transitions"])
        self.assertIn("hat", self.catalog["props"])
        self.assertIn("room_theme", self.catalog["music"])
        self.assertIn("whoosh_fast", self.catalog["sfx"])
        self.assertIn("engine_idle", self.catalog["procedural_sfx"])
        self.assertIn("comedy_shock", self.catalog["exaggerations"])
        self.assertIn("Formation", self.catalog["scene_director_actions"])
        self.assertIn("SceneDirector", self.catalog["directors"])

    def test_parse_real_baseline_structure(self) -> None:
        text = (self.episode_dir / "script.story").read_text(encoding="utf-8")
        entries, issues = story_tool.parse_story(text)
        self.assertEqual(14, len(entries))
        self.assertEqual(list(range(1, 15)), [entry.index for entry in entries])
        self.assertEqual(0, entries[0].start)
        self.assertFalse([issue for issue in issues if issue.severity == "error"], issues)

    def test_valid_story_passes_strict_validation(self) -> None:
        entries, issues = story_tool.validate_story(VALID_STORY, self.catalog)
        self.assertEqual(2, len(entries))
        self.assertFalse([issue for issue in issues if issue.severity == "error"], issues)

    def test_real_baseline_exposes_legacy_asset_and_position_errors(self) -> None:
        text = (self.episode_dir / "script.story").read_text(encoding="utf-8")
        _, issues = story_tool.validate_story(text, self.catalog)
        codes = {issue.code for issue in issues}
        self.assertIn("unknown-animation", codes)
        self.assertIn("position-number", codes)

    def test_rejects_structural_and_domain_errors(self) -> None:
        invalid = """1
00:00:01,000 --> 00:00:05,000 trailing
@GhostScene{Position:Nobita|x=0|y=0|z=Nobita|face=Ghost}{Camera:Imaginary|sideAngle:20}
[Ghost]{NotRegistered}台词。

1
00:00:03,000 --> 00:00:02,000
{Transition:MissingTransition|duration=1}
"""
        _, issues = story_tool.validate_story(invalid, self.catalog)
        codes = {issue.code for issue in issues}
        expected = {
            "timestamp-format",
            "entry-duplicate",
            "entry-sequence",
            "timestamp-order",
            "unknown-scene",
            "unknown-speaker",
            "unknown-animation",
            "unknown-camera",
            "unknown-transition",
            "position-number",
            "position-face",
            "tag-option",
        }
        self.assertTrue(expected.issubset(codes), sorted(codes))

    def test_allow_flags_support_dynamic_assets(self) -> None:
        custom = """1
00:00:00,000 --> 00:00:03,000
@CustomScene
[CustomHero]{CustomPose}走吧。
"""
        _, blocked = story_tool.validate_story(custom, self.catalog)
        self.assertTrue([issue for issue in blocked if issue.severity == "error"])

        _, allowed = story_tool.validate_story(
            custom,
            self.catalog,
            allow_characters=["CustomHero"],
            allow_animations=["CustomPose"],
            allow_scenes=["CustomScene"],
        )
        self.assertFalse([issue for issue in allowed if issue.severity == "error"], allowed)

    def test_rejects_unknown_props_but_allows_episode_extensions(self) -> None:
        custom_prop = """1
00:00:00,000 --> 00:00:03,000
@RoomScene
[Nobita]{Prop:MagicBox|character=Nobita}这是什么？
"""
        _, blocked = story_tool.validate_story(custom_prop, self.catalog)
        self.assertIn("unknown-prop", {issue.code for issue in blocked})

        _, allowed = story_tool.validate_story(custom_prop, self.catalog, allow_props=["MagicBox"])
        self.assertNotIn("unknown-prop", {issue.code for issue in allowed})

    def test_warns_when_character_uses_another_characters_animation_group(self) -> None:
        mismatched = """1
00:00:00,000 --> 00:00:03,000
@RoomScene
[Doraemon]{Scold}快点。
"""
        _, issues = story_tool.validate_story(mismatched, self.catalog)
        compatibility = [issue for issue in issues if issue.code == "animation-character"]
        self.assertEqual(1, len(compatibility))
        self.assertEqual("warning", compatibility[0].severity)

        matched = mismatched.replace("Doraemon", "Shizuka")
        _, matched_issues = story_tool.validate_story(matched, self.catalog)
        self.assertNotIn("animation-character", {issue.code for issue in matched_issues})

    def test_dialogue_timing_is_a_warning(self) -> None:
        rushed = """1
00:00:00,000 --> 00:00:01,000
@RoomScene
[Nobita]我今天有一件特别特别特别重要的事情必须马上告诉你！
"""
        _, issues = story_tool.validate_story(rushed, self.catalog)
        timing = [issue for issue in issues if issue.code == "dialogue-timing"]
        self.assertEqual(1, len(timing))
        self.assertEqual("warning", timing[0].severity)

    def test_catalog_and_validation_are_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            episode = Path(temp_dir)
            story = episode / "script.story"
            voice = episode / "config" / "voice_config.json"
            voice.parent.mkdir(parents=True)
            story.write_text(VALID_STORY, encoding="utf-8")
            voice.write_text('{"Nobita":{"custom":true}}', encoding="utf-8")
            before_story = story.read_bytes()
            before_voice = voice.read_bytes()

            catalog = story_tool.discover_catalog(PROJECT_ROOT, episode)
            story_tool.validate_story(story.read_text(encoding="utf-8"), catalog, allow_scenes=["NobitaRoom"])

            self.assertEqual(before_story, story.read_bytes())
            self.assertEqual(before_voice, voice.read_bytes())

    def test_catalog_follows_only_reachable_episode_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            episode = Path(temp_dir)
            (episode / "bootstrap.js").write_text(
                "import {\n  registerAll,\n} from 'dula-assets';\n"
                "import {\n  episodeAssets,\n} from './episode_assets.js';\n"
                "// import './unused.js';\n"
                "registerAll();\n",
                encoding="utf-8",
            )
            (episode / "episode_assets.js").write_text(
                "// registerScene('CommentedScene', CommentedScene);\n"
                "const fake = \"registerScene('StringScene', StringScene)\";\n"
                "registerScene(\n  'ReachableScene',\n  ReachableScene\n);\n"
                "registerCombatAction(\n  'ReachableCombo',\n  comboSpec\n);\n"
                "export const episodeAssets = true;\n",
                encoding="utf-8",
            )
            (episode / "unused.js").write_text(
                "registerScene('UnusedScene', UnusedScene);\n",
                encoding="utf-8",
            )

            catalog = story_tool.discover_catalog(PROJECT_ROOT, episode)
            self.assertIn("ReachableScene", catalog["scenes"])
            self.assertNotIn("UnusedScene", catalog["scenes"])
            self.assertNotIn("CommentedScene", catalog["scenes"])
            self.assertNotIn("StringScene", catalog["scenes"])
            self.assertIn("ReachableCombo", catalog["combat_actions"])

    def test_cli_requires_episode_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            episode = Path(temp_dir)
            story = episode / "script.story"
            story.write_text(VALID_STORY.replace("NobitaRoom", "RoomScene"), encoding="utf-8")
            argv = [
                "validate",
                "--story",
                str(story),
                "--episode-dir",
                str(episode),
                "--project-root",
                str(PROJECT_ROOT),
            ]

            output = io.StringIO()
            with redirect_stdout(output):
                missing_result = story_tool.main(argv)
            self.assertEqual(1, missing_result)
            self.assertIn("bootstrap-missing", output.getvalue())

            (episode / "bootstrap.js").write_text("export {};\n", encoding="utf-8")
            empty_output = io.StringIO()
            with redirect_stdout(empty_output):
                empty_result = story_tool.main(argv)
            self.assertEqual(1, empty_result)
            self.assertIn("bootstrap-register-all", empty_output.getvalue())

            (episode / "bootstrap.js").write_text(
                "import { registerAll } from 'dula-assets';\n\nregisterAll();\n",
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()):
                present_result = story_tool.main(argv)
            self.assertEqual(0, present_result)

    def test_rejects_legacy_speaker_and_empty_asset_names(self) -> None:
        legacy = """1
00:00:00,000 --> 00:00:03,000
{Nobita} hello
{Camera:}{Animation:}{Transition:}
"""
        _, issues = story_tool.validate_story(legacy, self.catalog)
        codes = {issue.code for issue in issues}
        self.assertIn("legacy-speaker", codes)
        self.assertIn("camera-name-empty", codes)
        self.assertIn("animation-name-empty", codes)
        self.assertIn("transition-name-empty", codes)

    def test_rejects_unknown_registry_backed_and_audio_tags(self) -> None:
        invalid = """1
00:00:00,000 --> 00:00:05,000
@RoomScene
{Music:Play|name=missing_theme}{SFX:Play|name=missing_hit}{SFX:Procedural|type=missing_type}
{Exaggeration:missing_effect}{SceneDirector:MissingAction}{Combat:Action|name=missing_combo|attacker=Nobita|defender=Doraemon}
[Nobita]测试。
"""
        _, issues = story_tool.validate_story(invalid, self.catalog)
        codes = {issue.code for issue in issues}
        expected = {
            "unknown-music",
            "unknown-sfx",
            "unknown-procedural-sfx",
            "unknown-exaggeration",
            "unknown-scene-director-action",
            "unknown-combat-action",
        }
        self.assertTrue(expected.issubset(codes), sorted(codes))

        _, allowed = story_tool.validate_story(
            invalid,
            self.catalog,
            allow_music=["missing_theme"],
            allow_sfx=["missing_hit"],
            allow_exaggerations=["missing_effect"],
            allow_combat_actions=["missing_combo"],
        )
        allowed_codes = {issue.code for issue in allowed}
        self.assertNotIn("unknown-music", allowed_codes)
        self.assertNotIn("unknown-sfx", allowed_codes)
        self.assertNotIn("unknown-exaggeration", allowed_codes)
        self.assertNotIn("unknown-combat-action", allowed_codes)


if __name__ == "__main__":
    unittest.main()
