"""Test bookkeeping failure modes, not artistic judgement."""
import argparse
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

import review_record as review


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        source = self.root / "source.bin"
        source.write_bytes(b"source-v1")
        self.record = self.root / "review.json"
        args = argparse.Namespace(source=source, output=self.record, subjects=["hero"],
                                  window=[{"id": "move", "start": 1, "end": 3}])
        with contextlib.redirect_stdout(io.StringIO()):
            review.initialize(args)
        self.data = review.read_json(self.record)
        image = self.root / "evidence.bin"
        image.write_bytes(b"evidence-v1")
        self.ev = {"path": image.name, "sha256": review.digest(image), "window": "move",
                   "at": [1.0, 2.0, 3.0], "method": "ordered_frames"}

    def run_record(self, data):
        self.record.write_text(json.dumps(data), encoding="utf-8")
        return review.validate(self.record)

    def completed(self):
        data = copy.deepcopy(self.data)
        for check in data["checks"]:
            check.update(status="no_issue_observed", observation="Synthetic test observation",
                         evidence=[copy.deepcopy(self.ev)])
        data["reviewer_conclusion"] = "Synthetic bookkeeping test; no artistic inference."
        return data

    def test_initialization_is_pending(self):
        result, code = self.run_record(self.data)
        self.assertEqual(code, 2)
        self.assertEqual(len(result["pending_checks"]), 14)
        self.assertEqual(result["artistic_acceptance"], "not_computed")

    def test_complete_record_is_not_artistic_acceptance(self):
        result, code = self.run_record(self.completed())
        self.assertEqual(code, 0)
        self.assertTrue(result["coverage_complete"])
        self.assertEqual(result["artistic_acceptance"], "not_computed")

    def test_deleted_dimension_cannot_silently_complete(self):
        data = self.completed()
        data["checks"].pop()
        result, code = self.run_record(data)
        self.assertEqual(code, 2)
        self.assertEqual(len(result["pending_checks"]), 1)

    def test_unknown_remains_pending(self):
        data = self.completed()
        data["checks"][0].update(status="needs_evidence", next_action="Get visible head")
        result, code = self.run_record(data)
        self.assertEqual(code, 2)
        self.assertFalse(result["coverage_complete"])

    def test_source_change_invalidates_record(self):
        (self.root / "source.bin").write_bytes(b"source-v2")
        result, code = self.run_record(self.completed())
        self.assertEqual(code, 1)
        self.assertTrue(any("stale" in e for e in result["errors"]))

    def test_replaced_evidence_invalidates_record(self):
        (self.root / "evidence.bin").write_bytes(b"replacement")
        result, code = self.run_record(self.completed())
        self.assertEqual(code, 1)
        self.assertTrue(any("evidence changed" in e for e in result["errors"]))

    def test_times_outside_window_are_rejected(self):
        data = self.completed()
        data["checks"][0]["evidence"][0]["at"] = [4.0]
        result, code = self.run_record(data)
        self.assertEqual(code, 1)
        self.assertTrue(any("outside" in e for e in result["errors"]))

    def test_open_issue_can_be_documented_without_being_fixed(self):
        data = self.completed()
        data["checks"][0].update(status="finding", issue_ids=["I1"])
        data["issues"] = [{
            "id": "I1", "subject": "hero", "dimension": "identity",
            "origin": "self_found", "status": "open", "fact": "Synthetic fact",
            "impact": "Synthetic impact", "hypothesis": "Unknown",
            "next_action": "Investigate", "priority": "high", "evidence": [self.ev],
        }]
        result, code = self.run_record(data)
        self.assertEqual(code, 0)
        self.assertEqual(result["unresolved_issues"], ["I1"])
        data["issues"][0]["status"] = "fixed"
        result, code = self.run_record(data)
        self.assertEqual(code, 1)
        self.assertTrue(any("verification" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
