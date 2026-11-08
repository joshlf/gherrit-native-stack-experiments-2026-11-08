# CI observations

These are live observations on November 8, 2026 in the public synthetic repository `joshlf/gherrit-native-stack-experiments-2026-11-08`. They establish the recorded traces on this host. They do not establish universal rollout, a future API contract, or the absence of later effects.

## First publication without a stacked activity type

PRs [#5](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/5) and [#6](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/6) were opened separately at 22:50 UTC over `exp/ci/initial/trunk`. Their heads were `997f486e9ce884ef20100499d56905d0c495f545` and `ae2f8017a6660746fb96e7d58f49b39f3dff473d`. The seed was `ed86001d0772bad37723d34c42172793a1065def`.

On the first `opened` event, the lower PR ran both unfiltered `observe` and `trunk-filter`; the upper PR ran only `observe`. Both event payloads had `stack: null`. The trunk-filter workflow listened to `opened`, `synchronize`, and `reopened`, with branches `[main, 'exp/**/trunk']`.

After the exact trunk gained required check `trunk-filter`, registration created stack #9 at 22:50:24Z. Registration emitted `pull_request` events with `action: stacked` for both existing PRs. The `types: [stacked]` workflow actually ran and succeeded: lower [42532221687](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/actions/runs/42532221687), upper [42532221810](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/actions/runs/42532221810). Their event payloads contained stack size 2, positions 1/2, and the correct trunk ref/SHA. Registration did not trigger the workflow whose explicit types excluded `stacked`. The upper PR remained `mergeStateStatus: BLOCKED`.

A supported workflow dispatch against the upper branch produced successful `trunk-filter` run [42532273639](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/actions/runs/42532273639). It checked out the raw upper head `ae2f8017...`, used a branch ref, and had no PR or stack event data. REST `commits/{head}/check-runs` showed its successful check on that head. A later PR GraphQL snapshot omitted that dispatch check from `statusCheckRollup`, and the upper PR remained `BLOCKED`. This dispatch alone did **not demonstrate a repaired PR gate**.

A subsequent labeled empty commit on the registered upper branch changed its head to `59b8824c75ddeb4282baecbf21d225d8a0cde82f`. Its `synchronize` event ran both `observe` and [trunk-filter 42532354077](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/actions/runs/42532354077), even though the direct PR base remained the lower branch. The upper PR then became `CLEAN`, with the required context in its PR rollup. No PR was closed or reopened.

That later synchronize run used merge object `e8c26972deb4143b501450bd343136357091aeac`, whose first parent was the lower PR's synthetic merge object `f3a323e33770969b9ad2ef6a4970f8f8beb5b518`, rather than the direct lower head seen at first open and registration. The linear fixture's tree stayed equal. The artifacts therefore support event-specific graph observations, not a single inferred graph rule.

`gh pr checks --required` reported no required checks for the upper PR because its direct base branch had no protection. That command's output did not describe the native trunk's check requirement; the PR GraphQL state still showed the upper gate blocked before its later PR-event run.

## An explicit stacked activity type supplies an adoption path

PRs [#11](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/11) and [#12](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/12) used a separate trunk, `exp/ci/adoption/trunk`. A distinct `.github/workflows/stacked-trunk.yml` existed only in that fixture's branches, introduced by trunk commit `e67444e5247309469fe75b1936218eb276a33b29`; neither main nor the shared negative-control workflow changed. The variant used the same trunk branch filter and explicitly listed `types: [opened, synchronize, reopened, stacked]`.

Before adoption, only the lower PR received `stacked-trunk` on `opened`; upper PR #12 received only unfiltered `observe`. The exact trunk then required `stacked-trunk`, with admin enforcement enabled and no required review. Registration created native stack #13 at 22:53:19Z. The upper's [stacked-trunk run 42532454006](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/actions/runs/42532454006) started at 22:53:24Z and succeeded at 22:53:29Z. The later upper PR snapshot showed `CLEAN` and included that successful required context in `statusCheckRollup`.

The upper event's `pull_request.base.ref` remained `exp/ci/adoption/lower`, while `GITHUB_BASE_REF` was `exp/ci/adoption/trunk`. Checkout used `refs/pull/12/merge`, object `0d9754604a7bd854ffe196da63c7e7b387d5a8af`, with parents `c61a9e147aabde79f9e36c38649d98a8844aaf00` (direct lower) and `7ba2c40fe6508b0cf4fa656a0d2abf4ccedb1f44` (upper head). Thus the observed trunk routing did not change this test merge object's first parent to the trunk. The fixture was linear, and this experiment did not test a diverged trunk or merge queue.

This trace establishes a first-check path for adopting existing PRs on the tested host: explicitly include `stacked` among PR activity types, filter against the stack trunk, and retain the unfiltered first-open path where needed. It does not justify assuming that default PR activity types include registration or that a manually dispatched branch run attaches to the PR gate.

## Evidence and remaining work

`state.json` binds all branches, PRs and stack IDs. `lab.py` records exact argv, timestamps, requests and responses under `evidence/commands.jsonl`; snapshots preserve full PR, review, commit, check, timeline, membership and ref data. `evidence/actions/<run-id>/` contains downloaded event payloads and actual checkout graphs. The fixture checkout preserves exact workflow sources and commit objects.

Merge-group coverage is not established by these PR-event runs. The later distinct-author review experiments below used the user's explicit approval for temporary bot PR creation. They did not change main or the shared workflow files.

An explicit own-PR approval probe on joshlf-authored PR #5 returned HTTP 422 with `Review Can not approve your own pull request`. It created no approval. This confirms why the current token alone cannot supply the separate reviewer needed for approval-retention tests.

## Required-signature control

PRs [#14](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/14) and [#15](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/15), stack #16, used `exp/ci/signatures/trunk`. That exact classic rule enabled required signatures with admin enforcement, without check or review requirements. Both authored source commits were unsigned. A native lower-prefix squash request, expected lower head `455114ec4c7973fd8f85251c9c2fba3bafea4bc6`, returned pending UUID `bcc6b1f4-3f54-4733-916a-9b5d8d6dbcbc`; polling returned terminal `failed` with `Commits must have verified signatures.` The next snapshot retained both original heads and bases. This exercised the signing rule's rejection path; it did not exercise suffix replacement under that rule.

Creating a synthetic lower file through the GitHub Contents API on `exp/ci/signatures-server/lower` produced commit `9a486592ec7eff7d42246fbf947cc37cb5017058`. Both the write response and subsequent Git commit GET reported `verification.verified: false`, reason `unsigned`. The explicit author was the established `Josh Liebow-Feeser <hello@joshlf.com>`; GitHub chose committer `Josh Liebow-Feeser <joshlf@users.noreply.github.com>`. This branch did not proceed to upper branch or PR creation. Server creation alone did not provide a verified source commit. No signing key was read, uploaded or changed.

The successful rule path used separate PRs [#35](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/35) and [#36](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/36), stack #37. Their exact trunk, `exp/ci/signed-prefix/trunk`, required verified signatures with admin enforcement. The lower branch reused the immutable, verified GitHub squash object `b031070c2fd06ad94ce5b31f7f04fe5eb24c36f8` from the coordinator's separate experiment. Its parent `d6223f27f364a74460a907df8087d3c52331ca3d` was the new fixture's trunk; no coordinator-owned ref changed. The newly authored upper source `c7264ef3584210aaaaa875b959771dee5c11a1c9` was unsigned.

Lower-prefix squash request `163f550e-a836-4f86-be94-e62e511bf62c` reported `merged`, producing verified landed commit `7ca2b1a7a38f3b3f6f1325c121bb11b025a1c786`. GitHub retargeted upper PR #36 to the trunk and rewrote its head to `7c586aee5324ed0aed0a97c310fdab00e025b27c`. The replacement verified successfully (`reason: valid`), with committer `GitHub <noreply@github.com>` and the landed commit as parent. Exact comparisons retained the old author's name, email and author date; message and AI trailer; full tree; and the parent-to-head binary diff bytes. The old upper was unsigned and the new upper signed. `evidence/signed-prefix-comparison.json` records those checks. There were no approvals on this fixture, so this result establishes signing and attribution behavior without establishing review retention.

A final discriminator reused those exact verified commits as two layers in a fresh fixture: lower [#94](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/94), upper [#95](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/95), stack #96, trunk `exp/ci/signed-source-unprotected/trunk`. The lower source was `7ca2b1a7...`, the upper source `7c586aee...`, and the trunk their lower source's parent `d6223f27...`. Both source verifications were retained before effects. Classic protection GET returned 404 and effective branch rules returned an empty list; no signing requirement was configured.

One lower-prefix squash request, UUID `e90d9909-4f9e-4cd9-b0d1-6533fb2a9080`, reached `merged` at landed commit `349a7ed53b228caec8d31c8aecd8204a9ef8d658`. The upper retargeted to its own trunk and became `4dfc140b7876f2583b05e7ff545756772099e342`, again verified with reason `valid` and committer `GitHub <noreply@github.com>`. Exact patch bytes, complete tree, author name/email/date and message remained equal. The new signature bytes and signed payload differed from the original: the result is a verified replacement object, not preservation of the old signed object. This directly demonstrates verified-source to verified-replacement behavior without a signing rule on this tested path. It complements the unsigned-to-unsigned unprotected review fixtures and the unsigned-to-signed protected fixture; it does not establish every server-rebase signing policy.

## Review retention with a distinct PR author

Six authorized `automation.yml` dispatches created PRs as `github-actions[bot]`; their code commits retained the established human author and disclosure trailer. The reviewer was the separately authenticated joshlf user. These were explicitly labeled synthetic approvals, not independent production code reviews. Workflow defaults remained read-only. All six creation runs completed successfully, their artifacts were downloaded under `evidence/automation/`, and the coordinator restored the original approval flag before the experiments finished. No more bot jobs were dispatched.

The three exact trunks required one approving review, dismissed stale approvals, did not require a last-push or code-owner approval, and had no required checks or signatures. Admin enforcement was initially off to allow the unrelated trunk advances in the local-rebase controls. It was enabled before each native-prefix test; those merge requests recorded `bypass_rules: false`. No ordinary `opened`-event Actions runs were observed for the bot-created PRs; PAT-authenticated registration subsequently scheduled `stacked-only`. This token-trigger confound is why these fixtures are not the first-CI experiment above.

### Local forced rebases

Each two-layer stack was approved at both exact original heads. An unrelated trunk commit was then pushed, and another snapshot still showed both approvals before rebasing. Both layers were rebased locally onto that new trunk. Before pushing, the harness required each layer's full parent-to-head binary diff bytes to remain identical. Both heads were then force-pushed atomically with explicit old-SHA leases.

| Control | PRs / stack | Observed reviews after the unchanged rebase |
| --- | --- | --- |
| No push hint | Lower #38, upper #39 / #44 | Lower review `5820103454` remained approved and moved to new lower SHA `54753a3e...`. Upper review `5820103526` was dismissed; upper became `REVIEW_REQUIRED` / `BLOCKED`. |
| `push.pushOption=pull.stacked` | Lower #41, upper #40 / #45 | Both reviews `5820103617` and `5820103750` remained approved; their `commit_id` values moved to new heads `c8186300...` and `0a30619d...`. Both PRs were `APPROVED` / `CLEAN`. |

The no-hint upper dismissal occurred at 23:08:47Z, targeting replacement `4931b47cde0dac009d2951adaf7af338d5e23eb5`; its timeline supplied no dismissal message. A later sample retained that dismissal. These controls establish the recorded per-layer outcome, not that the hint is required for every unchanged rewrite: the no-hint lower approval itself survived.

A substantive forced amendment to upper PR #40 then changed its file contents and message, still carrying `pull.stacked` and an exact lease. Its head changed to `69a8e028b2a7152666e4172087fec45c411e08e1`; review `5820103750` was dismissed at 23:10:24Z, and the PR became `REVIEW_REQUIRED` / `BLOCKED`. Thus the option did not preserve the approval in this substantive-change control.

### Native lower-prefix landing

The fresh squash fixture used lower [#42](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/42), upper [#43](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/43), stack #46. The other two methods reused the local-control fixtures **after** their observations above: both current heads were explicitly reapproved and snapshotted before landing. They are sequential method comparisons, not independent fresh replications.

| Native prefix method | Upper review and exact replacement | Observed upper approval |
| --- | --- | --- |
| Squash, fresh fixture | Review `5820103907`; `bfefe5c0...` → `ec46b426c00e80638f28570a02ae39e022ee6d16` | Dismissed at 23:09:05Z; `REVIEW_REQUIRED` / `BLOCKED`. |
| Merge, reused no-hint fixture | New review `5820117259`; `4931b47c...` → `0b68062bbb3060e6232251370afecd8efea0d96b` | Dismissed at 23:12:02Z; `REVIEW_REQUIRED` / `BLOCKED`. |
| Rebase, reused hint/substantive fixture | New review `5820117408`; `69a8e028...` → `b553aa5fc10118466b143d2e590f546e58b3f12b` | Retained; review `commit_id` moved to the new head; `APPROVED` / `CLEAN`. |

All three lower-prefix requests reached terminal `merged`; all upper PRs stayed open and retargeted to their own trunk. For every method, the exact own-layer binary diff, complete tree, author name/email/date, and message including its AI trailer were equal before and after the native rewrite. Both dismissed native reviews had the explicit timeline message `The merge-base changed after approval.` The replacements in these fixtures remained unsigned and used committer `Josh Liebow-Feeser <joshlf@users.noreply.github.com>`; the separate signature-rule fixture above demonstrates the different rule context.

The observations concern **automatic rewrites after prefix landing**. The website's explicit **Rebase stack** button was not exercised. The results therefore should not be reported as a test of that button's documented approval-retention promise, nor as proof that all native rebases preserve or dismiss approval. Exact method, rule, author and sequential-fixture conditions matter. Later finite samples are recorded without claiming that they establish server settlement.

*Authored by an AI agent acting on joshlf's behalf.*
