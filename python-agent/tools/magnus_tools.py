"""Explicit OPALX/Magnus operations; no shell commands or automatic actions."""
import asyncio
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
from datetime import datetime, timezone

from tools.file_tools import WorkspaceFiles
from tools.skill_tools import DEFAULT_SKILLS_ROOT

BLUEPRINT = 'opalx-simulation'
JOB_DIRECTORY = '.magnus-jobs'
TERMINAL = {'Success', 'Failed', 'Terminated'}


def _json_result(value):
    if isinstance(value, str):
        value = json.loads(value)
    if value is not None and not isinstance(value, dict):
        raise ValueError('Expected a structured Magnus result')
    return value


def _extract_bundle(archive: Path, staging: Path) -> Path:
    """Accept one directory of regular files; never extract links or traversal."""
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        for member in members:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or '..' in name.parts or '\\' in member.name
                    or not (member.isfile() or member.isdir())):
                raise ValueError('Unsafe member in simulation output archive')
        bundle.extractall(staging, members=members, filter='data')
    roots = list(staging.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError('Expected one simulation directory in output archive')
    return roots[0]


class MagnusBackend:
    """Small synchronous SDK adapter, called in worker threads by ADK tools."""
    def call(self, method: str, *args, **kwargs):
        from magnus import MagnusClient
        with MagnusClient() as client:
            return getattr(client, method)(*args, timeout=30, **kwargs)

    def download(self, secret: str, destination: Path, scratch: Path):
        from magnus import FileSecret, MagnusClient
        token = str(FileSecret(secret)).removeprefix('magnus-secret:')
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            temporary = Path(temporary)
            archive = temporary / 'payload.tar'
            with MagnusClient() as client:
                with client.http.stream('GET', f'{client.api_base}/files/download/{token}',
                                        timeout=60, follow_redirects=True) as response:
                    response.raise_for_status()
                    if response.headers.get('x-magnus-directory', '').lower() != 'true':
                        raise ValueError('Expected a directory output from OPALX')
                    with archive.open('wb') as stream:
                        for chunk in response.iter_bytes():
                            stream.write(chunk)
            unpacked = temporary / 'unpacked'
            unpacked.mkdir()
            source = _extract_bundle(archive, unpacked)
            # Destination is new and checked by the caller. No overwrite or action execution.
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)


