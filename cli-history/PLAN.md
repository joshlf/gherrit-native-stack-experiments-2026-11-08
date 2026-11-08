# CLI and history experiments

All GitHub writes target this lane's synthetic `exp/cli/**` refs and its own PRs,
comments and groups in the dedicated experiment repository. The executable is
the official `github/gh-stack` v0.3.0 darwin-arm64 release in `bin/`; it is not a
global extension. Local hooks are disabled only in this checkout.

The driver records intent before mutation and saves complete public responses,
exit status, exact refs, PR state and membership. A recorded mutation identity
cannot be rerun without reconciliation. No lost write is automatically retried.

| Case | Discriminating observation |
| --- | --- |
| Canonical PR URLs, existing adjacent bases, no `--open` | Membership changes while refs, title/body/readiness and bases remain identical. |
| Canonical PR URLs, incorrect upper base | The CLI can repair bases, so URLs alone do not imply a membership-only effect. |
| Local branch named after a PR | Numeric args push that branch into a local bare sink before PR lookup; URLs skip this push. No numeric GitHub branch is created. |
| Existing-stack reordered arguments | Record any base edits preceding the CLI's eventual additive-order refusal. This deliberately probes partial effects on disposable reviews. |
| Broader `submit` with a local archive tag | Trace the actual branch-only atomic push and check the archive remains absent remotely. |
| Owned history comment | Create, identify/list, update, preserve human-owned body edits, delete and journaled reattach. Check exact historical patch vs changed-parent tip comparison and practical comment caps. |

The history experiment proves API mechanics and exact-range meaning. Reviewer
findability in a long discussion and comprehension require a human walkthrough.
Finite traces do not establish provider completion or exclude delayed effects.

*Authored by an AI agent acting on joshlf's behalf.*
