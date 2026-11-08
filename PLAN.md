# GHerrit native-stack experiments

Authorized by the user's request to perform all feasible open experiments using
experiment branches or a dedicated repository. Hosted work is confined to
https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08.
No GHerrit production refs, settings, PRs, hooks or executables are modified.
All data are synthetic. Retain source objects, intents, results and failures.

## Ownership

- Root: main/bootstrap/global settings, remote exp/api/** and queue capability,
  structural edits, async merge timelines, lifecycle, failure boundaries, UI.
- CLI/history agent: remote exp/cli/** and its own PRs/comments/groups; local cli-history/.
- CI/reviews agent: remote exp/ci/** and exact matching protection, its own PRs;
  local ci-reviews/. Root supplies shared read-only workflow interfaces.
- Local Git agent: local-git/ only, real-Git import and local recovery fixtures.

No agent changes another lane or global settings/main. Settings changes are
recorded and apply only to this new experiment repository. No scheduled jobs,
external collaborators, paid runners, publication to other projects or stress tests.

## Questions and discriminating checks

1. Capture actual Git/PR/native state before/after first creation, duplicate writes,
   append, closure/reopen, unstack and completed-group continuation. Check exact
   identities and residual membership rather than exit status alone.
2. Observe direct async merge/squash/rebase of prefixes and full groups. Record
   request UUID, poll result, all member heads/bases/refs/trees and signed metadata
   over a bounded follow-up. Exercise race/cancellation and cross-operation
   interference cases on disposable fixtures. Finite quiet periods never prove
   no delayed provider write can occur.
3. Compare unsafe head reorder with release/park/atomic push/final bases/register;
   test insert/drop/fold/trunk changes and the ordinary F-before-B continuation.
   Assert canonical PR lifecycle, exact intended trees/ranges and archives.
4. Establish initial CI/event scheduling, stack metadata/test-merge graph and an
   actual dispatch repair path. Check matching workflow/run/head identities.
   Test queue capability/rules before inferring queue behavior; unsupported plans
   or missing second-actor permissions are explicit limitations.
5. Test review retention under stale dismissal using separate bot PR authors and
   the existing user reviewer, plus force-push hints/substantive changes/native
   rewrites and signatures. Experimental reviews are labeled as such.
6. Check the official CLI's narrow PR-URL boundary against exact side effects,
   numeric argument ambiguity, and branch/archive publication behavior. Prototype
   generated history in a separate comment, preserving human body edits and exact
   historical patch comparisons; API availability is not a reviewer-usability proof.
7. Use real Git for repeated I/L/H import, conflicts and per-change attribution,
   lower-only subsequent edits, parent drift, landed amendments, dirty work and
   source-tip races. Fault-inject local journals/acceptance/transfer and explicit
   lost-receipt boundaries. Prototype evidence is not deployed GHerrit correctness.

Every case records its hypothesis, setup, exact resources, observation/oracle,
result and limits. Unexpected results remain evidence rather than weakened tests.
One client dispatch is logged before each write; no blind retries of uncertain
mutations. Provider/platform scope is stated, not derived from a desired result.

*Authored by an AI agent acting on joshlf's behalf.*
