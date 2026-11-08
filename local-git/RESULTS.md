# Local Git experiment results

The final harness run passed **122 of 122 checks** on Git 2.54.0 (Apple Git-157)
and Python 3.9.6. These are local fixture results and a local recovery-policy
prototype. They do not establish deployed GHerrit behavior or a GitHub handoff.
No GHerrit source, Cargo build, remote ref, PR, or hosted stack was changed.

The final run is
[`runs/20261108T175427-1794178467639760000`](runs/20261108T175427-1794178467639760000).
Its [`results.json`](runs/20261108T175427-1794178467639760000/results.json)
records every assertion, expected/actual values, per-change ranges, accepted
results, continuation snapshots, interrupted processes, and transfer decisions.
The saved harness SHA-256 is
`548714fe2959e48dfd61286683a4773405affc23b2591e2a48637c5c76ebb7e3`.

## What the local algorithm exercised

For each change, the harness takes explicit incorporated I, local L, and observed
hosted H base/tip ranges. It uses actual `git merge-tree --write-tree` with an
explicit `--merge-base` for each step:

1. Apply I's range onto H's comparison parent, producing normalized I.
2. Apply L's range onto that same parent, producing normalized L.
3. Integrate normalized L and H's tip using normalized I as the explicit base.
4. Replay the integrated range onto the preceding accepted output layer, using
   H's comparison parent as the explicit base.
5. Record the resulting commit with that preceding output as its parent and the
   exact local commit message. Keep H separately as the incorporated range.

The fixture author/signing choice is explicit: Josh Liebow-Feeser
`<hello@joshlf.com>`, unsigned commits, and the required `Agent-authored-by`
trailer. Actual message bytes are retained. This does not test key access or
signed-commit author decisions.

| Case | Observed result |
| --- | --- |
| Repeated hosted import | Importing hosted x=1 and later x=2 retained unpublished y=1. Local r and hosted q in upper B both survived. |
| Lower-only amendment after integration | Changing A's y from 1 to 2 retained y=2 through B. B's patch still contained only B's b/q/r changes. |
| Shared-file ownership | A and B edited separated hunks in one file. A's later lower-only hunk stayed out of B's zero-context patch; exact A and B trees matched the expected contents. |
| Multi-commit hosted range | A two-commit hosted B range imported q=3 while retaining local r and B's layer ownership. |
| Ordinary Git authoring | Real `commit --amend` and `rebase` changed SHAs while preserving the exact A message/ID. Import retained the amendment and new trunk. A real revert was retained as new-ID R; a subsequent deliberate reset kept R pinned and exposed its differences from the accepted input. |
| Conflicts | Normalization, same-line integration, and replay conflicts all stopped with original commits, conflict trees, and full Git diagnostics preserved. |
| Captured successful submission | The checkpoint model advanced to the captured export. A later local edit remained a visible pending diff. This tests the checkpoint decision, not a hosted submission. |
| Landed prefix with pending work | A squash-style landed A had a different SHA and was not a descendant of old A. Given merged-A/open-B lifecycle inputs, the fixture constructed new-ID F below B, retained B's authored message, and verified that F's parent tree supplied the field B needed. Canonical review names are fixture metadata. No provider regrouping was attempted. |
| Changed comparison parent | The raw old-tip/new-tip diff showed an unrelated trunk change. Each exact historical base/tip patch excluded it. `git range-diff` recognized the same patch when its message was preserved. |
| Unchanged import | Repeating the same input preserved the exact final tree. Scratch commits may have new identities; this does not implement a publisher's no-new-archive decision. |

The explicit reset fixture supplies its mapping and acceptance as an input. The
harness does not infer the author's intent from arbitrary rewritten history or
provide the author-facing mapping review.

## What the negative controls refuted

These are small, deliberately wrong variants of this fixture algorithm:

| Wrong variant | Distinguishing observation |
| --- | --- |
| Reuse last authored x=0 as the second import's baseline | Git reported an x conflict between retained x=1 and observed x=2. The incorporated-x=1 baseline imported successfully. |
| Replace incorporated hosted baseline with the accepted local result | The next import silently lost pending y=1. |
| Reset upper output to its comparison-parent-normalized integrated tree, omitting replay | The lower-only y=2 disappeared, and B's patch acquired a y deletion. This is the tested cumulative-tree reset mutation. |
| Mark the whole live branch submitted | Comparing live input against that checkpoint hid the later edit completely. |
| Accept by `reset --hard` on the source | The disposable negative fixture moved the source ref, changed the staged index, and discarded dirty tracked-file content. Its untracked file remained. |
| Transfer only canonical bindings | Admission reported missing accepted checkpoint and pending-operation evidence and withheld mutation authority. |
| Append F above dependent B | B's preceding tree lacked the field it uses. F before B supplied it. |

