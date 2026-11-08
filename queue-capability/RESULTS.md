# Merge-queue capability result

Merge-queue behavior could not be tested in this personal experimental repository.
A single, schema-validated queue ruleset request was rejected. No ruleset, queue
PR, native group or enqueue operation was created. Testing stopped at this
capability boundary.

Current primary documentation says public-repository merge queues are available
for organization-owned repositories. Repository metadata confirms that
`joshlf/gherrit-native-stack-experiments-2026-11-08` is public, owned by a `User`,
and accessible with admin permission. This documented eligibility restriction
fits the observed rejection; the API error itself does not identify an account
plan or ownership as its cause. See [GitHub's managing guide](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).

## Exact request and observed state

The request specified an active branch ruleset named
`queue-capability-2026-11-08`, targeting only
`refs/heads/exp/queue/trunk`, with no bypass actors and one `merge_queue` rule.
Before dispatch, its fields, enum values and numeric ranges were validated
against the current [official API schema](https://github.com/github/rest-api-description/blob/2f8f80e47ea4d3292cf4e37ba9d9b25475e06140/descriptions/api.github.com/api.github.com.json).
The seven required parameters were:

| Parameter | Value |
| --- | --- |
| `check_response_timeout_minutes` | 5 |
| `grouping_strategy` | `ALLGREEN` |
| `max_entries_to_build` | 1 |
| `max_entries_to_merge` | 2 |
| `merge_method` | `SQUASH` |
| `min_entries_to_merge` | 2 |
| `min_entries_to_merge_wait_minutes` | 1 |

POST `/repos/joshlf/gherrit-native-stack-experiments-2026-11-08/rulesets`
returned HTTP 422, `Validation Failed`, with
`errors: ["Invalid rule 'merge_queue': "]`. Both before and after ruleset
listings were empty. This was a known rejection, not an unknown response that
was retried.

The sole retained experimental ref is `refs/heads/exp/queue/trunk`, pointing at
`b031070c2fd06ad94ce5b31f7f04fe5eb24c36f8`; GitHub reported that seed commit's
signature as verified. The namespace was empty before the probe. Existing
repository merge options matched before/after, including `allow_auto_merge=false`.
No repository-wide option or workflow permission was changed, and no change to
`allow_auto_merge` was needed or requested.

## Evidence and limits

`probe.py` retains the exact request and journals intent before each of its two
writes: trunk creation and the rejected ruleset creation. `evidence/` retains
commands, timestamps, subprocess receipts, raw responses, repository metadata,
refs and ruleset listings. `CAPABILITY.json` records the conclusion, and
`verify.py` checks those retained observations without another hosted write.
All checks pass in `VERIFICATION.json`.

`sources/` retains the primary documentation and schema, their commits and
SHA-256 manifest. Documentation commit:
`8cd1075179df75319912891d6620c9cb78eefb4d`. API schema commit:
`2f8f80e47ea4d3292cf4e37ba9d9b25475e06140`.

Async queue admission versus landing, merge-group checks, ejection, queued
unstack, cancellation and queue/stack interactions remain **untested**. Ordinary
native-stack merge traces from other lanes do not establish those queue effects.
No other account, organization or repository was created to bypass the boundary.

*Authored by an AI agent acting on joshlf's behalf.*
