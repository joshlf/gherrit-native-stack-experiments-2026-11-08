# What the native-stack experiments establish

We exercised the feasible open questions in a dedicated public repository:
[joshlf/gherrit-native-stack-experiments-2026-11-08](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08).
The results remove several implementation uncertainties and contradict a few
assumptions in [GHerrit design issue #518](https://github.com/joshlf/gherrit/issues/518).
They do **not** establish a provider guarantee that a completed merge can never
write again, or validate a production GHerrit implementation.

All source, branches, PRs, reviews and workflow data were synthetic. Production
GHerrit refs, PRs, settings, hooks and executables were untouched. Hosted trials
ran on November 8, 2026, using REST version `2026-03-10`, `gh` 2.102.0, and the
official `gh-stack` v0.3.0 binary in a private experiment directory. The source
study pins `github/gh-stack` at `bd0a32504f9ae9f795875a9e6bb90ff7408fda08`.

## Findings that change the design's factual premises

**Completed groups accepted new work.** Group #28 was closed with all members
merged. Appending D reopened that same group; appending E and subsequently
landing D also succeeded. E was then released and registered with F in a new
group. The earlier assertion that completed groups cannot accept append is too
strong for this host. Regrouping remains useful, but is not the only observed
continuation. This discrepancy with documentation still needs an upstream
contract answer. See [lifecycle results](api/RESULTS.md).

**First CI has a concrete scheduling path.** Registration emitted actual
`pull_request` events with `action: stacked`. A workflow explicitly listening to
`stacked`, with a trunk branch filter, ran for the existing upper PR and supplied
its required check. A workflow whose types excluded `stacked` did not run on
registration. Manual dispatch produced a green check on the upper head but did
not clear that PR's required gate. `gh pr checks --required` also missed the
upper PR's native-trunk requirement. Trunk routing did not imply one checkout
graph: direct event bases, `GITHUB_BASE_REF` and merge-object parents differed,
and parent topology varied by event. The linear fixtures do not establish a
general diverged-trunk graph rule. See [CI results](ci-reviews/RESULTS.md).

**Approval retention depends on the path and merge method.** With stale-review
dismissal enabled, an unchanged local atomic rebase with `pull.stacked` retained
both approvals in the tested fixture; without it, the upper approval was
dismissed. A substantive amendment carrying the hint still lost approval.
Automatic native suffix rewrites after prefix **squash** and **merge** dismissed
the upper approval despite identical layer patches; the tested **rebase** case
retained it. The native dismissal message was “The merge-base changed after
approval.” These are bounded, partly sequential controls. The website's explicit
**Rebase stack** operation was not tested. See [review conditions and exact
comparisons](ci-reviews/RESULTS.md#review-retention-with-a-distinct-pr-author).

**Auto-merge was explicitly unavailable for native stacks.** After temporarily
enabling the repository feature and holding a required check, the actual GraphQL
mutation returned “Auto-merge is not supported for stacked pull requests.” A
positive capability boolean had not established support. The original setting
was restored; neither PR has an armed request. See [auto-merge
results](auto-merge-capability/RESULTS.md).

**Verified suffix commits can remain verified.** A required-signature fixture
rejected an unsigned lower source. With a verified lower source, the native
rewrite produced a verified upper replacement while retaining its exact layer
patch, author and message. A separate unprotected fixture began with a verified
upper source and also produced a verified replacement. Other unsigned fixtures
stayed unsigned. These observations do not support either a universal
signature-loss claim or a universal signing promise. See the [signature
controls](ci-reviews/RESULTS.md#required-signature-control).

**History-comment mechanics work, with limits.** A separately owned comment kept
a stable ID through updates; deletion was detected and explicit reattachment
created a new ID. Concurrent PR-body and history-comment updates preserved both
artifacts, while a stale whole-body write overwrote newer synthetic body text.
The pin mutation rejected the PR with “Issue cannot be a pull request,” despite
`viewerCanPin: true`. The API accepted exactly 262,144 ASCII bytes and rejected
262,145 in the bounded probe; the server error still mentioned 65,536 characters.
These are measured payloads, not a universal Unicode limit or a human usability
study. See [history results](cli-history/RESULTS.md) and the
[concurrent-write control](cli-history/CONCURRENT-HISTORY.md).

## Findings that support the proposed mechanisms

The real-Git import prototype completed **122 checks**, with retained negative
controls that expose plausible wrong models. It exercised repeated import,
amend/rebase/revert/reset, retained local edits, conflicts, per-layer patch
attribution, changed parents, dirty/staged/untracked inputs, moving source tips,
eight SIGKILL boundaries and unresolved publisher transfer. The negative controls
show why the incorporated hosted basis and last authored submission need to
remain separate. See [local algorithm results](local-git/RESULTS.md).

The connected hosted test completed **A–B → landed A → F–B → landed F → imported
B again**. F was required below B by an executable dependency. B retained its
original PR/node identity, and old/new authored archives kept exact targets.
The second import either selected the exact hosted range with no remote write,
or retained only the edit made after the captured submission. This was a
prototype using actual native outcomes, not migrated GHerrit code. Its 137
executed assertions include two retained failures: an inconsistent post-merge
read, and an incorrect 204-only unstack oracle. See the [hosted integration
report](local-git/hosted-integration/RESULTS.md).

Structural trials preserved canonical reviews through reorder, insertion, drop,
fold and a trunk change using release → park → atomic heads/archives → final
bases → register. A negative control omitting parking caused GitHub to mark the
moved PR merged into another head; reopening and base repair were rejected.
This confirms a real lifecycle hazard and supports the tested parking sequence.
It does not establish a cross-resource transaction. See
[structural evidence](api/RESULTS.md#structural-changes-and-the-lifecycle-hazard).

An actual atomic Git push rejected the entire vector after a wrong lease. The
equivalent non-atomic control partially published heads and archives despite
failure. An async 409 returned the **existing** request's method and UUID when a
new request asked for a different method. The adapter must compare the receipt
to its own intent. A selected-SHA race landed the requested old content while a
later head push remained on the merged PR's branch. Closed-middle and
required-check failures left their prefixes unmerged; one pending-merge/unstack
race failed cleanly. These finite traces guide recovery, but are not universal
race guarantees. See [race results](api/RESULTS.md).

Three real hosted writes also completed while their client processes were killed
before accepting acknowledgements. Sole-writer recovery recognized positive
create/append transitions without resending. The client retained an unresolved
unstack because membership absence alone did not settle its old dispatch; an
independent oracle confirmed actual success. This tests conservative recovery
after an injected client failure, not provider idempotency or a real network
timeout. See [lost-receipt evidence](api/RESULTS.md#lost-acknowledgements-without-blind-retries).

The released CLI was dynamically checked. Recognized PR URLs with correct bases
did not push branches in the tested link call. Wrong bases were repaired before
registration, and `--open` made drafts ready even when a later order check
failed. Bare numeric arguments collided with local branch names. Broad submit
pushed branch refs atomically but omitted the archive tag. The CLI can still earn
a narrow adapter role, but it does not remove GHerrit's effect accounting. See
[CLI controls](cli-history/RESULTS.md).

A real pre-push hook ran during outer `git push --dry-run` and published through
its own nested push. The captured argv, stdin, working directory and selected
standard Git environment matched the actual-push case. That supports the explicit
invocation proposal's concern; it does not prove that every possible dry-run
detection mechanism is unavailable. See [hook results](cli-history/hook-dryrun/RESULTS.md).

## What remains open, and why more of these experiments cannot settle it

| Question | What we learned | Remaining boundary |
| --- | --- | --- |
| When is republishing after native work safe? | Two fixtures exposed PR-head/Git-ref disagreement around terminal success; one did so in strictly subsequent reads. Later reads converged. | Cached reads, replication and progressing writes are not distinguished. No finite quiet period proves no future write. A provider contract or explicitly weaker recovery promise remains necessary. |
| Does import work through real native changes? | Local fixtures and one connected two-cycle hosted workflow succeeded with exact layer trees and canonical B. | General mapping, all histories, signing UX and implementation correctness still need code and acceptance tests. |
| Can every interruption recover? | Real hosted lost-receipt boundaries and local SIGKILL/ref-checkpoint cases support the conservative policy. | This is not exhaustive crash/power-loss coverage, API idempotency, or authority over independent writers. |
| Can canonical PRs survive structural editing? | Safe trials passed and the unsafe control reproduced irreversible marked-merged state. Partial unstack retained the merged member and released the open one. | Queue locks, unobserved pending effects and arbitrary concurrent lifecycle changes remain outside the supported evidence. |
| Does first CI run? | Explicit `stacked` activity plus trunk filtering supplied the upper gate. Dispatch alone did not. | Queue/`merge_group` behavior and a target repository's own workflows require their own tests. |
| Do queue admission, failure and cancellation work? | The exact merge-queue ruleset was rejected with 422. No queue was created. | This is a user-owned repository; current documentation limits public merge queues to organization-owned repositories. The API error itself did not identify the cause. An authorized eligible organization repository is needed. See [queue capability](queue-capability/RESULTS.md). |
| Can the native UI supply a usable receipt, and do reviewers find history? | API receipts and history storage were tested. | Browser access was unavailable, and native Chrome control failed before any interaction. UI-only Rebase stack, receipt capture and an actual reviewer walkthrough remain untested. |
| Which invocation and publisher architecture should we choose? | Hook and CLI controls expose concrete costs; separate history avoids whole-body contention. | Explicit commands versus a compatible hook, one publisher versus a service, and richer authoring are product/design choices. API experiments alone cannot choose their acceptable tradeoffs. |

We did not create more than 100 PRs merely to rediscover a documented limit,
create or use another organization's repository, invent a human usability study,
or run expensive builds. Multi-commit local authoring groups, shared-prefix forks and larger
groups still need an explicit mapping/publication policy before its behavior
can be meaningfully tested.

## Evidence and restoration

Each lane's report links machine summaries, source harnesses and raw evidence.
Failed assumptions and runner versions are retained. Some source scripts bind
to these exact resources and intentionally refuse replay: they are evidence of
the executed experiment, not a production client or a safe general-purpose tool.
The full local archive includes Git object stores and downloaded Actions event
artifacts so that later agents need not repeat the hosted work.

The two temporary repository feature settings were restored: workflow defaults
are read-only, Actions may not create/approve PRs, and `allow_auto_merge` is false.
The six bot-creation runs completed; no auto-merge request was armed. Exact
branch protections on synthetic trunks remain part of the fixtures. No scheduled
automation was installed. All synthetic refs, PRs, archives and evidence are
retained for inspection.

*Authored by an AI agent acting on joshlf's behalf.*
