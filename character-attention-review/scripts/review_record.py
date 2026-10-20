"""Coverage bookkeeping only. No image inference, artistic scores, or remote calls."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

DIMENSIONS = Path(__file__).resolve().parents[1] / "references/attention-dimensions.json"
STATES = {"unreviewed", "finding", "no_issue_observed", "needs_evidence", "not_applicable"}
ISSUE_STATES = {"open", "in_progress", "fixed", "deferred", "disproven"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def relative(path, base):
    return Path(os.path.relpath(path.resolve(), base.resolve())).as_posix()


def present(value):
    return isinstance(value, str) and bool(value.strip())


def window(value):
    name, start, end = value.rsplit(":", 2)
    start, end = float(start), float(end)
    if not name or not all(math.isfinite(t) for t in (start, end)) or not 0 <= start < end:
        raise argparse.ArgumentTypeError("window must be name:start:end, 0 <= start < end")
    return {"id": name, "start": start, "end": end}


def initialize(args):
    source, output = args.source.resolve(), args.output.resolve()
    if not source.is_file():
        raise ValueError("Source file does not exist")
    if output.exists():
        raise ValueError("Record exists; use a new revision path")
    dimensions = read_json(DIMENSIONS)
    if len(set(args.subjects)) != len(args.subjects):
        raise ValueError("Duplicate subjects")
    if len({w["id"] for w in args.window}) != len(args.window):
        raise ValueError("Duplicate windows")
    data = {
        "schema_version": 1,
        "source": {"path": relative(source, output.parent), "sha256": digest(source)},
        "scope": {"subjects": args.subjects, "windows": args.window,
                  "accepted_properties": [], "limitations": ""},
        "checks": [
            {"subject": subject, "dimension": d["id"], "status": "unreviewed",
             "observation": "", "evidence": [], "issue_ids": [], "next_action": ""}
            for subject in args.subjects for d in dimensions
        ],
        "issues": [],
        "iterations": [],
        "misses": [],
        "reviewer_conclusion": "Not reviewed. Coverage completion is not artistic acceptance.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"created": str(output), "pending_checks": len(data["checks"])},
                     ensure_ascii=False))


def validate(record):
    data, base = read_json(record), record.resolve().parent
    errors, pending = [], []
    if data.get("schema_version") != 1:
        errors.append("Unsupported schema_version")
    source = data.get("source", {})
    path = base / source.get("path", "")
    if not path.is_file() or source.get("sha256") != digest(path):
        errors.append("Source missing or changed: review evidence is stale")
    scope = data.get("scope", {})
    subjects = scope.get("subjects", [])
    windows = scope.get("windows", [])
    if not subjects or len(set(subjects)) != len(subjects):
        errors.append("Subjects missing or duplicated")
    window_map = {}
    for w in windows:
        try:
            valid = (present(w["id"]) and
                     all(isinstance(w[k], (int, float)) and math.isfinite(w[k])
                         for k in ("start", "end")) and 0 <= w["start"] < w["end"])
            if not valid or w["id"] in window_map:
                raise ValueError()
            window_map[w["id"]] = w
        except (KeyError, TypeError, ValueError):
            errors.append("Invalid or duplicate window")
    if not window_map:
        errors.append("No valid review windows")
    dimensions = {d["id"] for d in read_json(DIMENSIONS)}
    expected = {(subject, dim) for subject in subjects for dim in dimensions}
    seen = set()

    def evidence(items, context):
        if not isinstance(items, list) or not items:
            errors.append(context + ": missing evidence")
            return
        for ev in items:
            if not isinstance(ev, dict):
                errors.append(context + ": invalid evidence")
                continue
            artifact = base / ev.get("path", "")
            if not artifact.is_file():
                errors.append(context + ": evidence file missing")
            elif ev.get("sha256") != digest(artifact):
                errors.append(context + ": evidence changed or has no fingerprint")
            if ev.get("method") not in {"still", "ordered_frames", "realtime", "slow_motion",
                                        "audio_listening", "audiovisual"}:
                errors.append(context + ": specify actual viewing method")
            w, times = window_map.get(ev.get("window")), ev.get("at", [])
            if not w or not isinstance(times, list) or not times:
                errors.append(context + ": missing window/times")
            elif any(not isinstance(t, (int, float)) or not math.isfinite(t)
                     or not w["start"] <= t <= w["end"] for t in times):
                errors.append(context + ": evidence times outside declared window")

    issues = {}
    for issue in data.get("issues", []):
        iid = issue.get("id")
        if not present(iid) or iid in issues:
            errors.append("Missing or duplicate issue id")
            continue
        issues[iid] = issue
        if (issue.get("subject"), issue.get("dimension")) not in expected:
            errors.append(iid + ": issue subject/dimension outside scope")
        if issue.get("origin") not in {"user_reported", "self_found", "retrospective"}:
            errors.append(iid + ": invalid origin")
        if issue.get("status") not in ISSUE_STATES:
            errors.append(iid + ": invalid issue status")
        for key in ("fact", "impact", "hypothesis", "next_action", "priority"):
            if not present(issue.get(key)):
                errors.append(iid + ": missing " + key)
        evidence(issue.get("evidence"), iid)
        if issue.get("status") in {"fixed", "disproven"}:
            if not present(issue.get("result")):
                errors.append(iid + ": closed issue needs observed result")
            evidence(issue.get("verification"), iid + " verification")
            if issue.get("status") == "fixed" and not present(issue.get("change")):
                errors.append(iid + ": fixed issue needs actual change")
    for check in data.get("checks", []):
        key = (check.get("subject"), check.get("dimension"))
        context = "/".join(str(s) for s in key)
        if key not in expected or key in seen:
            errors.append(context + ": unexpected or duplicate check")
        seen.add(key)
        status = check.get("status")
        if status not in STATES:
            errors.append(context + ": invalid status")
        if status in {"unreviewed", "needs_evidence"}:
            pending.append(context)
        if status != "unreviewed" and not present(check.get("observation")):
            errors.append(context + ": missing observation or applicability reason")
        if status in {"finding", "no_issue_observed"}:
            evidence(check.get("evidence"), context)
        if status == "needs_evidence" and not present(check.get("next_action")):
            errors.append(context + ": missing evidence recovery action")
        linked = check.get("issue_ids", [])
        if status == "finding" and not linked:
            errors.append(context + ": finding has no issue")
        for iid in linked:
            if iid not in issues or (issues[iid].get("subject"), issues[iid].get("dimension")) != key:
                errors.append(context + ": invalid issue link " + str(iid))
    pending.extend("/".join(key) for key in sorted(expected - seen))
    if not present(data.get("reviewer_conclusion")):
        errors.append("Missing reviewer conclusion")
    report = {
        "record_valid": not errors,
        "coverage_complete": not errors and not pending,
        "artistic_acceptance": "not_computed",
        "pending_checks": pending,
        "unresolved_issues": [iid for iid, issue in issues.items()
                              if issue.get("status") in {"open", "in_progress", "deferred"}],
        "errors": errors,
    }
    return report, 1 if errors else 2 if pending else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--source", type=Path, required=True)
    init.add_argument("--output", type=Path, required=True)
    init.add_argument("--subjects", nargs="+", required=True)
    init.add_argument("--window", type=window, action="append", required=True)
    check = sub.add_parser("check")
    check.add_argument("record", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize(args)
            return 0
        result, code = validate(args.record)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return code
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"record_valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
