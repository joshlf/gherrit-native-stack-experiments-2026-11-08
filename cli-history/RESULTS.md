# CLI and history results

The released `github/gh-stack` v0.3.0 can provide the proposed narrow URL-based
membership path under explicit preconditions. It is not an interchangeable full
publisher for GHerrit's coupled heads-and-archives contract. The independent
history-comment prototype preserves human-owned PR text, but PR-comment pinning
is unavailable on the tested API path and reviewer usability remains untested.

All writes used synthetic resources in
[joshlf/gherrit-native-stack-experiments-2026-11-08](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08),
confined to `exp/cli/**` refs and this lane's PRs/comments/groups. GHerrit source,
production repositories, global hooks, global configuration and global extension
installation were not changed. The executable is private to `bin/`; release
metadata and its SHA-256 are retained in `evidence/`.

## Observed CLI behavior

| Experiment | Result | Evidence |
| --- | --- | --- |
| Canonical URLs for PRs #1/#2, correct adjacent bases, explicit `--base main`, no `--open` | Stack #7 created. Exact owned refs, PR identities, heads/bases, title/body, draft states and auto-merge state were unchanged. | `before-url-link-*`, `after-url-link-*`, `url-link.*` |
| Canonical URLs for PRs #3/#4 with upper PR initially based on main | CLI repaired #4's base to `exp/cli/c`, then created stack #8. Text, readiness and refs were preserved. URLs alone therefore do not imply membership-only effects. | `before-base-link-*`, `after-base-link-*` |
| A local branch literally named `1`, with a local bare sink selected as push remote | Canonical URLs left the sink empty. Bare numeric `1 2` pushed branch `1` before resolving those same PRs. No numeric GitHub ref was created. | `numeric-*`, `canonical-url-with-sink.*` |
| Private Git shim runs real local-sink push, then reports failure | CLI exited 1, while the sink gained branch `3`. Hosted refs/PRs remained unchanged. This is a deterministic subprocess fault injection, not an observed provider failure. | `subprocess-lost-success.*`, `lost-signal-*` |
| Existing stack #8 passed in reversed order | GitHub rejected both incompatible base changes with 422; CLI then exited 5 for additive-order refusal. Refs/bases/membership/readiness remained unchanged. | `reorder-link-rejected.*`, `before/after-reorder-link-*` |
| Same reversed order with explicit `--open` | CLI again exited 5, but both draft PRs became ready before the refusal. Failed CLI status did not mean no effects. | `open-reorder-link-rejected.*`, `before/after-open-reorder-link-*` |
| Broader `submit --auto --remote origin` with a local archive tag | Exact trace shows an atomic, explicitly leased branch-only push. `exp/cli/b` moved to `7238c801660d738d3403e1bff2ab5dd5b331b382`; the archive tag remained absent remotely. | `broad-submit-origin.git-trace`, `before/after-broad-submit-*` |

The first broad-submit invocation refused ambiguous configured remotes before any
fetch/push. Its trace and reread refs/PRs established that boundary before the
separate explicit-origin invocation. No uncertain mutation was blindly retried.
The successful push's send-pack trace also omitted the unchanged A lease,
consistent with the design's warning about equal refs being ineffective guards.

A constrained adapter must therefore validate canonical same-repository URLs,
required order/bases and lifecycle, choose the trunk explicitly, exclude
`--open`, pin the binary/version contract, and reconcile every effect after
failure. These observations do not supply a provider completion guarantee.

## History prototype

[PR #10](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/10)
has an independently owned
[history comment](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/10#issuecomment-6728278369).
The comment uses a stable artifact marker, with its PR and GitHub comment/node IDs
bound in `history-binding.json`. REST listing found it, and PATCH retained its
original ID during ordinary updates. A separately simulated PR-body edit survived
both history updates and reattachment; this was an API separation exercise, not
a real second human or a concurrency test.

Exact base/tip tags under `exp/cli/history/` retain two authored submissions.
Each exact GitHub comparison contains only `history-change.txt`. Comparing their
tips also includes `history-trunk-drift.txt`, an unrelated parent change. The
comment labels that distinction and links both exact patches. It does not claim
an ancestry-independent range-to-range “changes since review” implementation.

Deletion deliberately removed original comment `6728274710`. Reading that ID
returned 404 and listing found no marker. The journal then recorded an explicit
reattach decision, producing replacement `6728278369` with the same artifact
marker and retained history. The old direct URL cannot be retained across this
loss. A read-only local resolver also checks the bound actor/PR/marker and stops
on synthetic duplicate, foreign-actor, wrong-PR and edited-marker snapshots;
listed candidates require an explicit reattachment decision. These local controls
are saved in `history-identity-policy-results.json`. A missing scan alone would not settle an earlier unknown create; this test
used an acknowledged creation/update/deletion sequence.

GraphQL exposes `pinIssueComment`, `isPinned` and `viewerCanPin`. For this PR
comment, `viewerCanPin` was true, but the mutation was rejected as UNPROCESSABLE:
“Issue cannot be a pull request.” Readback confirmed `isPinned=false`. Schema
presence and permission booleans did not establish PR applicability. No successful
pin/unpin cycle occurred, and the final comment remains unpinned.

## Size and rendering bounds

Exact request/returned-body and GET equality, including SHA-256, establish:

| Body | Observed result |
| --- | --- |
| 65,536 ASCII characters | Accepted. |
| 65,537 ASCII characters | Accepted; GET matched the exact sent body. |
| 262,144 ASCII characters/bytes | Accepted; GET matched SHA-256 `e7cc8e8b7173db3617c6baeea5805150c34c0965665a5cf102d0c0b90df328ba`. |
| 262,145 ASCII characters/bytes | Rejected 422, with error text claiming “maximum is 65536 characters.” |
| 131,115 Unicode characters, 262,144 UTF-8 bytes | Accepted; GET matched SHA-256 `691a5fd3107266d8b0a8b63a0e60ed71f5fbc8eecc348ff14647293d6b004e03`. |

The bounded larger probe used six calls and restored the small size-probe note.
This establishes the observed ASCII boundary on this path, not a general Unicode
or server-wide limit. Full-media API output included HTML for the 65,537-character
body; HTML availability is not evidence that a large comment is readable.

A local prototype checks a conservative 60,000 UTF-8-byte rendering budget,
including ASCII/Unicode boundary controls. Its over-budget policy retains the
prior comment and journal and requires an explicit alternate-history decision;
it never silently truncates exact history. This policy is not integrated into
GHerrit and has not been validated with reviewers.

## Reproduction and limits

`run.py` and `history.py` retain the intended transitions and refuse to reuse a
recorded mutation identity. Do not rerun them against the retained resources as
though they were idempotent. `journal.jsonl` records dispatch intent and observed
subprocess responses. `evidence/` contains requests, raw public responses,
commands, exit codes and before/after refs and PR state. `analyze.py` reruns only
local assertions; all 14 checks pass in `RESULTS.json`.

The remaining work is a reviewer walkthrough in a long discussion, reliable
visibility without PR-comment pinning, role/permission tests with another actor,
real multi-actor duplicate-marker and human-edit behavior, true concurrent body/history updates,
and recovery after an actually indeterminate API write. The prototype does not
claim a complete reviewer interface, production GHerrit implementation, global
write exclusion, cross-resource atomicity or a native-provider handoff guarantee.

*Authored by an AI agent acting on joshlf's behalf.*
