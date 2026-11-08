#!/usr/bin/env python3
"""Prototype exact history boundaries and independently owned PR comment effects."""
import json, pathlib, sys
import run as lab
ROOT, CLONE, EVIDENCE = lab.ROOT, lab.CLONE, lab.EVIDENCE
BINDING = ROOT / 'history-binding.json'
MARKER = '<!-- gherrit-history:v1 artifact=cli-history-2026-11-08 -->'

def data(): return json.loads(BINDING.read_text())
def save(value): lab.dump(BINDING, value)
def sha(ref): return lab.git('history-resolve-' + ref.replace('/', '-'), 'rev-parse', ref).stdout.strip()
def body(d, version):
    rows = []
    for n in range(1, version + 1):
        base, tip = d['v' + str(n)]['base'], d['v' + str(n)]['tip']
        rows.append(f'| v{n} | [{base[:12]}]({lab.URL}/commit/{base}) | [{tip[:12]}]({lab.URL}/commit/{tip}) | [Exact authored patch]({lab.URL}/compare/{base}...{tip}) |')
    result = MARKER + '\n## GHerrit submission history (prototype)\n\n'
    result += 'This comment is generated history. The PR title and description are human-owned.\n\n'
    result += '| Submission | Historical base | Historical tip | Patch |\n| --- | --- | --- | --- |\n' + '\n'.join(rows) + '\n'
    if version > 1:
        a, b = d['v1']['tip'], d['v2']['tip']
        result += f'\n[Tip-to-tip comparison]({lab.URL}/compare/{a}..{b}) includes parent drift. It is not an ancestry-independent “changes since review” patch. Open both exact patches above to compare the authored changes.\n'
    result += '\n' + lab.DISCLOSURE + '\n'
    return result

def create():
    base = sha('origin/main')
    lab.git('history-trunk-v1', 'branch', 'exp/cli/history/trunk', base, mutation={'local_branch': 'exp/cli/history/trunk'})
    tip = lab.commit('history-v1', 'exp/cli/history/head', base, 'history-change.txt', 'authored value = 1\n')
    for name, target in [('base-v1', base), ('tip-v1', tip)]:
        lab.git('history-tag-' + name, 'tag', 'exp/cli/history/' + name, target, mutation={'local_tag': 'exp/cli/history/' + name})
    specs = ['refs/heads/exp/cli/history/' + n + ':refs/heads/exp/cli/history/' + n for n in ['trunk', 'head']] + ['refs/tags/exp/cli/history/' + n + ':refs/tags/exp/cli/history/' + n for n in ['base-v1', 'tip-v1']]
    lab.git('history-push-v1', 'push', '--atomic', *['--force-with-lease=' + s.split(':')[1] + ':' for s in specs], 'origin', *specs, mutation={'all_absent': specs})
    pr = lab.create_pr('history-create-pr', 'exp/cli/history/head', 'exp/cli/history/trunk', 'History comment experiment', draft=False)
    d = {'pr': pr, 'marker': MARKER, 'v1': {'base': base, 'tip': tip}, 'comment_ids': [], 'status': 'before-comment'}
    save(d)
    response = lab.api('history-create-comment', f'repos/{lab.REPO}/issues/{pr}/comments', 'POST', {'body': body(d, 1)})
    c = json.loads(response.stdout)
    d.update({'current_comment_id': c['id'], 'current_comment_node_id': c['node_id'], 'comment_url': c['html_url'], 'status': 'attached-v1'}); d['comment_ids'].append(c['id']); save(d)
    lab.api('history-list-v1', f'repos/{lab.REPO}/issues/{pr}/comments?per_page=100')
    lab.state('history-after-v1', [pr])

