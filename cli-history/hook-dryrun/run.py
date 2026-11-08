#!/usr/bin/env python3
"""Compare dry-run and actual outer pushes with an independently publishing hook."""
import datetime, hashlib, json, os, pathlib, shutil, subprocess
ROOT = pathlib.Path(__file__).resolve().parent
E = ROOT / 'evidence'
REPO = ROOT / 'repo'
GIT = shutil.which('git')
ENV = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
ENV.update(GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0')

def dump(path, value): path.write_text(json.dumps(value, indent=2) + '\n')
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def run(label, args, cwd=REPO):
    command = [GIT, *args]
    with (ROOT / 'commands.jsonl').open('a') as out:
        out.write(json.dumps({'state': 'dispatch-intent', 'label': label, 'at': now(), 'cwd': str(cwd), 'command': command}) + '\n')
    result = subprocess.run(command, cwd=cwd, env=ENV, capture_output=True, text=True)
    (E / (label + '.stdout')).write_text(result.stdout)
    (E / (label + '.stderr')).write_text(result.stderr)
    dump(E / (label + '.json'), {'command': command, 'cwd': str(cwd), 'exit': result.returncode})
    with (ROOT / 'commands.jsonl').open('a') as out:
        out.write(json.dumps({'state': 'response-observed', 'label': label, 'at': now(), 'exit': result.returncode}) + '\n')
    assert result.returncode == 0, label + ': ' + result.stderr
    return result.stdout

def refs(label):
    state = {}
    for name, repo in [('source', REPO), ('outer', ROOT / 'outer.git'), ('inner', ROOT / 'inner.git')]:
        value = run(label + '-' + name + '-refs', ['for-each-ref', '--format=%(refname) %(objectname)'], cwd=repo)
        state[name] = dict(line.split() for line in value.splitlines())
    dump(E / (label + '-state.json'), state)
    return state

def main():
    assert not REPO.exists() and not (ROOT / 'outer.git').exists() and not (ROOT / 'inner.git').exists(), 'Use a fresh fixture; do not replay into retained sinks'
    empty = ROOT / 'empty-template'; empty.mkdir(exist_ok=True)
    version = run('git-version', ['--version'], cwd=ROOT).strip()
    dump(ROOT / 'fixture.json', {'git_binary': GIT, 'git_version': version, 'source_repo': str(REPO), 'outer_sink': str(ROOT/'outer.git'), 'inner_sink': str(ROOT/'inner.git'), 'environment_control': 'clear inherited GIT_* only in child processes; use no system/global config; no global files changed'})
    run('init-source', ['-c', 'core.hooksPath=/dev/null', 'init', '--template=' + str(empty), '-b', 'source', str(REPO)], cwd=ROOT)
    for name in ['outer', 'inner']:
        run('init-' + name, ['-c', 'core.hooksPath=/dev/null', 'init', '--template=' + str(empty), '--bare', str(ROOT/(name+'.git'))], cwd=ROOT)
        run('remote-' + name, ['remote', 'add', name, str(ROOT/(name+'.git'))])
    run('identity-name', ['config', '--local', 'user.name', 'Josh Liebow-Feeser'])
    run('identity-email', ['config', '--local', 'user.email', 'hello@joshlf.com'])
    (REPO / 'payload.txt').write_text('Synthetic fixture for outer dry-run and inner publication.\n')
    run('stage', ['add', 'payload.txt'])
    run('commit', ['-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', 'commit', '-m', "Record synthetic hook publication fixture\n\nAgent-authored-by: AI agent acting on joshlf's behalf"])
    sha = run('source-sha', ['rev-parse', 'HEAD']).strip()
    run('commit-metadata', ['show', '-s', '--format=fuller', 'HEAD'])
    hook = REPO / '.git/hooks/pre-push'
    hook.parent.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / 'pre-push.py', hook); hook.chmod(0o755)
    run('fixture-hooks-path', ['config', '--local', 'core.hooksPath', str(hook.parent)])
    run('local-hooks-path-read', ['config', '--local', '--get', 'core.hooksPath'])
    initial = refs('before-dry-run')
    assert initial == {'source': {'refs/heads/source': sha}, 'outer': {}, 'inner': {}}
    refspec = 'refs/heads/source:refs/heads/outer-publication'
    run('outer-dry-run', ['push', '--porcelain', '--dry-run', 'outer', refspec])
    (E / 'hook-active.json').rename(E / 'dry-run-hook.json')
    dry_state = refs('after-dry-run')
    assert dry_state['outer'] == {} and dry_state['inner'] == {'refs/heads/inner-publication': sha}
    run('reset-inner-sink', ['update-ref', '-d', 'refs/heads/inner-publication', sha], cwd=ROOT/'inner.git')
    run('reset-inner-tracking', ['update-ref', '-d', 'refs/remotes/inner/inner-publication', sha])
    actual_initial = refs('before-actual')
    assert actual_initial == initial
    run('outer-actual', ['push', '--porcelain', 'outer', refspec])
    (E / 'hook-active.json').rename(E / 'actual-hook.json')
    actual_state = refs('after-actual')
    assert actual_state['outer'] == {'refs/heads/outer-publication': sha}
    assert actual_state['inner'] == {'refs/heads/inner-publication': sha}
    dry = json.loads((E/'dry-run-hook.json').read_text())
    actual = json.loads((E/'actual-hook.json').read_text())
    compared = ['argv', 'stdin', 'cwd', 'standard_git_environment_allowlist', 'environment']
    assert {k:dry[k] for k in compared} == {k:actual[k] for k in compared}
    assert dry['inner_push']['exit'] == actual['inner_push']['exit'] == 0
    expected = f'refs/heads/source {sha} refs/heads/outer-publication ' + '0'*40 + '\n'
    assert dry['stdin'] == actual['stdin'] == expected
    run('final-clean-tree', ['diff', '--exit-code'])
    result = {'git_version': version, 'source_commit': sha, 'identical_initial_refs': initial == actual_initial,
              'dry_run_invoked_hook': True, 'dry_run_inner_publication': dry_state['inner'], 'dry_run_outer_refs': dry_state['outer'],
              'actual_inner_publication': actual_state['inner'], 'actual_outer_publication': actual_state['outer'],
              'captured_hook_inputs_equal': True, 'captured_input_fields': compared,
              'environment_allowlist': dry['standard_git_environment_allowlist'], 'observed_dry_run_signal_in_captured_inputs': False,
              'hook_sha256': hashlib.sha256((ROOT/'pre-push.py').read_bytes()).hexdigest(),
              'claim_scope': 'This Git version, local transport, one changed ref, captured documented argv/stdin and explicitly allowlisted standard Git environment only. No claim that every detection mechanism is impossible.',
              'hosted_writes': 0, 'global_hook_or_config_writes': 0}
    dump(ROOT / 'RESULTS.json', result)
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
