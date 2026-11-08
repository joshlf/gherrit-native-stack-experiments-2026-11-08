#!/usr/bin/env python3
"""Fixture hook: capture explicit inputs, then perform one separate local push."""
import json, os, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]
CONFIG = json.loads((ROOT / 'fixture.json').read_text())
ALLOWLIST = [
    'GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_PREFIX',
    'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE',
    'GIT_PROTOCOL', 'GIT_PUSH_OPTION_COUNT', 'GIT_PUSH_OPTION_0', 'GIT_PUSH_OPTION_1',
    'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_NOSYSTEM', 'GIT_TERMINAL_PROMPT',
]
record = {'argv': sys.argv[1:], 'stdin': sys.stdin.read(), 'cwd': os.getcwd(),
          'standard_git_environment_allowlist': ALLOWLIST,
          'environment': {key: os.environ.get(key) for key in ALLOWLIST}}
path = ROOT / 'evidence/hook-active.json'
path.write_text(json.dumps(record, indent=2) + '\n')
command = [CONFIG['git_binary'], '-c', 'core.hooksPath=/dev/null', 'push',
           '--no-verify', 'inner', 'refs/heads/source:refs/heads/inner-publication']
result = subprocess.run(command, text=True, capture_output=True)
record['inner_push'] = {'command': command, 'exit': result.returncode,
                        'stdout': result.stdout, 'stderr': result.stderr}
path.write_text(json.dumps(record, indent=2) + '\n')
sys.exit(result.returncode)
