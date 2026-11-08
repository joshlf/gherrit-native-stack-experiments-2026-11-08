#!/usr/bin/env python3
"""Run isolated, journaled gh-stack CLI and history-surface experiments."""
import datetime, hashlib, json, os, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent
REPO = 'joshlf/gherrit-native-stack-experiments-2026-11-08'
URL = 'https://github.com/' + REPO
CLONE = ROOT / 'checkout'
BIN = ROOT / 'bin/darwin-arm64'
EVIDENCE = ROOT / 'evidence'
JOURNAL = ROOT / 'journal.jsonl'
DISCLOSURE = "*Authored by an AI agent acting on joshlf's behalf.*"

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(path, value):
    pathlib.Path(path).write_text(json.dumps(value, indent=2) + '\n')
def event(value):
    with JOURNAL.open('a') as f: f.write(json.dumps({'time': now(), **value}) + '\n')
def run(name, command, cwd=CLONE, mutation=None, allowed=(0,), env=None):
    if mutation is not None:
        prior = [json.loads(x) for x in JOURNAL.read_text().splitlines()] if JOURNAL.exists() else []
        assert not any(x.get('name') == name and x.get('state') == 'dispatch-intent' for x in prior), 'Reconcile before reusing mutation identity: ' + name
        event({'name': name, 'state': 'dispatch-intent', 'command': command, 'intent': mutation})
    started = now()
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env={**os.environ, **(env or {})})
    (EVIDENCE / (name + '.stdout')).write_text(result.stdout)
    (EVIDENCE / (name + '.stderr')).write_text(result.stderr)
    dump(EVIDENCE / (name + '.json'), {'command': command, 'cwd': str(cwd), 'start': started, 'end': now(), 'exit': result.returncode})
    if mutation is not None: event({'name': name, 'state': 'response-observed', 'exit': result.returncode})
    print(name, 'exit', result.returncode, result.stdout[:250].strip(), result.stderr[:250].strip(), flush=True)
    assert result.returncode in allowed, name + ' failed; reconcile observed state before any retry'
    return result

def api(name, endpoint, method='GET', body=None, allowed=(0,)):
    command = ['gh', 'api', '-H', 'Accept: application/vnd.github+json', endpoint]
    if method != 'GET': command += ['--method', method]
    if body is not None:
        path = EVIDENCE / (name + '.request.json'); dump(path, body)
        command += ['--input', str(path)]
    return run(name, command, mutation={'endpoint': endpoint, 'method': method, 'body': body} if method != 'GET' else None, allowed=allowed)

