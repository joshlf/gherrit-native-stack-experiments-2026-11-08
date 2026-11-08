# Hosted reconciliation experiment

Use only `joshlf/gherrit-native-stack-experiments-2026-11-08` refs under
`exp/integration/repeat-01/**`. Keep this checkout and journal separate from the
other experiment lanes. No main, workflow, settings, bot, or production changes.

1. Publish synthetic A/B with exact immutable v1 archives and native membership.
   Keep unpublished A′ adding a model field and B′ accessing that field locally.
2. Squash-land old A through the async endpoint. Preserve the actual trunk and
   rewritten B. Use the tested real-Git I/L/H normalization and replay to construct
   new-ID F before canonical B, and check the executable dependency and each patch.
3. Release eligible old membership; confirm B parked at trunk; atomically push F,
   rewritten B and new exact archives; set final adjacent bases; register F/B.
   Verify B's original review/node identity, A's terminal state, and old archives.
4. Capture the successful publication checkpoint while retaining a later local B
   edit. Land F and import actual B again with and without that pending edit.
   Distinguish a hosted-equivalent no-effect continuation from pending local work.

Persist intent before every hosted write, retain raw responses, use fresh-ref
absence expectations and explicit changed-head leases, and stop on unknown or
unexpected outcomes. A finite successful trace does not prove provider settlement
or establish a production GHerrit protocol. Any failure remains evidence.

*Authored by an AI agent acting on joshlf's behalf.*
