"""Execute source-tracked Seed TTS / Seed-Audio jobs from an episode recipe.

This produces candidate assets, not a listening approval or a final mix.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
import sys

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "volc-voice-casting" / "scripts"))
from seedtts_say import synthesize
from seedaudio_gen import generate


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("episode", type=Path)
    ap.add_argument("--config", required=True)
    ap.add_argument("--only", help="Comma-separated job IDs")
    args = ap.parse_args()
    episode = args.episode.resolve()
    # Load the established speech credential without printing it.
    env_path = SKILLS.parent / "dula-story" / ".env.speech"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
            if raw.strip() and not raw.lstrip().startswith("#") and "=" in raw:
                k, v = raw.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
    recipe = json.loads((episode / args.config).read_text(encoding="utf-8-sig"))
    for source in recipe.get("sources", []):
        if digest(episode / source["path"]) != source["sha256"]:
            raise SystemExit(f"Stale source: {source['path']}")
    selected = set(args.only.split(",")) if args.only else None
    failures = []
    for job in recipe["jobs"]:
        if job.get("disabled"):
            continue
        if selected and job["id"] not in selected:
            continue
        out = (episode / job["output"]).resolve()
        if not out.is_relative_to(episode):
            raise SystemExit("Job output must stay inside the episode")
        source = out.with_suffix(out.suffix + ".source.json")
        request = {k: job[k] for k in ("provider", "text", "speaker", "delivery", "prompt") if k in job}
        tag = hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if out.exists() and source.exists():
            old = json.loads(source.read_text(encoding="utf-8"))
            if old.get("tag") == tag and old.get("sha256") == digest(out) and old.get("durationValid", True):
                print(f"cached {job['id']}", flush=True)
                continue
        try:
            billed = None
            if job["provider"] == "seedtts":
                synthesize(job["text"], job["speaker"], out, **job.get("delivery", {}))
            elif job["provider"] == "seed-audio":
                billed = generate(job["prompt"], out)
            else:
                raise ValueError("Unsupported provider")
            seconds = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                              "format=duration", "-of", "csv=p=0", str(out)], text=True).strip())
            bounds = job.get("durationRange", [0.05, 120])
            valid = bounds[0] <= seconds <= bounds[1]
            metadata = {"id": job["id"], **request, "tag": tag, "sha256": digest(out),
                        "billedSeconds": billed, "duration": seconds, "durationValid": valid,
                        "status": "generated_not_listening_approved" if valid else "rejected_duration"}
            source.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            if not valid:
                raise ValueError(f"Duration {seconds:.3f}s outside {bounds}; retained for evidence")
            print(f"generated {job['id']}: {out.stat().st_size} bytes", flush=True)
        except Exception as exc:
            failures.append(job["id"])
            print(f"FAILED {job['id']}: {exc}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
