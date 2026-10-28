# Audio Direction Contract

Use `config/audio_direction.json` as the reviewed creative handoff between the sound director and specialist workflows. Keep `script.story` authoritative for timing.

## Shape

```json
{
  "version": 1,
  "status": "reviewed",
  "sources": [
    {
      "path": "script.story",
      "sha256": "..."
    },
    {
      "path": "config/keyframe_timeline.json",
      "sha256": "..."
    }
  ],
  "policies": {
    "priority": ["dialogue", "storySfx", "ambience", "music"],
    "musicMode": "directed",
    "ambienceMode": "directed",
    "breath": "natural-tts-pauses-no-layered-breath"
  },
  "mix": {
    "dialogueVolume": 1.0,
    "bgmVolume": 0.3,
    "sfxVolume": 0.8,
    "useDucking": true,
    "duckDepth": 0.3
  },
  "characters": {
    "Speaker": {
      "voice": "zh-TW-YunJheNeural",
      "locale": "zh-TW",
      "identityPolicy": "preserve-native-voice"
    }
  },
  "dialogue": [],
  "ambience": [],
  "sfx": [],
  "music": [],
  "exclusions": []
}
```

## Dialogue Entry

```json
{
  "entry": 11,
  "character": "Boy",
  "text": "这样赢，才帅。",
  "startTime": 18.2,
  "endTime": 20.45,
  "scene": "AnimeBasketballSequenceScene",
  "shotIds": ["boy_boasts"],
  "previousEntry": 10,
  "nextEntry": 18,
  "intent": "装作轻松地耍帅",
  "subtext": "想给对方留下印象，不是真的挑衅",
  "delivery": {
    "tone": "playful_confident",
    "energy": 0.58,
    "pace": 1.03,
    "volume": 1.0,
    "pitchSemitones": 0.0,
    "emphasis": "normal",
    "distance": "medium",
    "space": "gym",
    "pauseBeforeMs": 80,
    "pauseAfterMs": 180,
    "breath": "natural"
  }
}
```

Use `pace`, `volume`, and `pitchSemitones` as small deltas around a character's selected native voice. Do not encode gender or age by shifting pitch/formants.

Recommended safe delivery range:

- `energy`: `0..1`
- `pace`: normally `0.90..1.10`
- `volume`: normally `0.85..1.12`
- `pitchSemitones`: normally `-0.5..+0.5`
- `pauseBeforeMs`, `pauseAfterMs`: `0..1200`
- `emphasis`: `soft`, `normal`, or `strong`
- `distance`: `intimate`, `near`, `medium`, or `far`
- `space`: a semantic room label such as `dry`, `room`, `gym`, or `outdoor`

## Ambience and SFX

Use ambience for continuous space and SFX for discrete events:

```json
{
  "id": "gym-roomtone",
  "entry": 1,
  "name": "gym_roomtone",
  "startTime": 0.0,
  "endTime": 30.0,
  "volume": 0.16,
  "role": "bed",
  "priority": "ambience"
}
```

```json
{
  "id": "entry-17-basketball-swishing",
  "entry": 17,
  "name": "basketball_swish",
  "startTime": 24.35,
  "volume": 0.95,
  "role": "event",
  "priority": "storySfx",
  "shotIds": ["rim_swish"]
}
```

Anchor to entry and shot IDs as well as resolved seconds. Keep source/license metadata beside downloaded or recorded assets.

## Music

```json
{
  "id": "duel-build",
  "mood": "tense_playful",
  "startTime": 12.0,
  "endTime": 19.5,
  "fadeIn": 0.5,
  "fadeOut": 0.8,
  "baseVolume": 0.3,
  "purpose": "raise anticipation, then leave the final play exposed"
}
```

Set `policies.musicMode`:

- `directed`: consume `music` as authoritative creative cues.
- `auto`: allow semantic scoring to propose cues.
- `none`: preserve intentional silence.

## Exclusions

Record a rejected or forbidden sound:

```json
{
  "id": "no-shot-whoosh",
  "scope": "final-shot",
  "sound": "projectile_whoosh",
  "reason": "The visible basketball motion and swish already communicate the action."
}
```

Specialists must not regenerate an excluded sound unless the user changes the direction.

## Cue-anchored pilot execution

`scripts/generate_seed_jobs.py EP --config RECIPE` executes source-fingerprinted
Seed TTS / Seed-Audio candidate jobs, preserving request parameters, output hash,
actual duration and a candidate status. It loads the established speech credential
without logging it. `disabled` retains rejected jobs without resubmitting them.
Always set `durationRange` for an ambience request: a 26-second quiet-theatre prompt
returned only 0.53 seconds despite API success; a clearer 10-second air-flow prompt
returned the requested length. An HTTP success or billed duration is insufficient.

`scripts/mix_cue_recipe.py EP --config RECIPE` resolves placements from the current
story-derived timeline, mixes existing generated assets into separate pilot stems,
and writes a 100 Hz envelope from the exact placed dialogue bus. It does not generate
waveforms or approve performances. `check_cue_mix.py` validates exported audio,
stem summation and Foley transients near authored events independently of dialogue.
Provisional casting and music excerpts remain explicitly provisional in the recipe.

## Precedence

Use this precedence:

```text
explicit user request
> reviewed audio_direction.json
> explicit script.story audio tags
> existing curated assets/cues
> specialist semantic inference
> procedural fallback
```

When the reviewed plan conflicts with `script.story`, update the story or cue materialization so the story remains the timing authority; do not silently create two timelines.

## Final-stem evidence after a serial rewrite

Keep dialogue, score, ambience and Foley/SFX as separate final stems. Check that their
sum agrees with the exported mix within PCM quantization error, and compare speech
with the other stems over genuinely voiced samples. A loud combined mix does not prove
speech is audible: music or impacts can supply that energy.

In the 2026-10-19 human-opponent rewrite, regenerated speech changed both attack-name
lengths and the release timing. Store a distinct release cue when the attack starts
after its spoken name; derive SFX and picture from that cue, and rebuild the lip envelope
from the exact voice PCM used in the final mix. Footsteps should come from actual landing
transitions, then receive a density/perspective review; sounding every small visible
movement is not the goal.

An audio model's observation is advisory. It can identify a boot sample that sounds like
a squeaking door or a wind bed that resembles thunder, but may also overstate certainty
or claim synchronization without seeing picture. Keep the audio hash, prompt, observation
and its limits. Recheck the corrected source and its mixed context rather than treating
transcription accuracy or a positive model verdict as artistic approval.

In a later opening-dialogue review, the audio model described sub-second pauses where
the measured schedule contained several seconds, and denied a music layer that was
present in the exported stem. Reject those claims as timing/mix evidence. Keep the raw
response with a reliability note; measure silence from the actual PCM and judge its
dramatic purpose against picture. Rephrasing the prompt until the model approves is
not a substitute for this check.