def update():
    d = data(); old_base, old_tip = d['v1']['base'], d['v1']['tip']
    base = lab.commit('history-drift', 'exp/cli/history/parent-v2', old_base, 'history-trunk-drift.txt', 'unrelated parent progress\n')
    tip = lab.commit('history-v2', 'exp/cli/history/submission-v2', base, 'history-change.txt', 'authored value = 2\n')
    for name, target in [('base-v2', base), ('tip-v2', tip)]:
        lab.git('history-tag-' + name, 'tag', 'exp/cli/history/' + name, target, mutation={'local_tag': 'exp/cli/history/' + name})
    d['v2'] = {'base': base, 'tip': tip}; save(d)
    lab.api('history-human-body-edit', f'repos/{lab.REPO}/pulls/{d["pr"]}', 'PATCH', {'body': 'Human-owned sentinel edited independently of generated history.\n\n' + lab.DISCLOSURE})
    refs = [base + ':refs/heads/exp/cli/history/trunk', tip + ':refs/heads/exp/cli/history/head'] + ['refs/tags/exp/cli/history/' + n + ':refs/tags/exp/cli/history/' + n for n in ['base-v2', 'tip-v2']]
    leases = ['--force-with-lease=refs/heads/exp/cli/history/trunk:' + old_base, '--force-with-lease=refs/heads/exp/cli/history/head:' + old_tip] + ['--force-with-lease=refs/tags/exp/cli/history/' + n + ':' for n in ['base-v2', 'tip-v2']]
    lab.git('history-push-v2', 'push', '--atomic', *leases, 'origin', *refs, mutation={'refs': refs, 'leases': leases})
    lab.api('history-update-comment', f'repos/{lab.REPO}/issues/comments/{d["current_comment_id"]}', 'PATCH', {'body': body(d, 2)})
    for name, a, b in [('exact-v1', old_base, old_tip), ('exact-v2', base, tip), ('tips-v1-v2', old_tip, tip)]:
        lab.git('history-' + name + '-diff', 'diff', '--stat', a, b)
        lab.api('history-' + name + '-api-compare', f'repos/{lab.REPO}/compare/{a}...{b}')
    lab.api('history-list-v2', f'repos/{lab.REPO}/issues/{d["pr"]}/comments?per_page=100')
    lab.state('history-after-v2', [d['pr']])
    d['status'] = 'attached-v2'; save(d)

def reattach():
    d = data(); old_id = d['current_comment_id']
    lab.api('history-delete-comment', f'repos/{lab.REPO}/issues/comments/{old_id}', 'DELETE')
    lab.api('history-get-deleted', f'repos/{lab.REPO}/issues/comments/{old_id}', allowed=(1,))
    response = lab.api('history-find-after-loss', f'repos/{lab.REPO}/issues/{d["pr"]}/comments?per_page=100')
    matches = [c for c in json.loads(response.stdout) if MARKER in c['body']]
    assert not matches
    d['status'] = 'missing'; d['superseded_comment_id'] = old_id; save(d)
    lab.event({'name': 'history-reattach-decision', 'state': 'operator-policy', 'decision': 'explicitly recreate missing generated history under the authorized loss/reattach experiment', 'old_id': old_id, 'artifact': MARKER})
    c = json.loads(lab.api('history-create-replacement', f'repos/{lab.REPO}/issues/{d["pr"]}/comments', 'POST', {'body': body(d, 2) + f'\nReattached after the prior generated comment ({old_id}) was deleted.\n'}).stdout)
    d.update({'current_comment_id': c['id'], 'current_comment_node_id': c['node_id'], 'comment_url': c['html_url'], 'status': 'reattached-v2'}); d['comment_ids'].append(c['id']); save(d)
    lab.api('history-list-reattached', f'repos/{lab.REPO}/issues/{d["pr"]}/comments?per_page=100')
    lab.state('history-after-reattach', [d['pr']])

def caps():
    d = data(); prefix = 'Synthetic comment-size boundary probe.\n\n'; suffix = '\n\n' + lab.DISCLOSURE
    def sized(n): return prefix + 'x' * (n - len(prefix) - len(suffix)) + suffix
    c = json.loads(lab.api('history-cap-create-65536', f'repos/{lab.REPO}/issues/{d["pr"]}/comments', 'POST', {'body': sized(65536)}).stdout)
    d['size_probe_comment_id'] = c['id']; save(d)
    lab.api('history-cap-update-65537', f'repos/{lab.REPO}/issues/comments/{c["id"]}', 'PATCH', {'body': sized(65537)}, allowed=(1,))
    lab.api('history-cap-read', f'repos/{lab.REPO}/issues/comments/{c["id"]}')
    lab.api('history-cap-collapse', f'repos/{lab.REPO}/issues/comments/{c["id"]}', 'PATCH', {'body': 'Synthetic comment-size probe completed. Raw responses are retained in the local experiment evidence.\n\n' + lab.DISCLOSURE})

