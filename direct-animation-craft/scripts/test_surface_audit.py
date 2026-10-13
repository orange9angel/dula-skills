import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from surface_audit import audit_surfaces


class SurfaceAuditTests(unittest.TestCase):
    def test_empty_or_invalid_contract_cannot_pass(self):
        self.assertFalse(audit_surfaces(self.trace, {'pairs': []})['passed'])
        self.config['pairs'][0]['window'] = [1, 1]
        self.assertFalse(audit_surfaces(self.trace, self.config)['passed'])
        self.config['pairs'][0]['window'] = [0, .1]
        self.config['pairs'][0]['max_crossings'] = -1
        self.assertFalse(audit_surfaces(self.trace, self.config)['passed'])

    def test_surface_crossings_cannot_pass_on_zero_depth(self):
        config = {'pairs': [{'key': 'cloth', 'window': [0, 1/30], 'max_depth': 0,
                            'max_crossings': 0, 'method': 'triangles'}]}
        value = {'depth': 0, 'evaluated': 12, 'method': 'triangles', 'crossings': 2}
        trace = {'fps': 30, 'frames': [{'t': 0, 'surface': {'pairs': {'cloth': value}}}]}
        report = audit_surfaces(trace, config)
        self.assertFalse(report['passed'])
        self.assertEqual(report['events'][0]['worst_crossings'], 2)
        value['crossings'] = 0
        self.assertTrue(audit_surfaces(trace, config)['passed'])
        del value['crossings']
        self.assertTrue(audit_surfaces(trace, config)['coverage_errors'])

    def setUp(self):
        self.config = {'fps_min': 30, 'pairs': [
            {'key': 'arm:torso', 'window': [0, .1], 'max_depth': .005, 'method': 'actual'}]}
        self.trace = {'fps': 30, 'frames': [
            {'t': i / 30, 'surface': {'pairs': {'arm:torso': {
                'depth': 0, 'evaluated': 100, 'method': 'actual'}}}} for i in range(3)]}

    def test_clean_and_injected_intrusion(self):
        self.assertTrue(audit_surfaces(self.trace, self.config)['passed'])
        for f in self.trace['frames']:
            f['surface']['pairs']['arm:torso']['depth'] = .02
        report = audit_surfaces(self.trace, self.config)
        self.assertFalse(report['passed'])
        self.assertEqual(len(report['events']), 1)
        self.assertEqual(report['events'][0]['frames'], 3)

    def test_missing_middle_frame_or_pair_fails(self):
        for missing in ['frame', 'pair']:
            trace = copy.deepcopy(self.trace)
            if missing == 'frame':
                trace['frames'].pop(1)
            else:
                trace['frames'][1]['surface']['pairs'].clear()
            report = audit_surfaces(trace, self.config)
            self.assertFalse(report['passed'])
            self.assertTrue(report['coverage_errors'])

    def test_empty_nan_and_wrong_method_cannot_pass(self):
        for key, value in [('depth', float('nan')), ('evaluated', 0), ('method', 'wrong')]:
            trace = copy.deepcopy(self.trace)
            trace['frames'][1]['surface']['pairs']['arm:torso'][key] = value
            self.assertFalse(audit_surfaces(trace, self.config)['passed'])

    def test_input_fingerprint_detects_stale_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.js'
            path.write_bytes(b'original')
            self.config['require_build'] = True
            self.assertFalse(audit_surfaces(self.trace, self.config)['passed'])
            self.trace['build'] = {'inputs': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]}
            self.assertTrue(audit_surfaces(self.trace, self.config)['passed'])
            path.write_bytes(b'changed')
            self.assertFalse(audit_surfaces(self.trace, self.config)['passed'])


if __name__ == '__main__':
    unittest.main()
