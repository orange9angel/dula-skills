# Provider adapters

Treat the compiled generation request as the stable interface. Adapt provider syntax without weakening continuity constraints.

## Capability map

Determine these capabilities from the active model and tool:

| Capability | Meaning | Continuity use |
|---|---|---|
| `referenceImages` | Accept one image alongside text | Preserve canonical identity |
| `multiImageReference` | Accept multiple labeled images | Combine identity, setting, style, and prior-frame state |
| `sequentialGroup` | Return an ordered, related sequence in one task | Preserve latent scene and identity state across an action |
| `imageEdit` | Transform a supplied image | Repair or advance one approved frame |
| `seed` | Expose deterministic or semi-deterministic seed control | Reduce sampling variance; never treat as identity lock |
| `negativePrompt` | Separate negative constraint channel | Move compiled negatives into the provider field |
| `maskEdit` | Edit a selected region | Repair hands, faces, props, or background without replacing the frame |

Unknown is different from false. Test a capability before relying on it.

## Strategy order

Use the strongest available strategy:

1. sequential group + canonical references;
2. sequential group without references, after establishing a precise character sheet;
3. per-shot image edit with canonical references + nearest approved frame;
4. per-shot generation with canonical references and stable seed;
5. text-only generation with repeated hard locks.

Report lower confidence for each step down this list.

## Built-in image generation tools and Imagen

Use the available image generation/editing tool directly:

- Supply local canonical references when the tool accepts file paths.
- Include the smallest set of recent conversation images needed when a target reference has no local path.
- Ask for an ordered group in one request only if the tool exposes multi-output sequential generation.
- If it returns one image per request, compile and submit the per-shot fallback prompt.
- Include the canonical identity reference on every request; add the nearest accepted prior frame when multi-reference input is supported.
- Preserve the original image for local edits and state exactly which region may change.

Do not assume that “multiple outputs” means temporal sequence. Inspect ordering and continuity before accepting.

## Adding another provider

An adapter must:

1. read the compiled generation request;
2. resolve project-relative references without modifying them;
3. map only supported capabilities;
4. submit group-first when sequential output is real;
5. fall back only for missing or rejected shots;
6. save deterministic shot filenames;
7. append a sanitized run record;
8. avoid logging or persisting credentials and signed URLs;
9. support a no-network dry-run that exposes the mapped request shape;
10. leave review status as `generated`, never `accepted`.

Keep provider code out of `SKILL.md`. Keep credentials in environment variables or the provider's credential store.

## Prompt mapping

The compiled request separates:

- `group.prompt`: ordered sequence intent;
- `shots[].prompt`: isolated fallback intent;
- `references`: stable local reference paths;
- `negativeConstraints`: forbidden content;
- `provider.options`: non-secret provider settings.

Map a separate negative prompt field when available. Otherwise append the negative constraints once. Do not silently discard them.

If the provider has structured reference roles, map identity, style, setting, and continuity frames separately. Otherwise order input images from strongest to most local:

1. canonical identity;
2. stable scene/style;
3. nearest accepted continuity frame;
4. shot-specific detail reference.