def caps_reconcile():
    d = data(); cid = d['size_probe_comment_id']
    response = lab.api('history-cap-reconcile-read', f'repos/{lab.REPO}/issues/comments/{cid}')
    current = json.loads(response.stdout)
    assert len(current['body']) == 65537
    html = lab.run('history-cap-rendered-api', ['gh', 'api', '-H', 'Accept: application/vnd.github.full+json', f'repos/{lab.REPO}/issues/comments/{cid}'])
    rendered = json.loads(html.stdout)
    lab.dump(ROOT / 'comment-size-observation.json', {'accepted_body_characters': len(current['body']), 'accepted_body_utf8_bytes': len(current['body'].encode()), 'rendered_fields': list(rendered.keys()), 'body_html_bytes': len(rendered.get('body_html', '').encode()), 'limit_status': '65536 is not a server cap in this observed request path; larger-host maximum untested'})
    lab.api('history-cap-collapse-reconciled', f'repos/{lab.REPO}/issues/comments/{cid}', 'PATCH', {'body': 'Synthetic comment-size probe completed: 65,536 and 65,537 ASCII characters were both accepted. No server maximum was established. Raw responses remain in the local experiment evidence.\n\n' + lab.DISCLOSURE})
    def admitted(text): return len(text.encode('utf-8')) <= 60000
    checks = {'ascii_at_client_budget': admitted('x' * 60000), 'ascii_over_client_budget': admitted('x' * 60001), 'unicode_at_client_budget': admitted('é' * 30000), 'unicode_over_client_budget': admitted('é' * 30001), 'real_history_fits': admitted(body(d, 2))}
    assert checks == {'ascii_at_client_budget': True, 'ascii_over_client_budget': False, 'unicode_at_client_budget': True, 'unicode_over_client_budget': False, 'real_history_fits': True}
    lab.dump(ROOT / 'prototype-render-budget.json', {'budget_utf8_bytes': 60000, 'over_budget_policy': 'retain prior comment and journal; refuse update and require an explicit alternate-history decision; never silently truncate exact history', 'checks': checks, 'scope': 'local prototype admission only; no reviewer usability or provider maximum claim'})

def pin():
    d = data(); cid = d['current_comment_node_id']
    def query(label):
        request = EVIDENCE / (label + '.request.json')
        lab.dump(request, {'query': 'query($id: ID!) { node(id:$id) { ... on IssueComment { id url isPinned pinnedAt pinnedBy { login } viewerCanPin viewerCanUnpin viewerCanUpdate viewerCanDelete isMinimized author { login } body } } }', 'variables': {'id': cid}})
        result = lab.run(label, ['gh', 'api', 'graphql', '--input', str(request)])
        return json.loads(result.stdout)['data']['node']
    before = query('history-pin-before')
    if not before['viewerCanPin']:
        lab.dump(ROOT / 'pin-result.json', {'available': False, 'observation': before}); return
    def mutate(label, operation):
        request = EVIDENCE / (label + '.request.json')
        lab.dump(request, {'query': 'mutation($id: ID!, $receipt: String!) { ' + operation + '(input: {issueCommentId:$id, clientMutationId:$receipt}) { clientMutationId issueComment { id isPinned pinnedAt pinnedBy { login } } } }', 'variables': {'id': cid, 'receipt': label}})
        lab.run(label, ['gh', 'api', 'graphql', '--input', str(request)], mutation={'operation': operation, 'comment_node_id': cid, 'receipt_label': label, 'note': 'clientMutationId is a correlation field, not an assumed idempotency key'})
    mutate('history-pin', 'pinIssueComment'); pinned = query('history-pinned-read')
    assert pinned['isPinned'] is True
    lab.api('history-pinned-rest', f'repos/{lab.REPO}/issues/comments/{d["current_comment_id"]}')
    mutate('history-unpin', 'unpinIssueComment'); unpinned = query('history-unpinned-read')
    assert unpinned['isPinned'] is False
    mutate('history-pin-final', 'pinIssueComment'); final = query('history-final-pin-read')
    assert final['isPinned'] is True
    lab.dump(ROOT / 'pin-result.json', {'available': True, 'comment_id': d['current_comment_id'], 'pin_observed': pinned, 'unpin_observed': unpinned, 'final_state': final, 'limits': 'same repository-owner identity; no second-role authorization or reviewer findability walkthrough'})

