# Factual corrections for design issue #518

This audit compares the local `body-final.md` with the November 8 experiment
evidence. The audited body SHA-256 is
`f0480a3506a888537fad12217bb4e39f160707548af6ab22eea61bcfbaef3cea`.
Line references name that revision. This is a bounded correction list, not a new
design. No remote reads or writes were needed; the recorded source and evidence
were inspected locally.

## Statements that must change

1. **Completed native groups cannot be extended — line 127.** This is contradicted
   by the observed host. Group #28 was `open:false`, with #25/#26/#27 all merged.
   Appending D #29 returned 200 and the same group became `open:true`, retaining
   those historical members. The intervening unstack had returned 422. Replace
   the platform prohibition with this conditional observation. If the proposal
   still selects a new group for later work, label that a client policy rather
   than an API necessity. Do not treat the subsequent D/E new-group 422 as an
   independent continuation failure: D had actually joined #28. A later explicit
   release followed by E/F registration succeeded as group #61.
   Evidence: [`api/basic-results.json`](api/basic-results.json),
   [`complete-append-rejected.meta.json`](api/evidence/complete-append-rejected.meta.json),
   [`api/structure-results.json`](api/structure-results.json).

2. **No CLI adapter behavior has been dynamically validated — line 230.** This is
   now false. Released v0.3.0 URL linking created native groups; with correct
   adjacent bases and no `--open`, it preserved the tested refs, identities,
   prose, readiness, and auto-merge state. It also repaired a wrong base in a
   separate fixture. Canonical URLs therefore avoided branch pushes but did not
   imply membership-only effects. Bare numeric identifiers pushed a colliding
   local branch; explicit `--open` changed draft state before a later refusal.
   Replace the untested-status sentence with those bounded results and the
   adapter's actual preconditions. The broader branch-only atomic submit trace
   **confirms**, rather than removes, the heads-plus-archives limitation in line
   228. Starting with direct typed APIs remains a design choice.
   Evidence: [`cli-history/RESULTS.md`](cli-history/RESULTS.md).

3. **Treat `types: [stacked]` only as an unverified assumption — line 248.** The
   caution was appropriate before testing, but the Actions trigger is now
   directly observed on this host: registration emitted `pull_request` with
   `action: stacked`; an explicit stacked workflow ran for both members. An
   adoption workflow listing `[opened, synchronize, reopened, stacked]` with the
   trunk filter supplied the upper's required context and made its gate CLEAN.
   Replace agnosticism with that observed path, while retaining the first-open
   warning. Explicit default activity types excluding `stacked` did not rerun at
   registration. A successful branch workflow dispatch did not repair the PR
   gate in its control, despite a successful head check. Do not present dispatch
   as an already validated repair.
   Evidence: [`ci-reviews/RESULTS.md`](ci-reviews/RESULTS.md), first-publication and
   adoption sections, including runs 42532221810 and 42532454006.

4. **The validation checks have not been run — line 262; future-only status in
   lines 9, 105, and 169.** The blanket statement is obsolete. Replace it with
   completed bounded coverage and remaining gates. Real Git fixtures, actual
   native methods, same-order atomic amendment/rejection controls, structural
   sequences, partial unstack, CLI behavior, CI adoption, history prototypes,
   local interrupted-prefix/transfer policy, and one hosted repeated F-before-B
   workflow now have evidence. These are experiment implementations, not deployed
   GHerrit. The hosted integration retains two failed checks: an actual inconsistent
   observation and a corrected 204-only client unstack oracle. Do not report all
   validation as complete or all cases green. Queue execution, human walkthroughs,
   arbitrary writers, general mapping/signing UX, and provider settlement remain
   unestablished. One downstack-race case also retains a harness exception and
   must not be counted as a passed case from its result entry alone.
   Evidence: [`local-git/RESULTS.md`](local-git/RESULTS.md),
   [`hosted integration`](local-git/hosted-integration/RESULTS.md),
   [`api/race-results.json`](api/race-results.json), and the lane reports below.

## Replace broad uncertainty with the specific observed limits

