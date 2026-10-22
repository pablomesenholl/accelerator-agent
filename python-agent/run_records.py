"""Workspace-local run summaries and safe error descriptions."""
from datetime import datetime, timezone
import asyncio
import json
import os
import re
import time
import uuid

RUN_DIRECTORY = '.agent-runs'


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def diagnostic_message(exc):
    """Sanitize errors even when no writable workspace could be established."""
    message = re.sub(r'https?://[^\s\'"<>]+', '[URL REDACTED]', str(exc))
    secrets = [value for name, value in os.environ.items() if value and
               name.endswith(('_API_KEY', '_TOKEN', '_SECRET', '_API_BASE'))]
    for secret in sorted(secrets, key=len, reverse=True):
        message = message.replace(secret, '[REDACTED]')
    return message or type(exc).__name__


class RunRecord:
    def __init__(self, files, **options):
        self.files = files
        self.started = time.monotonic()
        self.secrets = [value for name, value in os.environ.items() if value and
                        (name.endswith(('_API_KEY', '_TOKEN', '_SECRET', '_API_BASE')))]
        self.run_id = uuid.uuid4().hex
        self.relative_path = f'{RUN_DIRECTORY}/{self.run_id}.json'
        self.data = dict(schema_version=1, run_id=self.run_id, status='running',
                         stage='startup', started_at=utc_now(), finished_at=None,
                         elapsed_seconds=None, configuration=None, model=None,
                         session_id=None, model_requests=0, tool_calls=0,
                         tool_error_count=0, model_usage=[], error=None,
                         cleanup_errors=[], **options)
        self.save()

    @property
    def path(self):
        return self.files.root / self.relative_path

    def redact(self, value):
        if isinstance(value, str):
            for secret in sorted(self.secrets, key=len, reverse=True):
                value = value.replace(secret, '[REDACTED]')
            return value
        if isinstance(value, dict):
            return {key: self.redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        return value

    def error(self, exc, stage):
        name = type(exc).__name__
        if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt)):
            category = 'cancelled'
        elif isinstance(exc, TimeoutError) or name in {'Timeout', 'ReadTimeout', 'ConnectTimeout'}:
            category = 'timeout'
        elif name == 'RepeatedToolCallError':
            category = 'tool_loop'
        elif name == 'LlmCallsLimitExceededError':
            category = 'request_limit'
        elif isinstance(exc, ConnectionError) or name == 'APIConnectionError':
            category = 'connection'
        elif name in {'AuthenticationError', 'PermissionDeniedError'}:
            category = 'authentication'
        elif name == 'RateLimitError':
            category = 'rate_limit'
        elif stage in {'configuration', 'task_input', 'startup', 'session', 'cleanup', 'recording'}:
            category = stage
        else:
            category = 'execution'
        # Provider exceptions can contain request URLs; keep those out of diagnostics.
        return self.redact(dict(type=name, category=category, stage=stage,
                                message=diagnostic_message(exc)))

    def save(self):
        target = self.files._path(self.relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.files._path(f'{RUN_DIRECTORY}/{self.run_id}.tmp')
        created = False
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                created = True
                json.dump(self.redact(self.data), stream, indent=2, ensure_ascii=False)
                stream.write('\n')
            temporary.replace(target)
        finally:
            if created:
                temporary.unlink(missing_ok=True)

    def finish(self, error=None):
        self.data.update(status=('cancelled' if error and error['category'] == 'cancelled'
                                 else 'failed' if error else 'completed'),
                         error=error, finished_at=utc_now(),
                         elapsed_seconds=round(time.monotonic() - self.started, 3))
        self.save()
