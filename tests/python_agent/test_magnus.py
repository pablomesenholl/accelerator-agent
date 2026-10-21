"""Offline Magnus adapter tests: fake backend only, no Qwen or OPALX."""
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'python-agent'))
from tools.magnus_tools import MagnusTools, _extract_bundle, JOB_DIRECTORY
from tools.file_tools import WorkspaceFiles
from google.adk.tools.function_tool import FunctionTool
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from agent import _ToolLoopGuard, RepeatedToolCallError, run_task

SCHEMA = [{'key': 'simulation', 'type': 'file_secret'},
          {'key': 'input_file', 'type': 'text'}, {'key': 'output', 'type': 'text'}]


class FakeBackend:
    def __init__(self):
        self.calls = []
        self.launch_error = False
        self.status = 'Success'
        self.result = {'success': True, 'returncode': 0, 'input_file': 'lattice.in',
                       'output_secret': 'fake-secret', 'message': 'Completed'}
        self.downloads = 0

    def call(self, method, *args, **kwargs):
        self.calls.append((method, args, kwargs))
        if method == 'get_blueprint_schema':
            return SCHEMA
        if method == 'launch_blueprint':
            if self.launch_error:
                raise TimeoutError('Lost launch response')
            return 'job-123'
        if method == 'get_job':
            return {'status': self.status, 'action': 'DO NOT EXECUTE'}
        if method == 'get_job_result':
            return json.dumps(self.result)
        if method == 'get_job_logs':
            return {'logs': 'x' * 10000, 'page': 0, 'total_pages': 1}
        raise AssertionError(method)

    def download(self, secret, destination, scratch):
        self.downloads += 1
        destination.mkdir(parents=True)
        (destination / 'result.stat').write_text('example output')


class MagnusToolsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'workspace'
        (self.root / 'input').mkdir(parents=True)
        (self.root / 'input/lattice.in').write_text('unit test input, not a physical model')
        self.backend = FakeBackend()
        inspector = MagnusTools(self.root, backend=self.backend)
        info = await inspector.inspect_simulation_input('input', 'lattice.in')
        self.approval = {**info, 'status': 'PASS', 'checks': {
            'structure': 'PASS', 'specification': 'PASS', 'physics': 'PASS',
            'native_parser': 'SKIPPED_NOT_AVAILABLE'}}
        (self.root / 'validation.json').write_text(json.dumps(self.approval))
        self.tools = MagnusTools(self.root, True, 'validation.json', self.backend)

    async def submit(self):
        result = await self.tools.submit_opalx_simulation('input', 'lattice.in')
        self.assertNotIn('error', result, result)
        return result

    async def test_inspection_is_read_only_and_checks_schema(self):
        self.assertTrue((await self.tools.inspect_opalx_backend())['compatible'])
        self.assertFalse(any(c[0] == 'launch_blueprint' for c in self.backend.calls))
        with patch.object(self.backend, 'call', return_value=[]):
            self.assertFalse((await self.tools.inspect_opalx_backend())['compatible'])
        with patch.object(self.backend, 'call', side_effect=ConnectionError('offline')):
            self.assertIn('error', await self.tools.inspect_opalx_backend())

    async def test_submission_requires_enablement_and_matching_pass(self):
        disabled = MagnusTools(self.root, backend=self.backend)
        self.assertIn('error', await disabled.submit_opalx_simulation('input', 'lattice.in'))
        self.tools.approval['status'] = 'INCONCLUSIVE'
        self.assertIn('error', await self.tools.submit_opalx_simulation('input', 'lattice.in'))
        self.tools.approval['status'] = 'PASS'
        (self.root / 'input/lattice.in').write_text('modified after review')
        self.assertIn('error', await self.tools.submit_opalx_simulation('input', 'lattice.in'))
        self.assertFalse(any(c[0] == 'launch_blueprint' for c in self.backend.calls))

    async def test_missing_validation_layers_prevent_submission(self):
        for key in ('structure', 'specification', 'physics', 'native_parser'):
            with self.subTest(layer=key):
                value = self.tools.approval['checks'].pop(key)
                self.assertIn('error', await self.tools.submit_opalx_simulation('input', 'lattice.in'))
                self.tools.approval['checks'][key] = value

    async def test_report_is_snapshotted_before_model_changes(self):
        self.tools.approval['status'] = 'FAIL'
        (self.root / 'validation.json').write_text(json.dumps(self.approval))
        self.assertIn('error', await self.tools.submit_opalx_simulation('input', 'lattice.in'))

    async def test_submission_is_nonblocking_and_reuses_persisted_job(self):
        first = await self.submit()
        self.assertFalse(first['reused'])
        resumed = MagnusTools(self.root, True, 'validation.json', self.backend)
        second = await resumed.submit_opalx_simulation('input', 'lattice.in')
        self.assertTrue(second['reused'])
        self.assertEqual(first['job_id'], second['job_id'])
        launches = [c for c in self.backend.calls if c[0] == 'launch_blueprint']
        self.assertEqual(len(launches), 1)
        self.assertFalse(launches[0][2]['use_preference'])
        self.assertFalse(launches[0][2]['save_preference'])
        self.assertFalse(any(c[0] == 'get_job' for c in self.backend.calls))
        self.assertEqual(json.loads((self.root / first['record']).read_text())['state'], 'submitted')

    async def test_uncertain_submission_is_not_retried(self):
        self.backend.launch_error = True
        self.assertIn('error', await self.tools.submit_opalx_simulation('input', 'lattice.in'))
        self.assertIn('uncertain', (await self.tools.submit_opalx_simulation('input', 'lattice.in'))['error'])
        self.assertEqual(len([c for c in self.backend.calls if c[0] == 'launch_blueprint']), 1)

    async def test_paths_and_bundle_links_are_rejected_before_upload(self):
        outside = Path(self.temp.name) / 'private.in'
        outside.write_text('private')
        for source, main in [(str(outside), outside.name), ('../private.in', outside.name),
                             ('input', '../private.in'), ('input', str(outside)),
                             ('.', 'input/lattice.in'), ('input/lattice.in', 'wrong.in')]:
            with self.subTest(source=source, main=main):
                self.assertIn('error', await self.tools.inspect_simulation_input(source, main))
        (self.root / 'input/link').symlink_to(outside)
        self.assertIn('error', await self.tools.inspect_simulation_input('input', 'lattice.in'))
        (self.root / 'input/link').unlink()
        (self.root / 'input/hardlink').hardlink_to(outside)
        self.assertIn('error', await self.tools.inspect_simulation_input('input', 'lattice.in'))

    async def test_status_logs_and_download_reconnect_without_actions(self):
        await self.submit()
        resumed = MagnusTools(self.root, backend=self.backend)
        status = await resumed.get_opalx_job_status('job-123')
        self.assertTrue(status['simulation_success'])
        self.assertFalse(status['outputs_retrieved'])
        logs = await resumed.read_opalx_job_logs('job-123', max_chars=100)
        self.assertEqual(len(logs['logs']), 100)
        self.assertEqual(logs['next_start'], 100)
        self.assertIn('error', await resumed.read_opalx_job_logs('job-123', max_chars=7000))
        self.assertIn('error', await resumed.get_opalx_job_status('unknown-job'))
        result = await resumed.retrieve_opalx_outputs('job-123')
        self.assertTrue(result['outputs_retrieved'])
        self.assertTrue((self.root / result['output_path'] / 'result.stat').is_file())
        await resumed.retrieve_opalx_outputs('job-123')
        self.assertEqual(self.backend.downloads, 1)
        self.assertFalse(any(c[0] in ('get_job_action', 'run_blueprint') for c in self.backend.calls))

    async def test_failure_outputs_are_not_reported_as_success(self):
        await self.submit()
        self.backend.status = 'Failed'
        self.backend.result.update(success=False, returncode=1)
        result = await self.tools.retrieve_opalx_outputs('job-123')
        self.assertTrue(result['outputs_retrieved'])
        self.assertFalse(result['simulation_success'])

    async def test_running_missing_output_and_existing_destination(self):
        await self.submit()
        self.backend.status = 'Running'
        self.assertIn('error', await self.tools.retrieve_opalx_outputs('job-123'))
        self.backend.status = 'Success'
        self.backend.result.pop('output_secret')
        self.assertIn('error', await self.tools.retrieve_opalx_outputs('job-123'))
        self.backend.result['output_secret'] = 'fake'
        _, record = self.tools._record('job-123')
        (self.root / record['output']).mkdir(parents=True)
        self.assertIn('error', await self.tools.retrieve_opalx_outputs('job-123'))
        self.assertEqual(self.backend.downloads, 0)

    async def test_job_store_cannot_be_overwritten_by_agent_files(self):
        submitted = await self.submit()
        files = WorkspaceFiles(self.root, read_only_roots=(self.root / JOB_DIRECTORY,))
        self.assertIn('error', files.write_file(submitted['record'], 'forged'))

    async def test_read_only_polling_is_exempt_but_submission_is_not(self):
        guard = _ToolLoopGuard()
        status = FunctionTool(self.tools.get_opalx_job_status)
        for _ in range(5):
            guard.before_tool(status, {'job_id': 'job-123'}, None)
        submit = FunctionTool(self.tools.submit_opalx_simulation)
        for _ in range(2):
            guard.before_tool(submit, {'simulation': 'input', 'input_file': 'lattice.in'}, None)
        with self.assertRaises(RepeatedToolCallError):
            guard.before_tool(submit, {'simulation': 'input', 'input_file': 'lattice.in'}, None)

    async def test_adk_exposes_and_executes_magnus_tools_without_an_llm(self):
        sequence = [
            ('inspect_opalx_backend', {}),
            ('submit_opalx_simulation', {'simulation': 'input', 'input_file': 'lattice.in'}),
            ('get_opalx_job_status', {'job_id': 'job-123'}),
            ('read_opalx_job_logs', {'job_id': 'job-123'}),
            ('retrieve_opalx_outputs', {'job_id': 'job-123'}),
        ]

        class ExecutionModel(BaseLlm):
            model: str = 'offline-execution'

            async def generate_content_async(self, llm_request, stream=False):
                declarations = {decl.name for tool in llm_request.config.tools
                                for decl in tool.function_declarations or []}
                assert {name for name, _ in sequence} <= declarations
                instructions = llm_request.config.system_instruction
                assert 'Execution handoff (operator configuration)' in instructions
                assert '"submission_enabled": true' in instructions
                assert '"input_file": "lattice.in"' in instructions
                assert '"simulation": "input"' in instructions
                count = sum(bool(part.function_response) for content in llm_request.contents
                            for part in content.parts or [])
                if count < len(sequence):
                    name, args = sequence[count]
                    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
                else:
                    part = types.Part(text='Done')
                yield LlmResponse(content=types.Content(role='model', parts=[part]))

        with patch('agent.create_model', return_value=ExecutionModel()), \
                patch('agent.MagnusTools', return_value=self.tools):
            result = await run_task('Execute reviewed input', self.root, progress=False,
                                    enable_magnus=True, allow_simulation=True,
                                    validation_report='validation.json')
        self.assertEqual(result.response, 'Done')
        self.assertEqual(result.tool_calls, [name for name, _ in sequence])
        self.assertTrue(result.tool_results[-1]['response']['outputs_retrieved'])
        self.assertEqual(self.backend.downloads, 1)
        self.assertEqual(len([call for call in self.backend.calls if call[0] == 'launch_blueprint']), 1)


class OutputArchiveTest(unittest.TestCase):
    def test_links_traversal_and_absolute_paths_are_rejected(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/escape', tarfile.REGTYPE),
                           ('bundle/link', tarfile.SYMTYPE), ('bundle/hard', tarfile.LNKTYPE)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                archive = base / 'output.tar'
                with tarfile.open(archive, 'w') as stream:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = '../escape'
                    stream.addfile(member)
                (base / 'unpacked').mkdir()
                with self.assertRaises(ValueError):
                    _extract_bundle(archive, base / 'unpacked')

    def test_valid_bundle_is_extracted_inside_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            archive = base / 'output.tar'
            with tarfile.open(archive, 'w') as stream:
                member = tarfile.TarInfo('bundle/result.stat')
                member.size = 2
                stream.addfile(member, io.BytesIO(b'ok'))
            (base / 'unpacked').mkdir()
            root = _extract_bundle(archive, base / 'unpacked')
            self.assertEqual((root/'result.stat').read_text(), 'ok')


if __name__ == '__main__':
    unittest.main()