These observations justify keeping the compared roles separate in these cases.
They do not prove that every cumulative or alternative integration algorithm
fails, or that the proposed algorithm handles every Git history.

## Accepting a continuation without displacing authoring

The fixture captured committed source T, then advanced the source ref to U with
a compare-and-swap `update-ref` while scratch integration ran. It retained staged,
unstaged, and untracked author work. Acceptance journaled intent, created fresh
continuation R with an all-zero expected old value, and atomically replaced the
continuation's JSON checkpoint. Source U, index bytes, and every working-file byte
were identical before and after acceptance. The old source checkpoint stayed
unchanged.

An occupied continuation name failed its absence guard and retained its original
target. An ordinary `git switch` to R was blocked because tracked author edits
would be overwritten; that failed switch also preserved the workspace. This is
an executable local boundary, not a completed GHerrit command or a usability
walkthrough with an independent author.

## Interruption and transfer

Eight separate child processes were killed with real `SIGKILL`. Before killing,
each child durably wrote a marker at the selected prefix. The local provider
emulator writes a JSON request/receipt store; continuation refs are real Git refs.

| Kill prefix | Recorded state at interruption | Emulator requests after recovery | Recovery |
| --- | --- | --- | --- |
| Before planned record | No operation record | 1 | Complete |
| Planned record | Known not dispatched | 1 | Complete |
| Dispatch intent recorded, call not made | Indeterminate | 0 | Block unknown; do not resend |
| Emulator applied, response not recorded | Indeterminate | 1 | Block unknown; do not resend |
| Acknowledgement recorded | Acknowledged | 1 | Complete |
| Continuation ref created, checkpoint absent | Acknowledged | 1 | Verify ref and install checkpoint |
| Checkpoint installed, completion absent | Acknowledged | 1 | Retain exact checkpoint and complete |
| Complete record | Complete | 1 | Complete without another effect |

No prefix advanced the old source checkpoint. An unknown outcome installed no
completed continuation checkpoint. An absent emulator effect did not authorize a
resend after dispatch intent was durable.

A replacement fixture received bindings, the accepted checkpoint, the pending
manifest, the operation record, and Git objects/refs after the old process was
killed. It retained the unknown guard and sent no second request. Explicitly
reconciling the emulator's uniquely attributable operation receipt then completed
local acceptance without resending. This receipt has deliberately defined local
sole-writer semantics; it supplies no GitHub idempotency or completion guarantee.
A separate negative probe supplied the desired head with a receipt attributed
to another writer. Even with explicit receipt reconciliation requested, recovery
remained blocked, sent no request, and installed no completed checkpoint. Its
evidence is `negative-unattributed-provider-state/probe-result.json` in the final
run. The transfer admission policy is cooperative and is not a fence against
somebody editing/deleting records or bypassing the harness.

## Evidence and remaining work

Each run retains its exact harness, environment/hash, command JSONL transcripts,
merge records, input and output repositories, pinned objects, full messages,
base/tip trees and patches, index/worktree snapshots, operation files, child PIDs,
SIGKILL exit codes, and recovery outputs. `git fsck --full --no-reflogs` passed for
the main final fixture. All earlier runs remain, including the first failed run:
its `range-diff` expectation incorrectly assumed a fixture-generated message
change was an unchanged patch. Preserving the rebased message corrected that
fixture error; the failed evidence was retained.

The local examples support implementing and challenging this reconciliation
direction. GHerrit integration, automatic/approved change mapping, broader rename
and merge histories, signing decisions, power-loss durability, independent author
usability, provider lifecycle/structural effects, and the safe hosted handoff
remain unestablished here. Finite local success does not resolve delayed GitHub
suffix writes.

Run again from this directory with `python3 harness.py run`. Every invocation
creates a new evidence directory and updates `latest-run.json`.

*Authored by an AI agent acting on joshlf's behalf.*
