"""Drop acknowledgements after real hosted writes; recover without resending.

The child retains a separate oracle receipt before SIGKILL. Recovery does not
read that receipt. This injects a client failure after a server response; it does
not simulate an unobserved server execution or establish provider quiescence.
"""
from lab import *
import sys, signal

CLIENT = HOME / 'lost-receipts-client.json'
RESULT = HOME / 'lost-receipts-results.json'


def dispatch_without_client_ack(label, method, path, payload):
    records = json.loads(CLIENT.read_text()) if CLIENT.exists() else {}
    if label in records:
        raise RuntimeError('Retain existing unresolved dispatch; do not resend')
    records[label] = {'state': 'dispatched-without-ack', 'method': method,
                      'path': path, 'payload': payload, 'at': now()}
    atomic_json(CLIENT, records)
    child = command([sys.executable, __file__, '--child', label, method, path,
                     json.dumps(payload)])
    if child.returncode != -signal.SIGKILL:
        raise RuntimeError('Child did not reach the intended killed boundary: '
                           + str(child.returncode) + child.stderr)
    return {'exit': child.returncode, 'client_ack': None}


def observe_memberships(case, label):
    observations = {}
    for letter, number in case['prs'].items():
        value = api(label + '-' + letter, 'GET',
                    f'repos/{REPO}/pulls/{number}', fresh=True)
        if value['http'] != 200:
            raise RuntimeError('Membership observation unavailable')
        observations[letter] = value['data'].get('stack')
    return observations


def run():
    if RESULT.exists() or CLIENT.exists():
        raise RuntimeError('Existing dispatch/results need reconciliation, not replay')
    case = fixture('lost-receipts', 3, register=False)
    before = observe_memberships(case, 'receipt-before')
    assert all(value is None for value in before.values()), before
    create_path = f'repos/{REPO}/stacks'
    create_payload = {'pull_requests': [case['prs']['A'], case['prs']['B']]}
    create = dispatch_without_client_ack('receipt-create', 'POST', create_path,
                                         create_payload)
    created = observe_memberships(case, 'receipt-created')
    assert created['A'] and created['B'] and not created['C'], created
    stack = created['A']['number']
    assert created['B']['number'] == stack, created
    group = api('receipt-created-group', 'GET', create_path + '/' + str(stack),
                fresh=True)
    assert group['http'] == 200, group
    # Only the fresh fixture's controller can create this exact grouping here.
    # A multi-writer environment needs stronger attribution than this fixture.
    create_recovery = {'decision': 'positive transition attributable in sole-writer fixture',
                       'stack': stack, 'observed_memberships': created,
                       'client_ack': None, 'resent': False}
    append_path = create_path + '/' + str(stack) + '/add'
    append_payload = {'pull_requests': [case['prs']['C']]}
    append = dispatch_without_client_ack('receipt-append', 'POST', append_path,
                                         append_payload)
    appended = observe_memberships(case, 'receipt-appended')
    assert all(value and value['number'] == stack for value in appended.values()), appended
    append_recovery = {'decision': 'positive membership transition attributable in sole-writer fixture',
                       'observed_memberships': appended, 'resent': False}
    unstack = dispatch_without_client_ack('receipt-unstack', 'POST',
                                          create_path + '/' + str(stack) + '/unstack', None)
    released = observe_memberships(case, 'receipt-released')
    assert all(value is None for value in released.values()), released
    unstack_recovery = {'decision': 'remain indeterminate; absence alone does not settle the dispatched write',
                        'observed_memberships': released, 'resent': False,
                        'overlapping_writes_after': 0}
    # Inspect the independent oracle only after recording recovery decisions.
    recovery = {'create': create_recovery, 'append': append_recovery,
                'unstack': unstack_recovery}
    atomic_json(HOME / 'lost-receipts-recovery-before-oracle.json', recovery)
    oracle = {label: json.loads((EVIDENCE / (label + '.meta.json')).read_text())
              for label in ('receipt-create', 'receipt-append', 'receipt-unstack')}
    assert [oracle[x]['http'] for x in oracle] == [201, 200, 204], oracle
    atomic_json(RESULT, {'fixture': case, 'faults': [create, append, unstack],
                        'recovery': recovery,
                        'oracle_http': {k: v['http'] for k, v in oracle.items()},
                        'limits': ['Injected after actual server acknowledgement',
                                   'No true network timeout or provider fence',
                                   'Attribution limited to isolated sole-writer fixture',
                                   'Unstack remains unresolved from client evidence alone']})
    print(json.dumps({'status': 'recorded', 'stack': stack,
                      'oracle_http': {k: v['http'] for k, v in oracle.items()}}))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--child':
        _, _, label, method, path, payload = sys.argv
        api(label, method, path, json.loads(payload), cooldown=0)
        os.kill(os.getpid(), signal.SIGKILL)
    else:
        run()
