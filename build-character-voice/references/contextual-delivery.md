# Contextual Character Delivery

Read this reference before compiling or manually tuning character speech.

## Decide Acting from Context

For each line, answer:

1. What does the speaker want from the other character?
2. What are they hiding or avoiding?
3. What changed in the previous beat?
4. What response must this line invite?
5. Does the camera show intimacy, public projection, distance, or physical effort?
6. Where is this character on the scene's emotional arc?

Treat punctuation and keywords as evidence, not the decision. “真的吗？” can be delighted, suspicious, teasing, frightened, or flat depending on the response and picture.

## Semantic Delivery Controls

Use these controls in `audio_direction.json`:

- `tone`: a semantic label such as `calm`, `teasing`, `playful_confident`, `worried`, or `command`.
- `energy`: performance activation from `0` to `1`.
- `pace`: a small factor around `1.0`.
- `volume`: a small factor around `1.0`.
- `pitchSemitones`: a small contour offset, not an identity transform.
- `emphasis`: `soft`, `normal`, or `strong`.
- `distance`: `intimate`, `near`, `medium`, or `far`.
- `space`: `dry`, `room`, `gym`, `outdoor`, or another semantic space.
- `pauseBeforeMs` and `pauseAfterMs`: dramatic timing; do not synthesize silence samples.
- `breath`: `natural`, `held`, `audible-inhale`, or `none`.

Safe defaults:

| Control | Normal range | Escalate only when |
| --- | --- | --- |
| `pace` | `0.90..1.10` | A stylized shout, panic, exhaustion, or slow narration requires it |
| `volume` | `0.85..1.12` | The character is physically distant or genuinely shouting |
| `pitchSemitones` | `-0.5..+0.5` | A brief expressive contour is clearly audible in reference |
| SOX presence/EQ | roughly `±2 dB` | The recording or spatial perspective needs correction |
| compression | light | Peaks prevent intelligibility or continuity |

## Native TTS vs Post Processing

Send these to native TTS:

- speaking rate and phrase timing
- modest pitch contour
- emphasis and volume
- punctuation and pauses
- pronunciation and locale

Send these to SOX/ffmpeg:

- high-pass and low-pass cleanup
- restrained warmth, presence, or brightness
- light compression and limiting
- distance filtering
- subtle room consistency

Do not send age, gender, or accent to SOX. A large pitch/formant shift changes identity and often creates the “older woman” or “unnaturally high boy” failure.

## SOX Discipline

Build per-line treatments from the reviewed director entry. Never choose a chain from dialogue text alone.

Good uses:

- slightly more compression/presence for a protest or call
- reduced brightness and volume for an intimate line
- modest low-pass and presence reduction for a distant speaker
- consistent cleanup across all lines from one voice

Bad uses:

- `female = +2st`, `child = +5st`, or similar identity presets
- reverb on every ellipsis
- chorus/flanger on a “cute” line
- independent speed changes in both TTS and SOX
- added breath or sob samples because the text contains “呜”

## Continuity

Review lines in scene order. Limit the difference between adjacent lines unless the story contains a real emotional turn. Keep a character's spectral identity stable even when energy changes.

For a playful basketball exchange:

- A quiet opening line can be near-neutral with natural space.
- A boast should gain confidence through pace and emphasis, not a higher voice.
- A protest can gain energy and compression without becoming shrill.
- A final teasing line should leave room after the punchline instead of adding a comic vocal effect.
