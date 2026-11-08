# Hosted end-to-end reconciliation

The disposable A–B → landed A → F–B → landed F → imported B workflow completed
using actual GitHub native rewrites and the real-Git I/L/H algorithm. Canonical
[B #63](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/63)
retained its original PR/node identity throughout. Original
[A #62](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/62)
and new-ID
[F #88](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/88)
landed; B remained open. All effects were confined to
`exp/integration/repeat-01/**` in the experiment repository.

The first post-landing observation was **inconsistent even after a terminal
`merged` receipt**. The runner stopped before structural publication. Later
coherent observations allowed this bounded disposable-repository experiment to
continue. That choice is not a production admission rule or evidence of provider
settlement. A separate runner error also stopped execution: it incorrectly
expected only a 204 unstack response, while this partial release correctly
returned documented 200. Both failed checks and source versions are retained.

[`summary.json`](summary.json) contains the exact ranges, identities, effects,
archives, and limitations; [`state.json`](state.json) retains all 137 assertions,
including the two failed checks and 135 successful checks. This count describes
the executed checks, not statistical confidence or an all-green test suite.

## Terminal receipt versus PR/ref observation

The old-A squash request was accepted with UUID
`fa731902-d616-4aa1-9598-672dd28b50e7`. Its terminal `merged` poll ended at
23:21:38.842657Z on November 8, 2026.

| Observation | Exact value |
| --- | --- |
| Original submitted B tip | `f15cb29aac3b8740374c2fa3c4239cdcd5ab58f0` |
| B PR GET, 23:21:39.184033–39.581906Z | That old B head, but the new trunk comparison base `9764253d75c6ed4bfda1ebe562618fa6644a49d5` |
| Subsequent `ls-remote` | Rewritten B `933e62a007da8cc6131e683774a34bddf644af55` |
| Ref-read timing bounds | After group GET ended 23:21:39.894195Z and before the failed guard at 23:21:40.049230Z; exact command timestamp was not recorded |
| Both B trees | `382bf79f041a01df8ca41cbb63b991734f42d41b` |
| Parent transition | Original A `84ff590243f50d703c26712bf28a986b412bfd66` → landed trunk `9764253d75c6ed4bfda1ebe562618fa6644a49d5` |

The original authored B identity/message/author survived in its exact archive.
The rewritten B retained its author/message and changed parent/committer. The
sample does not distinguish cached observation lag, a concurrently progressing
rewrite, or another cause. In particular, it does not prove that the ref changed
after the terminal receipt: the reads were sequential and no earlier ref sample
at that instant exists.

The preserved
[`terminal-versus-head-ref-mismatch.json`](evidence/terminal-versus-head-ref-mismatch.json)
contains timing, receipt UUID, raw commit headers/messages, and the failed guard.
The first normalized snapshot was not written before its guard failed in runner
v1; its raw API receipts and Git command output remain. A clearly labelled
reconstruction is also retained. Runner v2 moved snapshot persistence before the
guard and added a newly labelled read-only recovery stage. It did not weaken the
head/ref check or resend the merge request.

## The retained amendment required F before B

The original A introduced `Record.legacy`; original B read that field. Local A′
added `Record.field = 'retained'`, and local B′ accessed `Record.field`. Those
unpublished inputs remained pinned locally while old A landed.

After fresh samples agreed on the actual trunk and hosted B, the harness:

1. Applied A's pending delta to the landed trunk to create explicit new-ID F.
2. Normalized B's incorporated and local ranges onto the actual hosted comparison
   parent, integrated them with actual hosted B, then replayed the result onto F.
3. Checked the exact resulting trees and individual layer patches. F changed only
   `integration_case/model.py`; B changed only `integration_case/consumer.py`.
4. Executed B successfully with F present. The negative control using B's
   comparison-parent-normalized tree without F failed specifically with
   `AttributeError` for the missing `Record.field`, rather than an unrelated
   import or syntax error.

The initial I/L/H inputs and every normalized/intermediate/output commit remain
in the repository and
[`resume-first-import-inventory.json`](evidence/resume-first-import-inventory.json).
[`per-layer-author-and-dependency-checks.json`](evidence/per-layer-author-and-dependency-checks.json)
records exact commit headers/messages, Josh Liebow-Feeser
`<hello@joshlf.com>` as author, and one required `Agent-authored-by` trailer for
the selected authored, local, replayed, and native B commits. Local generated
commits were deliberately unsigned; this is not a signing UX test.

## Structural publication retained the canonical review

Old native group #64 initially contained A #62 followed by B #63. The one unstack
dispatch returned **200**, with a residual group containing only merged A.
The original 204-only assertion was a harness error: the frozen REST contract
explicitly distinguishes residual-group 200 from dissolved-group 204. The
failure, receipt, and runner v2 source are retained. Runner v3 reused that same
receipt without another unstack dispatch and required residual membership exactly
[A], then independently checked that B was released.

B was already based on the trunk following native A landing. The parking stage
therefore confirmed the required parked state and recorded `none_required`; it
did not exercise a nontrivial parking base edit.

The next Git transaction atomically published the new F head, changed B head,
F/v1 archive, and B/v2 archive. It used an absence expectation for new refs and an
explicit old-hosted-B lease for B. It left A's head and old archives untouched.
Then the runner created F #88 at the trunk, set existing B #63's base to F, checked
the adjacent bases/heads, and registered ordered [F #88, B #63] as group #89.

All confirmation reads retained B's node ID
`PR_kwDOVnhIZ88AAAABNuiaBw`. A stayed merged. The final observations retained all
four exact archives:

| Archive suffix under `exp/integration/repeat-01/authored/` | Target |
| --- | --- |
| A/v1 | `84ff590243f50d703c26712bf28a986b412bfd66` |
| B/v1 | `f15cb29aac3b8740374c2fa3c4239cdcd5ab58f0` |
| F/v1 | `b8d92c60ae731825b720f4dae01373b5b3bf24cc` |
| B/v2 | `b49dfdbd8e207d6f3bd55d03996bb0c51877e652` |

Raw intents, push arguments/output, API receipts, final-base observations, exact
membership, and the captured export checkpoint are in `evidence/` and
`state.json`. This is a successful finite sequence of separate effects, not one
cross-resource transaction or proof against delayed writes.

## Landing F and importing B again

F #88 then landed through the async squash endpoint. Two agreeing samples showed
F merged, B still open with the same review identity, trunk
`ce8d49b86294b945d860f53d634483fdb3f7274c`, and rewritten B
`c2f671d686eec1642775752a2139a9d2e694dc17` based on that trunk. The trunk tree
equaled F's exact published tree.

The harness ran two imports from the captured F/B export basis:

- With no later local edit, the algorithm's candidate matched the actual hosted B
  tree and message. The explicitly selected fresh continuation used the **exact
  hosted B range**. It required no remote ref/base/membership effect and created
  no authored archive. The algorithm's scratch candidate has a different SHA;
  equality of those two commit IDs was neither assumed nor asserted.
- A later local B commit had added a `pending_note()` function after the captured
  export was confirmed but before its checkpoint was installed. The captured
  submission checkpoint retained the exported B target. Importing this later
  local range retained only the pending consumer edit, with the new hosted B
  range recorded separately as the incorporated baseline. Its executable consumer
  still passed.

Both fresh continuation refs were created locally with absence expectations.
Their explicit intent/checkpoint files distinguish last authored submission,
incorporated hosted range, and selected accepted local result. The original
source inputs remain pinned. The no-pending acceptance is an experiment decision
after tree/message checks, not a deployed GHerrit no-op implementation or an
automatic mapping policy. Author intent/mapping was supplied explicitly.

The final observation confirmed that these imports made no further remote
ref/archive changes. The second native B raw commit, all local outputs, runtime
results, and
[`second-import-inventory.json`](evidence/second-import-inventory.json) remain.
Independent
[`artifact-verification.json`](evidence/artifact-verification.json) also checks
exact tree identity: F equals local A′, exported B equals local B′, second native
B equals exported B, and the pending import equals the later local tree. It names
the actually selected continuation checkpoints separately from scratch candidates.
`git fsck --full --no-reflogs` completed successfully.

## Scope and remaining limits

There were two atomic Git pushes and nine distinct hosted API write dispatches.
Every hosted write had a persisted intent before dispatch and a retained receipt.
The unstack request was sent once despite the client status-oracle correction.
No main, workflow, settings, bot, production, or other experiment-lane resource was
modified. This checkout/state did not use the root API helper or shared registry.

The experiment connects actual native outcomes to the local range algorithm and
shows the F-before-canonical-B case can complete in this observed configuration.
It also exposes a real inconsistent observation boundary and a corrected client
oracle assumption. It does not establish provider settlement, arbitrary
concurrent-writer safety, approval/check/queue preservation, nontrivial structural
parking, signing choices, general change mapping, or production GHerrit behavior.
Successful continuation after coherent reads remains an intentionally bounded
choice in this disposable repository.

*Authored by an AI agent acting on joshlf's behalf.*
