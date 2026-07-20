# Dula Story Format

Use this reference while authoring or validating `script.story`. The executable source of truth is `dula-engine/lib/StoryParser.js`; registry availability comes from `dula-assets/index.js` and registrations in the target episode.

## Block Grammar

Each block is an SRT-style entry separated by a blank line:

```text
1
00:00:00,000 --> 00:00:04,000
@RoomScene{Position:Nobita|x=-0.8|y=0.01|z=0.5|face=center}{Camera:Static|position=0,3,7|lookAt=0,1,0}
[Narrator]放学后的房间安静得反常。

2
00:00:04,400 --> 00:00:08,400
[Nobita]{Shrug}今天连叹气都没有回声。
```

Author with stricter rules than the runtime parser:

- Number entries consecutively from `1`.
- Use exact `HH:MM:SS,mmm --> HH:MM:SS,mmm` timestamps.
- Keep `end > start`, no overlaps, and a short pause between spoken entries.
- Start the first entry at zero and establish a registered scene before dialogue.
- Put at most one `[Speaker]` in a block.
- Put the spoken line on one line. Configuration tags may occupy a preceding line in the same block.
- Use ASCII letters, digits, and underscores for scene names because scene parsing uses `\w+`.

## Tags

Supported parser namespaces include:

```text
Animation Camera Music Ball Prop Position SFX Transition Event Dunk
Hitstop Voice Combat SceneDirector Exaggeration
```

Use `=` for every option:

```text
{Camera:CloseUp|target=Nobita|distance=4.0|sideAngle=20}
```

Do not write `sideAngle:20` or `endTime:80`; the parser ignores those malformed options.

Common forms:

```text
@ParkScene
[Nobita]{SurprisedJump}怎么会这样？
{Animation:WaveHand|character=Shizuka}
{Position:Nobita|x=-1.2|y=0.01|z=1.0|face=Shizuka}
{Event:Move|character=Nobita|x=1|z=0|duration=1.2|relative=true}
{Camera:TwoShot|characterA=Nobita|characterB=Doraemon|distance=6.5|height=2.2}
{Transition:Fade|duration=0.8}
{Music:Play|name=room_theme|fadeIn=1.0|baseVolume=0.5|endTime=60}
```

Bare `{Action}` and `{Animation:Action|...}` names must be registered animations. A syntactically accepted unknown action is silently skipped by the runtime and is therefore invalid authoring.

## Asset Rules

- Run `story_tool.py catalog` for the target episode. It also lists animation source groups, supported props, registered/local music and SFX names, and procedural SFX types. Never infer availability from a class filename or another episode's script.
- Prefer the `common` animation group or the actor's own group. A character-specific animation may be globally registered yet assume anatomy or behavior belonging to a different character.
- Treat `Narrator` as a voice-only pseudo-speaker. It does not instantiate a visual character.
- Prefer `[Speaker]{Action}`. Targeted `{Character}{Action}` syntax has narrower ASCII-only parsing and is easier to misuse.
- Do not invent prop names. Props depend on scene/runtime implementations; confirm usage in `Storyboard.js` or a proven episode first.
- Use only cataloged music, SFX, procedural SFX, exaggerations, SceneDirector actions, and combat actions. Use an explicit validator allow flag only when another pipeline stage will really provide the named asset.
- Use a new scene alias only after the target `bootstrap.js` registers it.
- Preserve existing positions across adjacent entries. Use `{Event:Move|...}` when movement should be visible instead of teleporting by changing coordinates.

## Timing

Estimate the audible line before assigning the slot:

- Chinese dialogue: begin with roughly 4 characters per second.
- English dialogue: begin with roughly 2.5 words per second.
- Add 0.3-0.8 seconds for reaction or breath; add more for acting-heavy beats.
- Keep dialogue comfortably inside its entry. Re-run audio scheduling after TTS because actual voices differ.

## Visual Safety

- Keep speaking characters at least about 1 meter apart unless contact is intentional.
- Use `CloseUp distance >= 3.0` for standard characters and `>= 4.0` for wide characters such as Doraemon.
- Use `OverShoulder distance >= 4.5` and `TwoShot distance >= 6.0`.
- Avoid moving cameras through characters, walls, furniture, trees, or props.
- In `RoomScene`, favor the open area around `z >= -0.5`; furniture occupies deeper negative z positions.

## Known Reference Caveat

`dula-story/episodes/doraemon_stone_hat` demonstrates the full pipeline and the `NobitaRoom` alias, but do not copy it verbatim. Its current story includes unregistered legacy names such as `JumpForJoy`, `ShowTears`, and `ThumbsUp`, plus a nonnumeric `z=Nobita`. Run the current catalog and validator instead.

## Verification Order

1. Run `story_tool.py validate` until it returns zero.
2. Check `bootstrap.js` with `node --check`.
3. Run `dula-inspect-team` for repository-level static inspection.
4. Generate audio and correct timing overruns.
5. Run `dula-verify`, inspect every important shot, then render.
