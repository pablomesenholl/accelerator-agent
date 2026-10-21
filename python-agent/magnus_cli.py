"""Use the Magnus adapter directly, without an LLM."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

from tools.magnus_tools import MagnusTools


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path('output/python-agent'))
    parser.add_argument('--allow-simulation', action='store_true')
    parser.add_argument('--validation-report')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('inspect')
    inputs = commands.add_parser('input')
    inputs.add_argument('simulation')
    inputs.add_argument('input_file')
    submit = commands.add_parser('submit')
    submit.add_argument('simulation')
    submit.add_argument('input_file')
    for name in ('status', 'logs', 'fetch'):
        command = commands.add_parser(name)
        command.add_argument('job_id')
        if name == 'logs':
            command.add_argument('--page', type=int, default=-1)
            command.add_argument('--start', type=int, default=0)
    args = parser.parse_args()
    if args.command == 'submit' and (not args.allow_simulation or not args.validation_report):
        parser.error('submit requires --allow-simulation and --validation-report')
    try:
        tools = MagnusTools(args.workspace, args.allow_simulation, args.validation_report)
        calls = {
            'inspect': lambda: tools.inspect_opalx_backend(),
            'input': lambda: tools.inspect_simulation_input(args.simulation, args.input_file),
            'submit': lambda: tools.submit_opalx_simulation(args.simulation, args.input_file),
            'status': lambda: tools.get_opalx_job_status(args.job_id),
            'logs': lambda: tools.read_opalx_job_logs(args.job_id, args.page, args.start),
            'fetch': lambda: tools.retrieve_opalx_outputs(args.job_id),
        }
        result = asyncio.run(calls[args.command]())
    except (Exception, KeyboardInterrupt) as exc:
        result = {'error': str(exc)}
    print(json.dumps(result, indent=2))
    return 1 if 'error' in result or result.get('compatible') is False else 0


if __name__ == '__main__':
    sys.exit(main())
