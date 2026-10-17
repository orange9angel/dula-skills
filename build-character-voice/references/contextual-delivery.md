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

Measure reply gaps from the final placed PCM, not only adjacent story windows.
In S1E4, two playful exchanges had about 2.81 and 3.00 seconds between a finished
line and its reply, despite short gaps between their authored windows. New acting
instructions alone did not change those holds. Review the preceding line, listener
reaction and answer as one exchange. A short response can enter sooner, while a
prop handover or an intentionally difficult answer may need its full pause.

For an isolated audition, shorten a hold at an existing camera cut only after the
visible action has completed; keep the selected score continuous across the edit.
If adopted into the episode, revise story timing and regenerate dependent cues,
audio, subtitles and lips. An editorial trial is not a new production timeline.
When words or delivery change, align visemes to the exact new PCM. Do not reuse
the old mouth timing or claim naturalness from alignment success alone.

Review lines in scene order. Limit the difference between adjacent lines unless the story contains a real emotional turn. Keep a character's spectral identity stable even when energy changes.

For a playful basketball exchange:

- A quiet opening line can be near-neutral with natural space.
- A boast should gain confidence through pace and emphasis, not a higher voice.
- A protest can gain energy and compression without becoming shrill.
- A final teasing line should leave room after the punchline instead of adding a comic vocal effect.

## Relationship Direction and Executable Controls

- A character can retain the same voice while the scene changes from danger to intimacy.
  Do not carry a combat or exhausted performance into a romantic conversation by default.
  Quiet speech should retain breath support, responsive inflection and a clear intention.
- For custom episode synthesizers, inspect the actual request builder. A reviewed plan's
  `energy`, `intent`, or `subtext` has no audible effect if never compiled into supported
  native controls. Put relationship and the line's intention in the provider's supported
  instruction field; include those fields and the request-schema version in cache keys.
- Rehearse a request and a teasing response at comparable loudness before regenerating
  the character. Keep short concern/surprise beats; warm direction is not uniform happiness.
- `scripts/listen_audio.py` can send supplied audio to the existing DashScope audio reviewer
  (`--prompt`, `--out`, `--env-dir`). Treat its observations as advisory: blinded comparisons
  can be inconsistent, and a whole-scene pass may miss one odd line. Retain the reviewed
  audio hash and distinguish model observation from human listening and user acceptance.
- After repeated feedback that a voice sounds weak, audition a different native actor.
  A voice designed as frail can resist cheerful direction. Compare a short positive
  acting instruction with the longer instruction; avoid endlessly adding negative
  adjectives. Reuse the exact selected audition audio when the production line matches,
  including its request and audio hashes, instead of silently drawing another take.
- Keep audio-review questions neutral. Leading questions can produce inconsistent,
  overly specific performance claims. The user's hearing overrides model approval;
  one favorable model comparison remains provisional casting, not artistic acceptance.

## Scene-specific replies instead of a uniform genre voice

- S1E4 user review rejected a heroine's explanation as deliberately performed rather
  than addressed to her worried classmate. Every line had inherited an instruction
  for a smiling romantic-comedy performance, including the difficult admission.
  A pleasing timbre and correct words did not establish a believable conversation.
- Replace that uniform instruction with a concise situation: who just spoke, what
  the character has observed, and what they want to communicate to that person.
  For a difficult answer, direct the observation and honest admission; avoid adding
  a list of voice-quality adjectives or requesting a smile through every beat.
- Compare the preceding line plus the complete reply, at comparable loudness and
  without score. Include a neutral same-actor take before assuming a new actor is
  required. Preserve the selected audition audio, then rebuild final PCM and lips.
  S1E4's revised takes passed content/timing checks and received a provisional model
  preference; naturalness remains pending user listening, not an established cure.