def pin_reconcile():
    request = EVIDENCE / 'history-pin-before.request.json'
    observed = json.loads(lab.run('history-pin-reconcile-read', ['gh', 'api', 'graphql', '--input', str(request)]).stdout)['data']['node']
    assert observed['isPinned'] is False
    rejected = json.loads((EVIDENCE / 'history-pin.stdout').read_text())
    lab.dump(ROOT / 'pin-result.json', {'available_for_pr_comment': False, 'schema_mutation_exists': True, 'viewerCanPin_reported': True, 'rejected_mutation_response': rejected, 'post_state': observed, 'limit': 'Issue-comment pinning is not applicable to this PR comment despite viewerCanPin=true; no pin/unpin cycle occurred'})

def caps_bounded():
    import hashlib
    d = data(); cid = d['size_probe_comment_id']
    def digest(text): return hashlib.sha256(text.encode()).hexdigest()
    old_request = json.loads((EVIDENCE / 'history-cap-update-65537.request.json').read_text())['body']
    old_get = json.loads((EVIDENCE / 'history-cap-reconcile-read.stdout').read_text())['body']
    assert old_request == old_get
    observations = [{'case': 'ascii65537_previous_get', 'characters': len(old_get), 'utf8_bytes': len(old_get.encode()), 'sha256': digest(old_get), 'exact_get_match': True}]
    prefix = 'Synthetic bounded size probe.\n\n'; suffix = '\n\n' + lab.DISCLOSURE
    def sized(limit, filler):
        remain = limit - len((prefix + suffix).encode())
        count, tail = divmod(remain, len(filler.encode()))
        return prefix + filler * count + 'x' * tail + suffix
    def update(label, text):
        result = lab.api(label, f'repos/{lab.REPO}/issues/comments/{cid}', 'PATCH', {'body': text}, allowed=(0,1))
        if result.returncode == 0:
            returned = json.loads(result.stdout)['body']; assert returned == text
        observations.append({'case': label, 'exit': result.returncode, 'characters': len(text), 'utf8_bytes': len(text.encode()), 'sha256': digest(text), 'returned_body_exact': result.returncode == 0})
        return result.returncode
    ascii_text = sized(262144, 'x')
    rc = update('history-cap-ascii262144', ascii_text)
    got = json.loads(lab.api('history-cap-ascii262144-get', f'repos/{lab.REPO}/issues/comments/{cid}').stdout)['body']
    if rc == 0: assert got == ascii_text
    observations.append({'case': 'ascii262144_get', 'exact_get_match': rc == 0 and got == ascii_text, 'utf8_bytes': len(got.encode()), 'sha256': digest(got)})
    update('history-cap-ascii262145', sized(262145, 'x'))
    utf8_text = sized(262144, 'é')
    rc = update('history-cap-utf8-262144bytes', utf8_text)
    got = json.loads(lab.api('history-cap-utf8-get', f'repos/{lab.REPO}/issues/comments/{cid}').stdout)['body']
    if rc == 0: assert got == utf8_text
    observations.append({'case': 'utf8_get', 'exact_get_match': rc == 0 and got == utf8_text, 'characters': len(got), 'utf8_bytes': len(got.encode()), 'sha256': digest(got)})
    lab.api('history-cap-final-restore', f'repos/{lab.REPO}/issues/comments/{cid}', 'PATCH', {'body': 'Synthetic bounded comment-size probe completed. Exact request/response and GET body hashes are retained in the local evidence; no reviewer usability claim is made.\n\n' + lab.DISCLOSURE})
    lab.dump(ROOT / 'bounded-comment-size-results.json', {'observations': observations, 'requests': 6, 'largest_request_body_utf8_bytes': 262145, 'scope': 'measured paths only; no claimed server maximum unless an explicit rejection established it'})

if __name__ == '__main__':
    {'create': create, 'update': update, 'reattach': reattach, 'caps': caps, 'caps-reconcile': caps_reconcile, 'pin': pin, 'pin-reconcile': pin_reconcile, 'caps-bounded': caps_bounded}[sys.argv[1]]()