5. **Signing — lines 49, 167, and the validation list.** Keep the requirement for
   explicit signing decisions, but record the observed rule dependence. With no
   signature rule, the basic replacement B/C heads were unsigned for merge,
   squash, and rebase; final merge/squash landing commits were verified, while
   rebase's final landing was unsigned. This did not test stripping an existing
   signature because source heads were unsigned. Under an enforced signature
   rule, unsigned lower input was rejected. In a separate successful fixture,
   verified lower input landed and an unsigned upper was rewritten into a
   verified commit while preserving author name/email/date, message/trailer,
   full tree, and exact layer diff. A final fresh unprotected fixture used a
   verified original upper (`7c586aee...`) and produced a verified replacement
   (`4dfc140b...`), again retaining the exact patch/tree/author/message. Its new
   signature and signed payload differed: this was a verified replacement,
   not retention of the original signed object. Neither server creation nor a
   general native rewrite should be described as always signed or always unsigned.
   Evidence: [`api/basic-results.json`](api/basic-results.json),
   [`ci-reviews/RESULTS.md`](ci-reviews/RESULTS.md), required-signature section.

6. **Approval retention — lines 47, 49, and 216.** The meaning of `pull.stacked`
   as an unchanged-rebase hint remains supported. The controls now add concrete
   limits: the hinted unchanged local rewrite retained both approvals; a no-hint
   rewrite retained the lower but dismissed the upper; a substantive hinted
   amendment dismissed its upper approval. Native automatic prefix landing under
   one-approval/stale-dismissal rules dismissed unchanged upper approvals for the
   observed squash and merge cases, with the reason that the merge base changed;
   the rebase case retained approval. Merge/rebase reused reapproved earlier
   fixtures, so these are sequential observations, not independent replications.
   The explicit website **Rebase stack** button was not tested. Do not equate it
   with automatic suffix rewrites or promise universal native approval retention.
   Evidence: [`ci-reviews/RESULTS.md`](ci-reviews/RESULTS.md), review-retention
   section.

7. **Auto-merge — line 49.** Universal availability is still unsupported, and the
   tested host now has a discriminating negative result. With the repository
   option explicitly enabled, real pending required checks, a positive viewer
   permission boolean, and an expected-head guard, native auto-merge was rejected
   as unsupported. Readback retained null requests and unchanged refs; the option
   was restored. Report that result, not an inferred permanent global prohibition.
   Accepted auto-merge and automatic prefix landing were not exercised.
   Evidence: [`auto-merge-capability/RESULTS.md`](auto-merge-capability/RESULTS.md).

8. **Queue — lines 49, 142, 248, and 260.** The experimental repository is public
   and user-owned. A schema-validated queue ruleset request returned 422; no queue
   PR/group/enqueue was created. Current documentation's organization-owned
   eligibility restriction fits that rejection, but the generic API error does
   not independently prove its cause. Admission versus landing, `merge_group`
   coverage, ejection, queued unstack, and cancellation remain untested. Ordinary
   direct native merges and pending async work are not merge-queue evidence.
   Evidence: [`queue-capability/RESULTS.md`](queue-capability/RESULTS.md).

9. **History comment status — lines 103–107 and 239.** The separate owned-comment
   choice remains a choice. A bounded prototype now exists: bound comment identity,
   exact historical ranges, ordinary updates, acknowledged deletion/explicit
   reattachment, and local identity controls were exercised while keeping prose
   separate. An additional same-account subprocess experiment preserved concurrent
   body/comment updates, while a stale whole-body write overwrote newer synthetic
   text. Its request intervals overlapped; server ordering/CAS and independent
   human actors were not established. Pinning this PR comment was rejected despite
   `viewerCanPin=true`; discoverability in a long discussion remains untested.
   Size probes accepted 262,144 ASCII bytes and rejected 262,145 on that path,
   even though the error claimed a 65,536-character maximum. The prototype's
   conservative 60,000-byte budget is its policy, not a universal server limit.
   Unknown comment-create recovery, cross-role permissions, reviewer usability,
   and ancestry-independent range-to-range comparison remain unproved.
   Evidence: [`cli-history/RESULTS.md`](cli-history/RESULTS.md),
   [`concurrent-history/RESULTS.json`](cli-history/concurrent-history/RESULTS.json).

