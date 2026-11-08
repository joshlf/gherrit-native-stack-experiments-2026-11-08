# Concurrent body and history control

The programmed separate-artifact control preserved both updates: simultaneous
client PATCHes to PR10's synthetic body and its distinct generated history
comment each returned HTTP 200, and subsequent GETs matched both sent payloads.
A stale whole-body control then overwrote a newer synthetic body sentinel.
Finally, both original texts were restored and their exact hashes matched.

All actors used the same authenticated account. All modified text was synthetic
experiment data. This is an actual REST probe, not a human editing walkthrough,
a cross-role permission test or evidence of API compare-and-swap support.

## Exact interleaving

The resources were [PR10](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/10)
and [generated comment 6728278369](https://github.com/joshlf/gherrit-native-stack-experiments-2026-11-08/pull/10#issuecomment-6728278369).
Initial GETs first confirmed that their current bodies exactly matched retained
payloads from this experiment's earlier writes. Unexpected text would have
stopped the probe before mutation.

| Phase | PR body observed afterward | Generated comment observed afterward |
| --- | --- | --- |
| Two PATCH subprocesses released through one start barrier | Programmed actor A's body update | Programmed history actor A's independent update |
| Intervening programmed body actor B writes | Newer actor B sentinel | History actor A's update |
| Stale writer sends a whole-body PATCH derived from the earlier actor A read | Actor A text plus stale-writer addition; actor B sentinel is absent | History actor A's update retained |
| Joined, quiescent actors; fresh matching reads; restoration | Exact original synthetic body | Exact original generated comment |

The two independent PATCH client intervals overlapped. Their request bodies,
raw HTTP responses, timestamps and subsequent GET receipts are retained. This
establishes overlapping client operations; server arrival order or linearization
was not observed. The history comment kept its GitHub ID throughout.

The stale writer deliberately used an unconditional whole-body replacement.
Its successful request removed the intervening text despite deriving its payload
from a previously valid read. No conditional-write mechanism was exercised, and
this does not establish that no coordinated or conditional body-update protocol
could exist. A generated body section using this same unconditional stale
read/modify/write pattern would inherit the demonstrated overwrite risk.

## Restoration and evidence

All programmed actors had finished before restoration. Fresh GETs matched this
probe's known synthetic state, after which the captured original bodies were
restored. This preflight check guarded a quiescent fixture; it is not a server
CAS guarantee or protection against an arbitrary concurrent writer.

Final body SHA-256:
`27fce1f648da8ba0268cd1760f307ce832e12d7b9dd70ba3a895a52fb5652b17`.
Final generated-comment SHA-256:
`b26fda821e30b296a4351eb1737d381a4ecccf32a79f148a6ca46005005dd9ea`.
Both equal their initial captured hashes.

`concurrent_history.py` preserves the source. `concurrent-history/evidence/`
contains exact requests, raw HTTP responses, parsed payloads and command/timing
metadata. Its journal contains six PATCH intents with six matching HTTP 200
receipts. Every expected write was confirmed by a later GET; no unknown write
was retried. All local evidence checks pass in `VERIFICATION.json`, and
`RESULTS.json` records the findings and limits. No settings changed. Earlier
CLI/history results remain unchanged as their original point-in-time record.

The remaining history questions concern human discovery and comprehension,
other actors' permissions and behavior, and recovery after genuinely unknown
API outcomes. This probe closes the bounded programmed body/history concurrency
control without establishing those broader properties.

*Authored by an AI agent acting on joshlf's behalf.*
