# Hosted harness audit

The recorded basic traces support the three requested merge-method observations.
They also contain a substantive surprise: adding D to a completed squash group
returned **200** and reopened that same group. The harness's expected-failure
label is wrong for this observed outcome. Its later new-group attempt is therefore
not an independent continuation test.

This audit read `api/lab.py`, `api/run_basic.py`, `resources.json`,
`basic-results.json`, raw API evidence, and already-fetched Git objects. It issued
no API requests, fetches, pushes, or other experiment operations and changed no
source or evidence under `api/`. The final aggregate read was at
2026-11-08T23:01:43Z; additional offline tree/body comparisons used those recorded
files. The audited source hashes were:

- `lab.py`: `ecd773e3a2fd6ef46743d001669b5c6c84e12ca31b3cd559e1f2447fa9772aad`
- `run_basic.py`: `3f04401c53d79752c02e6147c17ff415d8465f3cb8d464f487fe70cc4ff4a1e0`

## Findings that affect interpretation

### Completed-group append succeeded; following controls changed meaning

[`merge-squash-complete-after.snapshot.json`](../api/evidence/merge-squash-complete-after.snapshot.json)
records group #28 with `open:false` and PRs #25/#26/#27 all merged.
[`merge-squash-complete-unstack.meta.json`](../api/evidence/merge-squash-complete-unstack.meta.json)
then records a 422 rejection: those merged PRs could not be removed.
[`complete-append-rejected.meta.json`](../api/evidence/complete-append-rejected.meta.json)
records a subsequent 200 response with the same group #28, now `open:true`, and
open PR D #29 appended after those three merged members.

This is observed completed-group reuse in this fixture. It is evidence against
the design's blanket assertion that completed groups cannot be extended. It is
not evidence that every completed group, rule configuration, or target host will
permit that operation.

The harness continues after this unexpected success. D's retarget-to-trunk request
returns 422, and creating a new D/E group returns 422 because D is already a stack
member. Those are consequences of D's actual enrollment in #28. They do not show
that a fresh, independent D/E continuation would fail. The executor should branch
on the append outcome and preserve the resulting state; a new-group experiment
needs an actually independent fixture or a separately confirmed release of D.

The filename `complete-append-rejected` and the source comment asserting that a
completed group cannot accept a follow-up should not be used as result labels.

### Unstack-before-append is a conditional oracle problem

In the audited `merge_case`, the `/unstack` call precedes the completed-group
append probe (`run_basic.py` lines 58 and 65). If unstack had removed the group,
an append rejection could have meant only that the resource was absent. In the
actual merge and squash traces, completed-group unstack returned 422; the squash
append response confirms the original group still existed. Thus this ordering
problem did **not** explain away the observed successful append.

A reusable test should either probe append before unstack or assert the precise
post-unstack group state before interpreting the next operation.

### A conflicting merge receipt needs its own method check

`poll_merge` (`lab.py` lines 122–131) follows any returned UUID, including one in
a 409 response for an existing request. It does not compare the returned
`merge_method`, `merge_action`, and `expected_head_sha` with the requested intent.
A conflicting existing request could therefore be reported under the wrong
method name. This is a harness classification risk, not an observed provider
defect in these three traces.

All six observed prefix/full requests were 202, and their receipts matched the
requested method, direct-merge action, and selected head SHA. Their terminal
polls reported `merged`. No method result here was invalidated by a mismatched
409 receipt.

### Unsigned suffixes are observed; signature stripping was not tested

The commit API's recorded B and C head verification objects say `unsigned` for
all three methods. Offline inspection also found no `gpgsig` header on the
original authored A/B/C commits in any method fixture. These traces support the
claim that the observed rewritten suffix head commits were unsigned. They do not
demonstrate that native rewriting removed an existing author signature.

The code records only each PR's head commit metadata. A broader statement about
every commit in an arbitrary multi-commit hosted layer would require enumerating
that layer's full range. The present synthetic layers each have one authored
commit, and their rewritten heads form the expected adjacent chain.

The final landing commits also differ by method: merge and squash record
`verification.reason: valid`; rebase records `verification.reason: unsigned`.
Do not generalize the first two into a claim that every native landing is signed.

## What was independently checked

The audited `basic-results.json` had `capabilities`, `merge-merge`,
`merge-squash`, and `merge-rebase`, with no recorded case exception.

| Method | Exact membership before/prefix/full | Prefix lifecycle | Full lifecycle | Final trunk verification |
| --- | --- | --- | --- | --- |
| merge | #21, #22, #23 | A merged; B/C open | A/B/C merged; group closed | valid |
| squash | #25, #26, #27 | A merged; B/C open | A/B/C merged; group closed | valid |
| rebase | #31, #32, #33 | A merged; B/C open | A/B/C merged; group closed | unsigned |

For each method, the sampled PR head SHAs matched the corresponding sampled
remote refs before landing, after the prefix, and after full landing. Offline
`rev-parse <sha>^{tree}` comparisons established:

- The prefix trunk tree equaled the original authored A tree.
- The completed trunk tree equaled the original authored C cumulative tree.
- Each observed B/C suffix head tree equaled its corresponding authored B/C tree.

The methods use distinct case-specific paths and commit identities. Compare their
within-fixture transformations and normalized content, not raw tree IDs across
different fixture directories.

Each synchronous endpoint negative control returned 403 in these fixtures. The
async receipt parser's `details.uuid` and top-level `status` interpretation matches
the recorded pending/merged response bodies. Across the 159 completed metadata
files read, every raw response had one HTTP block, its status agreed with `http`,
its decoded body agreed with `data`, and no `parse_error` was recorded.

The capability trace also supports the narrower recorded observations: singleton
registration 422, two-member registration 201 with exact order, append 200,
duplicate membership attempts 422, closed-unmerged B remaining in the group,
reopen 200, and successful open-group unstack preserving PR identities/adjacent
bases while removing stack metadata. Those observations do not imply the same
unstack outcome for merged or locked members; the completed-group trace actually
returned 422.

## Harness limitations, separate from provider behavior

The script records many states without asserting all of them before the next
effect. In particular, `merge_case` does not enforce the expected prefix lifecycle,
exact membership, head/ref agreement, and successful full landing as continuation
gates. The offline checks above validate these actual method traces. A changed or
partially failed fixture could otherwise proceed into a different experiment.

Malformed/non-JSON responses can produce `data: null`; later `.get(...)` calls in
`poll_merge` can then raise an ordinary Python exception. Such a result would be
a harness failure or an unresolved observation, not proof that a provider merge
failed. None of the audited responses had this problem.

Cached commit/push labels are returned without checking that new requested inputs
match the old ones, and a case entry in `basic-results.json` is skipped even if it
contains an error. Accordingly, editing a fixture and rerunning the same labels
does not establish a fresh comparison or a general resumable workflow. Current
method names/inputs were consistent in the inspected trace.

The intent files are useful experiment records. Their atomic-rename helper has
no file/directory `fsync`, and the hosted harness does not implement a general
overlapping-operation barrier for every uncertain response. It should not be
presented as the production durable publisher protocol. The separate local
fault-injection harness tests its own explicit prototype policy.

Finally, successful terminal polls and several agreeing samples describe a finite
observed trace. They do not establish that no delayed suffix effect can occur.
This audit neither resolves the provider handoff question nor authorizes further
mutations of protected resources.

*Authored by an AI agent acting on joshlf's behalf.*