10. **Hook dry-run caution — line 236.** Keep the caution and add its empirical
    basis: outer `git push --dry-run` ran a local hook that successfully published
    to its separate inner sink. Captured standard hook inputs were identical to
    the actual-push case. The outer sink stayed empty. This demonstrates that an
    inner publisher does not inherit dry-run semantics automatically; it does not
    prove that every possible detection mechanism is impossible.
    Evidence: [`hook-dryrun/RESULTS.md`](cli-history/hook-dryrun/RESULTS.md).

## Findings that strengthen existing qualifications

The provider-handoff gate in lines 195–201 remains unresolved. The integration's
terminal-merged receipt was followed by a PR read reporting old B's head with the
new trunk base, while the subsequent ref read reported rewritten B. Both B trees
were identical, with different parents. The sequence does not identify cache lag
versus a progressing rewrite, and it does not locate a ref change after the
terminal receipt. Later coherent reads and successful continuation establish a
finite trace, not settlement. Keep this distinction prominent.

The structural sequence now has successful controlled traces and a negative
control. Reorder, insertion, drop, fold, and trunk change retained canonical
identities and archives in the parked sequence. The unsafe reorder path recorded
`merged:true` for B while the trunk stayed unchanged, followed by rejected
base repair/reopen attempts; this was not a closed-unmerged review. Partial release actually returned
200 with merged historical members retained. None of those traces supplies a
global transaction or lifecycle guarantee. The hosted F-before-B case confirmed
parking was already satisfied; it did not itself test a nontrivial parking PATCH.

The local interrupted-prefix harness and hosted lost-receipt experiments support
the recovery distinctions, without establishing a general idempotency service.
Hosted faults were injected after actual acknowledgements; create/append had
isolated positive evidence, while client-side unstack remained unresolved from
absence alone. Keep unknown outcomes distinct from rejection and retain the
single-writer attribution limit.

## Choices and guarantees this audit does not change

Explicit commands versus hooks, direct APIs versus a constrained CLI adapter,
one publisher versus a service, canonical PR continuity, human-owned prose,
owned history comments, one-commit local input, immutable exact archives,
new-ID follow-ups for terminal changes, and fresh continuation acceptance are
selected policies. The experiments add evidence and costs; they do not turn
those selections into platform requirements or mandate different choices.

No experiment implements production GHerrit native publication or proves delayed
native effects have ceased. Arbitrary multi-writer exclusion, UI intent capture,
general change mapping, all review/rule combinations, queue behavior, real human
usability, and exhaustive interruption/power-loss recovery remain beyond the
evidence. Do not remove those limits when correcting the factual passages.

## Fresh read of the experiment overview

The overview `RESULTS.md` at SHA-256
`505651eb0b2b2da8ac969597ca69323f84c0928a4b67a1f95a54e474adaebd53`
matches the lane reports on its main findings. Its relative report links resolve.
The final unprotected verified-original/verified-replacement case is now present
in the CI lane report and supports the overview's signing statement.

Two precision corrections remain:

- The provider-handoff table says terminal success was followed by a mismatch
  in two fixtures. The observer's D GET overlapped the terminal poll; the hosted
  integration's reads were strictly subsequent. Suggested factual wording:
  “Two fixtures exposed PR/ref disagreement around terminal success; one did so
  in strictly subsequent reads. Later reads converged.”
- The final paragraph should say “multi-commit local authoring groups,” rather
  than the broader “multi-commit layers,” when describing unmapped future work.
  The local harness already exercised a two-commit hosted range.

Two short scope qualifiers would make the summary easier to read independently:

- Identify the concurrent body/history actors as same-account programmed
  subprocesses with overlapping client intervals. The experiment did not observe
  server ordering or establish cross-role permissions.
- Distinguish the observed CI scheduling/trunk-filter routing from a general
  checkout-graph guarantee. Event-specific merge parents differed in the linear
  fixtures, and diverged-trunk/queue integration graphs remain untested.

*Authored by an AI agent acting on joshlf's behalf.*
