# Native auto-merge capability result

The native-stack auto-merge mutation was explicitly rejected on this host:
`Auto-merge is not supported for stacked pull requests.` The repository option
was enabled for the probe, then restored to its original false value and
independently read back. Neither PR remains armed, and no check was released.

The fixture consists of [PR #80](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/80)
and [PR #81](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/81),
in [stack #82](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/stack/82).
Only new `exp/auto/**` refs and these reviews were used. The exact trunk
`exp/auto/trunk` requires the synthetic `exp-auto-held` status, including for
administrators. The requirement was installed before opening the PRs. Pending
statuses were posted to both authored heads and the observed lower test-merge
commit. Required-check inspection showed PENDING on both PRs, and GraphQL
reported both as BLOCKED before the mutation.

## Discriminating observations

| Boundary | Observation |
| --- | --- |
| Repository capability option | Original `allow_auto_merge=false`; authorized PATCH set true; subsequent preflight read confirmed true. |
| Native membership | Explicit ordered stack #82 contains #80 then #81. |
| Precondition | Selected lower member #80 was open, unmerged, blocked by the required status and had no auto-merge request. |
| Permission field | `viewerCanEnableAutoMerge=true` for both members. |
| Mutation | One `enablePullRequestAutoMerge` call selected #80 with `expectedHeadOid=3655a4d15df12824ea58e5b02dce361f2b73bd51`, SQUASH and the required agent-authorship commit-body trailer. |
| Response | GraphQL UNPROCESSABLE: `Auto-merge is not supported for stacked pull requests.` The mutation result was null. |
| Readback | Both `autoMergeRequest` fields stayed null; both PRs remained open/unmerged; neither was queued. All three owned branch refs were unchanged by the attempt. |
| Cleanup | No armed request required disabling. The original false repository flag was restored by PATCH and independently GET-verified. |

The effective native-specific rejection occurred despite an enabled repository
option, an expected-head guard, actual blocking checks and a positive viewer
permission boolean. The boolean therefore did not establish support for this
native member. This observation agrees with the inspected official CLI
[FAQ at the pinned revision](https://github.com/github/gh-stack/blob/bd0a32504f9ae9f795875a9e6bb90ff7408fda08/docs/src/content/docs/faq.md#can-i-enable-auto-merge-on-a-stacked-pr),
which describes native auto-merge as unavailable. It does not establish a
permanent or universal rollout rule.

## Retained state and evidence

| Ref | SHA |
| --- | --- |
| `exp/auto/trunk` | `b031070c2fd06ad94ce5b31f7f04fe5eb24c36f8` |
| `exp/auto/lower` | `3655a4d15df12824ea58e5b02dce361f2b73bd51` |
| `exp/auto/upper` | `00f7d538eccffeeec78d5ffd8ce8389c2e86796f` |

`probe.py`, `journal.jsonl` and `evidence/` retain setup and mutation intents,
GraphQL schema/introspection, exact request/response bodies, status receipts,
required-check observations, exact protection, PR/group snapshots and refs.
`flag-state.json` retains the original and verified restored option values.
`verify.py` reruns only local evidence checks; all checks pass in `RESULTS.json`.
Authored fixture commits use the required Josh Liebow-Feeser identity and trailer.
No workflow/security permission or unrelated repository option was changed.

Status release, accepted auto-merge, queue admission and native automatic prefix
landing remain untested because the operation was rejected. There was no armed
operation to observe for the proposed bounded landing interval. Ordinary manual
native merges from other lanes do not establish automatic landing behavior.

*Authored by an AI agent acting on joshlf's behalf.*
