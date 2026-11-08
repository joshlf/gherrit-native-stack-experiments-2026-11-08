# Native lifecycle, publication and race experiments

These are observations from the public synthetic repository
`joshlf/gherrit-native-stack-experiments-2026-11-08` on November 8, 2026.
They establish the recorded cases, not a future provider contract. Raw requests,
responses, dispatch intents, exact refs, local objects and failed assumptions are
retained in `evidence/`. `resources.json` binds fixture names to branches and PRs.
All REST calls used API version `2026-03-10`.

## Native lifecycle and landing methods

In the capabilities fixture, singleton creation and duplicate membership writes
returned 422. Append returned 200. Closing the middle PR retained its membership;
reopening succeeded. Unstacking an entirely open group returned 204 and preserved
the PR objects and their bases. A deliberately separate second unstack returned
404. A later merge attempt through a closed middle PR failed, and no member
landed; reopening the middle PR still succeeded.

Separate merge, squash and rebase fixtures each completed both a lower-prefix
landing and the remaining full prefix through the async endpoint. The old
synchronous merge endpoint returned 403 for native members. Async acceptance
returned 202 with a UUID, selected SHA and method/action. Exact final trunk trees
matched the expected changes; remaining PRs stayed open and were rewritten and
retargeted. Unstacking a fully merged group returned 422. Full observations and
timelines are in `basic-results.json`.

### A completed group accepted later work

The documented assumption that a completed group cannot accept append did not
hold in this fixture. Group #28 was observed `open: false`, with A/B/C merged.
Appending D #29 returned 200, retained that grouping number and historical
members, and reopened the group. E #30 was subsequently appended successfully.
Native landing of D then succeeded. Unstack returned 200 with merged A/B/C/D
remaining, while E was released. E and a new F #60 registered as group #61,
preserving E's canonical PR.

The first runner expected append rejection and continued to label the request
`complete-append-rejected`. That label records its hypothesis, not the result.
Its following base-edit and duplicate-group 422 responses were contaminated by
the successful append; they do not establish that fresh regrouping is forbidden.
The separately recorded follow-up above establishes what actually happened.
This is a current host observation that conflicts with the earlier documentation,
not a promise that reopening completed groups is supported indefinitely.

## Structural changes and the lifecycle hazard

The safe fixture retained canonical PR/node identities through reorder C–A–B,
insertion C–D–A–B, explicit dropping D, explicit folding A into C, and a trunk
change. Each operation released membership, parked all surviving open PR bases
at the trunk, atomically pushed heads and archives with exact leases, installed
final bases, and registered the intended order. Dropped/folded reviews were
explicitly withdrawn. Source objects, old heads and archives were retained.

The negative control used A #57, B #58 and group #59. After release it deliberately
omitted parking, then reordered heads so that A's branch contained B's new head.
GitHub marked B **merged**, although the fixture trunk did not move. Attempts to
repair its base and reopen it both returned 422; the latter explicitly said the
PR could not be reopened. This reproduces the irreversible review-lifecycle
hazard, rather than an ordinary closed-unmerged PR that can be reopened.

`structure-results.json` contains every stage. The safe cases support the tested
sequence; they do not turn these separate Git/PR/group operations into a server
transaction or rule out all lifecycle races.

## Atomic publication and selected-revision races

With one wrong lease, an atomic push rejected the whole head/archive vector and
left every remote ref unchanged. Removing `--atomic` from the same vector
returned failure while publishing A and both new archive refs, but leaving B at
its old head. The new B archive therefore existed without B being published.
An explicitly recorded repair published B afterward. This is an actual hosted
control, not a mocked send-pack result.

The selected-head race requested squash of B #69 at original SHA
`f1daa6ba67937810841e63d8ef514dde56d78660`. A second request asking for rebase
returned 409 and the **original squash UUID/options**. It did not acknowledge the
new rebase intent. A concurrent exact-lease push of B=2 succeeded. The original
request then reported merged, and the trunk contained **B=1**, while the
now-merged PR's head/ref contained **B=2**. The experiment observed the old
requested revision landing; it did not demonstrate a live-head fence or landing
of the later edit.

In a separate three-layer race, only A changed while the selected C SHA remained
fixed. The request failed with a merge conflict; all members remained open and
the trunk stayed unchanged. The runner then incorrectly assumed success and
tried to read a nonexistent A file from the unchanged trunk. That oracle error
remains in `race-results.json`; `race-interpretation.json` records the read-only
reconstruction. This trial does not establish what every nonconflicting lower
change would do, or provide an all-member snapshot lease.

## Pending operations and cross-resource reads

Unstacking one fixture immediately after async acceptance returned 204. The
original merge subsequently failed with “it is no longer stacked.” No member
landed. This is one observed overlap order, not a cancellation API or a guarantee
that unstack always wins a race.

In the four-member observer fixture, a required check failed on C. Requesting
the A/B/C prefix failed with that check's name; no PR merged and the trunk stayed
unchanged. Releasing only that check allowed the same prefix to land. A new
disjoint ref published during the operation remained unchanged afterward.

Sixteen read cohorts captured intermediate PR lifecycle states and suffix
retarget/rewrite observations. At the first terminal `merged` poll, an overlapping
D GET still reported its old head; the later Git ref read reported its new head.
The next cohort agreed on the new head. These cohorts were concurrent endpoint
reads, **not atomic snapshots**. They expose an unusable cross-resource
observation, but do not distinguish API cache/replication lag from progressing
writes and do not prove that a suffix ref write occurred after the terminal
response. Lagging per-PR merged flags also do not prove partial Git landing.
The full timing intervals are in `evidence/observer-detailed-samples.json`.

A separate hosted import experiment observed an old PR head and new Git ref in
strictly subsequent reads after terminal success. See
`../local-git/hosted-integration/RESULTS.md` for its exact timing and limits.
Neither a terminal receipt nor several coherent samples proves that no later
provider write remains possible. This provider handoff question is still open.

## Lost acknowledgements without blind retries

`run_lost_receipts.py` made three actual hosted writes on PRs #90/#91/#92, group
#93, and killed the child with SIGKILL after the server response but before its
client acknowledgement. An independent oracle retained the responses. Recovery
did not read that oracle until its decisions were persisted.

Create and append produced uniquely attributable positive membership transitions
in this isolated sole-writer fixture; recovery identified the actual group and
members without resending. Unstack left no membership. The client deliberately
kept that dispatch unresolved: absence alone was insufficient to settle an old
write. The oracle subsequently confirmed HTTP 201/200/204. No write was retried,
and no overlapping write followed the unresolved unstack.

`lost-receipts-client.json`, `lost-receipts-recovery-before-oracle.json` and
`lost-receipts-results.json` preserve the separate views. This was an injected
client failure **after a real acknowledgement**, not an actual network timeout,
provider idempotency test or server-quiescence proof. A public API observation
that another writer could have produced would not supply the same attribution.

*Authored by an AI agent acting on joshlf's behalf.*