def git(name, *args, mutation=None, allowed=(0,)):
    return run(name, ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false', *args], mutation=mutation, allowed=allowed)

def state(label, prs):
    git(label + '-remote-refs', 'ls-remote', 'origin', 'refs/heads/exp/cli/*', 'refs/tags/exp/cli/*')
    git(label + '-local-refs', 'show-ref')
    api(label + '-stacks', 'repos/' + REPO + '/stacks?per_page=100')
    for number in prs:
        api(label + '-pr-' + str(number), 'repos/' + REPO + '/pulls/' + str(number))

def create_pr(name, branch, base, title, draft=True):
    result = api(name, 'repos/' + REPO + '/pulls', 'POST', {'head': branch, 'base': base, 'title': title, 'body': 'Synthetic CLI experiment. Human-owned text sentinel: ' + name + '.\n\n' + DISCLOSURE, 'draft': draft})
    return json.loads(result.stdout)['number']

def commit(name, branch, parent, filename, content):
    git(name + '-checkout', 'checkout', '-b', branch, parent, mutation={'local_branch': branch, 'parent': parent})
    (CLONE / filename).write_text(content)
    git(name + '-add', 'add', filename, mutation={'index_paths': [filename]})
    message = name.replace('-', ' ').capitalize() + "\n\nAgent-authored-by: AI agent acting on joshlf's behalf"
    git(name + '-commit', 'commit', '-m', message, mutation={'commit': branch, 'paths': [filename]})
    return git(name + '-sha', 'rev-parse', 'HEAD').stdout.strip()

def fixtures():
    run('clone', ['git', '-c', 'core.hooksPath=/dev/null', 'clone', URL + '.git', str(CLONE)], cwd=ROOT, mutation={'local_clone': str(CLONE)})
    git('identity-name', 'config', '--local', 'user.name', 'Josh Liebow-Feeser', mutation={'local_config': 'user.name'})
    git('identity-email', 'config', '--local', 'user.email', 'hello@joshlf.com', mutation={'local_config': 'user.email'})
    git('disable-hooks', 'config', '--local', 'core.hooksPath', '/dev/null', mutation={'local_config': 'core.hooksPath'})
    commits = {}
    for name, parent, filename, content in [('a', 'main', 'cli-a.txt', 'authored A v1\n'), ('b', 'exp/cli/a', 'cli-b.txt', 'authored B\n'), ('c', 'main', 'cli-c.txt', 'authored C\n'), ('d', 'exp/cli/c', 'cli-d.txt', 'authored D\n')]:
        commits[name] = commit('seed-' + name, 'exp/cli/' + name, parent, filename, content)
    refs = ['refs/heads/exp/cli/' + n + ':refs/heads/exp/cli/' + n for n in 'abcd']
    git('push-fixtures', 'push', '--atomic', *['--force-with-lease=refs/heads/exp/cli/' + n + ':' for n in 'abcd'], 'origin', *refs, mutation={'remote': URL, 'refs': refs, 'expected': 'all absent'})
    prs = {}
    for name, base in [('a', 'main'), ('b', 'exp/cli/a'), ('c', 'main'), ('d', 'main')]:
        prs[name] = create_pr('create-pr-' + name, 'exp/cli/' + name, base, 'CLI experiment ' + name.upper(), draft=name != 'b')
    dump(ROOT / 'fixtures.json', {'commits': commits, 'prs': prs})
    state('seeded', list(prs.values()))

def link_correct():
    data = json.loads((ROOT / 'fixtures.json').read_text()); prs = data['prs']
    state('before-url-link', [prs['a'], prs['b']])
    run('url-link', [str(BIN), 'link', '--base', 'main', URL + '/pull/' + str(prs['a']), URL + '/pull/' + str(prs['b'])], mutation={'canonical_pr_urls': [prs['a'], prs['b']], 'options': ['--base', 'main'], 'expected': 'membership only; no refs, text, readiness, or bases change'})
    state('after-url-link', [prs['a'], prs['b']])

def link_wrong_base():
    prs = json.loads((ROOT / 'fixtures.json').read_text())['prs']
    state('before-base-link', [prs['c'], prs['d']])
    run('base-repair-link', [str(BIN), 'link', '--base', 'main', URL + '/pull/' + str(prs['c']), URL + '/pull/' + str(prs['d'])], mutation={'canonical_pr_urls': [prs['c'], prs['d']], 'expected': 'D base repaired, then membership created; text/readiness/refs preserved'})
    state('after-base-link', [prs['c'], prs['d']])

def numeric():
    prs = json.loads((ROOT / 'fixtures.json').read_text())['prs']
    sink = ROOT / 'numeric-push-sink.git'
    run('numeric-sink-init', ['git', 'init', '--bare', str(sink)], cwd=ROOT, mutation={'local_bare': str(sink)})
    git('numeric-sink-remote', 'remote', 'add', 'sink', str(sink), mutation={'local_remote': 'sink'})
    git('numeric-branch', 'branch', str(prs['a']), 'exp/cli/a', mutation={'local_branch': str(prs['a'])})
    run('numeric-sink-before', ['git', '--git-dir=' + str(sink), 'for-each-ref', '--format=%(refname) %(objectname)'], cwd=ROOT)
    run('canonical-url-with-sink', [str(BIN), 'link', '--remote', 'sink', '--base', 'main', URL + '/pull/' + str(prs['a']), URL + '/pull/' + str(prs['b'])], mutation={'expected': 'no local-sink push; native group already matches'})
    run('numeric-sink-after-url', ['git', '--git-dir=' + str(sink), 'for-each-ref', '--format=%(refname) %(objectname)'], cwd=ROOT)
    run('numeric-ambiguous-link', [str(BIN), 'link', '--remote', 'sink', '--base', 'main', str(prs['a']), str(prs['b'])], mutation={'expected': 'numeric local branch pushed to isolated local sink before same PR lookup; GitHub group already matches'})
    run('numeric-sink-after-numbers', ['git', '--git-dir=' + str(sink), 'for-each-ref', '--format=%(refname) %(objectname)'], cwd=ROOT)
    state('after-numeric-link', [prs['a'], prs['b']])

def subprocess_failure():
    prs = json.loads((ROOT / 'fixtures.json').read_text())['prs']
    sink = ROOT / 'numeric-push-sink.git'
    shim = ROOT / 'git-shim'; shim.mkdir(exist_ok=True)
    real_git = subprocess.check_output(['which', 'git'], text=True).strip()
    wrapper = shim / 'git'
    wrapper.write_text('#!/usr/bin/env python3\nimport os, subprocess, sys\nargs=sys.argv[1:]\nresult=subprocess.run([' + repr(real_git) + '] + args)\nif "push" in args and result.returncode == 0:\n    print("Injected: Git push succeeded; subprocess reports failure", file=sys.stderr)\n    sys.exit(75)\nsys.exit(result.returncode)\n')
    wrapper.chmod(0o755)
    git('lost-signal-numeric-branch', 'branch', str(prs['c']), 'exp/cli/c', mutation={'local_branch': str(prs['c'])})
    state('before-subprocess-failure', [prs['c'], prs['d']])
    run('lost-signal-sink-before', ['git', '--git-dir=' + str(sink), 'for-each-ref', '--format=%(refname) %(objectname)'], cwd=ROOT)
    run('subprocess-lost-success', [str(BIN), 'link', '--remote', 'sink', '--base', 'main', str(prs['c']), str(prs['d'])], mutation={'expected': 'local sink push succeeds but injected child failure aborts link before subsequent API writes'}, allowed=tuple(range(1, 256)), env={'PATH': str(shim) + os.pathsep + os.environ['PATH']})
    run('lost-signal-sink-after', ['git', '--git-dir=' + str(sink), 'for-each-ref', '--format=%(refname) %(objectname)'], cwd=ROOT)
    state('after-subprocess-failure', [prs['c'], prs['d']])

def reorder_failure():
    prs = json.loads((ROOT / 'fixtures.json').read_text())['prs']
    state('before-reorder-link', [prs['c'], prs['d']])
    run('reorder-link-rejected', [str(BIN), 'link', '--base', 'main', URL + '/pull/' + str(prs['d']), URL + '/pull/' + str(prs['c'])], mutation={'expected': 'reorder rejected; observe whether earlier base edits survive'}, allowed=tuple(range(256)))
    state('after-reorder-link', [prs['c'], prs['d']])

def reorder_open_failure():
    prs = json.loads((ROOT / 'fixtures.json').read_text())['prs']
    state('before-open-reorder-link', [prs['c'], prs['d']])
    run('open-reorder-link-rejected', [str(BIN), 'link', '--open', '--base', 'main', URL + '/pull/' + str(prs['d']), URL + '/pull/' + str(prs['c'])], mutation={'expected': 'reorder eventually rejected; --open readiness mutations may persist'}, allowed=tuple(range(256)))
    state('after-open-reorder-link', [prs['c'], prs['d']])

def broad_submit():
    prs = json.loads((ROOT / 'fixtures.json').read_text())['prs']
    git('broad-checkout', 'checkout', 'exp/cli/b', mutation={'checkout': 'exp/cli/b'})
    run('broad-init', [str(BIN), 'init', '--base', 'main', 'exp/cli/a', 'exp/cli/b'], mutation={'local_gh_stack_tracking': ['exp/cli/a', 'exp/cli/b']})
    (CLONE / 'cli-a.txt').write_text('authored A v2 via broader submit\n')
    git('broad-stage', 'add', 'cli-a.txt', mutation={'index_paths': ['cli-a.txt']})
    git('broad-commit', 'commit', '-m', "Record broader submit fixture\n\nAgent-authored-by: AI agent acting on joshlf's behalf", mutation={'commit': 'exp/cli/b'})
    git('broad-archive', 'tag', 'exp/cli/archive/submit-v2', 'HEAD', mutation={'local_tag': 'exp/cli/archive/submit-v2'})
    state('before-broad-submit', [prs['a'], prs['b']])
    run('broad-submit', [str(BIN), 'submit', '--auto'], mutation={'expected': 'branch-only atomic push, local archive tag remains absent remotely'}, env={'GIT_TRACE': str(EVIDENCE / 'broad-submit.git-trace')})
    state('after-broad-submit', [prs['a'], prs['b']])

def broad_submit_explicit_remote():
    prs = json.loads((ROOT / 'fixtures.json').read_text())['prs']
    state('broad-submit-reconciled-after-refusal', [prs['a'], prs['b']])
    event({'name': 'broad-submit-reconciliation', 'state': 'known-not-sent', 'evidence': 'initial submit refused ambiguous remotes before its fetch/push phase; refs and PRs reread before new explicit-remote invocation'})
    run('broad-submit-origin', [str(BIN), 'submit', '--auto', '--remote', 'origin'], mutation={'expected': 'branch-only atomic push, local archive tag remains absent remotely', 'explicit_remote': 'origin'}, env={'GIT_TRACE': str(EVIDENCE / 'broad-submit-origin.git-trace')})
    state('after-broad-submit', [prs['a'], prs['b']])

if __name__ == '__main__':
    EVIDENCE.mkdir(exist_ok=True)
    stages = {'fixtures': fixtures, 'link-correct': link_correct, 'link-wrong-base': link_wrong_base, 'numeric': numeric, 'subprocess-failure': subprocess_failure, 'reorder-failure': reorder_failure, 'reorder-open-failure': reorder_open_failure, 'broad-submit': broad_submit, 'broad-submit-explicit-remote': broad_submit_explicit_remote}
    stages[sys.argv[1]]()