class MagnusTools:
    def __init__(self, workspace: Path, allow_simulation: bool = False,
                 validation_report: str | None = None, backend=None):
        self.files = WorkspaceFiles(workspace, read_only_roots=(DEFAULT_SKILLS_ROOT,))
        self.root = self.files.root
        self.backend = backend or MagnusBackend()
        self.allow_simulation = allow_simulation
        # Snapshot operator evidence before the model can write any files.
        self.approval = None
        if validation_report:
            self.approval = json.loads(self.files._path(validation_report).read_text())
            if not isinstance(self.approval, dict):
                raise ValueError('Validation report must be a JSON object')

    def _store(self) -> Path:
        path = self.files._path(JOB_DIRECTORY)
        path.mkdir(exist_ok=True)
        return path

    def _save(self, path: Path, record: dict):
        self.files._path(str(path.relative_to(self.root)))
        with tempfile.NamedTemporaryFile(mode='w', dir=self._store(), delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(record, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)

    def _input(self, simulation: str, input_file: str) -> dict:
        source = self.files._path(simulation)
        if source == self.root or source.is_relative_to(self.root / JOB_DIRECTORY):
            raise ValueError('Use a dedicated input file/directory, outside the job store')
        if not source.exists():
            raise ValueError('Simulation input does not exist')
        relative = Path(input_file)
        if relative.is_absolute() or '..' in relative.parts or not input_file:
            raise ValueError('input_file must be relative to the simulation input')
        main = source / relative if source.is_dir() else source
        if source.is_file() and relative != Path(source.name):
            raise ValueError('Single-file input_file must match the uploaded filename')
        main = self.files._path(str(main.relative_to(self.root)))
        if not main.is_file() or main.suffix != '.in':
            raise ValueError('Main input must be an existing .in file')
        paths = sorted(source.rglob('*')) if source.is_dir() else [source]
        digest = hashlib.sha256()
        digest.update(json.dumps(relative.as_posix()).encode() + b'\n')
        for path in paths:
            self.files._path(str(path.relative_to(self.root)))
            if path.is_dir():
                continue
            if not path.is_file():
                raise ValueError('Input bundles may contain only regular files/directories')
            file_digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    file_digest.update(chunk)
            name = str(path.relative_to(source) if source.is_dir() else path.name)
            digest.update(json.dumps([name, file_digest.hexdigest()]).encode() + b'\n')
        return {'simulation': source.relative_to(self.root).as_posix(),
                'input_file': relative.as_posix(), 'input_digest': digest.hexdigest()}

    def _record(self, job_id: str) -> tuple[Path, dict]:
        # Only jobs persisted in this workspace are accessible. No account-wide aliases.
        for path in self._store().glob('*.json'):
            self.files._path(str(path.relative_to(self.root)))
            record = json.loads(path.read_text())
            if record.get('job_id') == job_id and job_id:
                return path, record
        raise ValueError('Job ID is not recorded in this workspace')

    async def inspect_opalx_backend(self) -> dict:
        """Read the registered OPALX blueprint schema; never submit or register a job."""
        try:
            schema = await asyncio.to_thread(self.backend.call, 'get_blueprint_schema', BLUEPRINT)
            fields = {item['key']: item for item in schema}
            compatible = (fields.get('simulation', {}).get('type') == 'file_secret'
                          and fields.get('input_file', {}).get('type') == 'text'
                          and fields.get('output', {}).get('type') == 'text'
                          and not any(not item.get('is_optional') and item.get('default') is None
                                      and key not in {'simulation', 'input_file', 'output'}
                                      for key, item in fields.items()))
            return {'blueprint': BLUEPRINT, 'compatible': compatible, 'parameters': schema}
        except Exception as exc:
            return {'error': str(exc)}

    async def inspect_simulation_input(self, simulation: str, input_file: str) -> dict:
        """Check workspace paths and compute an input digest, without physics validation."""
        try:
            return await asyncio.to_thread(self._input, simulation, input_file)
        except Exception as exc:
            return {'error': str(exc)}

    async def submit_opalx_simulation(self, simulation: str, input_file: str) -> dict:
        """Submit a reviewed input once and return its persisted job ID without waiting.

        Requires operator-enabled execution and a matching PASS report captured at
        task start. An uncertain submission must be reconciled manually, not retried.
        """
        try:
            if not self.allow_simulation:
                raise ValueError('Submission disabled; operator must enable simulation')
            info = await asyncio.to_thread(self._input, simulation, input_file)
            approval = self.approval or {}
            if approval.get('status') != 'PASS' or any(approval.get(k) != v for k, v in info.items()):
                raise ValueError('Operator PASS report is missing or does not match input paths/digest')
            checks = approval.get('checks', {})
            if not isinstance(checks, dict) or any(checks.get(k) != 'PASS' for k in
                                                  ('structure', 'specification', 'physics')):
                raise ValueError('PASS report must include structure/specification/physics checks')
            if checks.get('native_parser') not in {'PASS', 'SKIPPED_NOT_AVAILABLE'}:
                raise ValueError('Report must state native_parser PASS or SKIPPED_NOT_AVAILABLE')
            identifier = hashlib.sha256(json.dumps(info, sort_keys=True).encode()).hexdigest()
            path = self._store() / f'{identifier}.json'
            if path.exists():
                self.files._path(str(path.relative_to(self.root)))
                existing = json.loads(path.read_text())
                if existing.get('job_id'):
                    return {'job_id': existing['job_id'], 'reused': True,
                            'record': str(path.relative_to(self.root))}
                raise ValueError('Submission pending/uncertain: inspect the job record and backend; do not resubmit')
            inspection = await self.inspect_opalx_backend()
            if not inspection.get('compatible'):
                raise ValueError(f'Registered blueprint is unavailable or incompatible: {inspection}')
            record = {**info, 'blueprint': BLUEPRINT, 'state': 'submitting',
                      'created_at': datetime.now(timezone.utc).isoformat(),
                      'output': f'magnus-results/{identifier}', 'validation': approval}
            # Exclusive reservation also prevents duplicate submission across processes.
            with path.open('x') as stream:
                json.dump(record, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())

            def launch():
                try:
                    job_id = self.backend.call('launch_blueprint', BLUEPRINT, args={
                        'simulation': str(self.root / info['simulation']),
                        'input_file': info['input_file'], 'output': str(self.root / record['output'])},
                        use_preference=False, save_preference=False)
                    if not isinstance(job_id, str) or not job_id:
                        raise ValueError('Backend returned no job ID')
                    record.update(job_id=job_id, state='submitted')
                    self._save(path, record)  # Persist in the worker even if the caller disconnects.
                    return {'job_id': job_id, 'record': str(path.relative_to(self.root)), 'reused': False}
                except Exception:
                    record['state'] = 'submission_unknown'
                    self._save(path, record)
                    raise
            return await asyncio.to_thread(launch)
        except Exception as exc:
            return {'error': str(exc)}

    async def get_opalx_job_status(self, job_id: str) -> dict:
        """Inspect a recorded job once; no submission, waiting loop, or action execution."""
        try:
            path, record = self._record(job_id)
            job = await asyncio.to_thread(self.backend.call, 'get_job', job_id)
            status = job.get('status', 'Unknown')
            result = None
            if status in TERMINAL:
                result = _json_result(await asyncio.to_thread(self.backend.call, 'get_job_result', job_id))
            record.update(state=status, result=result)
            self._save(path, record)
            return {'job_id': job_id, 'status': status, 'terminal': status in TERMINAL,
                    'simulation_success': bool(result and status == 'Success' and
                                               result.get('success') is True and result.get('returncode') == 0
                                               and result.get('input_file') == record['input_file']),
                    'input_file': record['input_file'],
                    'executed_input_file': (result or {}).get('input_file'),
                    'message': (result or {}).get('message'),
                    'returncode': (result or {}).get('returncode'), 'outputs_retrieved': record.get('retrieved', False)}
        except Exception as exc:
            return {'error': str(exc)}

    async def read_opalx_job_logs(self, job_id: str, page: int = -1,
                                 start: int = 0, max_chars: int = 4000) -> dict:
        """Read a bounded log slice; use explicit page/start values to continue."""
        try:
            self._record(job_id)
            if page < -1 or start < 0 or not 1 <= max_chars <= 6000:
                raise ValueError('Invalid page, start, or max_chars (1..6000)')
            data = await asyncio.to_thread(self.backend.call, 'get_job_logs', job_id, page=page)
            logs = data.get('logs', '')
            end = min(start + max_chars, len(logs))
            return {'job_id': job_id, 'page': data.get('page', page), 'logs': logs[start:end],
                    'next_start': end if end < len(logs) else None,
                    'total_pages': data.get('total_pages')}
        except Exception as exc:
            return {'error': str(exc)}

    async def retrieve_opalx_outputs(self, job_id: str) -> dict:
        """Download a terminal job's published directory into its fixed workspace destination.

        Failed OPALX jobs may have useful outputs. Never execute MAGNUS_ACTION.
        """
        try:
            status = await self.get_opalx_job_status(job_id)
            if 'error' in status or not status.get('terminal'):
                raise ValueError(status.get('error', 'Job has not finished'))
            path, record = self._record(job_id)
            target = self.files._path(record['output'])
            if record.get('retrieved'):
                if not target.is_dir():
                    raise ValueError('Previously retrieved outputs are missing')
                return {**status, 'output_path': record['output'], 'outputs_retrieved': True}
            secret = (record.get('result') or {}).get('output_secret')
            if not secret:
                raise ValueError('Job has no published output_secret; inspect logs/result')
            if target.exists():
                raise ValueError('Output destination exists; refusing to overwrite')
            await asyncio.to_thread(self.backend.download, secret, target, self._store())
            record['retrieved'] = True
            self._save(path, record)
            return {**status, 'output_path': record['output'], 'outputs_retrieved': True}
        except Exception as exc:
            return {'error': str(exc)}
