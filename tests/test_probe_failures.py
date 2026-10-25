import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from pipeline.extract.probe import fetch, main
from pipeline.extract.official import unpack


class ProbeFailures(unittest.TestCase):
    def test_failure_report_names_actual_dependencies_without_invented_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'evidence.json'
            client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403)))
            with patch('pipeline.extract.probe.httpx.Client', return_value=client), patch('sys.argv', ['probe', '--output', str(output)]):
                self.assertEqual(main(), 1)
            result = json.loads(output.read_text())
            self.assertFalse(result['technical_probe_passed'])
            self.assertTrue(any('shufersal' in reason for reason in result['gate_blockers']))
            self.assertFalse(any('Human review' in reason for reason in result['gate_blockers']))

    def test_access_denials_and_rate_limits_are_not_retried(self):
        for status in (403, 429):
            audit = {'requests': 0}
            with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status))) as client:
                with self.assertRaises(httpx.HTTPStatusError):
                    fetch(client, 'https://example.test/file', audit)
            self.assertEqual(audit['requests'], 1)

    def test_timeout_retries_are_bounded(self):
        def timeout(request):
            raise httpx.ReadTimeout('fixture timeout', request=request)
        audit = {'requests': 0}
        with httpx.Client(transport=httpx.MockTransport(timeout)) as client, patch('pipeline.extract.probe.time.sleep'):
            with self.assertRaises(httpx.ReadTimeout):
                fetch(client, 'https://example.test/file', audit)
        self.assertEqual(audit['requests'], 2)

    def test_oversized_response_is_rejected(self):
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b'x' * 100))) as client:
            with patch('pipeline.extract.probe.MAX_BYTES', 32):
                with self.assertRaisesRegex(ValueError, 'byte ceiling'):
                    fetch(client, 'https://example.test/file', {'requests': 0})

    def test_gzip_expansion_is_bounded(self):
        compressed = gzip.compress(b'x' * 2048)
        with patch('pipeline.extract.official.MAX_BYTES', 1024):
            with self.assertRaisesRegex(ValueError, 'XML exceeds'):
                unpack(compressed)

    def test_xml_entities_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'entities'):
            unpack(b'<!DOCTYPE root [<!ENTITY x "test">]><root>&x;</root>')

if __name__ == '__main__':
    unittest.main()
