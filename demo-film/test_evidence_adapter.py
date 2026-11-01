"""Offline replacement/safety contract tests; synthetic variants are never exported."""
import copy
import hashlib
import json
import unittest
import tempfile
from unittest.mock import patch
import build as film_build
from pathlib import Path
from evidence_adapter import EvidenceError, load, project, captures
from build import resolve

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / 'demo-manifest.json').read_text())
REPORT = json.loads((ROOT / MANIFEST['evidence']['source']).read_text())


class AdapterTests(unittest.TestCase):
    def adapt(self, report=None, featured=None):
        return project(report or REPORT, MANIFEST['evidence'], featured or MANIFEST['featured'], 'test-only')

    def test_contemporary_metrics_and_verdicts(self):
        data = load(ROOT, MANIFEST)
        self.assertEqual(data['original'], {'strict': 2, 'supported': 2, 'requests': 50})
        self.assertEqual(data['modified'], {'strict': 3, 'supported': 3, 'requests': 29})
        self.assertEqual(data['task_count'], 4)
        self.assertEqual(data['request_change_label'], '42% fewer in this recorded run')
        self.assertEqual(data['verdicts'], {'frozen': 'inconclusive', 'exploratory': 'not_supported'})
        self.assertIn('Improvement not established', data['qualification'])

    def test_source_hash_is_required(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest['evidence']['sha256'] = '0' * 64
        with self.assertRaisesRegex(EvidenceError, 'SHA256'):
            load(ROOT, manifest)

    def test_private_unknown_or_fixture_reports_rejected(self):
        for change in [{'audience': 'private'}, {'evidence_origin': {'provider': 'dev', 'presentation': 'recorded'}}, {'schema': 'unknown'}]:
            report = copy.deepcopy(REPORT)
            report.update(change)
            with self.assertRaises(EvidenceError):
                self.adapt(report)

    def test_missing_fields_do_not_become_zero_or_pass(self):
        report = copy.deepcopy(REPORT)
        del report['tasks'][0]['patched']['change-1'][0]['model_requests']
        report['tasks'][1]['placebo']['change-1'][0]['void'] = True
        data = self.adapt(report)
        self.assertIsNone(data['modified']['requests'])
        self.assertIsNone(data['original']['supported'])
        self.assertEqual(data['task_count'], 4)
        self.assertEqual(data['request_change_label'], 'Request change unavailable')

    def test_more_tasks_and_long_counts_derive_without_scene_changes(self):
        report = copy.deepcopy(REPORT)
        extra = copy.deepcopy(report['tasks'][0])
        extra['task_id'] = 'additional-task'
        report['tasks'].append(extra)
        for task in report['tasks']:
            task['placebo']['change-1'][0]['model_requests'] = 123456
            task['patched']['change-1'][0]['model_requests'] = 12345
        data = self.adapt(report)
        self.assertEqual(data['task_count'], 5)
        self.assertEqual(data['original']['requests'], 617280)
        narration = resolve('{evidence.task_count} tasks; {evidence.original.requests} requests', {'evidence': data})
        self.assertEqual(narration, '5 tasks; 617280 requests')

    def test_repeated_trials_not_silently_aggregated(self):
        report = copy.deepcopy(REPORT)
        report['tasks'][0]['patched']['change-1'] *= 2
        with self.assertRaisesRegex(EvidenceError, 'Repeated trials'):
            self.adapt(report)

    def test_switch_task_has_no_wrong_event_or_capture(self):
        featured = MANIFEST['featured'] | {'task_id': 'task-2'}
        data = project(REPORT, MANIFEST['evidence'], featured, MANIFEST['evidence']['sha256'])
        self.assertEqual(data['featured']['question'], REPORT['tasks'][1]['question'])
        self.assertEqual(data['featured']['events'], [])
        self.assertIsNone(data['featured']['focus'])
        manifest = MANIFEST | {'featured': featured}
        self.assertNotIn('storyboard', captures(ROOT, manifest, data))

    def test_explicit_event_selection_keeps_refs_order_and_focus(self):
        featured = MANIFEST['featured'] | {'event_refs': ['/storyboard/steps/0', '/storyboard/steps/7'], 'focus_ref': '/storyboard/steps/7'}
        data = self.adapt(featured=featured)
        self.assertEqual(data['featured']['event_count'], 2)
        self.assertEqual(data['featured']['focus']['text'], REPORT['storyboard']['steps'][7]['text'])
        self.assertEqual(data['featured']['focus']['ref'], '/storyboard/steps/7')
        for refs in [['/storyboard/steps/99'], ['/storyboard/steps/1', '/storyboard/steps/0']]:
            with self.assertRaises(EvidenceError):
                self.adapt(featured=featured | {'event_refs': refs})

    def test_new_source_drops_all_old_captures(self):
        self.assertEqual(captures(ROOT, MANIFEST, self.adapt()), {})

    def test_no_unselected_fields_exported(self):
        report = copy.deepcopy(REPORT)
        report['raw_trace'] = 'SECRET_SENTINEL'
        report['tasks'][0]['private_truth'] = 'SECRET_SENTINEL'
        report['storyboard']['steps'][0]['credentials'] = 'SECRET_SENTINEL'
        data = self.adapt(report)
        serialized = json.dumps(data)
        self.assertNotIn('SECRET_SENTINEL', serialized)
        self.assertNotIn('observations', data)
        self.assertNotIn('baseline', serialized)
        self.assertIn('/tasks/0/placebo/change-1/0', serialized)

    def test_source_is_read_only(self):
        source = ROOT / MANIFEST['evidence']['source']
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        load(ROOT, MANIFEST)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)

    def test_manifest_task_copy_order_and_visibility_without_scene_edits(self):
        manifest = copy.deepcopy(MANIFEST)
        manifest['featured']['task_id'] = 'task-2'
        manifest.pop('captures')
        manifest['scenes'][2]['headline'] = ['Inspect a different task.']
        manifest['scenes'][0]['visible'] = False
        manifest['scenes'] = list(reversed(manifest['scenes']))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'demo-film'
            root.mkdir()
            raw = json.dumps(REPORT).encode()
            (root / 'public-report.json').write_bytes(raw)
            manifest['evidence']['source'] = 'public-report.json'
            manifest['evidence']['sha256'] = hashlib.sha256(raw).hexdigest()
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest))
            with patch.object(film_build, 'ROOT', root):
                payload = film_build.build(path)
            self.assertEqual(payload['evidence']['featured']['task_id'], 'task-2')
            self.assertEqual(payload['evidence']['featured']['events'], [])
            self.assertEqual(payload['scenes'][0]['id'], '06-vision')
            self.assertFalse((root / 'frames/01-hook.html').exists())
            self.assertIn('Inspect a different task.', (root / 'frames/03-behavior.html').read_text())
            self.assertNotIn('Missing scroll index used', (root / 'generated/narration.txt').read_text())

    def test_explicit_same_schema_report_replacement(self):
        report = copy.deepcopy(REPORT)
        report['run']['id'] = 'test-only-replacement'
        report['tasks'] = report['tasks'][:2]
        report['demo_case']['label'] = 'Test-only alternate report'
        manifest = copy.deepcopy(MANIFEST)
        manifest['evidence']['run_id'] = report['run']['id']
        manifest.pop('captures')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'demo-film'
            root.mkdir()
            raw = json.dumps(report).encode()
            (root / 'alternate.json').write_bytes(raw)
            manifest['evidence']['source'] = 'alternate.json'
            manifest['evidence']['sha256'] = hashlib.sha256(raw).hexdigest()
            path = root / 'manifest.json'
            path.write_text(json.dumps(manifest))
            with patch.object(film_build, 'ROOT', root):
                payload = film_build.build(path)
            self.assertEqual(payload['evidence']['task_count'], 2)
            self.assertEqual(payload['evidence']['original']['requests'], 24)
            self.assertEqual(payload['evidence']['modified']['requests'], 17)
            self.assertEqual(payload['captures'], {})
            self.assertIn('24 to 17', (root / 'generated/narration.txt').read_text())

    def test_missing_optional_metadata_is_conservative(self):
        report = copy.deepcopy(REPORT)
        del report['evaluation']['exploratory']
        del report['demo_case']
        data = self.adapt(report)
        self.assertIsNone(data['verdicts']['exploratory'])
        self.assertEqual(data['label'], 'Recorded evaluation')
        self.assertEqual(resolve('{evidence.verdicts.exploratory}', {'evidence': data}), 'unavailable')


if __name__ == '__main__':
    unittest.main()
