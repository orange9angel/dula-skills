---
name: story-writer
description: Create or revise production-ready Dula `script.story` episodes from a theme, premise, or research brief. Use when an agent needs to research current or canonical context on the internet, design a funny or meaningful short story, write character dialogue and visual beats, map them to registered Dula scenes/actions/cameras, and validate the result before the existing audio and render skills run.
---

# Story Writer

Write the story layer for this repository. Use the current agent for research, reasoning, and prose; do not call a second LLM API. Keep the skill in `dula-skills/story-writer/` and write episode output under `dula-story/episodes/`.

## Boundaries

- Produce or revise `script.story`. For a brand-new episode, also create the minimal `bootstrap.js` needed to call `registerAll()` when it is absent.
- Do not create or overwrite `voice_config.json`, ambient configuration, music, SFX, generated audio, screenshots, or video unless the user separately asks for that work.
- Preserve an existing `script.story` unless the user clearly requested an edit or rewrite. When replacement authority is ambiguous, write `script.story.draft` and report it.
- Treat `dula-engine/lib/StoryParser.js` and actual registry calls in `dula-assets/index.js` plus the target episode as the contract. Do not invent actions, scenes, cameras, transitions, or props.
- Treat `doraemon_stone_hat` as a production reference, not a syntax authority. It contains legacy unregistered animation names and a bad position value.

## Load Context

Read only the references needed for the task:

- Read [references/story-format.md](references/story-format.md) before authoring or changing `.story` syntax.
- Read [references/writing-quality.md](references/writing-quality.md) before outlining, writing comedy, adapting research, or running the critic pass.
- Read [references/directing-craft.md](references/directing-craft.md) before outlining. It defines the structural disciplines (structure as meaning, information asymmetry, the empty beat, emotional rhythm, balance endings) that the outline and critic pass are checked against.

Discover the current engine vocabulary instead of copying a stale list:

```shell
python dula-skills/story-writer/scripts/story_tool.py catalog --episode-dir dula-story/episodes/<episode>
```

The catalog includes official registrations, animation source groups, reachable registrations found from the target bootstrap, supported props, audio registry names, local audio stems, and procedural SFX types. Prefer `common` animations or the speaking character's own group; global registration alone does not guarantee a good pose on every character. If a requested asset is absent, choose a registered alternative or implement/register the asset only when the user asked for engine or episode code changes.

## Workflow

1. **Resolve the brief.** Extract theme, audience, tone, target duration, cast, episode directory, and whether the request is a new story or a rewrite. Infer noncritical omissions from repository context. Default to a concise 60-120 second episode when duration is not specified.
2. **Inspect the target.** Read its existing `script.story`, `bootstrap.js`, relevant config keys, and nearby episode conventions. Run `catalog` before selecting visual tags.
3. **Research when useful.** Use available web search/fetch tools when the user requests internet research, facts may be current, or canon/cultural context affects the premise. Prefer primary or authoritative sources. Record a compact fact list and source URLs in working context; do not paste citations into dialogue. If web tools are unavailable, say so and avoid invented facts.
4. **Build story candidates.** Form at least two compact beat approaches with different comic or thematic engines. Select the stronger one using the rubric in `writing-quality.md`; do not merely combine both.
5. **Outline causally.** Define protagonist want, obstacle, escalating attempts, irreversible turn, payoff, and optional emotional aftertaste. Every beat must cause the next. Plant any callback before paying it off. Also state the one-sentence emotional wound, the target aftertaste word, the empty-beat position, and the per-beat intensity curve required by `directing-craft.md`.
6. **Draft for performance.** Give each speaker a distinct objective and rhythm. Prefer playable subtext, interruption, reaction, and visual action over explanation. Keep one speaking character per entry.
7. **Map to Dula.** Use only cataloged assets. Establish a scene before dialogue, keep positions stable unless movement is intentional, use safe camera distances, and allocate dialogue time from estimated speech rather than fixed-size slots.
8. **Validate and revise.** Run the strict validator, fix every error, then run the adversarial critic pass from `writing-quality.md`: a separate reading against the rubric and the directing-craft checks, with intent hidden from the critic. Rewrite weak beats rather than polishing isolated words.
9. **(Optional) Performance pass.** If the user wants richer acting, hand the draft to `performance-director` to optimize facial expressions and body actions based on semantics. See `dula-skills/performance-director/SKILL.md`.
10. **Hand off cleanly.** Report the story path, research sources when used, validator result, and any remaining audio/render work. Do not claim render readiness until the engine verification stages have run.

## Strict Validation

Run this after every material draft change:

```shell
python dula-skills/story-writer/scripts/story_tool.py validate --story dula-story/episodes/<episode>/script.story --episode-dir dula-story/episodes/<episode>
```

Use explicit allow flags only for real runtime assets that the static scanner cannot see:

```shell
python dula-skills/story-writer/scripts/story_tool.py validate --story <path> --episode-dir <dir> --allow-character CustomHero --allow-animation CustomPose --allow-prop CustomProp --allow-music planned_theme
```

After a complete episode has bootstrap and dependencies, run the repository gates from `dula-story`:

```shell
node --check ./episodes/<episode>/bootstrap.js
npx dula-inspect-team ./episodes/<episode>
```

After audio exists, run `npx dula-verify ./episodes/<episode>` and visually inspect the generated shots. Unknown animations may be skipped at runtime, so a successful render never replaces strict registry validation.

## Minimal Bootstrap

For a new episode using only official assets, create this only when `bootstrap.js` is absent:

```javascript
import { registerAll } from 'dula-assets';

registerAll();
```

Use `RoomScene`, not an episode-local alias such as `NobitaRoom`, unless that alias is actually registered in the target bootstrap.
